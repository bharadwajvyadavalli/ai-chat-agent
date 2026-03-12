"""
Reflexion orchestration pattern.

Execute → Critique → Retry loop for iterative improvement.
Based on the Reflexion paper: self-reflection for autonomous agents.
"""

from __future__ import annotations

from ..agent import Agent
from ..context import Context
from ..message import Message, MessageRole
from .base import Pattern, PatternConfig, PatternResult, register_pattern


@register_pattern("reflexion")
class ReflexionPattern(Pattern):
    """
    Reflexion: Act → Critique → Retry

    An actor agent attempts a task, a critic evaluates it,
    and the actor retries with feedback until success or max iterations.

    Use when:
    - First attempts are often imperfect
    - You can evaluate quality (critic can assess)
    - Iteration improves results
    - You want self-correction without human intervention

    Example: Code generation
      Generator produces code
      Critic: "Missing error handling, inefficient loop"
      Generator revises with feedback
      Critic: "Looks good"
      Done

    The pattern maintains reflection memory - the actor sees
    all previous attempts and critiques when retrying.
    """

    def __init__(
        self,
        config: PatternConfig | None = None,
        max_iterations: int = 3,
        success_threshold: float = 0.8,  # confidence threshold to stop
    ):
        super().__init__(config)
        self.max_iterations = max_iterations
        self.success_threshold = success_threshold

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        """
        Execute reflexion pattern.

        Expects 2 agents: [actor, critic]
        """
        if len(agents) < 2:
            return PatternResult(
                output=Message(
                    content="Reflexion requires 2 agents: actor, critic",
                    role=MessageRole.AGENT,
                ),
                success=False,
                error="Insufficient agents for reflexion",
            )

        actor, critic = agents[0], agents[1]
        intermediate_outputs: list[Message] = []

        # Reflection memory: track previous attempts and critiques
        reflection_history: list[dict] = []
        best_output: Message | None = None
        best_score: float = 0.0

        for iteration in range(self.max_iterations):
            # Build prompt with reflection history
            if iteration == 0:
                actor_prompt = input_message
            else:
                history_text = self._format_reflection_history(reflection_history)
                actor_prompt = Message(
                    content=f"Original task: {input_message.content}\n\n"
                            f"Previous attempts and feedback:\n{history_text}\n\n"
                            "Based on the feedback, provide an improved response.",
                    role=MessageRole.USER,
                )

            # Actor attempts the task
            try:
                attempt = await actor(actor_prompt, context)
                intermediate_outputs.append(attempt)
            except Exception as e:
                return PatternResult(
                    output=best_output or Message(content=str(e), role=MessageRole.AGENT),
                    intermediate_outputs=intermediate_outputs,
                    iterations=iteration + 1,
                    success=False,
                    error=f"Actor failed on iteration {iteration + 1}: {e}",
                )

            # Critic evaluates the attempt
            critique_prompt = Message(
                content=f"Original task: {input_message.content}\n\n"
                        f"Attempt:\n{attempt.content}\n\n"
                        "Evaluate this attempt. Provide:\n"
                        "1. SCORE: A number from 0.0 to 1.0\n"
                        "2. STRENGTHS: What was done well\n"
                        "3. WEAKNESSES: What needs improvement\n"
                        "4. SUGGESTIONS: Specific improvements for next attempt\n"
                        "5. PASS: YES if acceptable, NO if needs more work",
                role=MessageRole.USER,
            )

            try:
                critique = await critic(critique_prompt, context)
                intermediate_outputs.append(critique)
            except Exception as e:
                return PatternResult(
                    output=attempt,
                    intermediate_outputs=intermediate_outputs,
                    iterations=iteration + 1,
                    success=False,
                    error=f"Critic failed on iteration {iteration + 1}: {e}",
                )

            # Parse critique for score and pass/fail
            score, passed = self._parse_critique(critique.content)

            # Track best attempt
            if score > best_score:
                best_score = score
                best_output = attempt

            # Add to reflection history
            reflection_history.append({
                "iteration": iteration + 1,
                "attempt": attempt.content,
                "critique": critique.content,
                "score": score,
            })

            # Check if we should stop
            if passed or score >= self.success_threshold:
                return PatternResult(
                    output=attempt,
                    intermediate_outputs=intermediate_outputs,
                    iterations=iteration + 1,
                    success=True,
                )

        # Max iterations reached - return best attempt
        return PatternResult(
            output=best_output or intermediate_outputs[-2],  # last actor output
            intermediate_outputs=intermediate_outputs,
            iterations=self.max_iterations,
            success=best_score >= self.success_threshold,
            error=f"Max iterations reached. Best score: {best_score:.2f}",
        )

    def _format_reflection_history(self, history: list[dict]) -> str:
        """Format reflection history for the actor prompt."""
        sections = []
        for entry in history:
            sections.append(
                f"### Attempt {entry['iteration']} (Score: {entry['score']:.2f})\n"
                f"{entry['attempt']}\n\n"
                f"**Feedback:**\n{entry['critique']}"
            )
        return "\n\n---\n\n".join(sections)

    def _parse_critique(self, critique_text: str) -> tuple[float, bool]:
        """
        Parse score and pass/fail from critique text.

        Returns (score, passed) tuple.
        """
        text = critique_text.lower()

        # Try to extract score
        score = 0.5  # default
        import re
        score_match = re.search(r'score[:\s]+([0-9.]+)', text)
        if score_match:
            try:
                score = float(score_match.group(1))
                score = max(0.0, min(1.0, score))  # clamp to [0, 1]
            except ValueError:
                pass

        # Check for pass/fail
        passed = False
        if 'pass: yes' in text or 'pass:yes' in text:
            passed = True
        elif 'acceptable' in text and 'not acceptable' not in text:
            passed = True

        return score, passed


@register_pattern("self_refine")
class SelfRefinePattern(Pattern):
    """
    Self-refinement: single agent refines its own output.

    Similar to Reflexion but uses a single agent that both
    generates and critiques. Simpler but less powerful.

    Use when:
    - You want quick iteration without separate critic
    - The task is straightforward enough for self-assessment
    """

    def __init__(
        self,
        config: PatternConfig | None = None,
        max_iterations: int = 2,
    ):
        super().__init__(config)
        self.max_iterations = max_iterations

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        if not agents:
            return PatternResult(
                output=input_message,
                success=False,
                error="No agent provided",
            )

        agent = agents[0]
        intermediate_outputs: list[Message] = []

        # Initial attempt
        current_output = await agent(input_message, context)
        intermediate_outputs.append(current_output)

        # Self-refinement iterations
        for i in range(self.max_iterations - 1):
            refine_prompt = Message(
                content=f"Original task: {input_message.content}\n\n"
                        f"Your previous response:\n{current_output.content}\n\n"
                        "Review your response. Identify any issues, gaps, or areas "
                        "for improvement. Then provide an improved version.",
                role=MessageRole.USER,
            )

            current_output = await agent(refine_prompt, context)
            intermediate_outputs.append(current_output)

        return PatternResult(
            output=current_output,
            intermediate_outputs=intermediate_outputs,
            iterations=self.max_iterations,
            success=True,
        )
