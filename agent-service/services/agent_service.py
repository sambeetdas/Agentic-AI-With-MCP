import logging
import asyncio
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
#from langchain_core.pydantic_v1 import BaseModel, Field
from pydantic import BaseModel, Field


# (Your logging and State definition remain the same)
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- State Definition ---
class State(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    company_name: Optional[str]
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
        
        # --- 1. Create Simple LCEL Chains for Non-Tool-Using Nodes ---
        
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
        research_tools = [tool for tool in all_tools if tool.name in ["wiki_crawler"]]
        math_tools = [tool for tool in all_tools if tool.name in ["add", "subtract", "multiply", "divide", "average"]]

        # These are your specialist agents that need to reason about tools
        self.web_search_agent = create_react_agent(self.llm, tools=research_tools)
        self.math_agent = create_react_agent(self.llm, tools=math_tools)

        # --- 3. Build the Graph ---
        self.graph = self._create_graph()
    
    def _create_graph(self) -> StateGraph:
        """Builds the supervisor-based workflow."""
        workflow = StateGraph(State)

        # Define the nodes
        workflow.add_node("supervisor", self.supervisor_node)
        workflow.add_node("web_search", self.web_search_agent)
        workflow.add_node("math", self.math_agent)
        workflow.add_node("report_generator", self.report_generator_node)

        # Build the graph
        workflow.set_entry_point("supervisor")
        workflow.add_conditional_edges(
            "supervisor",
            lambda state: state["next"],
            {
                "web_search": "web_search",
                "math": "math",
                "report_generator": "report_generator",
            }
        )
        
        # After the workers are done, they go back to the supervisor for the next decision
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

    async def report_generator_node(self, state: State):
        """Invokes the report generator chain and returns the final report."""
        logger.info("Generating final report...")
        report = await self.report_generator_chain.ainvoke(state)
        # We add the final report to the 'messages' list in the state
        return {"messages": [report]}

    # (Your process and extract_company_name_from_query methods can remain largely the same)
    async def agent_invoke(self, query: str):
        print(f"Start process for : {query}")
        company_name = ""
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "company_name": company_name
        }
        
        final_state = await self.graph.ainvoke(initial_state, {"recursion_limit": 15})
        final_report = final_state['messages'][-1].content
        print(final_report)
        return final_report