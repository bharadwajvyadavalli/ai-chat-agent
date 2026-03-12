"""
Multi-Agent Orchestration Framework

A generic framework for orchestrating multiple AI agents to solve complex tasks.
Supports multiple orchestration patterns: sequential, parallel, hierarchical,
debate, and reflexion.
"""

from .agent import (
    Agent,
    AgentConfig,
    AgentRegistry,
    FunctionAgent,
    LLMAgent,
    get_agent,
    list_agents,
    register_agent,
)
from .context import Context, WorkflowState
from .message import Artifact, ArtifactType, Message, MessageRole
from .patterns import (
    Pattern,
    PatternConfig,
    PatternResult,
    pattern_registry,
    DebatePattern,
    HierarchicalPattern,
    MapReducePattern,
    ParallelPattern,
    ParallelThenSynthesizePattern,
    ReflexionPattern,
    SelfRefinePattern,
    SequentialPattern,
    SequentialWithGatePattern,
)

__version__ = "0.1.0"

__all__ = [
    # Core
    "Agent",
    "AgentConfig",
    "AgentRegistry",
    "FunctionAgent",
    "LLMAgent",
    "get_agent",
    "list_agents",
    "register_agent",
    # Context
    "Context",
    "WorkflowState",
    # Message
    "Artifact",
    "ArtifactType",
    "Message",
    "MessageRole",
    # Patterns
    "Pattern",
    "PatternConfig",
    "PatternResult",
    "pattern_registry",
    "DebatePattern",
    "HierarchicalPattern",
    "MapReducePattern",
    "ParallelPattern",
    "ParallelThenSynthesizePattern",
    "ReflexionPattern",
    "SelfRefinePattern",
    "SequentialPattern",
    "SequentialWithGatePattern",
]
