"""LangGraph state schema for ResearchSwarm orchestration.

Uses Annotated[List[dict], operator.add] reducers for research_findings
and image_findings to support concurrent fan-in writes from parallel
worker branches created via the LangGraph Send API.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict


class ResearchState(TypedDict, total=False):
    """Complete state container for the ResearchSwarm workflow."""

    session_id: str
    user_query: str
    sub_questions: List[Dict[str, Any]]
    current_sub_question: Optional[Dict[str, Any]]
    research_findings: Annotated[List[Dict[str, Any]], operator.add]
    image_findings: Annotated[List[Dict[str, Any]], operator.add]
    analyst_result: Optional[Dict[str, Any]]
    critic_result: Optional[Dict[str, Any]]
    report: Optional[str]
    sources: List[str]
    confidence: float
    retry_rounds: int
    retry_questions: List[str]
    over_budget: bool
    budget_exhausted: bool
    budget_note: Optional[str]
    error: Optional[str]
