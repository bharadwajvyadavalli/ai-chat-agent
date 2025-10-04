#!/usr/bin/env python3
"""
MCP Server for AI Chat Agent

This standalone MCP server exposes Calculator and Wikipedia tools from the existing tools.py
to external MCP clients. It wraps the existing functionality without modifying it.

Usage:
    python mcp_server.py
    
    Or integrate with MCP client:
    python -c "from mcp_client import MCPClient; client = MCPClient(); client.connect('stdio://python mcp_server.py')"
"""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

# Import existing tools without modification
from tools import Calculator, Wikipedia


class MCPServer:
    """MCP Server that wraps existing Calculator and Wikipedia tools"""
    
    def __init__(self):
        self.calculator = Calculator()
        self.wikipedia = Wikipedia()
        self.tools = {
            "calculator": {
                "name": "calculator",
                "description": "Perform mathematical calculations and solve equations",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to calculate"
                        }
                    },
                    "required": ["expression"]
                }
            },
            "wikipedia": {
                "name": "wikipedia",
                "description": "Search Wikipedia for information about topics, people, places",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for Wikipedia"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol requests"""
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "ai-chat-agent-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "notifications/initialized":
            # Acknowledge initialization
            return None
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "tools": list(self.tools.values())
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            try:
                if tool_name == "calculator":
                    expression = arguments.get("expression", "")
                    result = self.calculator.execute(expression)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result
                                }
                            ]
                        }
                    }
                
                elif tool_name == "wikipedia":
                    query = arguments.get("query", "")
                    result = self.wikipedia.execute(query)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result
                                }
                            ]
                        }
                    }
                
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Tool '{tool_name}' not found"
                        }
                    }
            
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found"
                }
            }
    
    async def run_stdio(self):
        """Run server using stdio transport"""
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    break
                
                request = json.loads(line.strip())
                response = await self.handle_request(request)
                if response is not None:
                    print(json.dumps(response), flush=True)
                
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)


async def main():
    """Main entry point for standalone MCP server"""
    server = MCPServer()
    
    # Print server info
    print("MCP Server started with tools:", file=sys.stderr)
    for tool in server.tools.values():
        print(f"  - {tool['name']}: {tool['description']}", file=sys.stderr)
    
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
