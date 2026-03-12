"""
Research Assistant Example

Demonstrates multi-agent orchestration for deep research:
- Researcher: Gathers information on a topic
- Fact Checker: Verifies claims and sources
- Critic: Identifies gaps and biases
- Synthesizer: Creates balanced summary
"""

from .workflow import research_workflow, research_topic

__all__ = [
    "research_workflow",
    "research_topic",
]
