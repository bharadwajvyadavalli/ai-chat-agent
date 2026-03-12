"""
PR Review Example

Demonstrates multi-agent orchestration for code review:
- Security Agent: Identifies security vulnerabilities
- Performance Agent: Spots performance issues
- Style Agent: Checks code style and readability
- Synthesizer: Combines reviews into prioritized feedback
"""

from .agents import (
    security_agent,
    performance_agent,
    style_agent,
    synthesizer_agent,
)
from .workflow import pr_review_workflow, review_pr

__all__ = [
    "security_agent",
    "performance_agent",
    "style_agent",
    "synthesizer_agent",
    "pr_review_workflow",
    "review_pr",
]
