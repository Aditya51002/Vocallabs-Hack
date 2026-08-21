# ResearchSwarm Failure Log & Post-Mortem Analysis

This document provides a transparent, engineering-grade record of real runtime failures, architectural vulnerabilities, edge-case bottlenecks encountered during development, and the concrete mitigations implemented.

---

## 1. In-Memory Session State Loss on Backend Restart

### Problem & Symptoms
The orchestrator originally maintained an in-memory dictionary `_sessions: Dict[str, SessionState]`. While DAG structure was persisted to Redis, session metadata (e.g. `planner_task_id`, `retry_rounds`, `analyst_result`, `critic_result`, in-flight task listeners) only resided in process memory. Whenever the backend process restarted or crashed, all in-flight research sessions were orphaned. Clients reconnecting via WebSocket or polling GET `/api/sessions/{id}` received 404 or stalled indefinitely.

### Root Cause
Session lifecycle and message-dispatch state were decoupled: DAG execution was tracked in Redis, but task routing state was ephemeral.

### Solution & Fix
1. Implemented `_persist_session_meta()` in `orchestrator.py` storing a structured metadata dictionary to `session:{id}:meta_v2` in Redis after every agent phase transition.
2. Added `restore_sessions()` called during FastAPI `lifespan` startup. On startup, the backend scans `session:*:dag` keys in Redis, reconstructs `SessionState` for incomplete sessions, and re-attaches Pub/Sub task listeners.

---

## 2. Search Provider Outages Causing Catastrophic Session Abort

### Problem & Symptoms
`TavilySearchClient` called the Tavily API with zero fallback. If Tavily threw a 429 Rate Limit, 503 Server Error, or if `TAVILY_API_KEY` was missing/invalid, a `RuntimeError` crashed the worker task, halting the entire 5-agent pipeline.

### Root Cause
Single point of failure on an external API without degradation or fallback strategy.

### Solution & Fix
1. Added asynchronous DuckDuckGo search fallback (`AsyncDDGS().atext()`) that executes automatically whenever Tavily fails or is unconfigured.
2. If both Tavily and DuckDuckGo fail, the search client returns an empty result set with a `degraded: True` sentinel rather than raising an unhandled exception.
3. Updated `ResearcherAgent` to recognize degraded mode: it proceeds using LLM parametric knowledge, caps confidence score at $\le 0.40$, and flags `"degraded_mode": true` in structured findings so downstream agents (Analyst, Critic, Writer) clearly highlight data source constraints.

---

## 3. Silent Token Leakage and Runaway API Quota Burn

### Problem & Symptoms
Neither Groq nor Gemini LLM calls tracked token consumption in real time. Sessions often re-sent full JSON schemas (over 120 tokens per prompt) on every sub-question call, and research queries were unbounded, leading to rapid 429 quota exhaustion.

### Root Cause
Lack of per-session budget enforcement and redundant token overhead in prompt formatting.

### Solution & Fix
1. Created `TokenUsage` and `LLMResult` dataclasses in `llm_router.py`. All LLM completions and streaming routines capture `prompt_tokens` and `completion_tokens` returned in API response metadata.
2. Implemented `TokenBudgetTracker` backed by atomic Redis `INCRBY` counters:
   - **Soft limit (9,000 tokens):** Skips adversarial Critic retry round and caps Writer generation to 800 tokens with budget notice.
   - **Hard limit (13,000 tokens):** Immediately halts research fan-out and synthesizes a final brief from existing findings.
3. Moved JSON schemas into agent `SYSTEM_PROMPT` definitions, stripping ~120 tokens from every user message.
4. Added content-addressed `ResearchCache` (sha256 of normalized question + sorted keywords) with 1-hour TTL to eliminate redundant LLM calls on repeated or re-queried sub-questions.

---

## 4. LangGraph Fan-In Reducer Missing (Issue 17)

### Problem & Symptoms
When migrating to LangGraph `StateGraph`, parallel researchers were dispatched via `Send("researcher_worker_node", ...)`. Each worker returned a dictionary update `{"research_findings": [result]}` to the same state key. Without a reducer annotation, LangGraph either raised `InvalidUpdateError` on concurrent writes or silently overwrote previous worker outputs, retaining only the last researcher's findings.

### Root Cause
LangGraph TypedDict channels require explicit reducer annotations for keys that receive concurrent updates from fan-out branches.

### Solution & Fix
Updated `ResearchState` TypedDict in `graph_state.py` with:
```python
research_findings: Annotated[List[Dict[str, Any]], operator.add]
image_findings: Annotated[List[Dict[str, Any]], operator.add]
```
Added a unit test in `test_graph.py` asserting that 3+ parallel researcher worker branches correctly accumulate into the final list.

---

## 5. LangGraph Critic Retry Loop Re-Entry (Issue 18)

### Problem & Symptoms
When the Critic rejected an analysis and produced `retry_questions`, routing back to `researcher_worker_node` via a standard conditional edge passed the entire `ResearchState` rather than individualized worker payloads. This caused the researcher node to fail because it expected a single `current_sub_question`.

### Root Cause
LangGraph worker nodes designed for individual items cannot be invoked with full graph state via simple edges without item dispatching.

### Solution & Fix
Updated `route_after_critic()` in `graph.py` to dynamically return a list of `Send("researcher_worker_node", {"session_id": ..., "current_sub_question": ...})` items for each retry question.

---

## 6. Empty Planner Sub-Questions Deadlock (Issue 19)

### Problem & Symptoms
If the Planner LLM returned an empty task list (`{"tasks": []}`), `dispatch_researchers()` returned an empty list `[]`. In LangGraph, returning an empty list from a conditional edge with no fallback edge leads to state deadlock.

### Root Cause
Conditional fan-out edge did not handle the zero-item edge case.

### Solution & Fix
Added explicit guard in `dispatch_researchers()`: if `len(sub_questions) == 0`, the router returns `"analyst_node"` directly, allowing the workflow to gracefully synthesize an empty/fallback brief without deadlocking.

---

## 7. Thundering Herd on Redis Retry

### Problem & Symptoms
When multiple agent tasks experienced transient connection drops or timeouts simultaneously, their retry mechanisms retried at fixed exponential intervals, causing sudden bursts of simultaneous reconnects.

### Root Cause
Deterministic exponential backoff without randomized jitter.

### Solution & Fix
Introduced uniform random jitter in `orchestrator.py`:
```python
delay = (2 ** retries) + random.uniform(0.0, 0.5)
```
and wrapped task execution in non-blocking `asyncio.create_task()` to prevent blocking the event loop.
