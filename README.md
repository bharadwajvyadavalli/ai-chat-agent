# Multi-Agent Orchestration Framework

**Most AI chat agents are demos. This one is built like a production system.**

A production-grade framework for orchestrating multiple AI agents with intelligent memory, real-world tool integration, and comprehensive observability.

## Why This Project?

This framework demonstrates production engineering thinking:

- **Real-World Tools**: Web search and SQL query tools, not just calculators
- **Intelligent Memory**: ASMR integration for multi-agent retrieval (Relevance, Recency, Conflict, Synthesis)
- **Error Handling**: Retries, timeouts, rate limiting, circuit breakers
- **Observability**: Structured JSON logging, metrics endpoint, execution traces
- **Clean Architecture**: Typed interfaces, separation of concerns, extensible patterns

## Features

### Core Orchestration
- **Multiple Patterns**: Sequential, Parallel, Hierarchical, Debate, Reflexion
- **Agent Types**: LLM-powered agents, function agents, custom agents
- **Context Management**: Shared state, working memory, conversation history

### Production Tools
- **Web Search**: DuckDuckGo integration (no API key required)
- **SQL Query**: Safe read-only queries with injection protection
- **Extensible**: Abstract BaseTool class for custom tools

### Intelligent Memory
- **Working Memory**: Short-term key-value store
- **Episodic Memory**: Session history with importance scoring
- **Semantic Memory**: Vector-based similarity search
- **ASMR Integration**: Multi-agent retrieval with reasoning

### Web Interface
- **Flask Chat UI**: Modern, responsive design
- **SSE Streaming**: Real-time token display
- **Tool Visualization**: See tool usage and results
- **Memory Display**: Show retrieved context

### Observability
- **Structured Logging**: JSON format for machine parsing
- **Metrics Endpoint**: Request counts, latencies, error rates
- **Execution Traces**: Full visibility into agent decisions

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
```

Or with pip:
```bash
pip install -r requirements.txt
pip install flask duckduckgo-search structlog
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 3. Initialize Sample Database

```bash
python data/setup_sample_db.py
```

### 4. Run the Web Interface

```bash
python main.py web
```

Open http://localhost:5000 in your browser.

### 5. Or Run Demos

```bash
# PR Review (multi-agent code review)
python main.py pr-review

# Research Assistant (iterative with reflexion)
python main.py research

# Pattern Demo
python main.py patterns
```

## Architecture

```
ai-chat-agent/
├── orchestrator/           # Core framework
│   ├── agent.py           # Agent base class, LLMAgent, FunctionAgent
│   ├── message.py         # Typed message protocol
│   ├── context.py         # Shared state management
│   ├── runtime.py         # Workflow executor
│   ├── tracing.py         # Execution traces
│   ├── resilience.py      # Rate limiting, retries, circuit breakers
│   ├── patterns/          # Orchestration patterns
│   │   ├── sequential.py  # A → B → C
│   │   ├── parallel.py    # A, B, C → combine
│   │   ├── hierarchical.py# Manager → Workers
│   │   ├── debate.py      # Advocate ↔ Adversary → Judge
│   │   └── reflexion.py   # Act → Critique → Retry
│   ├── memory/            # Memory subsystem
│   │   ├── working.py     # Key-value task state
│   │   ├── episodic.py    # Session history
│   │   ├── semantic.py    # Vector search
│   │   └── retriever.py   # ASMR integration bridge
│   ├── tools/             # Tool framework
│   │   ├── base.py        # BaseTool abstract class
│   │   ├── registry.py    # Tool registration
│   │   ├── web_search.py  # DuckDuckGo search
│   │   └── sql_query.py   # SQL query tool
│   └── observability/     # Monitoring
│       ├── logger.py      # Structured logging
│       └── metrics.py     # Metrics collection
├── web/                   # Flask application
│   ├── app.py            # Routes and SSE streaming
│   └── chat_service.py   # Chat logic with tools
├── templates/            # HTML templates
├── static/               # CSS/JS assets
├── tests/                # pytest tests
├── examples/             # Demo workflows
│   ├── pr_review/        # Multi-agent code review
│   └── research/         # Research with reflexion
└── data/                 # Sample database
```

## Orchestration Patterns

### Sequential
Agents execute one after another. Each output becomes the next input.

```python
pattern = SequentialPattern()
result = await pattern.execute([extract, transform, load], input_msg, context)
```

### Parallel + Synthesize
Specialists run concurrently, then a synthesizer combines outputs.

```python
pattern = ParallelThenSynthesizePattern()
result = await pattern.execute([security, perf, style, synth], input_msg, context)
```

