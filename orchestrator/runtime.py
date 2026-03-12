"""
Runtime executor for multi-agent workflows.

The runtime is responsible for:
- Loading workflow configurations
- Creating agent and pattern instances
- Executing workflows with proper state management
- Tracking costs and emitting traces
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import yaml

from .agent import Agent, AgentConfig, AgentRegistry, LLMAgent
from .context import Context, WorkflowState
from .message import Message, MessageRole
from .patterns import Pattern, PatternConfig, PatternResult, pattern_registry
from .tracing import Trace, TraceEvent, Tracer


@dataclass
class WorkflowConfig:
    """
    Configuration for a workflow.

    Can be loaded from YAML or constructed programmatically.
    """
    name: str
    description: str = ""
    pattern: str = "sequential"
    pattern_config: dict = field(default_factory=dict)
    agents: list[dict] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "WorkflowConfig":
        """Load workflow configuration from a YAML file."""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            pattern=data.get("pattern", "sequential"),
            pattern_config=data.get("pattern_config", {}),
            agents=data.get("agents", []),
            tools=data.get("tools", []),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowConfig":
        """Load workflow configuration from a dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            pattern=data.get("pattern", "sequential"),
            pattern_config=data.get("pattern_config", {}),
            agents=data.get("agents", []),
            tools=data.get("tools", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowResult:
    """Result of executing a workflow."""
    output: Message
    pattern_result: PatternResult
    execution_id: str
    workflow_name: str
    total_tokens: int
    total_latency_ms: int
    total_cost_usd: float
    trace: Trace | None = None
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "workflow_name": self.workflow_name,
            "success": self.success,
            "error": self.error,
            "output": self.output.to_dict(),
            "pattern_result": self.pattern_result.to_dict(),
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "total_cost_usd": self.total_cost_usd,
            "trace": self.trace.to_dict() if self.trace else None,
        }


