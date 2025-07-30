import asyncio
from typing import Optional
import json
from fastmcp import Client


class MCP:
    def __init__(self):
        # Initialize FastMCP client
        self.client: Optional[Client] = None
        self.messages = []

    async def connect_to_server(self):
        """
        Connect to MCP server using FastMCP HTTP streaming
        """
        with open('mcp_config.json') as f:
            mcp_servers = json.load(f)['mcpServers']

        try:
            # Initialize FastMCP client with HTTP streaming transport
            self.client = Client("http://localhost:8000/mcp/")
            
            # Use async context manager for proper connection
            await self.client.__aenter__()
            
            # List available tools
            tools = await self.client.list_tools()
            
            print("\nConnected to FastMCP server with tools:", [tool.name for tool in tools])
        except Exception as e:
            print(f"Error connecting to FastMCP server: {e}")
            self.client = None

    async def close(self):
        """
        Close connections
        """
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception:
                pass



    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect_to_server()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


async def main():
    async with MCP():
        # Keep the connection alive for testing
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())