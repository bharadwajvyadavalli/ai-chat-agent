"""
Web interface for the multi-agent orchestration framework.

Provides:
- Flask web application
- SSE streaming chat
- Tool visualization
- Conversation management
"""

from .app import create_app
from .chat_service import ChatService

__all__ = ["create_app", "ChatService"]