class Runtime:
    """
    Runtime executor for multi-agent workflows.

    The runtime:
    1. Loads workflow configurations
    2. Creates agent and pattern instances
    3. Manages execution context
    4. Tracks costs and emits traces

    Example:
        runtime = Runtime()

        # Load a workflow
        workflow = runtime.load_workflow("examples/pr_review/workflow.yaml")

        # Execute it
        result = await runtime.execute(
            workflow,
            input_message=Message(content="Review this PR: ..."),
        )

        print(result.output.content)
        print(f"Cost: ${result.total_cost_usd:.4f}")
    """

    def __init__(
        self,
        agent_registry: AgentRegistry | None = None,
        tracer: Tracer | None = None,
        llm_client: Any = None,
    ):
        self.agent_registry = agent_registry or AgentRegistry()
        self.tracer = tracer or Tracer()
        self.llm_client = llm_client

        # Cost tracking (approximate, per 1K tokens)
        self.model_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        }

    def load_workflow(self, config: WorkflowConfig | str | dict) -> WorkflowConfig:
        """
        Load a workflow configuration.

        Accepts:
        - WorkflowConfig instance
        - Path to YAML file
        - Dictionary
        """
        if isinstance(config, WorkflowConfig):
            return config
        elif isinstance(config, str):
            return WorkflowConfig.from_yaml(config)
        elif isinstance(config, dict):
            return WorkflowConfig.from_dict(config)
        else:
            raise TypeError(f"Invalid config type: {type(config)}")

    def create_agents(self, agent_configs: list[dict]) -> list[Agent]:
        """Create agent instances from configuration."""
        agents = []
        for config in agent_configs:
            agent_config = AgentConfig(
                name=config["name"],
                description=config.get("description", ""),
                system_prompt=config.get("system_prompt", config.get("prompt", "")),
                model=config.get("model", "gpt-4"),
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 2000),
                tools=config.get("tools", []),
            )
            agent = LLMAgent(agent_config, llm_client=self.llm_client)
            agents.append(agent)
        return agents

    def create_pattern(self, pattern_name: str, config: dict | None = None) -> Pattern:
        """Create a pattern instance."""
        pattern_class = pattern_registry.get(pattern_name)
        pattern_config = PatternConfig(
            name=pattern_name,
            **config if config else {},
        )
        return pattern_class(pattern_config)

    async def execute(
        self,
        workflow: WorkflowConfig | str | dict,
        input_message: Message | str,
        context: Context | None = None,
    ) -> WorkflowResult:
        """
        Execute a workflow.

        Args:
            workflow: Workflow configuration (or path/dict)
            input_message: The input to process
            context: Optional pre-existing context

        Returns:
            WorkflowResult with output and execution metadata
        """
        # Load workflow config
        config = self.load_workflow(workflow)

        # Create execution context
        execution_id = str(uuid4())
        if context is None:
            context = Context(execution_id=execution_id)
        else:
            context.execution_id = execution_id

        # Set up workflow state
        context.workflow_state = WorkflowState(
            workflow_id=execution_id,
            workflow_name=config.name,
        )

        # Start trace
        trace = self.tracer.start_trace(execution_id, config.name)

        # Normalize input
        if isinstance(input_message, str):
            input_message = Message(content=input_message, role=MessageRole.USER)

        # Add input to context
        context.add_message(input_message)

        # Create agents
        agents = self.create_agents(config.agents)
        trace.add_event(TraceEvent(
            name="agents_created",
            data={"agents": [a.name for a in agents]},
        ))

        # Create pattern
        pattern = self.create_pattern(config.pattern, config.pattern_config)
        trace.add_event(TraceEvent(
            name="pattern_created",
            data={"pattern": config.pattern},
        ))

        # Execute
        start_time = time.time()
        try:
            pattern_result = await pattern.execute(agents, input_message, context)
            context.workflow_state.mark_completed()

        except Exception as e:
            context.workflow_state.mark_failed(str(e))
            trace.add_event(TraceEvent(
                name="execution_failed",
                data={"error": str(e)},
            ))
            return WorkflowResult(
                output=Message(content=str(e), role=MessageRole.AGENT),
                pattern_result=PatternResult(
                    output=Message(content=str(e), role=MessageRole.AGENT),
                    success=False,
                    error=str(e),
                ),
                execution_id=execution_id,
                workflow_name=config.name,
                total_tokens=context.total_tokens,
                total_latency_ms=int((time.time() - start_time) * 1000),
                total_cost_usd=self._estimate_cost(context.total_tokens, "gpt-4"),
                trace=trace,
                success=False,
                error=str(e),
            )

        # Complete trace
        total_latency = int((time.time() - start_time) * 1000)
        trace.add_event(TraceEvent(
            name="execution_completed",
            data={
                "success": pattern_result.success,
                "iterations": pattern_result.iterations,
                "latency_ms": total_latency,
            },
        ))

        return WorkflowResult(
            output=pattern_result.output,
            pattern_result=pattern_result,
            execution_id=execution_id,
            workflow_name=config.name,
            total_tokens=context.total_tokens,
            total_latency_ms=total_latency,
            total_cost_usd=self._estimate_cost(context.total_tokens, "gpt-4"),
            trace=trace,
            success=pattern_result.success,
            error=pattern_result.error,
        )

    def _estimate_cost(self, tokens: int, model: str) -> float:
        """Estimate cost based on token usage."""
        if model not in self.model_costs:
            model = "gpt-4"  # default
        costs = self.model_costs[model]
        # Rough estimate: assume 50/50 input/output split
        return (tokens / 1000) * (costs["input"] + costs["output"]) / 2


# Convenience function for quick execution
async def run_workflow(
    workflow: WorkflowConfig | str | dict,
    input_text: str,
    **kwargs,
) -> WorkflowResult:
    """
    Convenience function to run a workflow.

    Example:
        result = await run_workflow(
            "examples/pr_review/workflow.yaml",
            "Review this code: ...",
        )
        print(result.output.content)
    """
    runtime = Runtime(**kwargs)
    return await runtime.execute(workflow, input_text)
