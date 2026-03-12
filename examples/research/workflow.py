"""
Research Assistant Workflow

Uses the Reflexion pattern for iterative research improvement.
"""

from orchestrator import (
    AgentConfig,
    Context,
    LLMAgent,
    Message,
    MessageRole,
)
from orchestrator.patterns import ReflexionPattern, DebatePattern
from orchestrator.runtime import Runtime, WorkflowConfig, WorkflowResult


# Research Agent
researcher_config = AgentConfig(
    name="researcher",
    description="Gathers comprehensive information on a topic",
    system_prompt="""You are a thorough research assistant. When given a topic:

1. **Gather Information**: Provide comprehensive information on the topic
2. **Multiple Perspectives**: Include different viewpoints and approaches
3. **Structure**: Organize information clearly with headers
4. **Sources**: Note where information typically comes from (academic, industry, etc.)
5. **Recency**: Note if information might be time-sensitive

Format your response with:
- Key Facts
- Different Perspectives
- Current State / Recent Developments
- Open Questions / Areas of Debate

Be thorough but focused. Aim for depth over breadth.""",
    model="gpt-4",
    temperature=0.7,
)

# Critic Agent
critic_config = AgentConfig(
    name="critic",
    description="Evaluates research quality and identifies gaps",
    system_prompt="""You are a critical research evaluator. Analyze the research for:

1. **Completeness**: Are there missing perspectives or information?
2. **Accuracy**: Are claims well-supported? Any potential errors?
3. **Balance**: Is the coverage balanced or biased toward one view?
4. **Depth**: Is the analysis sufficiently deep?
5. **Clarity**: Is the information well-organized and clear?

Provide:
- SCORE: 0.0 to 1.0 (how good is this research?)
- STRENGTHS: What was done well
- WEAKNESSES: What needs improvement
- SUGGESTIONS: Specific improvements for the next iteration
- PASS: YES if this is publication-ready, NO if it needs more work

Be constructive and specific. Point to exact areas that need work.""",
    model="gpt-4",
    temperature=0.3,
)

researcher_agent = LLMAgent(researcher_config)
critic_agent = LLMAgent(critic_config)


# Workflow configuration
research_workflow = WorkflowConfig(
    name="deep-research",
    description="Iterative research with self-improvement via Reflexion pattern",
    pattern="reflexion",
    pattern_config={
        "max_iterations": 3,
        "success_threshold": 0.8,
    },
    agents=[
        {
            "name": "researcher",
            "description": "Gathers comprehensive information",
            "system_prompt": researcher_config.system_prompt,
            "model": "gpt-4",
            "temperature": 0.7,
        },
        {
            "name": "critic",
            "description": "Evaluates research quality",
            "system_prompt": critic_config.system_prompt,
            "model": "gpt-4",
            "temperature": 0.3,
        },
    ],
    tools=[],
)


async def research_topic(
    topic: str,
    depth: str = "moderate",  # shallow, moderate, deep
    max_iterations: int = 3,
) -> WorkflowResult:
    """
    Research a topic using iterative multi-agent refinement.

    Args:
        topic: The topic to research
        depth: How deep to go (affects iteration count)
        max_iterations: Maximum refinement iterations

    Returns:
        WorkflowResult with the final research output

    Example:
        result = await research_topic(
            topic="The impact of large language models on software development",
            depth="deep",
        )
        print(result.output.content)
    """
    # Adjust iterations based on depth
    depth_iterations = {
        "shallow": 1,
        "moderate": 2,
        "deep": 3,
    }
    iterations = min(depth_iterations.get(depth, 2), max_iterations)

    # Build input message
    input_text = f"""Research the following topic thoroughly:

**Topic:** {topic}

**Depth requested:** {depth}

Please provide comprehensive, balanced research on this topic."""

    # Create runtime with adjusted config
    workflow = WorkflowConfig(
        name="deep-research",
        description="Iterative research with self-improvement",
        pattern="reflexion",
        pattern_config={
            "max_iterations": iterations,
            "success_threshold": 0.8,
        },
        agents=research_workflow.agents,
        tools=[],
    )

    runtime = Runtime()
    return await runtime.execute(
        workflow,
        input_message=Message(content=input_text, role=MessageRole.USER),
    )


async def debate_topic(
    topic: str,
    num_rounds: int = 2,
) -> WorkflowResult:
    """
    Explore a topic through structured debate.

    Two agents argue opposing positions, then a judge synthesizes.

    Args:
        topic: The topic or question to debate
        num_rounds: Number of debate rounds

    Returns:
        WorkflowResult with the judge's synthesis
    """
    # Debate agents
    advocate_config = AgentConfig(
        name="advocate",
        description="Argues in favor of the position",
        system_prompt="You are a skilled debater. Argue IN FAVOR of the given position. "
                     "Use logic, evidence, and persuasive reasoning. Address counterarguments.",
        model="gpt-4",
        temperature=0.7,
    )

    adversary_config = AgentConfig(
        name="adversary",
        description="Argues against the position",
        system_prompt="You are a skilled debater. Argue AGAINST the given position. "
                     "Use logic, evidence, and persuasive reasoning. Address counterarguments.",
        model="gpt-4",
        temperature=0.7,
    )

    judge_config = AgentConfig(
        name="judge",
        description="Evaluates debate and reaches balanced conclusion",
        system_prompt="You are an impartial judge. Evaluate both sides of the debate. "
                     "Identify the strongest arguments from each side. Reach a balanced "
                     "conclusion, noting where each side made valid points.",
        model="gpt-4",
        temperature=0.5,
    )

    workflow = WorkflowConfig(
        name="debate",
        description="Structured debate on a topic",
        pattern="debate",
        pattern_config={
            "num_rounds": num_rounds,
        },
        agents=[
            {"name": "advocate", **advocate_config.__dict__},
            {"name": "adversary", **adversary_config.__dict__},
            {"name": "judge", **judge_config.__dict__},
        ],
        tools=[],
    )

    runtime = Runtime()
    return await runtime.execute(
        workflow,
        input_message=Message(content=topic, role=MessageRole.USER),
    )


# Example usage
if __name__ == "__main__":
    import asyncio

    async def main():
        print("=" * 60)
        print("RESEARCH EXAMPLE")
        print("=" * 60)

        result = await research_topic(
            topic="The future of AI agents in software engineering",
            depth="moderate",
        )

        print(result.output.content)
        print()
        print(f"Iterations: {result.pattern_result.iterations}")
        print(f"Tokens used: {result.total_tokens}")
        print(f"Latency: {result.total_latency_ms}ms")

    asyncio.run(main())
