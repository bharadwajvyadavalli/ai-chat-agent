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
from .resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    FallbackResult,
    RateLimitConfig,
    RetryConfig,
    RetryError,
    TimeoutConfig,
    TimeoutError,
    TokenBucketRateLimiter,
    get_rate_limiter,
    retry_with_backoff,
    with_fallback,
    with_retry,
    with_timeout,
)

__version__ = "2.0.0"

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
    # Resilience
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    "FallbackResult",
    "RateLimitConfig",
    "RetryConfig",
    "RetryError",
    "TimeoutConfig",
    "TimeoutError",
    "TokenBucketRateLimiter",
    "get_rate_limiter",
    "retry_with_backoff",
    "with_fallback",
    "with_retry",
    "with_timeout",
]
