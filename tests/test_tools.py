"""
Tests for tool implementations.

Tests:
- BaseTool functionality
- WebSearchTool
- SQLQueryTool
- ToolResult structure
"""

import asyncio
import pytest
from pathlib import Path

from orchestrator.tools import BaseTool, ToolResult, WebSearchTool, SQLQueryTool


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_ok_result(self):
        """Test creating a successful result."""
        result = ToolResult.ok(
            data={"key": "value"},
            tool_name="test_tool",
            latency_ms=100.0,
            extra_field="extra",
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.tool_name == "test_tool"
        assert result.latency_ms == 100.0
        assert result.metadata["extra_field"] == "extra"

    def test_fail_result(self):
        """Test creating a failed result."""
        result = ToolResult.fail(
            error="Something went wrong",
            tool_name="test_tool",
            latency_ms=50.0,
        )

        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"
        assert result.tool_name == "test_tool"

    def test_to_dict(self):
        """Test JSON serialization."""
        result = ToolResult.ok(data=[1, 2, 3], tool_name="test")
        data = result.to_dict()

        assert data["success"] is True
        assert data["data"] == [1, 2, 3]
        assert data["tool_name"] == "test"


class DummyTool(BaseTool):
    """A dummy tool for testing BaseTool functionality."""

    def __init__(self, should_fail: bool = False, delay: float = 0.0):
        super().__init__(timeout_seconds=1.0)
        self._should_fail = should_fail
        self._delay = delay

    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "A dummy tool for testing"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Test input"},
            },
            "required": ["input"],
        }

    async def execute(self, input: str = "") -> ToolResult:
        if self._delay > 0:
            await asyncio.sleep(self._delay)

        if self._should_fail:
            raise ValueError("Intentional failure")

        return ToolResult.ok(
            data=f"Processed: {input}",
            tool_name=self.name,
        )


