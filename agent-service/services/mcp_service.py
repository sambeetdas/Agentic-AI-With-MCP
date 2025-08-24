import os
from langchain_mcp_adapters.client import MultiServerMCPClient

class MCPService:

    async def get_all_tools(self):
        mcp_client = MultiServerMCPClient({
        "tool-repository": {
            "transport": "streamable_http",
            "url": os.getenv('MCP_URL'),
        }
        })

        all_tools = await mcp_client.get_tools()
        return all_tools

