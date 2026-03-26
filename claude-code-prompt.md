# Claude Code Prompt: Upgrade ai-chat-agent

## Context
This is an existing AI chat agent project at `./ai-chat-agent/` — a GPT-4 powered conversational agent with MCP tool integration (Calculator, Wikipedia), SQLite storage, and Flask web UI. The codebase is functional but tutorial-level. I want to upgrade it into a portfolio-quality project that demonstrates production engineering thinking.

There is also a sibling project at `./agent-memory-system/` (ASMR) — a multi-agent retrieval pipeline with Relevance, Recency, Conflict, and Synthesis agents. We will integrate it as the memory/retrieval backend.

## Goals
Transform this from a tutorial demo into a production-grade agent system that showcases:
- Real-world tool integration (not just calculator/wikipedia)
- Intelligent memory via ASMR integration
- Error handling and resilience
- Observability and debugging
- Clean project structure

---

## Phase 1: Project Restructure

Reorganize the flat file layout into a proper package structure:

```
ai-chat-agent/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py            # Main agent orchestration
│   │   ├── router.py           # Tool routing logic (extract from agent.py)
│   │   └── config.py           # Configuration management
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract tool interface
│   │   ├── calculator.py       # Calculator tool
│   │   ├── wikipedia.py        # Wikipedia tool
│   │   ├── web_search.py       # NEW: Web search tool
│   │   └── sql_query.py        # NEW: SQL query tool over sample dataset
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py           # MCP server
│   │   ├── client.py           # MCP client
│   │   └── integration.py      # MCP integration layer
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── storage.py          # SQLite conversation storage
│   │   └── retriever.py        # NEW: ASMR integration bridge
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py           # Flask routes (extract from interface.py)
│   └── observability/
│       ├── __init__.py
│       └── logger.py           # Structured logging, metrics
├── static/                     # Flask static assets
├── templates/                  # Flask templates
├── tests/
│   ├── test_agent.py
│   ├── test_tools.py
│   └── test_memory.py
├── data/
│   └── sample.db               # Sample SQLite DB for sql_query tool
├── main.py                     # Entry point
├── pyproject.toml              # Replace requirements.txt
├── README.md
├── architecture.svg
└── .env.example
```

- Move all source files into `src/` with proper `__init__.py` files
- Update all imports accordingly
- Make sure `main.py` still works as the single entry point for both console and web modes
- Replace `requirements.txt` with `pyproject.toml` using modern Python packaging

---

## Phase 2: Add Real-World Tools

### 2a: Web Search Tool
Add a web search tool using DuckDuckGo (no API key required):
- `pip install duckduckgo-search`
- Implement in `src/tools/web_search.py`
- Takes a search query, returns top 3-5 results with title, snippet, URL
- Register as an MCP tool

### 2b: SQL Query Tool
Add a SQL query tool that queries a sample SQLite database:
- Create `data/sample.db` with a realistic sample dataset (e.g., a small e-commerce schema: products, orders, customers — ~50 rows each)
- Tool takes a natural language question, the agent generates SQL, executes it safely (read-only), returns results
- Add SQL injection protection (read-only connection, query validation)
- Register as an MCP tool