class TestBaseTool:
    """Tests for BaseTool abstract class."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful tool execution."""
        tool = DummyTool()
        result = await tool.run(input="test")

        assert result.success is True
        assert result.data == "Processed: test"
        assert result.tool_name == "dummy_tool"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_failed_execution(self):
        """Test tool execution that raises an error."""
        tool = DummyTool(should_fail=True)
        result = await tool.run(input="test")

        assert result.success is False
        assert "Intentional failure" in result.error
        assert tool._error_count == 1

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test tool timeout handling."""
        tool = DummyTool(delay=2.0)  # Delay longer than timeout
        result = await tool.run(timeout=0.1, input="test")

        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_openai_schema(self):
        """Test OpenAI function calling schema generation."""
        tool = DummyTool()
        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "dummy_tool"
        assert schema["function"]["description"] == "A dummy tool for testing"
        assert "properties" in schema["function"]["parameters"]

    def test_stats_tracking(self):
        """Test execution statistics tracking."""
        tool = DummyTool()

        # Run multiple times
        asyncio.run(tool.run(input="test1"))
        asyncio.run(tool.run(input="test2"))

        stats = tool.get_stats()
        assert stats["call_count"] == 2
        assert stats["total_latency_ms"] > 0
        assert stats["error_count"] == 0


class TestWebSearchTool:
    """Tests for WebSearchTool."""

    def test_initialization(self):
        """Test tool initialization."""
        tool = WebSearchTool(max_results=3)

        assert tool.name == "web_search"
        assert "search" in tool.description.lower()
        assert tool._max_results == 3

    def test_validation_empty_query(self):
        """Test validation rejects empty query."""
        tool = WebSearchTool()
        is_valid, error = tool.validate(query="")

        assert is_valid is False
        assert "empty" in error.lower()

    def test_validation_long_query(self):
        """Test validation rejects overly long query."""
        tool = WebSearchTool()
        is_valid, error = tool.validate(query="x" * 600)

        assert is_valid is False
        assert "long" in error.lower()

    def test_validation_valid_query(self):
        """Test validation accepts valid query."""
        tool = WebSearchTool()
        is_valid, error = tool.validate(query="Python programming")

        assert is_valid is True
        assert error is None

    def test_parameters_schema(self):
        """Test parameter schema is correct."""
        tool = WebSearchTool()
        schema = tool.parameters_schema

        assert "query" in schema["properties"]
        assert "query" in schema["required"]


class TestSQLQueryTool:
    """Tests for SQLQueryTool."""

    @pytest.fixture
    def sample_db(self, tmp_path):
        """Create a sample database for testing."""
        import sqlite3

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
        """)

        cursor.executemany(
            "INSERT INTO products (name, price) VALUES (?, ?)",
            [
                ("Widget", 9.99),
                ("Gadget", 19.99),
                ("Gizmo", 29.99),
            ]
        )

        conn.commit()
        conn.close()

        return db_path

    def test_initialization(self, sample_db):
        """Test tool initialization."""
        tool = SQLQueryTool(db_path=sample_db)

        assert tool.name == "sql_query"
        assert "sql" in tool.description.lower()

    def test_validation_empty_query(self, sample_db):
        """Test validation rejects empty query."""
        tool = SQLQueryTool(db_path=sample_db)
        is_valid, error = tool.validate(query="")

        assert is_valid is False

    def test_validation_dangerous_drop(self, sample_db):
        """Test validation rejects DROP statement."""
        tool = SQLQueryTool(db_path=sample_db)
        is_valid, error = tool.validate(query="DROP TABLE products")

        assert is_valid is False
        assert "forbidden" in error.lower()

    def test_validation_dangerous_delete(self, sample_db):
        """Test validation rejects DELETE statement."""
        tool = SQLQueryTool(db_path=sample_db)
        is_valid, error = tool.validate(query="DELETE FROM products WHERE id = 1")

        assert is_valid is False

    def test_validation_dangerous_insert(self, sample_db):
        """Test validation rejects INSERT statement."""
        tool = SQLQueryTool(db_path=sample_db)
        is_valid, error = tool.validate(query="INSERT INTO products VALUES (4, 'Test', 1.99)")

        assert is_valid is False

    def test_validation_valid_select(self, sample_db):
        """Test validation accepts SELECT statement."""
        tool = SQLQueryTool(db_path=sample_db)
        is_valid, error = tool.validate(query="SELECT * FROM products")

        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_execute_select(self, sample_db):
        """Test executing a SELECT query."""
        tool = SQLQueryTool(db_path=sample_db)
        result = await tool.run(query="SELECT * FROM products ORDER BY id")

        assert result.success is True
        assert len(result.data["rows"]) == 3
        assert result.data["columns"] == ["id", "name", "price"]

    @pytest.mark.asyncio
    async def test_execute_with_where(self, sample_db):
        """Test executing a SELECT with WHERE clause."""
        tool = SQLQueryTool(db_path=sample_db)
        result = await tool.run(query="SELECT name FROM products WHERE price > 10")

        assert result.success is True
        assert len(result.data["rows"]) == 2

    @pytest.mark.asyncio
    async def test_execute_nonexistent_db(self, tmp_path):
        """Test error handling for nonexistent database."""
        tool = SQLQueryTool(db_path=tmp_path / "nonexistent.db")
        result = await tool.run(query="SELECT * FROM products")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_get_schema(self, sample_db):
        """Test getting database schema."""
        tool = SQLQueryTool(db_path=sample_db)
        schema = tool.get_schema()

        assert "products" in schema
        assert any(col["name"] == "name" for col in schema["products"])

    def test_format_results(self, sample_db):
        """Test formatting query results as table."""
        tool = SQLQueryTool(db_path=sample_db)
        result = asyncio.run(tool.run(query="SELECT * FROM products LIMIT 2"))
        formatted = tool.format_results(result)

        assert "Widget" in formatted
        assert "Gadget" in formatted
