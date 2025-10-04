#!/usr/bin/env python3
"""
MCP Integration for AI Chat Agent

This module provides MCP tool integration for the AI chat agent.
It connects to MCP servers and provides a unified interface for tool execution.
"""

import asyncio
import os
import sys
from typing import Dict, List, Optional, Any

# Import MCP client
from mcp_client import MCPClient


class MCPIntegration:
    """MCP tool integration for the AI chat agent"""
    
    def __init__(self):
        self.mcp_enabled = False
        self.mcp_clients = []
        self.available_tools = {}
    
    async def initialize(self) -> bool:
        """
        Initialize MCP integration
        
        Returns:
            bool: True if MCP is working, False otherwise
        """
        try:
            # Load MCP servers from config
            mcp_servers = self._get_mcp_servers()
            
            if not mcp_servers:
                # If no servers configured, use local server
                mcp_servers = ["stdio://python3 mcp_server.py"]
            
            # Connect to each server
            for server_command in mcp_servers:
                client = MCPClient()
                if await client.connect(server_command):
                    self.mcp_clients.append(client)
                    print(f"Connected to MCP server: {server_command}", file=sys.stderr)
                else:
                    print(f"Failed to connect to MCP server: {server_command}", file=sys.stderr)
            
            if self.mcp_clients:
                # Load MCP tools
                await self._load_mcp_tools()
                self.mcp_enabled = True
                return True
            else:
                print("No MCP servers connected", file=sys.stderr)
                return False
        
        except Exception as e:
            print(f"MCP initialization error: {e}", file=sys.stderr)
            return False
    
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names
        
        Returns:
            List of tool names
        """
        return list(self.available_tools.keys())
    
    async def execute_tool(self, tool_name: str, query: str) -> Optional[str]:
        """
        Execute a tool by name with the given query
        
        Args:
            tool_name: Name of the tool to execute
            query: Query/input for the tool
        
        Returns:
            Tool result as string, or None if tool not found
        """
        if tool_name in self.available_tools:
            return await self._execute_mcp_tool(tool_name, query)
        
        return None
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a tool
        
        Args:
            tool_name: Name of the tool
        
        Returns:
            Tool information dict or None
        """
        if tool_name in self.available_tools:
            tool_info = self.available_tools[tool_name]
            return {
                'name': tool_info['tool_name'],
                'type': 'mcp',
                'description': tool_info['info'].get('description', 'MCP tool'),
                'mcp_client': tool_info['client']
            }
        
        return None
    
    async def cleanup(self):
        """Cleanup MCP connections"""
        for client in self.mcp_clients:
            try:
                await client.disconnect()
            except:
                pass
        self.mcp_clients.clear()
    
    def _get_mcp_servers(self) -> List[str]:
        """Get MCP server commands from environment or config"""
        # Check environment variable first
        servers_env = os.getenv('MCP_SERVERS')
        if servers_env:
            return [server.strip() for server in servers_env.split(',')]
        
        # Check config file (if available)
        try:
            import config
            if hasattr(config, 'MCP_SERVERS'):
                return config.MCP_SERVERS
        except:
            pass
        
        return []
    
    async def _load_mcp_tools(self):
        """Load tools from all connected MCP clients"""
        for client in self.mcp_clients:
            try:
                tools = await client.get_tools()
                for tool_name, tool_info in tools.items():
                    # Add MCP tool to available tools
                    self.available_tools[tool_name] = {
                        'client': client,
                        'tool_name': tool_name,
                        'info': tool_info
                    }
            except Exception as e:
                print(f"Error loading tools from client: {e}", file=sys.stderr)
    
    async def _execute_mcp_tool(self, tool_name: str, query: str) -> Optional[str]:
        """Execute an MCP tool"""
        if tool_name not in self.available_tools:
            return None
        
        tool_info = self.available_tools[tool_name]
        client = tool_info['client']
        actual_tool_name = tool_info['tool_name']
        
        # Map query to appropriate arguments based on tool type
        arguments = self._map_query_to_arguments(actual_tool_name, query)
        
        return await client.call_tool(actual_tool_name, arguments)
    
    def _map_query_to_arguments(self, tool_name: str, query: str) -> Dict[str, str]:
        """Map query string to tool arguments"""
        if tool_name == 'calculator':
            return {'expression': query}
        elif tool_name == 'wikipedia':
            return {'query': query}
        else:
            # Generic mapping - try 'query' first, then 'expression'
            return {'query': query}
    


# Global instance for easy access
_mcp_integration = MCPIntegration()


async def initialize_mcp() -> bool:
    """Initialize MCP integration"""
    return await _mcp_integration.initialize()


def get_mcp_integration() -> MCPIntegration:
    """Get the global MCP integration instance"""
    return _mcp_integration


# Convenience functions
async def get_available_tools() -> List[str]:
    """Get list of available tool names"""
    return _mcp_integration.get_available_tools()


async def execute_tool(tool_name: str, query: str) -> Optional[str]:
    """Execute a tool by name"""
    return await _mcp_integration.execute_tool(tool_name, query)


async def cleanup_mcp():
    """Cleanup MCP connections"""
    await _mcp_integration.cleanup()


if __name__ == "__main__":
    # Test the integration
    async def test_integration():
        integration = MCPIntegration()
        
        if await integration.initialize():
            print("MCP integration initialized successfully")
            tools = integration.get_available_tools()
            print(f"Available tools: {tools}")
            
            # Test calculator
            result = await integration.execute_tool('calculator', '2 + 2')
            print(f"Calculator result: {result}")
            
            # Test wikipedia
            result = await integration.execute_tool('wikipedia', 'Python programming')
            print(f"Wikipedia result: {result}")
            
            await integration.cleanup()
        else:
            print("MCP integration failed to initialize")
    
    asyncio.run(test_integration())
