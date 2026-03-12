"""
PR Review Workflow

Orchestrates multiple review agents to produce comprehensive code review.
"""

from orchestrator import (
    Context,
    Message,
    MessageRole,
    ParallelThenSynthesizePattern,
    PatternConfig,
)
from orchestrator.runtime import Runtime, WorkflowConfig, WorkflowResult

from .agents import (
    security_agent,
    performance_agent,
    style_agent,
    synthesizer_agent,
)


# Workflow configuration
pr_review_workflow = WorkflowConfig(
    name="pr-review",
    description="Multi-agent code review with security, performance, and style analysis",
    pattern="parallel_then_synthesize",
    pattern_config={
        "max_iterations": 1,
        "timeout_seconds": 120,
    },
    agents=[
        {
            "name": "security_reviewer",
            "description": "Identifies security vulnerabilities",
            "system_prompt": security_agent.config.system_prompt,
            "model": "gpt-4",
            "temperature": 0.3,
        },
        {
            "name": "performance_reviewer",
            "description": "Spots performance issues",
            "system_prompt": performance_agent.config.system_prompt,
            "model": "gpt-4",
            "temperature": 0.3,
        },
        {
            "name": "style_reviewer",
            "description": "Checks code style and readability",
            "system_prompt": style_agent.config.system_prompt,
            "model": "gpt-4",
            "temperature": 0.5,
        },
        {
            "name": "synthesizer",
            "description": "Combines reviews into prioritized feedback",
            "system_prompt": synthesizer_agent.config.system_prompt,
            "model": "gpt-4",
            "temperature": 0.7,
        },
    ],
    tools=[],
    metadata={
        "version": "1.0.0",
        "author": "orchestrator",
    },
)


async def review_pr(
    code: str,
    pr_title: str | None = None,
    pr_description: str | None = None,
    file_path: str | None = None,
) -> WorkflowResult:
    """
    Review code changes using multi-agent orchestration.

    Args:
        code: The code to review (diff or full file)
        pr_title: Optional PR title for context
        pr_description: Optional PR description for context
        file_path: Optional file path for context

    Returns:
        WorkflowResult with the synthesized review

    Example:
        result = await review_pr(
            code='''
            def process_user_input(user_id):
                query = f"SELECT * FROM users WHERE id = {user_id}"
                return db.execute(query)
            ''',
            pr_title="Add user lookup function",
        )
        print(result.output.content)
    """
    # Build the input message with context
    parts = []

    if pr_title:
        parts.append(f"**PR Title:** {pr_title}")

    if pr_description:
        parts.append(f"**PR Description:** {pr_description}")

    if file_path:
        parts.append(f"**File:** {file_path}")

    parts.append("**Code to Review:**")
    parts.append(f"```\n{code}\n```")

    input_text = "\n\n".join(parts)

    # Create runtime and execute
    runtime = Runtime()
    result = await runtime.execute(
        pr_review_workflow,
        input_message=Message(content=input_text, role=MessageRole.USER),
    )

    return result


async def review_pr_diff(
    diff: str,
    pr_url: str | None = None,
) -> WorkflowResult:
    """
    Review a git diff using multi-agent orchestration.

    Args:
        diff: The git diff output
        pr_url: Optional PR URL for context

    Returns:
        WorkflowResult with the synthesized review
    """
    parts = []

    if pr_url:
        parts.append(f"**PR URL:** {pr_url}")

    parts.append("**Diff to Review:**")
    parts.append(f"```diff\n{diff}\n```")

    input_text = "\n\n".join(parts)

    runtime = Runtime()
    return await runtime.execute(
        pr_review_workflow,
        input_message=Message(content=input_text, role=MessageRole.USER),
    )


# Example usage
if __name__ == "__main__":
    import asyncio

    sample_code = '''
def get_user_data(user_id):
    # Get user from database
    query = f"SELECT * FROM users WHERE id = {user_id}"
    result = db.execute(query)

    # Process all items
    items = []
    for user in result:
        for order in get_orders(user.id):
            for item in get_items(order.id):
                items.append(item)

    return {"user": result, "items": items}
'''

    async def main():
        result = await review_pr(
            code=sample_code,
            pr_title="Add user data endpoint",
            pr_description="New endpoint to fetch user data with their order items",
        )

        print("=" * 60)
        print("PR REVIEW RESULT")
        print("=" * 60)
        print(result.output.content)
        print()
        print(f"Tokens used: {result.total_tokens}")
        print(f"Latency: {result.total_latency_ms}ms")
        print(f"Estimated cost: ${result.total_cost_usd:.4f}")

    asyncio.run(main())
