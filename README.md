# Multi-Agent Orchestration Framework

A generic framework for orchestrating multiple AI agents to solve complex tasks. Implements multiple coordination patterns with full observability.

## Features

- **Multiple Orchestration Patterns**: Sequential, Parallel, Hierarchical, Debate, Reflexion
- **Memory System**: Working memory, episodic memory, semantic memory (vector search)
- **Tool Framework**: Registry, sandboxed execution, automatic schema generation
- **Observability**: Execution traces, cost tracking, latency metrics
- **Production Ready**: Typed interfaces, error handling, extensible architecture

## Architecture

```
orchestrator/
├── agent.py          # Base agent class, LLM agent, function agent
├── message.py        # Typed message protocol with artifacts
├── context.py        # Shared state and workflow tracking
├── runtime.py        # Workflow executor
├── tracing.py        # Observability and traces
├── patterns/         # Orchestration patterns
│   ├── sequential.py # A → B → C
│   ├── parallel.py   # A, B, C → combine
│   ├── hierarchical.py # Manager → Workers
│   ├── debate.py     # Advocate ↔ Adversary → Judge
│   └── reflexion.py  # Act → Critique → Retry
├── memory/           # Memory subsystem
│   ├── working.py    # Short-term task state
│   ├── episodic.py   # Session history
│   └── semantic.py   # Vector-based long-term memory
└── tools/            # Tool framework
    ├── registry.py   # Tool registration and execution
    └── sandbox.py    # Safe code execution
```

## Quick Start

```python
from orchestrator import (
    AgentConfig,
    LLMAgent,
    Message,
    ParallelThenSynthesizePattern,
)
from orchestrator.runtime import Runtime

# Define agents
security_agent = LLMAgent(AgentConfig(
    name="security_reviewer",
    description="Identifies security vulnerabilities",
    system_prompt="You are a security expert. Analyze code for vulnerabilities...",
))

performance_agent = LLMAgent(AgentConfig(
    name="performance_reviewer",
    description="Spots performance issues",
    system_prompt="You are a performance expert. Identify bottlenecks...",
))

synthesizer = LLMAgent(AgentConfig(
    name="synthesizer",
    description="Combines reviews",
    system_prompt="Synthesize the specialist reviews into prioritized feedback...",
))

# Run with parallel-then-synthesize pattern
async def review_code(code: str):
    runtime = Runtime()
    result = await runtime.execute(
        workflow={
            "name": "code-review",
            "pattern": "parallel_then_synthesize",
            "agents": [
                {"name": "security_reviewer", ...},
                {"name": "performance_reviewer", ...},
                {"name": "synthesizer", ...},
            ],
        },
        input_message=code,
    )
    return result.output.content
```

## Orchestration Patterns

### Sequential
Agents execute one after another. Each agent's output becomes the next agent's input.

```python
# Extract → Transform → Validate → Load
pattern = SequentialPattern()
result = await pattern.execute([extract, transform, validate, load], input_msg, context)
```

### Parallel + Synthesize
Specialists run concurrently, then a synthesizer combines their outputs.

```python
# Security, Performance, Style reviews → Synthesizer
pattern = ParallelThenSynthesizePattern()
result = await pattern.execute([security, perf, style, synth], input_msg, context)
```

### Hierarchical
A manager delegates to workers, then synthesizes results.

```python
# Manager analyzes task → delegates to specialists → combines results
pattern = HierarchicalPattern()
result = await pattern.execute([manager, worker1, worker2], input_msg, context)
```

### Debate
Two agents argue opposing positions, a judge synthesizes.

```python
# Advocate ↔ Adversary → Judge
pattern = DebatePattern(num_rounds=2)
result = await pattern.execute([advocate, adversary, judge], input_msg, context)
```

### Reflexion
Actor attempts task, critic evaluates, actor retries with feedback.

```python
# Generate → Critique → Improve (repeat)
pattern = ReflexionPattern(max_iterations=3)
result = await pattern.execute([actor, critic], input_msg, context)
```

## Memory System

### Working Memory
Short-term key-value store for current task state.

```python
context.set("extracted_entities", entities)
entities = context.get("extracted_entities")
```

### Episodic Memory
Session history with importance-based retrieval.

```python
memory = EpisodicMemory()
memory.add("User asked about X", importance=0.8)
recent = memory.get_recent(10)
important = memory.get_important(threshold=0.7)
```

### Semantic Memory
Vector-based long-term storage with similarity search.

```python
memory = SemanticMemory()
await memory.add("Important fact about X", source="document.pdf")
results = await memory.search("query about X", top_k=5)
```

## Tool Framework

Register tools that agents can use:

```python
from orchestrator.tools import tool, ToolRegistry

@tool(description="Search the web for information")
def web_search(query: str) -> str:
    # Implementation
    return results

# Or register manually
registry = ToolRegistry()
registry.register_function(my_function, name="my_tool")

# Get OpenAI function calling schema
schemas = registry.get_openai_schemas()
```

## Observability

Full execution traces with cost tracking:

```python
result = await runtime.execute(workflow, input_msg)

# Access trace
trace = result.trace
trace.print_summary()

# Metrics
print(f"Tokens: {result.total_tokens}")
print(f"Latency: {result.total_latency_ms}ms")
print(f"Cost: ${result.total_cost_usd:.4f}")
```

## Examples

### PR Review
Multi-agent code review with security, performance, and style specialists.

```bash
cd examples/pr_review
python workflow.py
```

### Research Assistant
Iterative research with fact-checking using Reflexion pattern.

```bash
cd examples/research
python workflow.py
```

## Installation

```bash
pip install -r requirements.txt
```

Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-key"
```

## Development

```bash
# Run tests
pytest

# Format code
black orchestrator/

# Type check
mypy orchestrator/
```

## Design Principles

1. **Separation of Concerns**: Agents have single responsibilities
2. **Typed Interfaces**: Messages, contexts, and results are typed
3. **Pattern Agnostic**: Core primitives work with any pattern
4. **Observable**: Full traces for debugging and optimization
5. **Extensible**: Add new patterns, agents, or tools easily

## License

MIT
