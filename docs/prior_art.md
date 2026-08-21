# Prior Art & Competitive Differentiation

This document analyzes the landscape of automated research agents and highlights the concrete architectural and operational differentiations of ResearchSwarm.

---

## 1. Competitive Landscape Overview

We examine ResearchSwarm against three prominent existing research and multi-agent frameworks:

1. **Stanford STORM / Co-STORM (Synthesis of Topic Outlines through Repeated Multi-perspective Exploration)**
   - *Approach:* Generates Wikipedia-style articles by simulating multi-perspective conversations (e.g. interviewer vs. expert) using retrieval-augmented generation.
   - *Strengths:* Thorough outline generation and comprehensive long-form writing.
   - *Limitations:* High token overhead, slow multi-turn conversational loops, lack of adversarial fact-checking/critique, and no token budget governance or real-time cost bounding.

2. **Perplexity AI / Deep Research (Proprietary Search-Grounded LLMs)**
   - *Approach:* Black-box, proprietary iterative search and answer generation engine.
   - *Strengths:* Clean UI, rapid retrieval, and polished inline citations.
   - *Limitations:* Proprietary closed-source architecture; no visible claim-level trust ledger or confidence scoring; opaque execution DAG; cannot inspect agent reasoning, disagreement, or retry traces.

3. **AutoGen / CrewAI (General-Purpose Multi-Agent Frameworks)**
   - *Approach:* Conversational multi-agent systems where agents chat with each other to complete goals.
   - *Strengths:* Flexible setup, broad ecosystem, easy prompt-based role definition.
   - *Limitations:* Prone to infinite conversational loops, hallucinations compounded across turns, heavy token burn without hard limits, lack of deterministic DAG state transitions, and fragile parallel worker aggregation.

---

## 2. Feature & Architectural Comparison Matrix

| Capability / Dimension | Stanford STORM | Perplexity Deep Research | AutoGen / CrewAI | **ResearchSwarm (Ours)** |
| :--- | :--- | :--- | :--- | :--- |
| **Orchestration Architecture** | Multi-turn conversational interview | Proprietary black-box pipeline | Open-ended agent conversation loop | **Deterministic LangGraph StateGraph with `Send` fan-out & `operator.add` reducers** |
| **Evidence Grounding** | Web snippets in conversation | Live web search index | Tool-use search calls | **Dual-provider resilient search (Tavily + DuckDuckGo fallback) with eTLD+1 domain dedup** |
| **Adversarial Fact-Checking** | ❌ None (Perspective only) | ❌ Internal self-consistency | ❌ Optional chat critic | **Dedicated Critic Agent with confidence scoring & conditional retry loops** |
| **Token Budget Governance** | ❌ Unbounded token usage | ❌ Fixed black-box subscription | ❌ Prone to runaway chat loops | **Per-session TokenBudgetTracker with 9k soft / 13k hard enforcement limits** |
| **Multimodal Inputs** | ❌ Text only | Text + Image (basic) | Basic file tool use | **Dual input: Groq Whisper voice + Client canvas compressed Gemini 2.0 Flash vision** |
| **Content Caching** | ❌ No cross-session cache | Proprietary index cache | ❌ Ephemeral memory | **Content-addressed Redis Cache (SHA-256) for research queries & image embeddings** |
| **Model Right-Sizing** | Single model (e.g. GPT-4) | Proprietary mixture | Static assignment | **Dynamic tiering: Fast 8B for Planner/Worker/Critic, 70B/Gemini Flash for Analyst/Writer** |
| **Trust Ledger & Auditability** | End citations only | Footnote links | Chat history transcript | **Structured claim ledger with per-fact confidence scores, URLs, and critic notes** |
| **Export Formats** | Markdown | Web UI / Markdown | Console / Markdown | **Multi-format export: Verified PDF, DOCX, Markdown, and JSON** |

---

## 3. Core Differentiators of ResearchSwarm

### 1. Deterministic DAG vs. Conversational Loops
General-purpose frameworks like AutoGen and CrewAI rely on natural language conversational turn-taking. This often results in wandering threads, repetitive back-and-forth chatter, and non-deterministic execution times. ResearchSwarm employs a strict **LangGraph StateGraph** where transitions are governed by typed data schemas and conditional routing edges. Every agent has an exact role with typed inputs and outputs.

### 2. Multi-Tier Token Governance
In commercial environments, multi-agent systems often fail due to runaway token costs. ResearchSwarm treats tokens as a first-class constrained resource:
- Prompt JSON schemas are baked into `SYSTEM_PROMPT` once rather than repeated on every call.
- Fast tasks (planning, keyword search filtering, fact-checking) route to **Llama 3.1 8B**, reserving **Llama 3.3 70B** and **Gemini 2.0 Flash** for synthesis and report generation.
- Atomic Redis counters enforce a **9,000 token soft limit** (curtailing retries) and a **13,000 token hard limit** (halting exploration and forcing immediate synthesis).

### 3. Adversarial Fact-Checking & Claim Ledger
Rather than assuming synthesized text is correct, ResearchSwarm introduces an explicit **Critic Agent** that stress-tests the Analyst's output. Any claim with confidence $<0.60$ is flagged, and syntheses with overall confidence $<0.50$ trigger targeted gap re-queries. The final report is delivered alongside a verifiable **Claim Ledger** listing every individual fact, source URL, and assigned confidence score.

### 4. Zero Single-Point-of-Failure Resilience
ResearchSwarm is engineered for production reliability:
- **Search Resiliency:** If Tavily experiences an outage or rate-limit, the system seamlessly transitions to DuckDuckGo. If both fail, it operates in graceful degraded mode without crashing.
- **Session Survival:** Redis-backed checkpointing and metadata persistence ensure that in-flight workflows resume immediately upon backend restarts without loss of state.
