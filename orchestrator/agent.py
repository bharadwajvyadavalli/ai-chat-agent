"""
Base agent class and registry for multi-agent orchestration.

Agents are the units of work in the orchestration pipeline. Each agent
has a single responsibility and communicates via typed Messages.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .context import Context
from .message import Message, MessageRole


@dataclass
class AgentConfig:
    """
    Configuration for an agent.

    Separates the agent's identity/behavior config from its implementation.
    This allows the same agent class to be reused with different prompts.
    """
    name: str
    description: str
    system_prompt: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    tools: list[str] = field(default_factory=list)  # tool names this agent can use
    metadata: dict = field(default_factory=dict)


class Agent(ABC):
    """
    Base class for all agents in the orchestration pipeline.

    Each agent:
    - Has a unique name and description
    - Takes a Message + Context as input
    - Returns a Message as output
    - Can use tools via the context

    Subclasses must implement the `run` method.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.description = config.description

    @abstractmethod
    async def run(self, input_message: Message, context: Context) -> Message:
        """
        Execute the agent's task.

        Args:
            input_message: The input to process
            context: Shared context with memory, history, and tools

        Returns:
            A Message containing the agent's output
        """
        pass

    async def __call__(self, input_message: Message, context: Context) -> Message:
        """
        Execute the agent with timing and tracking.

        This wrapper handles:
        - Timing the execution
        - Setting source_agent on the output
        - Adding the output to context history
        """
        start_time = time.time()

        output = await self.run(input_message, context)

        # Ensure output has correct metadata
        output.source_agent = self.name
        output.parent_message_id = input_message.id
        if output.latency_ms is None:
            output.latency_ms = int((time.time() - start_time) * 1000)

        # Add to context history
        context.add_message(output)

        return output

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


class LLMAgent(Agent):
    """
    An agent powered by an LLM.

    This is the most common agent type. It sends prompts to an LLM
    and returns the response as a Message.
    """

    def __init__(self, config: AgentConfig, llm_client: Any = None):
        super().__init__(config)
        self.llm_client = llm_client

    async def run(self, input_message: Message, context: Context) -> Message:
        """
        Run the LLM with the configured prompt.

        Builds a prompt from:
        - System prompt (from config)
        - Recent history (from context)
        - Input message
        - Tool results (if any tools were used)
        """
        # Build messages for LLM
        messages = self._build_messages(input_message, context)

        # Call LLM
        response = await self._call_llm(messages)

        return Message(
            content=response["content"],
            role=MessageRole.AGENT,
            tokens_used=response.get("tokens"),
            model=self.config.model,
            confidence=response.get("confidence"),
        )

    def _build_messages(self, input_message: Message, context: Context) -> list[dict]:
        """Build the message list for the LLM call."""
        messages = [
            {"role": "system", "content": self.config.system_prompt}
        ]

        # Add relevant history
        messages.extend(context.get_history_for_prompt(max_messages=6))

        # Add the current input
        messages.append({
            "role": "user",
            "content": input_message.content
        })

        return messages

    async def _call_llm(self, messages: list[dict]) -> dict:
        """
        Call the LLM. Override this method to use different providers.

        Returns dict with 'content' and optionally 'tokens', 'confidence'.
        """
        if self.llm_client is None:
            # Default: use OpenAI
            return await self._call_openai(messages)

        # Use injected client
        return await self.llm_client.chat(messages, self.config)

    async def _call_openai(self, messages: list[dict]) -> dict:
        """Call OpenAI API."""
        import openai

        client = openai.AsyncOpenAI()
        response = await client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        return {
            "content": response.choices[0].message.content,
            "tokens": response.usage.total_tokens if response.usage else None,
        }


class FunctionAgent(Agent):
    """
    An agent that runs a Python function.

    Useful for deterministic transformations, validations,
    or integrations that don't need LLM reasoning.
    """

    def __init__(self, config: AgentConfig, func: callable):
        super().__init__(config)
        self.func = func

    async def run(self, input_message: Message, context: Context) -> Message:
        """Run the function and wrap the result in a Message."""
        import asyncio
        import inspect

        # Handle both sync and async functions
        if inspect.iscoroutinefunction(self.func):
            result = await self.func(input_message, context)
        else:
            result = await asyncio.to_thread(self.func, input_message, context)

        # If function returns a Message, use it directly
        if isinstance(result, Message):
            return result

        # Otherwise wrap the result
        return Message(
            content=str(result),
            role=MessageRole.AGENT,
        )


class AgentRegistry:
    """
    Registry for managing agents.

    Allows agents to be registered by name and retrieved later.
    Useful for workflow configuration where agents are referenced by name.
    """

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent."""
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' already registered")
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        """Get an agent by name."""
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not found. Available: {list(self._agents.keys())}")
        return self._agents[name]

    def list(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)


# Global registry for convenience
_global_registry = AgentRegistry()


def register_agent(agent: Agent) -> Agent:
    """Register an agent in the global registry."""
    _global_registry.register(agent)
    return agent


def get_agent(name: str) -> Agent:
    """Get an agent from the global registry."""
    return _global_registry.get(name)


def list_agents() -> list[str]:
    """List all agents in the global registry."""
    return _global_registry.list()
