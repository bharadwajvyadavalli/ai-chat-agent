"""
Sequential orchestration pattern.

Executes agents one after another: A → B → C
Each agent receives the output of the previous agent.
"""

from __future__ import annotations

from ..agent import Agent
from ..context import Context
from ..message import Message
from .base import Pattern, PatternConfig, PatternResult, register_pattern


@register_pattern("sequential")
class SequentialPattern(Pattern):
    """
    Sequential execution: A → B → C

    Each agent receives the output of the previous agent as input.
    The final agent's output becomes the pattern's output.

    Use when:
    - Tasks have clear dependencies
    - Each step transforms or enriches the previous output
    - Order matters

    Example: Extract → Transform → Validate → Load
    """

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        if not agents:
            return PatternResult(
                output=input_message,
                success=True,
            )

        intermediate_outputs: list[Message] = []
        current_input = input_message

        for i, agent in enumerate(agents):
            # Update workflow state
            if context.workflow_state:
                context.workflow_state.current_step = i + 1
                context.workflow_state.total_steps = len(agents)

            try:
                # Execute agent
                output = await agent(current_input, context)
                intermediate_outputs.append(output)

                # Output becomes input for next agent
                current_input = output

            except Exception as e:
                if self.config.stop_on_error:
                    return PatternResult(
                        output=current_input,
                        intermediate_outputs=intermediate_outputs,
                        iterations=i + 1,
                        success=False,
                        error=f"Agent '{agent.name}' failed: {str(e)}",
                    )
                # Continue on error - use previous output
                continue

        return PatternResult(
            output=current_input,
            intermediate_outputs=intermediate_outputs,
            iterations=len(agents),
            success=True,
        )


@register_pattern("sequential_with_gate")
class SequentialWithGatePattern(Pattern):
    """
    Sequential execution with conditional gates.

    Like SequentialPattern, but each agent can have a gate condition.
    If the gate fails, execution stops early (successfully).

    Useful for:
    - Early termination (e.g., "if not critical, stop")
    - Conditional pipelines (e.g., "only remediate if severity > low")
    """

    def __init__(
        self,
        config: PatternConfig | None = None,
        gates: dict[str, callable] | None = None,
    ):
        super().__init__(config)
        # gates: {agent_name: (context) -> bool}
        self.gates = gates or {}

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        if not agents:
            return PatternResult(output=input_message, success=True)

        intermediate_outputs: list[Message] = []
        current_input = input_message

        for i, agent in enumerate(agents):
            # Check gate before execution
            if agent.name in self.gates:
                gate_fn = self.gates[agent.name]
                if not gate_fn(context):
                    # Gate failed - stop execution (but it's a success)
                    return PatternResult(
                        output=current_input,
                        intermediate_outputs=intermediate_outputs,
                        iterations=i,
                        success=True,
                        error=None,
                    )

            try:
                output = await agent(current_input, context)
                intermediate_outputs.append(output)
                current_input = output

            except Exception as e:
                if self.config.stop_on_error:
                    return PatternResult(
                        output=current_input,
                        intermediate_outputs=intermediate_outputs,
                        iterations=i + 1,
                        success=False,
                        error=f"Agent '{agent.name}' failed: {str(e)}",
                    )
                continue

        return PatternResult(
            output=current_input,
            intermediate_outputs=intermediate_outputs,
            iterations=len(agents),
            success=True,
        )
