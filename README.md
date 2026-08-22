# ResearchSwarm — System Blueprint & Complete Developer/Agent Guide

> **ResearchSwarm** is a trust-first multi-agent research copilot for decision briefs. It transforms broad research queries into source-backed, audited decision briefs by orchestrating five specialist AI agents: **Planner**, **Researcher**, **Analyst**, **Critic**, and **Writer**.

This document serves as the **definitive blueprint** for any developer or AI agent working on, extending, or inspecting the ResearchSwarm codebase.

---

## Hackathon Submission Details

**Track**: Multimodal — voice (Groq Whisper) and image (Gemini 2.0 Flash vision) inputs are ingested through independent single-call pipelines, compressed/normalized to structured findings, and merged into the same evidence pool that web-search findings flow through. The Critic agent evaluates image- and voice-derived facts identically to web-derived facts — removing either modality collapses the pipeline's ability to ground a report in non-text evidence.

**Constraints satisfied** (2+ required, we satisfy 3):
1. **Two models/modalities genuinely cooperating**: Voice transcription (Groq Whisper) and image vision extraction (Gemini 2.0 Flash) both feed the same unified `ResearchState.research_findings` list that web-search-derived findings populate — not called redundantly, each modality contributes findings no other modality could.
2. **Degrade gracefully**: Search provider failure (Tavily down/unconfigured) falls back to DuckDuckGo (`AsyncDDGS`); if both fail, the pipeline proceeds on LLM general knowledge with `degraded_mode: true` flagged and confidence capped at 0.40, rather than crashing the session.
3. **Cost ceiling**: `TokenBudgetTracker` enforces a 9,000-token soft limit (skips Critic retry, shortens Writer output) and 13,000-token hard limit (stops research, synthesizes from existing findings) per session, visible live in the dashboard token counter.

---

## Live URL Links
->Frontend Web App: http://3.111.34.142:3000
->Backend API & Swagger Docs: http://3.111.34.142:8000/docs
->Backend Health Check: http://3.111.34.142:8000/health

##Login Credentials
->Email: aditya@gmail.com
->Password: Aditya510

## For Local Host
->Email: demo@example.com
->Password: password123

---

## 1. Executive Overview & Purpose

### The Problem
Traditional single-prompt LLM tools generate flat, opaque research reports that mask gaps in evidence, lack adversarial scrutiny, and hide hallucinated claims. In high-stakes environments (market entry, technical due diligence, strategic planning), decision-makers need **verifiable provenance**, **adversarial critique**, and **transparent confidence bounds**.

### The ResearchSwarm Solution
ResearchSwarm models the research process as a **coordinated multi-agent pipeline**:
1. **Planner**: Deconstructs user queries into target sub-questions.
2. **Researcher**: Executes live web searches (via Tavily) to harvest real evidence with source URLs.
3. **Analyst**: Synthesizes multi-source evidence into key themes, emerging trends, and risk vectors.
4. **Critic**: Performs adversarial evaluation against claim-level evidence, flagging unbacked assertions and requesting research retries if confidence is below 50%.
5. **Writer**: Streams a structured, professional Markdown decision brief to the user in real time.

All system activity is exposed in a real-time **Trust Ledger UI** that details agent states, individual claims, source URLs, confidence scores, critic notes, and execution DAG node statuses.

---

## 2. High-Level Architecture & Data Flow

