"""
Multi-Agent Orchestration Framework

Entry point for running examples, web server, and testing the framework.
"""

import asyncio
import os
import sys

from orchestrator import Message, MessageRole
from orchestrator.runtime import Runtime


async def demo_pr_review():
    """Demo the PR review workflow."""
    from examples.pr_review import review_pr

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

    print("=" * 60)
    print("PR REVIEW DEMO")
    print("=" * 60)
    print(f"\nCode to review:\n{sample_code}")
    print("=" * 60)
    print("\nRunning multi-agent review...\n")

    result = await review_pr(
        code=sample_code,
        pr_title="Add user data endpoint",
        pr_description="New endpoint to fetch user data with their order items",
    )

    print("REVIEW RESULT:")
    print("-" * 60)
    print(result.output.content)
    print("-" * 60)
    print(f"\nTokens used: {result.total_tokens}")
    print(f"Latency: {result.total_latency_ms}ms")
    print(f"Estimated cost: ${result.total_cost_usd:.4f}")


async def demo_research():
    """Demo the research workflow."""
    from examples.research import research_topic

    topic = "The impact of large language models on software development practices"

    print("=" * 60)
    print("RESEARCH DEMO")
    print("=" * 60)
    print(f"\nTopic: {topic}")
    print("=" * 60)
    print("\nRunning iterative research (Reflexion pattern)...\n")

    result = await research_topic(topic=topic, depth="moderate")

    print("RESEARCH RESULT:")
    print("-" * 60)
    print(result.output.content)
    print("-" * 60)
    print(f"\nIterations: {result.pattern_result.iterations}")
    print(f"Tokens used: {result.total_tokens}")
    print(f"Latency: {result.total_latency_ms}ms")
    print(f"Estimated cost: ${result.total_cost_usd:.4f}")


async def demo_patterns():
    """Demo different orchestration patterns."""
    from orchestrator import AgentConfig, LLMAgent, Context
    from orchestrator.patterns import (
        SequentialPattern,
        ParallelPattern,
        DebatePattern,
    )

    print("=" * 60)
    print("ORCHESTRATION PATTERNS DEMO")
    print("=" * 60)

    # Simple agents for demo
    agent1 = LLMAgent(AgentConfig(
        name="summarizer",
        description="Summarizes text",
        system_prompt="Summarize the given text in one sentence.",
        model="gpt-4",
    ))

    agent2 = LLMAgent(AgentConfig(
        name="expander",
        description="Expands on ideas",
        system_prompt="Expand on the main idea with additional context.",
        model="gpt-4",
    ))

    # Sequential: Summarize → Expand
    print("\n1. SEQUENTIAL PATTERN (Summarize → Expand)")
    print("-" * 40)

    pattern = SequentialPattern()
    context = Context()
    input_msg = Message(
        content="Artificial intelligence is transforming how we write software.",
        role=MessageRole.USER,
    )

    result = await pattern.execute([agent1, agent2], input_msg, context)
    print(f"Result: {result.output.content[:200]}...")

    print("\n" + "=" * 60)
    print("Demo complete!")


def run_web_server():
    """Start the Flask web server."""
    from web.app import create_app

    app = create_app()
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"

    print(f"Starting web server at http://{host}:{port}")
    print("Press Ctrl+C to stop")
    app.run(host=host, port=port, debug=debug)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Multi-Agent Orchestration Framework v2.0")
        print()
        print("Usage: python main.py <command>")
        print()
        print("Commands:")
        print("  web         Start the web chat interface")
        print("  pr-review   Run the PR review demo")
        print("  research    Run the research demo")
        print("  patterns    Demo orchestration patterns")
        print()
        print("Environment variables:")
        print("  OPENAI_API_KEY     Your OpenAI API key")
        print("  FLASK_HOST         Web server host (default: 127.0.0.1)")
        print("  FLASK_PORT         Web server port (default: 5000)")
        print("  MEMORY_BACKEND     Memory backend: asmr, semantic (default: semantic)")
        print()
        return

    command = sys.argv[1]

    if command == "web":
        run_web_server()
    elif command == "pr-review":
        asyncio.run(demo_pr_review())
    elif command == "research":
        asyncio.run(demo_research())
    elif command == "patterns":
        asyncio.run(demo_patterns())
    else:
        print(f"Unknown command: {command}")
        print("Run 'python main.py' for usage.")


if __name__ == "__main__":
    main()
