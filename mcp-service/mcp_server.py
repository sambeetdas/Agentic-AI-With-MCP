from mcp.server.fastmcp import FastMCP
from services.wikipedia import WikipediaService
from services.calculator import CalculatorService
from services.auth import AuthService, ACCESS_TOKEN_EXPIRE_MINUTES, require_auth_tool
from fastapi import HTTPException, status
from datetime import timedelta
from typing import Any


mcp = FastMCP("tool-repository", host="127.0.0.1", port=8001, debug=True)
wiki_service = WikipediaService()
calculator_service = CalculatorService()
auth_service = AuthService()

@mcp.tool(description= "Login to obtain a JWT token for authenticated access to other tools.")
async def login(username: str, password: str):
    """
    login authenticates a user and returns a JWT access token.

    Args:
    username: The username of the user.
    password: The password of the user.
    """
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required"
        )

    user = auth_service.get_user(username)
    if not user or not auth_service.verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@mcp.tool(description="Logout to invalidate the current JWT token.")
async def logout(headers: dict = None):
    """
    logout invalidates the current user's JWT token.

    Args:
    user: The current authenticated user.
    """
    auth_header = headers.get("Authorization") if headers else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token = auth_header.split(" ")[1]
    current_user = await auth_service.get_current_user(token)
    print(current_user)

    return {"msg": f"User {current_user['username']} successfully logged out"}

@mcp.tool(description="Crawl Wikipedia for information about a company.")
async def wiki_crawler(company_name: str, headers: dict = None):
    """
    Crawls Wikipedia for information about a company.

    Args:
    company_name: The name of the company to search for.
    """
    print("Company Name:", company_name)
    print("Headers:", headers)
    auth_header = headers.get("Authorization") if headers else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token = auth_header.split(" ")[1]
    print(token)
    current_user = await auth_service.get_current_user(token)
    print(current_user)
    return wiki_service.get_company_info_wikipedia(company_name)

@mcp.tool(description="Add two numbers.")
async def add(a: float, b: float, headers: dict = None) -> float:
    """
    Adds two numbers.
    
    Args:
    a: The first number.
    b: The second number.
    """
    print(headers)
    auth_header = headers.get("Authorization") if headers else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token = auth_header.split(" ")[1]
    current_user = await auth_service.get_current_user(token)
    print(current_user)
    return calculator_service.add(a, b)

@mcp.tool(description="Subtract the second number from the first number.")
async def subtract(a: float, b: float, headers: dict = None) -> float:
    """
    Subtracts the second number from the first number.

    Args:       
    a: The first number.
    b: The second number.
    """

    auth_header = headers.get("Authorization") if headers else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token = auth_header.split(" ")[1]
    current_user = await auth_service.get_current_user(token)
    print(current_user)
    return calculator_service.subtract(a, b)

@mcp.tool(description="Multiply two numbers.")
async def multiply(a: float, b: float, headers: dict = None) -> float:
    """
    Multiplies two numbers.
    
    Args:
    a: The first number.
    b: The second number.
    """
    auth_header = headers.get("Authorization") if headers else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token = auth_header.split(" ")[1]
    current_user = await auth_service.get_current_user(token)
    print(current_user)
    return calculator_service.multiply(a, b)

@mcp.tool(description="Divide the first number by the second number.")
async def divide(a: float, b: float, headers: dict = None) -> float:
    """
    Divides the first number by the second number.

    Args:
    a: The first number.
    b: The second number.
    """
    auth_header = headers.get("Authorization") if headers else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token = auth_header.split(" ")[1]
    current_user = await auth_service.get_current_user(token)
    print(current_user)
    return calculator_service.divide(a, b)  

@mcp.tool()
async def average(numbers: list[float], headers: dict = None) -> float:
    """
    Calculates the average of a list of numbers.

    Args:
    numbers: A list of numbers.
    """
    auth_header = headers.get("Authorization") if headers else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    token = auth_header.split(" ")[1]
    current_user = await auth_service.get_current_user(token)
    print(current_user)
    return calculator_service.Average(numbers)

if __name__ == "__main__":
    mcp.run(transport='streamable-http')