```text
                                       ┌─────────────────────────┐
                                       │    User Input Query     │
                                       └────────────┬────────────┘
                                                    │ POST /api/sessions
                                                    v
                                       ┌─────────────────────────┐
                                       │   FastAPI Web Server    │
                                       │    (backend/main.py)    │
                                       └────────────┬────────────┘
                                                    │
                                                    v
                                       ┌─────────────────────────┐
                                       │   Session Orchestrator  │
                                       │(core/orchestrator.py)   │
                                       └───────┬─────────┬───────┘
                                               │         │
                   Publishes Task Messages     │         │ Spawns & Tracks
                   to Redis Channels           v         v
┌────────────────────────────────────────────────────────┐  ┌─────────────────────────────────┐
│                      Redis Pub/Sub                     │  │        Task DAG Graph           │
│                   (core/message_bus.py)                │  │       (core/task_dag.py)        │
└─────────┬──────────────┬──────────────┬──────────────┬─┘  └─────────────────────────────────┘
          │              │              │              │
          v              v              v              v
    ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
    │  Planner  │  │Researcher │  │  Analyst  │  │  Critic   │
    │  Agent    │  │  Agents   │  │   Agent   │  │   Agent   │
    └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
          │              │              │              │
          └──────────────┴──────┬───────┴──────────────┘
                                │
                                v
                       ┌─────────────────┐
                       │  Writer Agent   │
                       └────────┬────────┘
                                │ Live Stream via Redis
                                v
                       ┌─────────────────┐
                       │  WebSocket API  │
                       │(api/websocket)  │
                       └────────┬────────┘
                                │ WS Broadcast: ws:broadcast:{session_id}
                                v
                       ┌─────────────────┐
                       │  React / Vite   │
                       │  Frontend UI    │
                       └─────────────────┘
```

---

## 3. Full Project File Structure

```text
researchswarm/
├── docker-compose.yml           # Multi-container setup (Backend, Frontend, Redis)
├── deploy.sh                    # Helper script for container cleanup & demo deployment
├── .env.example                 # Environment configuration template
├── README.md                    # System architecture & developer blueprint (this file)
│
├── backend/                     # FastAPI Python Backend Service
│   ├── main.py                  # App entry point, lifespan, CORS, and top-level error handlers
│   ├── config.py                # BaseSettings configuration schema with Pydantic validation
│   ├── requirements.txt         # Python package dependencies
│   ├── Dockerfile               # Production container image manifest for backend
│   │
│   ├── api/                     # REST & WebSocket API Routers
│   │   ├── routes.py            # Session management, status queries, report generation & exports (PDF/DOCX/MD/JSON)
│   │   ├── websocket.py         # Socket streaming manager for live agent progress
│   │   └── demo.py              # Session recording, offline replay, and seed endpoint
│   │
│   ├── core/                    # Core Infrastructure & Engine Components
│   │   ├── orchestrator.py      # Session lifecycle, task scheduling, DAG progress, timeout & retry loops
│   │   ├── message_bus.py       # Redis pub/sub wrapper, task claim locking, channel naming
│   │   ├── task_dag.py          # Directed Acyclic Graph state management & serialization
│   │   ├── llm_router.py        # Multi-provider LLM router (Groq Llama-3.3 & Gemini 2.0 Flash) with load balancing
│   │   ├── search_client.py     # Live web search interface wrapping Tavily API
│   │   ├── security.py          # API key validation, WebSocket auth, and rate-limiting
│   │   ├── schemas.py           # Pydantic schemas (AgentMessage, TaskMessage, AgentResult, ResearchQuery)
│   │   ├── types.py             # Enums for AgentType, TaskStatus, and MessageType
│   │   └── retry.py             # Exponential backoff utility for LLM and Redis calls
│   │
│   └── agents/                  # Autonomous Swarm Agents
│       ├── base_agent.py        # Abstract base class with claim locks, error safety, and heartbeats
│       ├── planner.py           # Decomposes queries into targeted sub-questions
│       ├── researcher.py        # Fetches live web evidence & extracts claims/sources
│       ├── analyst.py           # Synthesizes research findings into thematic insights
│       ├── critic.py            # Adversarial evidence auditor & confidence scorer
│       └── writer.py            # Streams structured Markdown decision briefs
│
└── frontend/                    # React + Vite + TypeScript Frontend Application
    ├── package.json             # Frontend NPM package manifest
    ├── vite.config.ts           # Vite build & dev server config
    ├── tailwind.config.ts       # Tailwind CSS styling configuration
    ├── tsconfig.json            # TypeScript compiler configuration
    ├── Dockerfile               # Nginx / static frontend container manifest
    │
    └── src/                     # React Source Code
        ├── main.tsx             # DOM root renderer
        ├── App.tsx              # Application layout, prompt form, mode toggle
        ├── config.ts            # Environment variables helper (API base URL, Demo mode flag)
        ├── index.css            # Tailwind directive imports & custom styles
        │
        ├── hooks/
        │   └── useSwarm.ts      # Custom Hook for session lifecycle, WebSocket events, export & replay
        │
        ├── components/
        │   ├── Dashboard.tsx    # Live pipeline visualization, visual trust ledger, critic notes, report viewer
        │   └── ReplayMode.tsx   # Recording selector, speed controller, and playback runner
        │
        └── types/
            └── messages.ts      # TypeScript definitions matching backend API payloads & WebSocket events
```

