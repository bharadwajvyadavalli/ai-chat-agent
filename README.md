# 🤖 AI Chat Agent with MCP Integration

Smart AI agent that automatically uses Calculator and Wikipedia tools based on your questions, powered by the Model Context Protocol (MCP) for modular and extensible tool integration.

## Features

- **Smart Tool Routing**: Auto-detects when to use Calculator, Wikipedia, both, or neither
- **MCP Architecture**: Modular tool system using Model Context Protocol
- **Persistent Storage**: All conversations saved locally
- **Email Summaries**: Send conversation history via email
- **Dual Interface**: Console and Web UI
- **Extensible**: Easy to add new tools via MCP servers

## 🏗️ Architecture

The system uses a modular, MCP-based architecture:

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────┐
│   Agent     │───▶│ MCP Integration │───▶│ MCP Client   │
│ (modified)  │    │   (simplified)  │    │              │
└─────────────┘    └─────────────────┘    └──────────────┘
       │                   │                       │
       ▼                   ▼                       ▼
┌─────────────┐    ┌─────────────────┐    ┌──────────────┐
│   Storage   │    │ MCP Tool        │    │ External     │
│   & LLM     │    │ Interface       │ MCP Servers  │
│             │    │                 │    │              │
└─────────────┘    └─────────────────┘    └──────────────┘
```

### Components

- **User Layer**: Console and Web browser interfaces
- **Interface Layer**: Flask web UI and terminal-based console  
- **Application Core**: Main orchestration, configuration management, and AI agent logic
- **MCP Integration**: Connects to MCP servers and provides tool interface
- **MCP Servers**: Standalone servers providing Calculator and Wikipedia tools
- **Storage Layer**: Persistent chat history with local database
- **External Services**: Integration with OpenAI API, Wikipedia API, and Gmail SMTP

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file:
```bash
OPENAI_API_KEY=your_key_here
GMAIL_EMAIL=your_email@gmail.com          # Optional
GMAIL_PASSWORD=your_gmail_app_password    # Optional
```

### 3. Run the System
```bash
# Console mode
python3 main.py

# Web mode  
python3 main.py web
```

The system will automatically:
- Connect to the local MCP server (`mcp_server.py`)
- Load available MCP tools (Calculator and Wikipedia)
- Route requests to MCP tools

## Examples

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

## Project Structure

```
ai-chat-agent/
├── main.py              # Entry point
├── agent.py             # Agent + LLM integration
├── tools.py             # Calculator + Wikipedia implementations
├── mcp_server.py         # MCP server exposing tools
├── mcp_client.py         # MCP client for connecting to servers
├── mcp_integration.py    # MCP tool integration
├── storage.py           # Message persistence
├── interface.py         # Console + Web UI
├── config.py            # Configuration
└── requirements.txt
```

## MCP Configuration

### Environment Variables

```bash
# Disable MCP integration (if needed)
MCP_ENABLED=false

# Specify MCP servers (comma-separated)
MCP_SERVERS="stdio://python3 mcp_server.py,stdio://python3 /path/to/other/server.py"
```

### Configuration File

Edit `config.py` to add MCP servers:

```python
# Example MCP server configurations
MCP_SERVERS = [
    "stdio://python3 mcp_server.py",
    "stdio://python3 /path/to/external/mcp/server.py",
    "stdio://node /path/to/node/mcp/server.js"
]
```

## Testing

### Test MCP Server Standalone
```bash
python3 mcp_server.py
```

### Test MCP Client
```bash
python3 mcp_client.py
```

### Test MCP Integration
```bash
python3 mcp_integration.py
```

### Test Full System
```bash
# With MCP enabled (default)
python3 main.py

# Without MCP (if disabled)
MCP_ENABLED=false python3 main.py
```

## Commands (Console Mode)

- Type your message to chat
- `email` - Send last 5 messages to email
- `quit` - Exit

## Web Interface

Run `python3 main.py web` and open http://localhost:5000

## Development

### Adding New MCP Tools

1. **In MCP Server** (`mcp_server.py`):
   ```python
   # Add tool to self.tools dictionary
   self.tools["new_tool"] = {
       "name": "new_tool",
       "description": "Description of new tool",
       "inputSchema": {...}
   }
   
   # Add handler in handle_request method
   elif tool_name == "new_tool":
       result = self.new_tool.execute(arguments.get("query", ""))
       return {...}
   ```

2. **In Agent** (`agent.py`):
   ```python
   # Add tool name to SYSTEM_PROMPT
   SYSTEM_PROMPT = """...with access to Calculator, Wikipedia, and new_tool tools..."""
   ```

### Connecting External MCP Servers

```bash
# Node.js MCP server
MCP_SERVERS="stdio://node /path/to/server.js"

# Python MCP server with arguments
MCP_SERVERS="stdio://python3 /path/to/server.py --port 8080"

# Multiple servers
MCP_SERVERS="stdio://python3 mcp_server.py,stdio://node external_server.js"
```

## Troubleshooting

### MCP Not Working

1. **Check Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Test Server**:
   ```bash
   python3 mcp_server.py
   ```

3. **Test Integration**:
   ```bash
   python3 mcp_integration.py
   ```

4. **Check Logs**: Look for error messages in console output

### Performance Issues

- MCP adds minimal overhead (~10ms per request)
- If issues occur, you can disable MCP: `export MCP_ENABLED=false`

### Connection Issues

- Ensure MCP servers are accessible
- Check server commands in `MCP_SERVERS`
- Verify server dependencies are installed

## Benefits of MCP Architecture

- **Extensibility**: Add new tools without modifying core code
- **Interoperability**: Connect to external MCP servers
- **Modularity**: Tools can be developed and deployed independently
- **Clean Architecture**: Clear separation between agent and tools
- **Scalability**: Multiple MCP servers can provide different tool sets

## Limitations

- **Async Overhead**: MCP tools run in async context
- **Network Dependency**: MCP servers must be available
- **Protocol Complexity**: MCP protocol adds some complexity
- **Debugging**: MCP errors may be harder to debug

## Future Enhancements

- **Tool Discovery**: Automatic discovery of MCP servers
- **Tool Caching**: Cache MCP tool results
- **Load Balancing**: Distribute requests across multiple MCP servers
- **Tool Metrics**: Monitor MCP tool performance
- **GUI Integration**: MCP tool configuration in web interface

## License

MIT