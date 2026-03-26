"""
SQL Query Tool: Execute read-only SQL queries on a database.

Features:
- Read-only execution (prevents data modification)
- Query validation (blocks dangerous patterns)
- Result formatting
- Query timeout
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .base import BaseTool, ToolResult


# Patterns that indicate potentially dangerous SQL
DANGEROUS_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bTRUNCATE\b",
    r"\bREPLACE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bPRAGMA\b(?!\s*table_info)",  # Allow table_info queries
    r";\s*--",  # Comment after semicolon (potential injection)
    r"UNION\s+ALL\s+SELECT.*UNION",  # Multiple unions (potential injection)
]


class SQLQueryTool(BaseTool):
    """
    Execute read-only SQL queries on a SQLite database.

    Security features:
    - Read-only connection mode
    - Query validation (blocks INSERT, UPDATE, DELETE, etc.)
    - Timeout enforcement
    - Result size limits
    """

    def __init__(
        self,
        db_path: str | Path,
        max_rows: int = 100,
        timeout_seconds: float = 10.0,
    ):
        """
        Initialize SQL query tool.

        Args:
            db_path: Path to SQLite database file
            max_rows: Maximum rows to return
            timeout_seconds: Query timeout
        """
        super().__init__(timeout_seconds=timeout_seconds)
        self._db_path = Path(db_path)
        self._max_rows = max_rows

    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return (
            "Execute a read-only SQL query on the sample database. "
            "Use this to query data about products, orders, and customers. "
            "Only SELECT queries are allowed."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to execute",
                },
            },
            "required": ["query"],
        }

    def validate(self, **kwargs) -> tuple[bool, str | None]:
        query = kwargs.get("query", "").strip()

        if not query:
            return False, "Query cannot be empty"

        # Check for dangerous patterns
        query_upper = query.upper()
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, query_upper, re.IGNORECASE):
                return False, f"Query contains forbidden pattern. Only SELECT queries allowed."

        # Must start with SELECT or WITH (for CTEs)
        if not query_upper.startswith(("SELECT", "WITH")):
            return False, "Query must be a SELECT statement"

        return True, None

    def get_schema(self) -> dict:
        """Get the database schema."""
        if not self._db_path.exists():
            return {"error": "Database not found"}

        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [
                    {
                        "name": row[1],
                        "type": row[2],
                        "nullable": not row[3],
                        "primary_key": bool(row[5]),
                    }
                    for row in cursor.fetchall()
                ]
                schema[table] = columns

            conn.close()
            return schema

        except Exception as e:
            return {"error": str(e)}

    async def execute(self, query: str) -> ToolResult:
        """
        Execute a SQL query.

        Args:
            query: SQL SELECT query

        Returns:
            ToolResult with query results
        """
        if not self._db_path.exists():
            return ToolResult.fail(
                error=f"Database not found: {self._db_path}",
                tool_name=self.name,
            )

        try:
            # Connect in read-only mode
            conn = sqlite3.connect(
                f"file:{self._db_path}?mode=ro",
                uri=True,
                timeout=self._timeout,
            )
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Execute query
            cursor.execute(query)
            rows = cursor.fetchmany(self._max_rows)

            # Get column names
            columns = [description[0] for description in cursor.description] if cursor.description else []

            # Convert to list of dicts
            results = [dict(row) for row in rows]

            # Check if there are more rows
            has_more = cursor.fetchone() is not None

            conn.close()

            return ToolResult.ok(
                data={
                    "columns": columns,
                    "rows": results,
                    "row_count": len(results),
                    "truncated": has_more,
                },
                tool_name=self.name,
                query=query,
            )

        except sqlite3.Error as e:
            return ToolResult.fail(
                error=f"SQL error: {str(e)}",
                tool_name=self.name,
            )
        except Exception as e:
            return ToolResult.fail(
                error=f"Query failed: {str(e)}",
                tool_name=self.name,
            )

    def format_results(self, result: ToolResult) -> str:
        """Format query results as a table."""
        if not result.success:
            return f"Query failed: {result.error}"

        data = result.data
        if not data["rows"]:
            return "Query returned no results."

        columns = data["columns"]
        rows = data["rows"]

        # Calculate column widths
        widths = {col: len(col) for col in columns}
        for row in rows:
            for col in columns:
                val = str(row.get(col, ""))
                widths[col] = max(widths[col], len(val))

        # Build table
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        separator = "-+-".join("-" * widths[col] for col in columns)

        lines = [header, separator]
        for row in rows:
            line = " | ".join(
                str(row.get(col, "")).ljust(widths[col])
                for col in columns
            )
            lines.append(line)

        if data["truncated"]:
            lines.append(f"\n... (results truncated at {self._max_rows} rows)")

        return "\n".join(lines)