---

## 4. Backend Core Engine Blueprint

### Entry Point & Middleware (`backend/main.py`)
- **Role**: Initializes the FastAPI application, wires application lifespan state (`app.state`), applies CORS rules, logs HTTP requests, and sets up global exception handling.
- **Key Objects**:
  - `lifespan(app: FastAPI)`: Asynchronous context manager that initializes shared singletons (`Redis`, `MessageBus`, `LLMRouter`, `TavilySearchClient`, `Orchestrator`) on startup and cleans them up on shutdown.
  - `app.state`: Holds shared instances accessible inside API endpoints (`request.app.state.orchestrator`, etc.).
  - `log_requests(request, call_next)`: Measures request execution time in milliseconds and logs inbound calls.

### Configuration System (`backend/config.py`)
- **Role**: Reads configuration from `.env` using Pydantic's `BaseSettings`. Validates CORS origin patterns (rejects wildcard `*` or missing schemes).
- **Key Variables**:
  - `groq_api_key`, `gemini_api_key`, `tavily_api_key`: Provider credentials.
  - `groq_model` (`llama-3.3-70b-versatile`), `gemini_model` (`gemini-2.0-flash`).
  - `groq_rpm_budget` (28), `gemini_rpm_budget` (14): Sliding-window rate limit budgets used by `LLMRouter`.
  - `max_researchers` (3): Controls how many parallel researcher worker tasks run.
  - `task_claim_retry_buffer_seconds` (300): TTL buffer for task claim locks.

### Orchestrator (`backend/core/orchestrator.py`)
- **Role**: The central coordinator for ResearchSwarm. Schedules and advances the execution graph through agent task channels.
- **Workflow & Execution Logic**:
  1. `start_session(query)`: Instantiates a `TaskDAG`, creates a `Planner` task node, persists DAG to Redis, and publishes task to `agent:planner:{session_id}`.
  2. `_handle_planner_result()`: Receives planner output containing sub-questions, creates `Researcher` task nodes, and enqueues them.
  3. `_handle_researcher_result()`: Waits for all researcher nodes in the current phase to complete, then triggers the `Analyst` node (`_trigger_analyst()`).
  4. `_handle_analyst_result()`: Takes analyst insights and triggers the `Critic` node (`_trigger_critic()`).
  5. `_handle_critic_result()`: Evaluates critic output. If `approved == False` or `final_confidence < 0.5`, it calls `_requeue_research()` to launch targeted retry researcher tasks (up to `MAX_RETRIES = 2`). If approved, it triggers `Writer` (`_trigger_writer()`).
  6. `_handle_writer_result()`: Receives final markdown report, updates DAG status to complete, and broadcasts final state.
  7. `_schedule_timeout(session_id, task_id)`: Enforces `TASK_TIMEOUT_SECONDS = 45` per task; triggers `_mark_failed()` upon expiration.

