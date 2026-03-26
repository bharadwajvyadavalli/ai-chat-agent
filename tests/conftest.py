"""
Pytest configuration and shared fixtures.
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def sample_db_path(project_root):
    """Get the path to the sample database."""
    return project_root / "data" / "sample.db"


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    import sqlite3

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            value REAL
        )
    """)

    cursor.executemany(
        "INSERT INTO test_table (name, value) VALUES (?, ?)",
        [("item1", 1.0), ("item2", 2.0), ("item3", 3.0)]
    )

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    class MockChoice:
        def __init__(self, content):
            self.message = type('obj', (object,), {
                'content': content,
                'tool_calls': None
            })()
            self.delta = type('obj', (object,), {'content': content})()

    class MockUsage:
        total_tokens = 100
        prompt_tokens = 60
        completion_tokens = 40

    class MockResponse:
        def __init__(self, content="Test response"):
            self.choices = [MockChoice(content)]
            self.usage = MockUsage()

    return MockResponse


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    from orchestrator import Message, MessageRole

    return [
        Message(content="Hello", role=MessageRole.USER),
        Message(content="Hi there!", role=MessageRole.AGENT),
        Message(content="How are you?", role=MessageRole.USER),
    ]


@pytest.fixture
def mock_embedding_fn():
    """Create a deterministic mock embedding function."""
    import hashlib

    def embed(text: str) -> list[float]:
        h = hashlib.md5(text.encode()).digest()
        return [b / 255.0 for b in h][:16]

    return embed


# Skip markers for tests that require specific conditions
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "requires_openai: mark test as requiring OpenAI API"
    )


def pytest_collection_modifyitems(config, items):
    """Skip tests based on markers and environment."""
    skip_slow = pytest.mark.skip(reason="slow tests skipped by default")
    skip_integration = pytest.mark.skip(reason="integration tests skipped by default")
    skip_openai = pytest.mark.skip(reason="requires OPENAI_API_KEY")

    for item in items:
        if "slow" in item.keywords and not config.getoption("--runslow", default=False):
            item.add_marker(skip_slow)
        if "integration" in item.keywords and not config.getoption("--runintegration", default=False):
            item.add_marker(skip_integration)
        if "requires_openai" in item.keywords and not os.getenv("OPENAI_API_KEY"):
            item.add_marker(skip_openai)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow tests"
    )
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="run integration tests"
    )
