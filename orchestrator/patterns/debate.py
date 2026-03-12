"""
Debate orchestration pattern.

Two agents argue opposing positions, then a judge synthesizes.
Based on Anthropic's debate research for AI alignment.
"""

from __future__ import annotations

from ..agent import Agent
from ..context import Context
from ..message import Message, MessageRole
from .base import Pattern, PatternConfig, PatternResult, register_pattern


@register_pattern("debate")
class DebatePattern(Pattern):
    """
    Adversarial debate: Advocate ↔ Adversary → Judge

    Two agents argue different positions on a topic.
    A judge agent synthesizes the best answer.

    Use when:
    - Truth matters more than speed
    - You want to expose weaknesses in arguments
    - The topic has legitimate opposing views
    - You want to avoid confirmation bias

    Example: Investment decision
      Bull Agent (argues FOR) ─┐
                               ├──▶ rounds of debate ──▶ Judge ──▶ Decision
      Bear Agent (argues AGAINST)┘

    The debate can run for multiple rounds, with each agent
    responding to the other's arguments.
    """

    def __init__(
        self,
        config: PatternConfig | None = None,
        num_rounds: int = 2,
    ):
        super().__init__(config)
        self.num_rounds = num_rounds

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        """
        Execute debate pattern.

        Expects 3 agents: [advocate, adversary, judge]
        """
        if len(agents) < 3:
            return PatternResult(
                output=Message(
                    content="Debate requires 3 agents: advocate, adversary, judge",
                    role=MessageRole.AGENT,
                ),
                success=False,
                error="Insufficient agents for debate",
            )

        advocate, adversary, judge = agents[0], agents[1], agents[2]
        intermediate_outputs: list[Message] = []
        debate_transcript = []

        # Initial positions
        advocate_prompt = Message(
            content=f"Topic: {input_message.content}\n\n"
                    "Argue IN FAVOR of this position. Make your strongest case.",
            role=MessageRole.USER,
        )
        adversary_prompt = Message(
            content=f"Topic: {input_message.content}\n\n"
                    "Argue AGAINST this position. Make your strongest case.",
            role=MessageRole.USER,
        )

        # Get initial arguments (parallel)
        try:
            advocate_response = await advocate(advocate_prompt, context)
            adversary_response = await adversary(adversary_prompt, context)
        except Exception as e:
            return PatternResult(
                output=Message(content=str(e), role=MessageRole.AGENT),
                success=False,
                error=f"Initial debate round failed: {e}",
            )

        intermediate_outputs.extend([advocate_response, adversary_response])
        debate_transcript.append(f"**{advocate.name}**: {advocate_response.content}")
        debate_transcript.append(f"**{adversary.name}**: {adversary_response.content}")

        # Additional rounds: respond to each other
        for round_num in range(1, self.num_rounds):
            # Advocate responds to adversary
            advocate_rebuttal_prompt = Message(
                content=f"Your opponent argued:\n\n{adversary_response.content}\n\n"
                        "Respond to their arguments and strengthen your position.",
                role=MessageRole.USER,
            )
            advocate_response = await advocate(advocate_rebuttal_prompt, context)

            # Adversary responds to advocate
            adversary_rebuttal_prompt = Message(
                content=f"Your opponent argued:\n\n{advocate_response.content}\n\n"
                        "Respond to their arguments and strengthen your position.",
                role=MessageRole.USER,
            )
            adversary_response = await adversary(adversary_rebuttal_prompt, context)

            intermediate_outputs.extend([advocate_response, adversary_response])
            debate_transcript.append(f"**{advocate.name}** (round {round_num + 1}): {advocate_response.content}")
            debate_transcript.append(f"**{adversary.name}** (round {round_num + 1}): {adversary_response.content}")

        # Judge evaluates the debate
        full_transcript = "\n\n---\n\n".join(debate_transcript)
        judge_prompt = Message(
            content=f"Original question: {input_message.content}\n\n"
                    f"Debate transcript:\n\n{full_transcript}\n\n"
                    "As an impartial judge, evaluate both sides. "
                    "Identify the strongest arguments from each side. "
                    "Reach a balanced conclusion, noting where each side made valid points "
                    "and where arguments were weak. Be specific about what convinced you.",
            role=MessageRole.USER,
        )

        try:
            judgment = await judge(judge_prompt, context)
        except Exception as e:
            return PatternResult(
                output=Message(
                    content=full_transcript,
                    role=MessageRole.AGENT,
                    source_agent="debate",
                ),
                intermediate_outputs=intermediate_outputs,
                iterations=self.num_rounds,
                success=False,
                error=f"Judge failed: {e}",
            )

        intermediate_outputs.append(judgment)

        return PatternResult(
            output=judgment,
            intermediate_outputs=intermediate_outputs,
            iterations=self.num_rounds + 1,  # rounds + judgment
            success=True,
        )


@register_pattern("fact_check")
class FactCheckPattern(Pattern):
    """
    Fact-checking pattern: Claim → Researcher → Verifier → Verdict

    A specialized debate variant where:
    1. Researcher finds evidence
    2. Verifier challenges the evidence
    3. Judge determines truth

    More structured than open debate - focused on factual accuracy.
    """

    async def execute(
        self,
        agents: list[Agent],
        input_message: Message,
        context: Context,
    ) -> PatternResult:
        if len(agents) < 3:
            return PatternResult(
                output=Message(
                    content="Fact-check requires 3 agents: researcher, verifier, judge",
                    role=MessageRole.AGENT,
                ),
                success=False,
                error="Insufficient agents",
            )

        researcher, verifier, judge = agents[0], agents[1], agents[2]
        intermediate_outputs: list[Message] = []

        # Step 1: Research the claim
        research_prompt = Message(
            content=f"Claim to verify: {input_message.content}\n\n"
                    "Find evidence for and against this claim. "
                    "Cite specific sources when possible.",
            role=MessageRole.USER,
        )
        research = await researcher(research_prompt, context)
        intermediate_outputs.append(research)

        # Step 2: Challenge the research
        verify_prompt = Message(
            content=f"Original claim: {input_message.content}\n\n"
                    f"Research findings:\n{research.content}\n\n"
                    "Challenge this research. What's missing? "
                    "Are the sources reliable? What biases might be present? "
                    "What would change your confidence?",
            role=MessageRole.USER,
        )
        verification = await verifier(verify_prompt, context)
        intermediate_outputs.append(verification)

        # Step 3: Final judgment
        judge_prompt = Message(
            content=f"Claim: {input_message.content}\n\n"
                    f"Research:\n{research.content}\n\n"
                    f"Verification/Challenges:\n{verification.content}\n\n"
                    "Based on the evidence and challenges, determine:\n"
                    "1. Verdict: TRUE / FALSE / PARTIALLY TRUE / UNVERIFIABLE\n"
                    "2. Confidence: HIGH / MEDIUM / LOW\n"
                    "3. Key supporting evidence\n"
                    "4. Key counter-evidence or gaps",
            role=MessageRole.USER,
        )
        judgment = await judge(judge_prompt, context)
        intermediate_outputs.append(judgment)

        return PatternResult(
            output=judgment,
            intermediate_outputs=intermediate_outputs,
            iterations=3,
            success=True,
        )