### Task DAG Execution Graph (`backend/core/task_dag.py`)
- **Role**: Data structure representing tasks, execution status (`PENDING`, `RUNNING`, `DONE`, `FAILED`, `RETRY`, `CANCELLED`), task dependencies, retries, and results.
- **Key Methods**:
  - `add_task(task, depends_on)`: Adds a node with prerequisite task IDs.
  - `get_ready_tasks()`: Returns pending nodes whose dependent tasks are all `DONE`.
  - `mark_done(task_id, result)`: Stores result payload and unlocks downstream nodes.
  - `to_json()` / `from_json()`: Serializes and rehydrates DAG state for Redis persistence (`session:{session_id}:dag`).

### Redis Message Bus (`backend/core/message_bus.py`)
- **Role**: Asynchronous pub/sub interface using `redis.asyncio`.
- **Key Methods**:
  - `publish(channel, message)`: Serializes `AgentMessage` to JSON and publishes to Redis. Automatically appends events to `session:{session_id}:events` list for recording.
  - `subscribe(channel)` / `subscribe_pattern(pattern)`: Async generator yielding deserialized `AgentMessage` objects.
  - `try_claim_task(task_id, owner, ttl_seconds)`: Uses `SET key owner EX ttl NX` to prevent multiple agent instances from processing the same task.
  - `release_task_claim(task_id, owner)`: Deletes the claim key if owned by the caller.

### LLM Router & Multi-Provider Engine (`backend/core/llm_router.py`)
- **Role**: Intelligent load balancer and fallback router across Groq (`AsyncGroq`) and Gemini (`google.genai`).
- **Load Balancing Logic**:
  - Maintains sliding-window call history (`_calls`) over 60 seconds per provider.
  - Computes provider load (`get_load(provider)`).
  - Routes agent calls according to preferred provider order:
    - **Planner & Critic**: Prefers Groq Llama-3.3, falls back to Gemini.
    - **Analyst & Writer**: Prefers Gemini 2.0 Flash, falls back to Groq.
    - **Researcher**: Alternates preference per request across workers to balance rate limits.
  - `complete(...)`: Tries preferred provider; if an exception occurs, automatically attempts fallback provider.
  - `stream(...)`: Streams response chunks; if initial call fails before yielding, attempts fallback provider.

### Search Client Integration (`backend/core/search_client.py`)
- **Role**: Interacts with the Tavily Search API (`https://api.tavily.com/search`).
- **Methods**:
  - `search(query, max_results=5)`: Returns web snippets with `title`, `url`, `content`, and `score`. Includes fallback error handling if Tavily API key is unconfigured or rate-limited.

### Security, Rate Limiting & Auth (`backend/core/security.py`)
- **Role**: Enforces API security and session isolation.
- **Capabilities**:
  - `require_auth`: Validates optional Bearer API keys configured in `RESEARCHSWARM_API_KEYS`.
  - `enforce_session_rate_limit`: Implements IP/User sliding window rate limits in Redis (`rate_limit:{user_id}`).
  - `ensure_session_access`: Prevents session hijacking by matching request owner against stored `owner_id` in `session:{session_id}:meta`.

### Data Models & Types (`backend/core/schemas.py`, `types.py`, `retry.py`)
- **`types.py`**: Enums for `AgentType` (`PLANNER`, `RESEARCHER`, `ANALYST`, `CRITIC`, `WRITER`), `TaskStatus`, and `MessageType`.
- **`schemas.py`**:
  - `AgentMessage`: Base envelope (`type`, `from_agent`, `to_agent`, `payload`, `status`, `confidence`).
  - `TaskMessage`: Extends `AgentMessage` with `task_id`, `parent_task_id`, `depth`.
  - `AgentResult`: Standardized task output payload (`task_id`, `content`, `confidence`, `sources`).
- **`retry.py`**: Decorator and helper `retry_with_backoff()` featuring exponential jitter backoff for network/LLM resilience.

---

## 5. Specialist Agent Swarm Blueprint

All agents inherit from `BaseAgent` (`backend/agents/base_agent.py`) which manages claim locks, logging, message listening loops, and error reporting.

