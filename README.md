# 🤖 AI Chat Agent with MCP Integration

An intelligent AI agent powered by OpenAI GPT-4 that automatically routes queries to appropriate tools (Calculator, Wikipedia) using the Model Context Protocol (MCP) for extensible tool integration.

## Features

- **Smart Tool Routing**: Automatically detects when to use Calculator, Wikipedia, both, or neither
- **MCP Architecture**: Modular, extensible tool system using Model Context Protocol
- **Persistent Storage**: All conversations saved locally in SQLite
- **Dual Interface**: Console CLI and Web UI (Flask)
- **Email Summaries**: Send conversation history via email

## Architecture

The system uses a layered MCP-based architecture:

- **User Interface**: Console mode or Web UI (Flask on port 5000)
- **AI Agent Core** (`agent.py`): GPT-4 integration, smart routing, context management
- **MCP Client** (`mcp_client.py`): Connects to MCP servers, handles tool discovery
- **Tool Layer**: Built-in tools (Calculator, Wikipedia) via MCP servers
- **Storage** (`storage.py`): SQLite database for conversation history

MCP enables modular tool integration—add new tools without modifying core code.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```env
OPENAI_API_KEY=your_key_here

# Optional: Email configuration
GMAIL_EMAIL=your_email@gmail.com
GMAIL_PASSWORD=your_app_password

# Optional: MCP configuration
MCP_ENABLED=true
MCP_SERVERS="stdio://python3 mcp_server.py"
```

### 3. Run

```bash
# Console mode
python3 main.py

# Web mode
python3 main.py web
```

Open http://localhost:5000 for web interface.

## Usage Examples

```
You: What is 156 * 23?
Agent: 156 multiplied by 23 equals 3,588.
[Tools: calculator]

You: Who was Albert Einstein?
Agent: Albert Einstein was a German-born theoretical physicist...
[Tools: wikipedia]

You: Calculate the square of the year Einstein was born
Agent: Einstein was born in 1879, and 1879² = 3,531,641.
[Tools: wikipedia, calculator]
```

## Console Commands

- Type your message to chat
- `email` - Send last 5 messages to email
- `quit` - Exit

## Project Structure

```
ai-chat-agent/
├── main.py               # Entry point
├── agent.py              # AI agent with GPT-4 integration
├── tools.py              # Built-in Calculator and Wikipedia tools
├── mcp_server.py         # MCP server exposing tools
├── mcp_client.py         # MCP client for server connections
├── mcp_integration.py    # MCP integration layer
├── storage.py            # SQLite conversation storage
├── interface.py          # Console and Flask web UI
├── config.py             # Configuration management
└── requirements.txt      # Python dependencies
```

## Adding New Tools

### Option 1: Extend `mcp_server.py`

Add tool definition and handler in the existing MCP server.

### Option 2: Create New MCP Server

Create a standalone MCP server and register it:

```env
MCP_SERVERS="stdio://python3 mcp_server.py,stdio://python3 custom_server.py"
```

See the MCP protocol specification for details on implementing servers.

## Testing

```bash
# Test MCP server
python3 mcp_server.py

# Test full system
python3 main.py
```

## License

MIT
