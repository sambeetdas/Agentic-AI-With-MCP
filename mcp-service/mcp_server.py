from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from services.wikipedia import WikipediaService
from services.calculator import CalculatorService

mcp = FastMCP("tool-repository", host="127.0.0.1", port=8001, debug=True)
wiki_service = WikipediaService()
calculator_service = CalculatorService()


@mcp.tool()
async def wiki_crawler(company_name: str):
    """
    Crawls Wikipedia for information about a company.

    Args:
    company_name: The name of the company to search for.
    """
    return wiki_service.get_company_info_wikipedia(company_name)

@mcp.tool()
async def add(a: float, b: float) -> float:
    """
    Adds two numbers.
    
    Args:
    a: The first number.
    b: The second number.
    """
    return calculator_service.add(a, b)

@mcp.tool()
async def subtract(a: float, b: float) -> float:
    """
    Subtracts the second number from the first number.

    Args:       
    a: The first number.
    b: The second number.
    """
    return calculator_service.subtract(a, b)

@mcp.tool()
async def multiply(a: float, b: float) -> float:
    """
    Multiplies two numbers.
    
    Args:
    a: The first number.
    b: The second number.
    """
    return calculator_service.multiply(a, b)

@mcp.tool()
async def divide(a: float, b: float) -> float:
    """
    Divides the first number by the second number.

    Args:
    a: The first number.
    b: The second number.
    """
    return calculator_service.divide(a, b)  

@mcp.tool()
async def average(numbers: list[float]) -> float:
    """
    Calculates the average of a list of numbers.

    Args:
    numbers: A list of numbers.
    """ 
    return calculator_service.Average(numbers)

if __name__ == "__main__":
    mcp.run(transport='streamable-http')