```
                         ┌─────────────────────────┐
                         │   BaseAgent (Abstract)  │
                         └────────────┬────────────┘
                                      │
       ┌──────────────────┬───────────┼───────────┬──────────────────┐
       │                  │           │           │                  │
       v                  v           v           v                  v
┌──────────────┐   ┌──────────────┐┌──────┐   ┌──────────────┐   ┌──────────────┐
│ PlannerAgent │   │ResearcherAgnt││Analyst│   │ CriticAgent  │   │ WriterAgent  │
└──────────────┘   └──────────────┘└──────┘   └──────────────┘   └──────────────┘
```

### Planner Agent (`backend/agents/planner.py`)
- **Task**: Receives overall user query and outputs 3–4 focused research sub-questions.
- **Output Schema**: JSON object containing list of tasks with `sub_question`, `search_keywords`, and `priority`.
- **Demo Fallback**: Returns structured solar/renewable energy sub-questions if running in demo mode.

### Researcher Agent (`backend/agents/researcher.py`)
- **Task**: Executes Tavily web searches for assigned sub-question keywords, parses returned web pages, and extracts claim-level facts with individual confidence scores and source URLs.
- **Output Schema**: JSON finding list containing `fact`, `source`, `confidence`.

### Analyst Agent (`backend/agents/analyst.py`)
- **Task**: Consolidates all collected researcher finding facts into high-level thematic synthesis, emerging trends, and risk factors.
- **Output Schema**: Structured JSON document containing `synthesis`, `key_trends`, `risks`, and `gaps`.

### Critic Agent (`backend/agents/critic.py`)
- **Task**: Acts as an adversarial evidence auditor. Evaluates analyst synthesis against raw researcher claims. Checks if statements are grounded in real sources.
- **Output Schema**: JSON containing `approved` (boolean), `final_confidence` (float 0.0–1.0), `critique_notes` (array of strings), and `retry_questions` (array of strings if gaps are present).

### Writer Agent (`backend/agents/writer.py`)
- **Task**: Generates the final executive decision brief formatted in Markdown.
- **Streaming Logic**: Uses `llm_router.stream()` to generate markdown tokens, emitting chunks via Redis to `ws:broadcast:{session_id}` so users watch the final report stream line by line.

---

## 6. API & WebSocket Specifications

### REST Routes (`backend/api/routes.py`)

| Endpoint | Method | Description | Request Payload / Params | Response Payload |
|---|---|---|---|---|
| `/api/sessions` | `POST` | Create & launch research run | `{"query": "string"}` | `{"session_id": "uuid", "status": "started", "estimated_time_seconds": 90}` |
| `/api/sessions/{session_id}` | `GET` | Get session DAG status & agent states | URL param `session_id` | `SessionStatusResponse` (DAG nodes, task status counts, elapsed seconds) |
| `/api/sessions/{session_id}/report` | `GET` | Retrieve complete final report & ledger | URL param `session_id` | `ReportResponse` (`report`, `sources`, `confidence`, `critic_notes`, `claim_ledger`) |
| `/api/sessions/{session_id}/export` | `GET` | Export report in standard file formats | `format=markdown\|json\|pdf\|docx` | File download attachment with appropriate MIME type |
| `/api/sessions/{session_id}` | `DELETE` | Cancel running session | URL param `session_id` | `{"cancelled": true}` |
| `/api/health` | `GET` | Detailed service health check | None | `{"status": "ok", "redis": "connected", "agents": "running"}` |
| `/health` | `GET` | Container readiness ping | None | `{"status": "ok"}` |

### WebSocket Streaming (`backend/api/websocket.py`)
- **URL**: `WS /ws/{session_id}`
- **Connection Lifecycle**:
  1. Client connects and authenticates token/session ownership.
  2. Server accepts connection, sends initial session state event (`session_state`).
  3. Connection manager (`ConnectionManager`) subscribes to Redis channel `ws:broadcast:{session_id}`.
  4. Server sends heartbeat `{"event": "ping"}` every 15 seconds.
  5. Incoming Redis agent updates are normalized and sent to WebSocket client as `agent_update` events containing `agent_type`, `task_id`, `status`, `content`, `confidence`, and `timestamp`.

