"""REST API routes for ResearchSwarm."""

from __future__ import annotations

import json
import textwrap
import zipfile
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.orchestrator import Orchestrator
from core.security import (
    AuthContext,
    enforce_session_rate_limit,
    ensure_session_access,
    normalize_session_id,
    require_auth,
)
from core.task_dag import TaskDAG
from core.types import AgentType, TaskStatus
from core.schemas import ResearchQuery

router = APIRouter(dependencies=[Depends(require_auth)])


class CreateSessionRequest(BaseModel):
    """Request body for creating a new research session."""

    query: str = Field(..., min_length=10, max_length=500, description="User query")


class SessionCreateResponse(BaseModel):
    """Response body for session creation."""

    session_id: str
    status: str
    estimated_time_seconds: int


class SessionStatusResponse(BaseModel):
    """Response body for session status queries."""

    session_id: str
    status: str
    dag_summary: Dict[str, Any]
    agent_states: Dict[str, Dict[str, int]]
    created_at: Optional[str]
    elapsed_seconds: Optional[float]


class ReportResponse(BaseModel):
    """Response body for session reports."""

    session_id: str
    report: str
    sources: List[str]
    confidence: float
    critic_notes: List[str]
    retry_questions: List[str]
    claim_ledger: List[Dict[str, Any]]


class CancelResponse(BaseModel):
    """Response body for session cancellation."""

    cancelled: bool


class HealthResponse(BaseModel):
    """Response body for health checks."""

    status: str
    redis: str
    agents: str


def _get_orchestrator(request: Request) -> Orchestrator:
    """Fetch orchestrator instance from app state."""

    return request.app.state.orchestrator


@router.post("/api/sessions", response_model=SessionCreateResponse)
async def create_session(
    request: Request,
    body: CreateSessionRequest,
    auth: AuthContext = Depends(require_auth),
) -> SessionCreateResponse:
    """Create a new research session."""

    await enforce_session_rate_limit(request, auth)
    orchestrator = _get_orchestrator(request)
    session_id = str(uuid4())
    query = ResearchQuery(
        user_query=body.query,
        session_id=session_id,
    )

    session_id = await orchestrator.start_session(query)

    created_at = datetime.now(timezone.utc).isoformat()
    await request.app.state.redis.hset(
        f"session:{session_id}:meta",
        mapping={"created_at": created_at, "query": body.query, "owner_id": auth.user_id},
    )

    return SessionCreateResponse(
        session_id=session_id,
        status="started",
        estimated_time_seconds=90,
    )


@router.get("/api/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(
    request: Request,
    session_id: UUID,
    auth: AuthContext = Depends(require_auth),
) -> SessionStatusResponse:
    """Fetch current session status and DAG summary."""

    session_id = normalize_session_id(session_id)
    await ensure_session_access(request, session_id, auth)
    orchestrator = _get_orchestrator(request)
    summary = await orchestrator.get_session_status(session_id)
    if summary.get("status") == "unknown":
        raise HTTPException(status_code=404, detail="Session not found")

    created_at = await request.app.state.redis.hget(
        f"session:{session_id}:meta", "created_at"
    )
    elapsed = None
    if created_at:
        try:
            created_dt = datetime.fromisoformat(created_at)
            elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds()
        except ValueError:
            elapsed = None

    agent_states: Dict[str, Dict[str, int]] = {}
    for task in summary.get("tasks", []):
        agent = task.get("agent_type")
        status_value = task.get("status")
        if not agent or not status_value:
            continue
        agent_states.setdefault(agent, {})
        agent_states[agent][status_value] = agent_states[agent].get(status_value, 0) + 1

    status_value = "done" if summary.get("complete") else "running"

    return SessionStatusResponse(
        session_id=session_id,
        status=status_value,
        dag_summary=summary,
        agent_states=agent_states,
        created_at=created_at,
        elapsed_seconds=elapsed,
    )


@router.get("/api/sessions/{session_id}/report", response_model=ReportResponse)
async def get_session_report(
    request: Request,
    session_id: UUID,
    auth: AuthContext = Depends(require_auth),
) -> ReportResponse:
    """Return the final report for a session if available."""

    session_id = normalize_session_id(session_id)
    await ensure_session_access(request, session_id, auth)
    return await _build_report_response(request, session_id)