### Debate
Two agents argue, a judge synthesizes a balanced conclusion.

```python
pattern = DebatePattern(num_rounds=2)
result = await pattern.execute([advocate, adversary, judge], input_msg, context)
```

### Reflexion
Actor attempts, critic evaluates, loop until quality threshold.

```python
pattern = ReflexionPattern(max_iterations=3, success_threshold=0.8)
result = await pattern.execute([actor, critic], input_msg, context)
```

## Tool System

### Using Built-in Tools

```python
from orchestrator.tools import WebSearchTool, SQLQueryTool

# Web search
search = WebSearchTool(max_results=5)
result = await search.run(query="Python best practices")

# SQL query
sql = SQLQueryTool(db_path="data/sample.db")
result = await sql.run(query="SELECT * FROM products WHERE price < 50")
```

### Creating Custom Tools

```python
from orchestrator.tools import BaseTool, ToolResult

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Does something useful"

    async def execute(self, **kwargs) -> ToolResult:
        # Your implementation
        return ToolResult.ok(data=result)
```

## Memory System

### Working Memory
```python
context.set("current_topic", "AI safety")
topic = context.get("current_topic")
```

### Episodic Memory
```python
memory = EpisodicMemory()
memory.add("User asked about X", importance=0.8)
important = memory.get_important(threshold=0.7)
```

### Semantic Memory with ASMR
```python
from orchestrator.memory import MemoryRetriever

retriever = MemoryRetriever()
await retriever.store("Important fact about AI")
response = await retriever.retrieve("Tell me about AI")
print(response.context)  # Formatted context for LLM
```

## Resilience Features

### Rate Limiting
```python
from orchestrator import get_rate_limiter, RateLimitConfig

limiter = get_rate_limiter(RateLimitConfig(
    requests_per_minute=60,
    tokens_per_minute=100000
))
await limiter.wait_and_acquire(estimated_tokens=1000)
```

### Retries with Backoff
```python
from orchestrator import retry_with_backoff, RetryConfig

result = await retry_with_backoff(
    my_function,
    RetryConfig(max_retries=3, initial_delay=1.0)
)
```

### Circuit Breaker
```python
from orchestrator import CircuitBreaker

breaker = CircuitBreaker(failure_threshold=5)
result = await breaker.call(unreliable_function)
```

## Observability

### Structured Logging
```python
from orchestrator.observability import get_logger, RequestLogger

logger = get_logger("my_module")
logger.info("Processing request", user_id="123", action="search")

# Per-request logging
with RequestLogger(query="user question") as log:
    log.record_tool("web_search", latency_ms=450, success=True)
    log.record_llm_usage(prompt_tokens=100, completion_tokens=50)
```

### Metrics Endpoint
```bash
curl http://localhost:5000/api/metrics
```

Returns:
```json
{
  "requests": {"total": 100, "success_rate": 0.98},
  "tokens": {"prompt": 50000, "completion": 15000},
  "tools": {
    "web_search": {"call_count": 25, "avg_latency_ms": 450}
  }
}
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=orchestrator

# Run specific test file
pytest tests/test_tools.py -v
```

## Configuration

All configuration via environment variables:

```bash
# Required
OPENAI_API_KEY=your-key

# Optional
OPENAI_MODEL=gpt-4           # Default model
MEMORY_BACKEND=semantic      # asmr, semantic, or sqlite
FLASK_HOST=127.0.0.1        # Web server host
FLASK_PORT=5000             # Web server port
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json             # json or text
RATE_LIMIT_REQUESTS_PER_MINUTE=60
TOOL_TIMEOUT=10             # Tool execution timeout (seconds)
LLM_TIMEOUT=30              # LLM call timeout (seconds)
```

## Engineering Decisions

### Why ASMR over Naive RAG?
Standard RAG just retrieves similar documents. ASMR uses multiple agents:
- **Relevance**: Filters superficially similar but irrelevant content
- **Recency**: Applies temporal reasoning, detects stale information
- **Conflict**: Resolves contradictions between memories
- **Synthesis**: Produces coherent, sourced context

### Why Not LangChain?
This framework is intentionally minimal:
- ~5000 lines vs 100k+ in LangChain
- Full visibility into every component
- Easy to understand, debug, and extend
- No hidden abstractions or magic

### Error Handling Strategy
1. **Tool level**: Each tool returns structured ToolResult (never throws)
2. **Agent level**: Retry with clarifying prompt on LLM errors
3. **System level**: Graceful degradation with fallback responses

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Submit a pull request