### Demo & Replay Engine (`backend/api/demo.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/api/demo/seed` | `GET` | Runs a demo research session, records all WebSocket events, and saves as default recording `solar_energy_demo`. |
| `/api/demo/recordings` | `GET` | Lists all saved session recording keys in Redis (`demo:recording:*`). |
| `/api/demo/record/{session_id}` | `POST` | Saves recorded WebSocket event timeline of a completed session under a given name. |
| `/api/demo/replay/{name}` | `POST` | Spawns a background replay task streaming stored events to a new session ID at requested speed multiplier (`speed=0.25` to `4.0`). |

---

## 7. Frontend Application Blueprint

Built with **React**, **TypeScript**, **Vite**, and **Tailwind CSS**.

```text
App.tsx (Main Shell & Input Form)
├── Mode Toggle (Live Session vs. Replay Browser)
├── Live Mode: Dashboard.tsx
│   ├── PipelineVisualizer (Planner -> Researcher -> Analyst -> Critic -> Writer)
│   ├── Visual Trust Ledger (Claim evidence, source badges, confidence metrics)
│   ├── Critic Audit Panel (Critic notes & identified retry questions)
│   └── Live Writer Markdown Viewer (Real-time streamed report & export buttons)
└── Replay Mode: ReplayMode.tsx
    ├── Recording Selector & Speed Multiplier (0.5x, 1x, 2x, 4x)
    └── Simulated Live Run Stream
```

### Main Application Shell (`frontend/src/App.tsx`)
- Maintains high-level mode state (`activeTab`: `"live"` vs `"replay"`).
- Renders header, query submission form, sample prompt chips, status banners, and delegates view rendering to `Dashboard` or `ReplayMode`.

### State & Communication Hook (`frontend/src/hooks/useSwarm.ts`)
- **Central State Manager**: Manages session creation, active WebSocket connection lifecycle, automatic reconnects, streamed text accumulation, and export file triggers.
- **Export Action**: `exportReport(format)` sends HTTP request to `/api/sessions/{session_id}/export?format={format}` and triggers browser file download.

### Live Dashboard UI (`frontend/src/components/Dashboard.tsx`)
- **Agent Pipeline Grid**: Displays 5 agent cards with status indicators (`pending`, `running`, `done`, `failed`, `retry`).
- **Trust Ledger Table**: Displays tabular claim-level evidence harvested by researchers, showing claim text, source URL link, task ID, and individual confidence pill badge.
- **Critic Audit Box**: Visualizes adversary findings, critic approval status, confidence score bar, and critic notes.
- **Report Previewer**: Renders streamed Markdown report with copy-to-clipboard and export buttons (Markdown, JSON, PDF, DOCX).

### Replay & Recording Viewer (`frontend/src/components/ReplayMode.tsx`)
- Queries available recordings via `GET /api/demo/recordings`.
- Starts replay playback via `POST /api/demo/replay/{name}?speed={speed}`.
- Connects to replay WebSocket stream to demonstrate system capabilities offline.

### Frontend Types & Config (`frontend/src/types/messages.ts`, `config.ts`)
- **`config.ts`**: Resolves `API_BASE_URL` (default `http://localhost:8000`) and `IS_DEMO_MODE` flag.
- **`messages.ts`**: Defines TypeScript interfaces for `AgentUpdateEvent`, `SessionStateEvent`, `ClaimItem`, `ReportData`, and `RecordingInfo`.

---

## 8. Inter-Module API & Service Connection Map

The table below details how data flows across files during a research run:

