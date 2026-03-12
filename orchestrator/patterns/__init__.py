"""
Orchestration patterns for multi-agent coordination.

Available patterns:
- sequential: A → B → C
- parallel: A, B, C → combine
- parallel_then_synthesize: A, B, C → Synthesizer
- hierarchical: Manager → Workers → Manager
- map_reduce: Workers → Reducer
- debate: Advocate ↔ Adversary → Judge
- fact_check: Researcher → Verifier → Judge
- reflexion: Act → Critique → Retry
- self_refine: Single agent iterative improvement
"""

from .base import (
    Pattern,
    PatternConfig,
    PatternResult,
    PatternRegistry,
    pattern_registry,
    register_pattern,
)
from .sequential import SequentialPattern, SequentialWithGatePattern
from .parallel import ParallelPattern, ParallelThenSynthesizePattern
from .hierarchical import HierarchicalPattern, MapReducePattern
from .debate import DebatePattern, FactCheckPattern
from .reflexion import ReflexionPattern, SelfRefinePattern

__all__ = [
    # Base
    "Pattern",
    "PatternConfig",
    "PatternResult",
    "PatternRegistry",
    "pattern_registry",
    "register_pattern",
    # Sequential
    "SequentialPattern",
    "SequentialWithGatePattern",
    # Parallel
    "ParallelPattern",
    "ParallelThenSynthesizePattern",
    # Hierarchical
    "HierarchicalPattern",
    "MapReducePattern",
    # Debate
    "DebatePattern",
    "FactCheckPattern",
    # Reflexion
    "ReflexionPattern",
    "SelfRefinePattern",
]
