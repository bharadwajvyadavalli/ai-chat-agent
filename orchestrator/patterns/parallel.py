"""
Parallel orchestration pattern.

Executes agents concurrently and combines their outputs.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from ..agent import Agent
from ..context import Context
from ..message import Artifact, ArtifactType, Message, MessageRole
from .base import Pattern, PatternConfig, PatternResult, register_pattern


# Type alias for combiner functions
Combiner = Callable[[list[Message], Context], Message]


def default_combiner(outputs: list[Message], context: Context) -> Message:
    """
    Default combiner: concatenate all outputs.

    Creates a message with all agent outputs as sections.
    """
    sections = []
    for msg in outputs:
        agent_name = msg.source_agent or "unknown"
        sections.append(f"## {agent_name}\n\n{msg.content}")

    combined_content = "\n\n---\n\n".join(sections)

    # Aggregate artifacts
    all_artifacts = []
    for msg in outputs:
        all_artifacts.extend(msg.artifacts)

    # Aggregate confidence (average)
    confidences = [m.confidence for m in outputs if m.confidence is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    return Message(
        content=combined_content,
        role=MessageRole.AGENT,
        source_agent="parallel_combiner",
        confidence=avg_confidence,
        artifacts=all_artifacts,
    )


@register_pattern("parallel")
class ParallelPattern(Pattern):
    """
    Parallel execution: A, B, C → combine

    All agents execute concurrently on the same input.
    A combiner function merges their outputs.

    Use when:
    - Tasks are independent
    - You want multiple perspectives
    - Speed matters (parallel = faster)

    Example: Security review + Performance review + Style review → Synthesize
    """

    def __init__(
        self,
        config: PatternConfig | None = None,
        combiner: Combiner | None = None,
    ):
        super().__init__(config)
        self.combiner = combiner or default_combiner

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        if not agents:
            return PatternResult(output=input_message, success=True)

        # Fork context for each agent (independent histories)
        contexts = [context.fork() for _ in agents]

        # Execute all agents concurrently
        tasks = [
            agent(input_message, ctx)
            for agent, ctx in zip(agents, contexts)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successes and failures
        outputs: list[Message] = []
        errors: list[str] = []

        for agent, result in zip(agents, results):
            if isinstance(result, Exception):
                errors.append(f"{agent.name}: {str(result)}")
            else:
                outputs.append(result)

        # Merge costs from child contexts
        for child_ctx in contexts:
            context.merge_costs(child_ctx)

        # Check if we have any outputs
        if not outputs:
            return PatternResult(
                output=Message(content="All agents failed", role=MessageRole.AGENT),
                intermediate_outputs=[],
                success=False,
                error="; ".join(errors),
            )

        # Combine outputs
        combined = self.combiner(outputs, context)
        context.add_message(combined)

        return PatternResult(
            output=combined,
            intermediate_outputs=outputs,
            iterations=1,
            success=len(errors) == 0,
            error="; ".join(errors) if errors else None,
        )


@register_pattern("parallel_then_synthesize")
class ParallelThenSynthesizePattern(Pattern):
    """
    Parallel execution followed by a synthesizer agent.

    All specialist agents run in parallel, then a synthesizer
    agent combines and refines their outputs.

    This is the most common pattern for multi-perspective analysis:
    - Run specialists in parallel (fast)
    - Synthesizer has access to all specialist outputs
    - Final output is coherent and prioritized

    Example: PR Review
      Security Agent  ─┐
      Performance Agent ─┼──▶ Synthesizer ──▶ Final Review
      Style Agent     ─┘
    """

    def __init__(
        self,
        config: PatternConfig | None = None,
        synthesizer: Agent | None = None,
    ):
        super().__init__(config)
        self.synthesizer = synthesizer

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        if not agents:
            return PatternResult(output=input_message, success=True)

        # If no synthesizer, last agent is the synthesizer
        if self.synthesizer:
            specialists = agents
            synth = self.synthesizer
        else:
            specialists = agents[:-1]
            synth = agents[-1]

        # Phase 1: Run specialists in parallel
        parallel_pattern = ParallelPattern(self.config)
        parallel_result = await parallel_pattern.execute(
            specialists, input_message, context
        )

        if not parallel_result.success and self.config.stop_on_error:
            return parallel_result

        # Phase 2: Synthesizer processes combined output
        # The synthesizer gets the combined parallel output
        synth_input = Message(
            content=f"Original request:\n{input_message.content}\n\n"
                    f"Specialist outputs:\n{parallel_result.output.content}",
            role=MessageRole.USER,
            parent_message_id=input_message.id,
        )

        try:
            final_output = await synth(synth_input, context)
        except Exception as e:
            return PatternResult(
                output=parallel_result.output,
                intermediate_outputs=parallel_result.intermediate_outputs,
                iterations=2,
                success=False,
                error=f"Synthesizer failed: {str(e)}",
            )

        return PatternResult(
            output=final_output,
            intermediate_outputs=[*parallel_result.intermediate_outputs, parallel_result.output],
            iterations=2,
            success=True,
        )
