"""
Chat Service: Handles chat logic, tool routing, and streaming.

This service bridges the web interface with the orchestration framework.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator

import openai

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single chat message."""
    id: str
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class Conversation:
    """A conversation with history."""
    id: str
    title: str
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": len(self.messages),
        }


class ChatService:
    """
    Service for handling chat interactions.

    Features:
    - OpenAI integration with streaming
    - Tool routing and execution
    - Memory retrieval
    - Conversation management
    """

    def __init__(self):
        self._conversations: dict[str, Conversation] = {}
        self._client = openai.AsyncOpenAI()
        self._tools = self._init_tools()
        self._memory_retriever = self._init_memory()

    def _init_tools(self) -> dict:
        """Initialize available tools."""
        from orchestrator.tools import WebSearchTool, SQLQueryTool
        from pathlib import Path

        tools = {}

        # Web search tool
        tools["web_search"] = WebSearchTool()

        # SQL query tool (if sample.db exists)
        db_path = Path("data/sample.db")
        if db_path.exists():
            tools["sql_query"] = SQLQueryTool(db_path)

        return tools

    def _init_memory(self):
        """Initialize memory retriever."""
        try:
            from orchestrator.memory import MemoryRetriever, MemoryConfig
            config = MemoryConfig.from_env()
            return MemoryRetriever(config)
        except Exception as e:
            logger.warning(f"Memory retriever not available: {e}")
            return None

    def _get_tool_schemas(self) -> list[dict]:
        """Get OpenAI function schemas for tools."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    async def process_message(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> dict:
        """
        Process a chat message (non-streaming).

        Args:
            message: User message
            conversation_id: Optional conversation ID

        Returns:
            Response dict with assistant message and metadata
        """
        # Get or create conversation
        conv = self._get_or_create_conversation(conversation_id)

        # Add user message
        user_msg = Message(
            id=str(uuid.uuid4()),
            role="user",
            content=message,
            timestamp=datetime.utcnow(),
        )
        conv.messages.append(user_msg)

        # Build messages for LLM
        messages = self._build_llm_messages(conv, message)

        # Call LLM
        start_time = time.time()
        response = await self._client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            messages=messages,
            tools=self._get_tool_schemas() if self._tools else None,
            temperature=0.7,
        )

        # Process response
        assistant_content = response.choices[0].message.content or ""
        tool_calls = response.choices[0].message.tool_calls

        # Handle tool calls if any
        tool_results = []
        if tool_calls:
            for tool_call in tool_calls:
                result = await self._execute_tool(
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments),
                )
                tool_results.append({
                    "tool": tool_call.function.name,
                    "result": result,
                })

            # Get final response with tool results
            messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})
            for i, tool_call in enumerate(tool_calls):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_results[i]["result"]),
                })

            final_response = await self._client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                messages=messages,
                temperature=0.7,
            )
            assistant_content = final_response.choices[0].message.content or ""

        latency_ms = (time.time() - start_time) * 1000

        # Add assistant message
        assistant_msg = Message(
            id=str(uuid.uuid4()),
            role="assistant",
            content=assistant_content,
            timestamp=datetime.utcnow(),
            metadata={
                "latency_ms": latency_ms,
                "tool_calls": tool_results,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
            },
        )
        conv.messages.append(assistant_msg)
        conv.updated_at = datetime.utcnow()

        return {
            "message": assistant_msg.to_dict(),
            "conversation_id": conv.id,
            "tool_calls": tool_results,
        }

    async def stream_message(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream a chat response using SSE.

        Yields events:
        - {"type": "start", "conversation_id": "..."}
        - {"type": "memory", "memories": [...]}
        - {"type": "tool_start", "tool": "...", "args": {...}}
        - {"type": "tool_end", "tool": "...", "result": {...}}
        - {"type": "token", "content": "..."}
        - {"type": "end", "message": {...}}
        """
        # Get or create conversation
        conv = self._get_or_create_conversation(conversation_id)

        yield {"type": "start", "conversation_id": conv.id}

        # Add user message
        user_msg = Message(
            id=str(uuid.uuid4()),
            role="user",
            content=message,
            timestamp=datetime.utcnow(),
        )
        conv.messages.append(user_msg)

        # Retrieve relevant memories
        memories_retrieved = []
        if self._memory_retriever:
            try:
                result = await self._memory_retriever.retrieve(message)
                memories_retrieved = [m.to_dict() for m in result.memories]
                if memories_retrieved:
                    yield {
                        "type": "memory",
                        "memories": memories_retrieved,
                        "context": result.context,
                    }
            except Exception as e:
                logger.warning(f"Memory retrieval failed: {e}")

        # Build messages
        messages = self._build_llm_messages(conv, message)

        start_time = time.time()
        full_content = ""
        tool_results = []

        try:
            # First call - check for tool use
            response = await self._client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                messages=messages,
                tools=self._get_tool_schemas() if self._tools else None,
                temperature=0.7,
                stream=False,  # First call non-streaming to check tools
            )

            tool_calls = response.choices[0].message.tool_calls
            initial_content = response.choices[0].message.content or ""

            # Handle tool calls
            if tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": initial_content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in tool_calls
                    ],
                })

                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    yield {
                        "type": "tool_start",
                        "tool": tool_name,
                        "args": tool_args,
                    }

                    result = await self._execute_tool(tool_name, tool_args)
                    tool_results.append({"tool": tool_name, "result": result})

                    yield {
                        "type": "tool_end",
                        "tool": tool_name,
                        "result": result,
                    }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    })

                # Stream final response with tool results
                stream = await self._client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4"),
                    messages=messages,
                    temperature=0.7,
                    stream=True,
                )
            else:
                # No tools, stream the response
                stream = await self._client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4"),
                    messages=messages,
                    temperature=0.7,
                    stream=True,
                )

            # Stream tokens
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_content += token
                    yield {"type": "token", "content": token}

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {"type": "error", "error": str(e)}
            return

        latency_ms = (time.time() - start_time) * 1000

        # Add assistant message
        assistant_msg = Message(
            id=str(uuid.uuid4()),
            role="assistant",
            content=full_content,
            timestamp=datetime.utcnow(),
            metadata={
                "latency_ms": latency_ms,
                "tool_calls": tool_results,
                "memories_retrieved": len(memories_retrieved),
            },
        )
        conv.messages.append(assistant_msg)
        conv.updated_at = datetime.utcnow()

        # Store conversation turn in memory
        if self._memory_retriever:
            try:
                await self._memory_retriever.store_conversation_turn(
                    message, full_content,
                    metadata={"conversation_id": conv.id}
                )
            except Exception as e:
                logger.warning(f"Failed to store conversation: {e}")

        yield {
            "type": "end",
            "message": assistant_msg.to_dict(),
        }

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """Execute a tool and return the result."""
        if tool_name not in self._tools:
            return {"error": f"Unknown tool: {tool_name}"}

        tool = self._tools[tool_name]
        try:
            result = await tool.run(**args)
            return result.to_dict()
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    def _build_llm_messages(self, conv: Conversation, current_message: str) -> list[dict]:
        """Build message list for LLM call."""
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(),
            }
        ]

        # Add conversation history (last 10 messages)
        for msg in conv.messages[-10:]:
            if msg.role in ("user", "assistant"):
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return messages

    def _get_system_prompt(self) -> str:
        """Get the system prompt."""
        tool_descriptions = "\n".join(
            f"- {name}: {tool.description}"
            for name, tool in self._tools.items()
        )

        return f"""You are a helpful AI assistant with access to tools.

Available tools:
{tool_descriptions}

When using tools:
1. Use web_search for current events, news, or information that may have changed
2. Use sql_query to query the sample e-commerce database (products, orders, customers)

Always be helpful, accurate, and concise. If you use a tool, explain what you found."""

    def _get_or_create_conversation(self, conversation_id: str | None) -> Conversation:
        """Get existing conversation or create new one."""
        if conversation_id and conversation_id in self._conversations:
            return self._conversations[conversation_id]

        conv = Conversation(
            id=conversation_id or str(uuid.uuid4()),
            title=f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )
        self._conversations[conv.id] = conv
        return conv

    def create_conversation(self, title: str) -> dict:
        """Create a new conversation."""
        conv = Conversation(
            id=str(uuid.uuid4()),
            title=title,
        )
        self._conversations[conv.id] = conv
        return conv.to_dict()

    def get_conversation(self, conversation_id: str) -> dict | None:
        """Get a conversation by ID."""
        conv = self._conversations.get(conversation_id)
        return conv.to_dict() if conv else None

    def list_conversations(self) -> list[dict]:
        """List all conversations."""
        return [
            {
                "id": conv.id,
                "title": conv.title,
                "message_count": len(conv.messages),
                "updated_at": conv.updated_at.isoformat(),
            }
            for conv in sorted(
                self._conversations.values(),
                key=lambda c: c.updated_at,
                reverse=True,
            )
        ]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False

    def list_tools(self) -> list[dict]:
        """List available tools."""
        return [
            {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters_schema,
            }
            for name, tool in self._tools.items()
        ]
