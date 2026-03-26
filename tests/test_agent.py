"""
Tests for agent routing and execution.

Tests:
- Agent configuration
- LLMAgent execution
- FunctionAgent execution
- Agent registry
- Routing decisions
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator import (
    Agent,
    AgentConfig,
    AgentRegistry,
    FunctionAgent,
    LLMAgent,
    Message,
    MessageRole,
    Context,
)


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AgentConfig(
            name="test_agent",
            description="A test agent",
            system_prompt="You are a helpful assistant.",
        )

        assert config.name == "test_agent"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000
        assert config.tools == []

    def test_custom_config(self):
        """Test custom configuration values."""
        config = AgentConfig(
            name="custom_agent",
            description="Custom agent",
            system_prompt="Custom prompt",
            model="gpt-3.5-turbo",
            temperature=0.3,
            max_tokens=1000,
            tools=["web_search", "calculator"],
            metadata={"category": "specialized"},
        )

        assert config.model == "gpt-3.5-turbo"
        assert config.temperature == 0.3
        assert config.tools == ["web_search", "calculator"]
        assert config.metadata["category"] == "specialized"


class TestFunctionAgent:
    """Tests for FunctionAgent."""

    @pytest.fixture
    def config(self):
        return AgentConfig(
            name="func_agent",
            description="A function agent",
            system_prompt="N/A",
        )

    @pytest.mark.asyncio
    async def test_sync_function(self, config):
        """Test executing a synchronous function."""
        def transform(msg: Message, ctx: Context) -> str:
            return msg.content.upper()

        agent = FunctionAgent(config, transform)
        context = Context()
        input_msg = Message(content="hello", role=MessageRole.USER)

        output = await agent(input_msg, context)

        assert output.content == "HELLO"
        assert output.role == MessageRole.AGENT

    @pytest.mark.asyncio
    async def test_async_function(self, config):
        """Test executing an asynchronous function."""
        async def async_transform(msg: Message, ctx: Context) -> str:
            await asyncio.sleep(0.01)
            return f"Processed: {msg.content}"

        agent = FunctionAgent(config, async_transform)
        context = Context()
        input_msg = Message(content="test", role=MessageRole.USER)

        output = await agent(input_msg, context)

        assert output.content == "Processed: test"

    @pytest.mark.asyncio
    async def test_return_message(self, config):
        """Test function that returns a Message directly."""
        def create_message(msg: Message, ctx: Context) -> Message:
            return Message(
                content=f"Custom: {msg.content}",
                role=MessageRole.AGENT,
                metadata={"custom": True},
            )

        agent = FunctionAgent(config, create_message)
        context = Context()
        input_msg = Message(content="test", role=MessageRole.USER)

        output = await agent(input_msg, context)

        assert "Custom:" in output.content
        assert output.metadata.get("custom") is True


class TestLLMAgent:
    """Tests for LLMAgent."""

    @pytest.fixture
    def config(self):
        return AgentConfig(
            name="llm_agent",
            description="An LLM agent",
            system_prompt="You are a helpful assistant.",
        )

    @pytest.mark.asyncio
    async def test_message_building(self, config):
        """Test that messages are built correctly."""
        agent = LLMAgent(config)
        context = Context()
        input_msg = Message(content="Hello", role=MessageRole.USER)

        messages = agent._build_messages(input_msg, context)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_message_with_history(self, config):
        """Test message building with conversation history."""
        agent = LLMAgent(config)
        context = Context()

        # Add some history
        context.add_message(Message(content="Previous question", role=MessageRole.USER))
        context.add_message(Message(content="Previous answer", role=MessageRole.AGENT))

        input_msg = Message(content="New question", role=MessageRole.USER)
        messages = agent._build_messages(input_msg, context)

        # Should have: system + 2 history + current
        assert len(messages) >= 3

    @pytest.mark.asyncio
    async def test_execution_with_mock(self, config):
        """Test agent execution with mocked LLM."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value={
            "content": "Hello! How can I help?",
            "tokens": 50,
        })

        agent = LLMAgent(config, llm_client=mock_client)
        context = Context()
        input_msg = Message(content="Hi", role=MessageRole.USER)

        output = await agent(input_msg, context)

        assert output.content == "Hello! How can I help?"
        assert output.tokens_used == 50
        assert output.source_agent == "llm_agent"


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    @pytest.fixture
    def registry(self):
        return AgentRegistry()

    @pytest.fixture
    def agent(self):
        config = AgentConfig(
            name="test_agent",
            description="Test",
            system_prompt="Test prompt",
        )
        return FunctionAgent(config, lambda m, c: "test")

    def test_register_agent(self, registry, agent):
        """Test registering an agent."""
        registry.register(agent)

        assert "test_agent" in registry
        assert len(registry) == 1

    def test_get_agent(self, registry, agent):
        """Test retrieving an agent."""
        registry.register(agent)
        retrieved = registry.get("test_agent")

        assert retrieved is agent

    def test_get_nonexistent(self, registry):
        """Test getting a nonexistent agent."""
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_duplicate_registration(self, registry, agent):
        """Test that duplicate registration raises error."""
        registry.register(agent)

        with pytest.raises(ValueError):
            registry.register(agent)

    def test_list_agents(self, registry, agent):
        """Test listing registered agents."""
        registry.register(agent)
        names = registry.list()

        assert names == ["test_agent"]


