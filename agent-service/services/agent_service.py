import logging
import asyncio
import json
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
#from langchain_core.pydantic_v1 import BaseModel, Field
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool
from typing import Callable


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- State Definition ---
class State(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    company_name: Optional[str]
    access_token: Optional[str]
    # The 'next' key will be populated by the supervisor
    next: str

class Router(BaseModel):
    """
    Defines the next team to deploy or the final action to take.
    """
    next: str = Field(
        description="Must be one of: 'web_search', 'math' or 'report_generator'.",
    )



class AgentService:
    def __init__(self, all_tools, llm):        
        self.llm = llm
        self.all_tools = all_tools
        self._access_token = None
        def get_token():
            return self._access_token
        
        # Supervisor Chain: This is much cleaner and more direct.
        supervisor_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a master project manager. Your team consists of two specialist teams: web_search and math.
            - web_search: Handles all public web searches get revenue, head count, headquarters, market cap etc (Wikipedia).
            - math: Handles mathematical operations only.

            Based on the user's query and the conversation history, decide which team to deploy next.
            Your response MUST be one of the following exact strings: "web_search", "math", or "report_generator".
            If enough info has been gathered to answer the query, respond with "report_generator".
            """),
            ("placeholder", "{messages}")
        ])
        self.supervisor_chain = supervisor_prompt | self.llm.with_structured_output(Router)

        # Report Generator Chain
        report_generator_prompt = ChatPromptTemplate.from_messages([
             ("system", """
            You are a professional report writer. Your task is to synthesize a final, comprehensive report based on the initial query and all the data collected by the research agents in the conversation history.
            Compile all gathered data into a single, well-structured report.
            """),
             ("placeholder", "{messages}")
        ])
        # We append a new AIMessage to the state so it's clear this is the final report.
        self.report_generator_chain = report_generator_prompt | self.llm

        # --- 2. Create ReAct Agents for Tool-Using Workers ---
        research_tools = [
            self.wrap_authenticated_tool(tool, get_token)
            for tool in self.all_tools if tool.name in ["wiki_crawler"]
        ]

        math_tools = [
            self.wrap_authenticated_tool(tool, get_token)
            for tool in self.all_tools if tool.name in ["add", "subtract", "multiply", "divide", "average"]
        ]

        # These are your specialist agents that need to reason about tools
        self.web_search_agent = create_react_agent(self.llm, tools=research_tools)
        self.math_agent = create_react_agent(self.llm, tools=math_tools)

        # --- 3. Build the Graph ---
        self.graph = self._create_graph()

    def wrap_authenticated_tool(self, mcp_tool, get_token):
        # Check if this is a math tool that doesn't need authentication
        math_tool_names = ["add", "subtract", "multiply", "divide", "average"]
        
        if mcp_tool.name in math_tool_names:
            # For math tools, create a simple wrapper without authentication
            async def _invoke_math(**tool_input):
                return await mcp_tool.ainvoke(tool_input)
            
            return StructuredTool.from_function(
                coroutine=_invoke_math,
                name=mcp_tool.name,
                description=mcp_tool.description or f"Math tool {mcp_tool.name}",
                args_schema=mcp_tool.args_schema
            )
        else:
            # For other tools that need authentication
            async def _invoke(**tool_input):
                token = get_token()
                if not token:
                    raise ValueError("No access token available for tool call")
                
                tool_input["headers"] = {"Authorization": f"Bearer {token}"}
                return await mcp_tool.ainvoke(tool_input)

            return StructuredTool.from_function(
                coroutine=_invoke,
                name=mcp_tool.name,
                description=mcp_tool.description or f"MCP tool {mcp_tool.name}",
                args_schema=mcp_tool.args_schema
            )     

    def _create_graph(self) -> StateGraph:
        """Builds the supervisor-based workflow."""
        workflow = StateGraph(State)

        # Define the nodes
        workflow.add_node("human_login", self.human_login_node)
        workflow.add_node("supervisor", self.supervisor_node)
        workflow.add_node("web_search", self.web_search_node)
        workflow.add_node("math", self.math_node)
        workflow.add_node("report_generator", self.report_generator_node)

        # Build the graph
        workflow.set_entry_point("human_login")
        workflow.add_conditional_edges("supervisor",
            lambda state: state["next"],
            {
                "web_search": "web_search",
                "math": "math",
                "report_generator": "report_generator",
            }
        )
        
        # After the workers are done, they go back to the supervisor for the next decision
        workflow.add_edge("human_login", "supervisor")
        workflow.add_edge("web_search", "supervisor")
        workflow.add_edge("math", "supervisor")
        workflow.add_edge("report_generator", END)
        
        return workflow.compile()

    # --- These are the functions that the graph nodes will execute ---
    async def supervisor_node(self, state: State):
        """Invokes the supervisor chain and parses its structured output."""
        logger.info("Supervisor deciding next step...")      
        # The supervisor chain now returns a Pydantic object (Router)
        response_object = await self.supervisor_chain.ainvoke(state)        
        # We access the decision via the object's attribute
        decision = response_object.next   
        logger.info(f"Supervisor decision: {decision}")
        # This guarantees the 'next' key will be one of the valid routes.
        return {"next": decision}

    # Human in loop
    async def human_login_node(self, state: State):
        """Asks the user for username and password input and calls the 'login' MCP tool."""
        logger.info("Engaging human for login credentials...")

        # If we already have an access token, we can skip login for this run
        if state.get("access_token"):
            logger.info("Access token already present, skipping human login prompt.")
            return {"messages": [AIMessage(content="Access token already available.")], "next": "supervisor"} # Route to supervisor

        print("\n--- Human Login Required ---")
        username = input("Please enter your username: ")
        password = input("Please enter your password: ")
        print("--- Input Received ---\n")

        # Find the login tool
        login_tool_list = [tool for tool in self.all_tools if tool.name == "login"]

        if not login_tool_list:
            logger.error("Login tool not found from MCP.")
            return {"messages": [AIMessage(content="Error: Login tool not available.")], "next": END}

        # Extract the single login tool from the list
        login_tool = login_tool_list[0]

        try:
            # Invoke the login tool
            login_response = await login_tool.ainvoke({"username": username, "password": password})
            access_token = json.loads(login_response).get("access_token")

            if access_token:
                logger.info("Successfully obtained access token.")
                self._access_token = access_token
                return {
                    "messages": [AIMessage(content="Successfully logged in and obtained access token.")],
                    "access_token": access_token
                }
            else:
                logger.warning("Login failed: No access token received.")
                return {"messages": [AIMessage(content="Login failed. Please try again.")], "next": "human_login"} # Loop back to login
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return {"messages": [AIMessage(content=f"Error during login: {e}. Please try again.")], "next": "human_login"} # Loop back to login
        
    async def report_generator_node(self, state: State):
        """Invokes the report generator chain and returns the final report."""
        logger.info("Generating final report...")
        report = await self.report_generator_chain.ainvoke(state)
        # We add the final report to the 'messages' list in the state
        return {"messages": [report]}

    async def web_search_node(self, state: State):
        """Web search agent with system prompt."""
        logger.info("Web search agent processing request...")
        
        # Add system message for web search agent
        messages_with_system = [
            SystemMessage(content="""You are a web research specialist. Use the wiki_crawler tool to search for company information including revenue, headcount, headquarters, market cap, and other relevant business data. Always use your tools when asked to find information.""")
        ] + state["messages"]
        
        # Create temporary state with system message
        temp_state = {**state, "messages": messages_with_system}
        
        # Invoke the web search agent
        result = await self.web_search_agent.ainvoke(temp_state)
        
        # Return only the new messages (excluding the system message we added)
        new_messages = result["messages"][len(messages_with_system):]
        return {"messages": new_messages}

    async def math_node(self, state: State):
        """Math agent with system prompt."""
        logger.info("Math agent processing request...")
        
        # Add system message for math agent
        messages_with_system = [
            SystemMessage(content="""You are a mathematical calculation specialist. You have access to mathematical tools: add, subtract, multiply, divide, and average. 

IMPORTANT: You MUST use your available tools for ANY mathematical calculations, even simple ones. Never perform calculations manually in your response. Always use the appropriate tool:
- Use 'add' tool for addition
- Use 'subtract' tool for subtraction  
- Use 'multiply' tool for multiplication
- Use 'divide' tool for division
- Use 'average' tool for calculating averages

When you receive a request involving numbers or calculations, immediately identify which mathematical operation is needed and use the corresponding tool.""")
        ] + state["messages"]
        
        # Create temporary state with system message
        temp_state = {**state, "messages": messages_with_system}
        
        # Invoke the math agent
        result = await self.math_agent.ainvoke(temp_state)
        
        # Return only the new messages (excluding the system message we added)
        new_messages = result["messages"][len(messages_with_system):]
        return {"messages": new_messages}

    async def agent_invoke(self, query: str):
        print(f"Start process for : {query}")
        
        # Initial state will include the query and an empty access_token
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "company_name": "", # Still here if needed later
            "access_token": None
        }
        
        final_state = await self.graph.ainvoke(initial_state, {"recursion_limit": 15})
        final_report = final_state['messages'][-1].content
        print(final_report)
        return final_report