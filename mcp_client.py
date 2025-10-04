#!/usr/bin/env python3
"""
MCP Client for AI Chat Agent

This module provides a simple interface to connect to MCP servers and use their tools.
It's designed to be self-contained and not require modifications to existing files.

Usage:
    client = MCPClient()
    await client.connect("stdio://python3 mcp_server.py")
    tools = await client.get_tools()
    result = await client.call_tool("calculator", {"expression": "2 + 2"})
"""

import asyncio
import json
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union


class MCPClient:
    """MCP Client for connecting to MCP servers"""
    
    def __init__(self):
        self.connected = False
        self.tools = {}
        self.process = None
        self.request_id = 0
    
    async def connect(self, server_command: str) -> bool:
        """
        Connect to an MCP server
        
        Args:
            server_command: Command to start the server (e.g., "stdio://python3 mcp_server.py")
        
        Returns:
            bool: True if connection successful
        """
        try:
            if server_command.startswith("stdio://"):
                # Extract the actual command
                command = server_command[8:]  # Remove "stdio://"
                self.process = await asyncio.create_subprocess_exec(
                    *command.split(),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Send initialize request
                init_request = {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "clientInfo": {
                            "name": "ai-chat-agent",
                            "version": "1.0.0"
                        }
                    }
                }
                
                await self._send_request(init_request)
                response = await self._read_response()
                
                if response and "result" in response:
                    # Send initialized notification
                    initialized = {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized"
                    }
                    await self._send_request(initialized)
                    
                    # Load available tools
                    await self._load_tools()
                    self.connected = True
                    return True
            
            return False
            
        except Exception as e:
            print(f"MCP connection error: {e}", file=sys.stderr)
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None
        self.connected = False
        self.tools = {}
    
    async def get_tools(self) -> Dict[str, Dict]:
        """
        Get available tools from the server
        
        Returns:
            Dict mapping tool names to tool definitions
        """
        if not self.connected:
            return {}
        
        return self.tools.copy()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """
        Call a tool on the MCP server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool
        
        Returns:
            Tool result as string, or None if error
        """
        if not self.connected or tool_name not in self.tools:
            return None
        
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            await self._send_request(request)
            response = await self._read_response()
            
            if response and "result" in response:
                content = response["result"].get("content", [])
                if content and content[0].get("type") == "text":
                    return content[0].get("text", "")
            
            elif response and "error" in response:
                error_msg = response["error"].get("message", "Unknown error")
                return f"Tool error: {error_msg}"
            
            return None
            
        except Exception as e:
            return f"Communication error: {e}"
    
    async def _load_tools(self):
        """Load available tools from the server"""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list"
        }
        
        try:
            await self._send_request(request)
            response = await self._read_response()
            
            if response and "result" in response:
                tools_list = response["result"].get("tools", [])
                self.tools = {tool["name"]: tool for tool in tools_list}
            
        except Exception as e:
            print(f"Error loading tools: {e}", file=sys.stderr)
    
    async def _send_request(self, request: Dict[str, Any]):
        """Send a request to the MCP server"""
        if self.process and self.process.stdin:
            message = json.dumps(request) + "\n"
            self.process.stdin.write(message.encode())
            await self.process.stdin.drain()
    
    async def _read_response(self) -> Optional[Dict[str, Any]]:
        """Read a response from the MCP server"""
        if self.process and self.process.stdout:
            line = await self.process.stdout.readline()
            if line:
                return json.loads(line.decode().strip())
        return None
    
    def _next_id(self) -> int:
        """Get next request ID"""
        self.request_id += 1
        return self.request_id
    
    def __del__(self):
        """Cleanup on deletion"""
        if self.process and self.connected:
            try:
                asyncio.create_task(self.disconnect())
            except:
                pass


# Convenience functions for easier integration
async def connect_to_server(server_command: str) -> Optional[MCPClient]:
    """
    Convenience function to connect to an MCP server
    
    Args:
        server_command: Server command (e.g., "stdio://python3 mcp_server.py")
    
    Returns:
        Connected MCPClient instance or None if failed
    """
    client = MCPClient()
    success = await client.connect(server_command)
    return client if success else None


async def quick_call(server_command: str, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
    """
    Quick function to call a tool on a server
    
    Args:
        server_command: Server command
        tool_name: Tool to call
        arguments: Tool arguments
    
    Returns:
        Tool result or None if failed
    """
    client = await connect_to_server(server_command)
    if client:
        try:
            result = await client.call_tool(tool_name, arguments)
            return result
        finally:
            await client.disconnect()
    return None


if __name__ == "__main__":
    # Example usage
    async def test_client():
        client = MCPClient()
        
        # Connect to local server
        if await client.connect("stdio://python3 mcp_server.py"):
            print("Connected to MCP server")
            
            # List tools
            tools = await client.get_tools()
            print("Available tools:", list(tools.keys()))
            
            # Test calculator
            result = await client.call_tool("calculator", {"expression": "2 + 2 * 3"})
            print(f"Calculator result: {result}")
            
            # Test wikipedia
            result = await client.call_tool("wikipedia", {"query": "Python programming"})
            print(f"Wikipedia result: {result}")
            
            await client.disconnect()
        else:
            print("Failed to connect to MCP server")
    
    asyncio.run(test_client())