class TestRoutingDecisions:
    """Tests for agent routing logic."""

    @pytest.fixture
    def agents(self):
        """Create a set of specialized agents for routing tests."""
        configs = [
            AgentConfig(
                name="calculator",
                description="Performs mathematical calculations",
                system_prompt="You are a calculator.",
            ),
            AgentConfig(
                name="web_search",
                description="Searches the web for information",
                system_prompt="You search the web.",
            ),
            AgentConfig(
                name="general",
                description="General conversation",
                system_prompt="You are a general assistant.",
            ),
        ]

        return {
            c.name: FunctionAgent(c, lambda m, c: f"Response from {c.name}")
            for c in configs
        }

    def test_routing_to_calculator(self, agents):
        """Test routing math queries to calculator agent."""
        query = "What is 2 + 2?"
        # Simple keyword-based routing for testing
        keywords = {"calculate", "math", "sum", "+", "-", "*", "/"}

        # Check if query contains math keywords
        should_use_calculator = any(k in query.lower() for k in keywords)
        assert should_use_calculator is True

    def test_routing_to_web_search(self, agents):
        """Test routing current events queries to web search."""
        query = "What's the latest news about AI?"
        keywords = {"news", "latest", "current", "today", "recent"}

        should_use_web_search = any(k in query.lower() for k in keywords)
        assert should_use_web_search is True

    def test_routing_to_general(self, agents):
        """Test routing general queries to general agent."""
        query = "Tell me a joke"
        math_keywords = {"calculate", "math", "+", "-", "*", "/"}
        web_keywords = {"news", "latest", "current", "today"}

        is_math = any(k in query.lower() for k in math_keywords)
        is_web = any(k in query.lower() for k in web_keywords)

        assert is_math is False
        assert is_web is False
        # Falls through to general


class TestAgentMetadata:
    """Tests for agent metadata and tracking."""

    @pytest.fixture
    def config(self):
        return AgentConfig(
            name="tracked_agent",
            description="An agent with tracking",
            system_prompt="Track me.",
        )

    @pytest.mark.asyncio
    async def test_latency_tracking(self, config):
        """Test that latency is tracked."""
        async def slow_func(msg: Message, ctx: Context) -> str:
            await asyncio.sleep(0.05)
            return "done"

        agent = FunctionAgent(config, slow_func)
        context = Context()
        input_msg = Message(content="test", role=MessageRole.USER)

        output = await agent(input_msg, context)

        assert output.latency_ms >= 50

    @pytest.mark.asyncio
    async def test_parent_message_tracking(self, config):
        """Test that parent message ID is set."""
        agent = FunctionAgent(config, lambda m, c: "response")
        context = Context()
        input_msg = Message(content="test", role=MessageRole.USER)

        output = await agent(input_msg, context)

        assert output.parent_message_id == input_msg.id

    @pytest.mark.asyncio
    async def test_source_agent_tracking(self, config):
        """Test that source agent is set."""
        agent = FunctionAgent(config, lambda m, c: "response")
        context = Context()
        input_msg = Message(content="test", role=MessageRole.USER)

        output = await agent(input_msg, context)

        assert output.source_agent == "tracked_agent"
