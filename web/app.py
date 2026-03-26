"""
Flask Web Application: Chat interface with streaming support.

Features:
- SSE streaming for real-time token display
- Tool usage visualization
- Memory retrieval display
- Conversation management
- Dark/light theme toggle
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Generator

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

logger = logging.getLogger(__name__)


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    # Configuration
    app.config.update(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-secret-key"),
        DEBUG=os.getenv("FLASK_DEBUG", "0") == "1",
    )
    if config:
        app.config.update(config)

    # Initialize components
    from .chat_service import ChatService
    chat_service = ChatService()
    app.chat_service = chat_service

    # Routes
    register_routes(app)

    return app


def register_routes(app: Flask) -> None:
    """Register all routes."""

    @app.route("/")
    def index():
        """Main chat interface."""
        return render_template("chat.html")

    @app.route("/api/chat", methods=["POST"])
    def chat():
        """Non-streaming chat endpoint."""
        data = request.json
        message = data.get("message", "")
        conversation_id = data.get("conversation_id")

        if not message:
            return jsonify({"error": "Message required"}), 400

        try:
            result = asyncio.run(
                app.chat_service.process_message(message, conversation_id)
            )
            return jsonify(result)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/stream", methods=["POST"])
    def stream():
        """SSE streaming endpoint for real-time responses."""
        data = request.json
        message = data.get("message", "")
        conversation_id = data.get("conversation_id")

        if not message:
            return jsonify({"error": "Message required"}), 400

        def generate() -> Generator[str, None, None]:
            """Generate SSE events."""
            try:
                # Use async generator in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def stream_response():
                    async for event in app.chat_service.stream_message(message, conversation_id):
                        yield f"data: {json.dumps(event)}\n\n"

                # Run async generator
                gen = stream_response()
                while True:
                    try:
                        event = loop.run_until_complete(gen.__anext__())
                        yield event
                    except StopAsyncIteration:
                        break

                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                loop.close()

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.route("/api/conversations", methods=["GET"])
    def list_conversations():
        """List all conversations."""
        conversations = app.chat_service.list_conversations()
        return jsonify({"conversations": conversations})

    @app.route("/api/conversations", methods=["POST"])
    def create_conversation():
        """Create a new conversation."""
        data = request.json or {}
        title = data.get("title", f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        conversation = app.chat_service.create_conversation(title)
        return jsonify(conversation)

    @app.route("/api/conversations/<conversation_id>", methods=["GET"])
    def get_conversation(conversation_id: str):
        """Get a specific conversation with history."""
        conversation = app.chat_service.get_conversation(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify(conversation)

    @app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
    def delete_conversation(conversation_id: str):
        """Delete a conversation."""
        success = app.chat_service.delete_conversation(conversation_id)
        if not success:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify({"success": True})

    @app.route("/api/tools", methods=["GET"])
    def list_tools():
        """List available tools."""
        tools = app.chat_service.list_tools()
        return jsonify({"tools": tools})

    @app.route("/api/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
        })

    @app.route("/api/metrics", methods=["GET"])
    def metrics():
        """Metrics endpoint for observability."""
        from orchestrator.observability import get_metrics

        metrics_data = get_metrics().get_metrics_dict()
        metrics_data["timestamp"] = datetime.utcnow().isoformat() + "Z"

        return jsonify(metrics_data)


# Run directly for development
if __name__ == "__main__":
    app = create_app()
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=True,
    )