```
User Click "Start Research" -> App.tsx
  └── Calls startSession() in useSwarm.ts
        └── HTTP POST /api/sessions -> backend/api/routes.py
              └── Calls orchestrator.start_session() -> backend/core/orchestrator.py
                    ├── Instantiates TaskDAG -> backend/core/task_dag.py
                    ├── Creates Planner TaskMessage -> backend/core/schemas.py
                    ├── Saves DAG to Redis -> backend/core/message_bus.py
                    └── Publishes to agent:planner:{id} -> Redis Channel

Redis Pub/Sub -> Agent Swarm Listening Loops -> backend/agents/base_agent.py
  ├── PlannerAgent receives task -> backend/agents/planner.py
  │     └── Calls llm_router.complete() -> backend/core/llm_router.py (Groq / Gemini)
  │     └── Emits task result -> backend/core/orchestrator.py
  │
  ├── Orchestrator parses sub-questions -> Spawns Researcher Tasks
  │     ├── ResearcherAgent receives task -> backend/agents/researcher.py
  │     │     └── Calls search_client.search() -> backend/core/search_client.py (Tavily)
  │     │     └── Parses web content & extracts claims -> Emits result
  │
  ├── Orchestrator collects all Researcher results -> Spawns Analyst Task
  │     ├── AnalystAgent receives task -> backend/agents/analyst.py
  │     │     └── Calls llm_router.complete() -> Synthesizes key themes & risks
  │
  ├── Orchestrator receives Analyst result -> Spawns Critic Task
  │     ├── CriticAgent receives task -> backend/agents/critic.py
  │     │     └── Audits analyst claims against evidence -> Emits verdict & confidence
  │     │
  │     └── [If Unapproved & Retries < 2] -> Orchestrator requeues Researcher tasks
  │
  └── Orchestrator triggers Writer Task -> backend/agents/writer.py
        └── Calls llm_router.stream() -> Streams markdown chunks
              └── Published to ws:broadcast:{session_id} -> Redis Channel
                    └── WebSocket Router forwards event -> backend/api/websocket.py
                          └── WebSocket Client in useSwarm.ts receives event
                                └── Renders in Dashboard.tsx UI
```

---

## 9. Execution Modes: Live LLM vs. Deterministic Demo

ResearchSwarm supports two distinct execution modes:

### 1. Live LLM Mode (Default Production)
- **Requirements**: Valid API keys in `.env`: `GROQ_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`.
- **Behavior**:
  - `LLMRouter` dispatches real inference requests to Groq (Llama-3.3-70B) and Gemini (2.0 Flash).
  - `TavilySearchClient` performs live web searches for real-time sources.

### 2. Deterministic Demo Mode (Offline / Hackathon Judging)
- **Activation**: Set `RESEARCHSWARM_DEMO_MODE=true` in `.env` (or leave API keys blank).
- **Behavior**:
  - Agents automatically detect demo mode (`_demo_mode_enabled() == True`).
  - `PlannerAgent`, `ResearcherAgent`, `AnalystAgent`, `CriticAgent`, and `WriterAgent` return instant, high-quality pre-baked research outputs for solar energy and tech topics.
  - Guarantees 100% reliable local demonstrations without requiring external API keys or incurring costs.

---

## 10. Setup, Installation & Deployment

### Quick Start with Docker Compose (Recommended)

1. Clone the repository and navigate to root:
   ```bash
   cd researchswarm
   ```
2. Create your `.env` file:
   ```bash
   cp .env.example .env
   ```
3. Launch all services (Redis, Backend, Frontend):
   ```bash
   docker compose up --build
   ```
4. Access the web dashboard:
   ```text
   http://localhost:3000
   ```

### Manual Local Development Setup

#### 1. Redis Server
Ensure Redis is running locally on port 6379:
```bash
redis-server
```

#### 2. Backend Service Setup
```bash
cd backend
python -m venv .venv

# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

#### 4. Running Backend Unit Tests
```bash
cd backend
pytest
```

---

*This blueprint reflects the exact architecture, file layout, and logic implementation of ResearchSwarm.*