@router.get("/api/sessions/{session_id}/export")
async def export_session_report(
    request: Request,
    session_id: UUID,
    format: str = Query(default="markdown", pattern="^(markdown|json|pdf|docx)$"),
    auth: AuthContext = Depends(require_auth),
) -> Response:
    """Export the final report as Markdown, JSON, PDF, or DOCX."""

    session_id = normalize_session_id(session_id)
    await ensure_session_access(request, session_id, auth)
    report = await _build_report_response(request, session_id)
    filename = f"researchswarm-{session_id}.{_export_extension(format)}"

    if format == "json":
        payload = json.dumps(report.model_dump(mode="json"), indent=2)
        media_type = "application/json"
        body = payload.encode("utf-8")
    elif format == "pdf":
        media_type = "application/pdf"
        body = _build_pdf(report.report)
    elif format == "docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        body = _build_docx(report.report)
    else:
        media_type = "text/markdown; charset=utf-8"
        body = report.report.encode("utf-8")

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _build_report_response(request: Request, session_id: str) -> ReportResponse:
    """Build the report response from the persisted session DAG."""

    raw_dag = await request.app.state.redis.get(f"session:{session_id}:dag")
    if not raw_dag:
        raise HTTPException(status_code=404, detail="Session not found")

    dag = TaskDAG.from_json(raw_dag)
    report_text = None
    sources: List[str] = []
    confidence = 0.0
    critic_notes: List[str] = []
    retry_questions: List[str] = []
    claim_ledger: List[Dict[str, Any]] = []

    for node in dag._nodes.values():
        if node.task.to_agent == AgentType.RESEARCHER and node.result:
            claim_ledger.extend(_extract_claims(node.result))

        if node.task.to_agent == AgentType.CRITIC and node.result:
            critique = _parse_result_content(node.result)
            critic_notes = [
                item for item in critique.get("critique_notes", []) if isinstance(item, str)
            ]
            retry_questions = [
                item for item in critique.get("retry_questions", []) if isinstance(item, str)
            ]
            raw_confidence = critique.get("final_confidence", node.result.get("confidence", 0.0))
            if isinstance(raw_confidence, (int, float)):
                confidence = float(raw_confidence)

        if node.task.to_agent != AgentType.WRITER:
            continue
        if node.status != TaskStatus.DONE:
            continue
        if not node.result:
            continue
        content = node.result.get("content")
        sources = node.result.get("sources", []) or []
        try:
            parsed = json.loads(content) if isinstance(content, str) else {}
            report_text = parsed.get("report")
        except json.JSONDecodeError:
            report_text = None
        if isinstance(node.result.get("confidence"), (int, float)):
            confidence = float(node.result.get("confidence"))

    if not report_text:
        raise HTTPException(status_code=404, detail="Report not ready")

    return ReportResponse(
        session_id=session_id,
        report=report_text,
        sources=sources,
        confidence=confidence,
        critic_notes=critic_notes,
        retry_questions=retry_questions,
        claim_ledger=claim_ledger,
    )


@router.delete("/api/sessions/{session_id}", response_model=CancelResponse)
async def cancel_session(
    request: Request,
    session_id: UUID,
    auth: AuthContext = Depends(require_auth),
) -> CancelResponse:
    """Cancel a running session."""

    session_id = normalize_session_id(session_id)
    await ensure_session_access(request, session_id, auth)
    orchestrator = _get_orchestrator(request)
    await orchestrator.cancel_session(session_id)
    return CancelResponse(cancelled=True)



def _parse_result_content(result: Dict[str, Any]) -> Dict[str, Any]:
    """Parse an AgentResult content payload into a dictionary."""

    content = result.get("content")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_claims(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract source-backed claims from a researcher result."""

    parsed = _parse_result_content(result)
    findings = parsed.get("findings", [])
    if not isinstance(findings, list):
        return []

    claims: List[Dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fact = finding.get("fact")
        if not isinstance(fact, str) or not fact.strip():
            continue
        confidence = finding.get("confidence", result.get("confidence", 0.0))
        claims.append(
            {
                "claim": fact.strip(),
                "source": finding.get("source") or "",
                "confidence": float(confidence)
                if isinstance(confidence, (int, float))
                else 0.0,
                "task_id": result.get("task_id"),
            }
        )
    return claims


def _export_extension(format_name: str) -> str:
    return "md" if format_name == "markdown" else format_name


def _build_pdf(markdown_text: str) -> bytes:
    """Generate a compact text-only PDF without external dependencies."""

    lines: List[str] = []
    for raw_line in _sanitize_export_text(markdown_text).splitlines() or ["ResearchSwarm report"]:
        stripped = raw_line.replace("\t", "    ")
        lines.extend(textwrap.wrap(stripped, width=88) or [""])

    pages = [lines[index : index + 46] for index in range(0, len(lines), 46)] or [[]]
    objects: List[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{3 + page_index * 2} 0 R".encode("ascii") for page_index in range(len(pages)))
        + f"] /Count {len(pages)} >>".encode("ascii"),
    ]

    for page_index, page_lines in enumerate(pages):
        page_obj = 3 + page_index * 2
        content_obj = page_obj + 1
        stream = _pdf_text_stream(page_lines)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_obj} 0 R >>".encode(
                "ascii"
            )
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref_offset = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return buffer.getvalue()


def _pdf_text_stream(lines: List[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "50 745 Td", "14 TL"]
    for line in lines:
        safe = _escape_pdf_text(line)
        commands.append(f"({safe}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _build_docx(markdown_text: str) -> bytes:
    """Generate a simple DOCX document using the standard OOXML package layout."""

    paragraphs = _sanitize_export_text(markdown_text).splitlines() or ["ResearchSwarm report"]
    document_body = "".join(
        f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>" for line in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{document_body}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _sanitize_export_text(text: str) -> str:
    """Remove control characters that are unsafe in PDF streams or OOXML."""

    safe_chars = []
    for char in text:
        codepoint = ord(char)
        if char in {"\n", "\r", "\t"}:
            safe_chars.append(char)
        elif (
            codepoint >= 0x20
            and codepoint not in {0x7F, 0xFFFE, 0xFFFF}
            and not 0xD800 <= codepoint <= 0xDFFF
        ):
            safe_chars.append(char)
        else:
            safe_chars.append(" ")
    return "".join(safe_chars)


def _escape_pdf_text(text: str) -> str:
    """Escape text for a PDF literal string."""

    return (
        _sanitize_export_text(text)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("%", "\\045")
    )