### 2c: Tool Base Class
Create an abstract base class in `src/tools/base.py`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolResult:
    success: bool
    data: Any
    error: str | None = None
    latency_ms: float = 0.0
    tool_name: str = ""

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult: ...
```

Refactor Calculator and Wikipedia tools to extend this base class.

---

## Phase 3: Error Handling & Resilience

Add robust error handling throughout:

1. **Tool execution**: Wrap every tool call in try/except. Return structured `ToolResult` with success/failure. Never let a tool crash the agent loop.

2. **LLM fallbacks**: If GPT-4 returns an invalid tool name or malformed arguments:
   - Log the error with full context
   - Retry once with a clarifying prompt
   - If retry fails, respond to the user gracefully: "I tried to use [tool] but encountered an issue. Here's what I can tell you without it..."

3. **Timeout handling**: Add configurable timeouts for tool calls (default 10s) and LLM calls (default 30s). Use `asyncio.wait_for` or equivalent.

4. **Rate limiting**: Add a simple token bucket rate limiter for the OpenAI API calls to prevent runaway costs.

---

## Phase 4: ASMR Memory Integration

Create `src/memory/retriever.py` that bridges agent-memory-system into the chat agent:

```python
# This module should:
# 1. Import from agent-memory-system (add as a dependency or local path)
# 2. On each user query, run ASMR retrieval pipeline to get relevant past context
# 3. Inject curated context into the system prompt before sending to GPT-4
# 4. After each conversation turn, store the exchange as a new memory in ASMR
# 5. Fall back gracefully to raw SQLite history if ASMR is unavailable
```

Key integration points:
- When building the GPT-4 prompt, prepend relevant memories from ASMR as system context
- Store new conversation turns as memories with proper metadata (timestamp, topic, entities)
- Make ASMR optional — if not installed/configured, fall back to the existing SQLite-only approach
- Add a config flag: `MEMORY_BACKEND=asmr|sqlite` in `.env`

---

## Phase 5: Streaming & Web UI

Upgrade the Flask web interface:

1. **Server-Sent Events (SSE)** for streaming responses:
   - Add a `/api/stream` endpoint that streams tokens as they arrive from GPT-4
   - Use OpenAI's `stream=True` parameter
   - Frontend: use `EventSource` to consume the stream and render tokens incrementally

2. **Show tool usage in the UI**:
   - When the agent routes to a tool, show a small status indicator: "🔧 Using calculator..."
   - After tool execution, show the tool result in a collapsible panel
   - Show which memories were retrieved (if ASMR is active)

3. **Conversation management**:
   - Add ability to start a new conversation
   - Show conversation history in a sidebar
   - Basic dark/light theme toggle

---

## Phase 6: Observability

Create `src/observability/logger.py` with structured logging:

1. **Per-request logging** (JSON format):
   ```json
   {
     "timestamp": "...",
     "query": "user input",
     "route_decision": "calculator+wikipedia",
     "tools_called": [
       {"name": "wikipedia", "latency_ms": 450, "success": true},
       {"name": "calculator", "latency_ms": 12, "success": true}
     ],
     "memories_retrieved": 3,
     "llm_tokens": {"prompt": 850, "completion": 120},
     "total_latency_ms": 2100
   }
   ```

2. **Add a `/api/metrics` endpoint** that returns:
   - Total requests served
   - Average latency by tool
   - Tool success/failure rates
   - Token usage totals

3. Use Python's `structlog` or just `logging` with JSON formatter — keep dependencies minimal.

---

## Phase 7: Tests

Add tests in `tests/`:

1. **test_tools.py**: Test each tool independently — valid inputs, edge cases, error cases
2. **test_agent.py**: Test routing logic — given a query, does it pick the right tool(s)?
3. **test_memory.py**: Test ASMR integration — store and retrieve memories, fallback behavior

Use `pytest`. Mock the OpenAI API calls. Focus on routing logic and error handling — these are the most interesting parts to test and the most likely to be asked about in interviews.

---

## Phase 8: README & Documentation

Rewrite `README.md` to reflect the upgraded project:

- Lead with the **problem statement**: "Most AI chat agents are demos. This one is built like a production system."
- Architecture diagram (update `architecture.svg`) showing: User → Flask API → Agent Router → [Tools | ASMR Memory | GPT-4] → Response
- Highlight the interesting engineering decisions:
  - Why ASMR over naive RAG for conversation memory
  - How tool routing works (decision tree, not just prompt stuffing)
  - Error handling and fallback strategies
  - Observability approach
- Quick start that actually works in <2 minutes
- Example conversations showing multi-tool routing and memory recall

---

## Constraints
- Keep Python 3.10+ compatibility
- Minimize dependencies — don't add LangChain or heavy frameworks
- Every new feature should have at least one test
- Don't break the existing console mode — it should still work
- Use async where it makes sense (tool calls, LLM calls) but don't over-engineer
- All config via environment variables with sensible defaults
- Add type hints everywhere

## Order of Operations
Execute phases 1 through 8 in order. After each phase, make sure the app still runs (`python main.py` for console, `python main.py web` for Flask). Commit after each phase with a descriptive message.
