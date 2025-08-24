import logging
import asyncio


from services.agent_service import AgentService
from services.mcp_service import MCPService
from services.llm_service import llm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def process(input: str):

    mcp = MCPService()
    all_tools = await mcp.get_all_tools()

    service = AgentService(all_tools, llm)
    result = await service.agent_invoke(input)
    return result

if __name__ == "__main__":
    input = "what is the combined headcount of Microsoft and Accenture?"
    asyncio.run(process(input))