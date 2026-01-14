"""
Amazon Bedrock AgentCore Runtime - Production Ready
Using Strands Agents with BedrockModel and MCP tools
Based on: https://github.com/awslabs/amazon-bedrock-agentcore-samples
"""

import os
import logging
import sys
import json
from typing import Optional
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from mcp import stdio_client, StdioServerParameters
from strands.tools.mcp import MCPClient
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the AgentCore Runtime App
app = BedrockAgentCoreApp()

# Initialize MCP server and client (will be set up on first use)
_mcp_client: Optional[MCPClient] = None
_mcp_context = None  # Context manager for MCP client
_agent: Optional[Agent] = None
_server_script_path: Optional[str] = None


# Define tools with @tool decorator
@tool
def get_weather(city: str = "default") -> str:
    """Get current weather information for a city.
    
    Args:
        city: The name of the city to get weather for (default: "default")
    
    Returns:
        A string describing the current weather
    """
    return f"Weather in {city} is sunny"


@tool
def calculate(operation: str, a: float, b: float) -> float:
    """Perform basic arithmetic operations.
    
    Args:
        operation: The operation to perform (add, subtract, multiply, divide)
        a: First number
        b: Second number
    
    Returns:
        The result of the arithmetic operation
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else 0
    }
    return operations.get(operation, lambda x, y: 0)(a, b)


@tool
def get_time() -> str:
    """Get the current time.
    
    Returns:
        A string with the current time information
    """
    from datetime import datetime
    return f"Current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


@tool
def reverse_string(text: str) -> str:
    """Reverse a string.
    
    Args:
        text: The string to reverse
    
    Returns:
        The reversed string
    """
    return text[::-1]


@tool
def query_countries_graphql(query_type: str = "country", code: str = "US", name: str = "", currency: str = "") -> str:
    """Query the Countries GraphQL API (https://countries.trevorblades.com) for country information.
    
    Args:
        query_type: Type of query - "country" (by code), "countries" (list), "continent" (by continent code), or "filter_by_currency" (filter by currency)
        code: Country code (e.g., "US", "BR", "ES") or continent code (e.g., "NA", "SA", "EU")
        name: Country name filter (optional, used with countries query)
        currency: Currency code to filter by (e.g., "USD", "EUR", "GBP") - used with "filter_by_currency" query type
    
    Returns:
        JSON string with country information from the GraphQL API
    """
    graphql_url = "https://countries.trevorblades.com/graphql"
    
    try:
        if query_type == "country":
            # Query a single country by code
            query = """
            query GetCountry($code: ID!) {
                country(code: $code) {
                    code
                    name
                    native
                    capital
                    emoji
                    currency
                    languages {
                        code
                        name
                    }
                    continent {
                        code
                        name
                    }
                }
            }
            """
            variables = {"code": code.upper()}
            
        elif query_type == "countries":
            # Query multiple countries
            query = """
            query GetCountries {
                countries {
                    code
                    name
                    capital
                    emoji
                    currency
                }
            }
            """
            variables = {}
            
        elif query_type == "continent":
            # Query countries in a continent
            query = """
            query GetCountriesByContinent($code: ID!) {
                continent(code: $code) {
                    code
                    name
                    countries {
                        code
                        name
                        capital
                        emoji
                    }
                }
            }
            """
            variables = {"code": code.upper()}
            
        elif query_type == "filter_by_currency":
            # Filter countries by currency
            currency_code = currency.upper() if currency else code.upper()
            query = """
            query GetCountriesByCurrency($currency: String!) {
                countries(filter: { currency: { eq: $currency } }) {
                    code
                    name
                    currency
                    capital
                    emoji
                }
            }
            """
            variables = {"currency": currency_code}
        else:
            error_msg = f"Unknown query_type: {query_type}. Use 'country', 'countries', 'continent', or 'filter_by_currency'"
            logger.error(f"query_countries_graphql error: {error_msg}")
            return json.dumps({"error": error_msg})
        
        # Log the complete GraphQL query for observability
        logger.info(f"GraphQL Query - URL: {graphql_url}, query_type: {query_type}")
        logger.info(f"GraphQL Query String:\n{query}")
        logger.info(f"GraphQL Variables: {json.dumps(variables, indent=2)}")
        
        response = requests.post(
            graphql_url,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            error_msg = result["errors"]
            logger.error(f"GraphQL API returned errors: {json.dumps(error_msg, indent=2)}")
            return json.dumps({"error": error_msg})
        
        # Log the response data (truncated if too long)
        response_data = result.get("data", {})
        response_str = json.dumps(response_data, indent=2)
        logger.info(f"GraphQL query successful. Response data (first 500 chars): {response_str[:500]}...")
        return response_str
        
    except requests.exceptions.RequestException as e:
        error_msg = f"GraphQL request failed: {str(e)}"
        logger.error(f"query_countries_graphql error: {error_msg}")
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"query_countries_graphql error: {error_msg}", exc_info=True)
        return json.dumps({"error": error_msg})


def create_mcp_server_script() -> str:
    """Create a Python script for the MCP server subprocess."""
    script_content = '''
import sys
import json
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AgentCore Tools Server")

@mcp.tool()
def get_weather(city: str = "default") -> str:
    """Get current weather information for a city."""
    return f"Weather in {city} is sunny"

@mcp.tool()
def calculate(operation: str, a: float, b: float) -> float:
    """Perform basic arithmetic operations."""
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else 0
    }
    return operations.get(operation, lambda x, y: 0)(a, b)

@mcp.tool()
def get_time() -> str:
    """Get the current time."""
    from datetime import datetime
    return f"Current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

@mcp.tool()
def reverse_string(text: str) -> str:
    """Reverse a string."""
    return text[::-1]

@mcp.tool()
def query_countries_graphql(query_type: str = "country", code: str = "US", name: str = "", currency: str = "") -> str:
    """Query the Countries GraphQL API (https://countries.trevorblades.com) for country information.
    
    Args:
        query_type: Type of query - "country" (by code), "countries" (list), "continent" (by continent code), or "filter_by_currency" (filter by currency)
        code: Country code (e.g., "US", "BR", "ES") or continent code (e.g., "NA", "SA", "EU")
        name: Country name filter (optional, used with countries query)
        currency: Currency code to filter by (e.g., "USD", "EUR", "GBP") - used with "filter_by_currency" query type
    
    Returns:
        JSON string with country information from the GraphQL API
    """
    graphql_url = "https://countries.trevorblades.com/graphql"
    
    try:
        if query_type == "country":
            query = """
            query GetCountry($code: ID!) {
                country(code: $code) {
                    code
                    name
                    native
                    capital
                    emoji
                    currency
                    languages {
                        code
                        name
                    }
                    continent {
                        code
                        name
                    }
                }
            }
            """
            variables = {"code": code.upper()}
        elif query_type == "countries":
            query = """
            query GetCountries {
                countries {
                    code
                    name
                    capital
                    emoji
                    currency
                }
            }
            """
            variables = {}
        elif query_type == "continent":
            query = """
            query GetCountriesByContinent($code: ID!) {
                continent(code: $code) {
                    code
                    name
                    countries {
                        code
                        name
                        capital
                        emoji
                    }
                }
            }
            """
            variables = {"code": code.upper()}
        elif query_type == "filter_by_currency":
            currency_code = currency.upper() if currency else code.upper()
            query = """
            query GetCountriesByCurrency($currency: String!) {
                countries(filter: { currency: { eq: $currency } }) {
                    code
                    name
                    currency
                    capital
                    emoji
                }
            }
            """
            variables = {"currency": currency_code}
        else:
            error_msg = f"Unknown query_type: {query_type}. Use 'country', 'countries', 'continent', or 'filter_by_currency'"
            return json.dumps({"error": error_msg})
        
        response = requests.post(
            graphql_url,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            error_msg = result["errors"]
            return json.dumps({"error": error_msg})
        
        return json.dumps(result.get("data", {}), indent=2)
        
    except Exception as e:
        error_msg = f"GraphQL request failed: {str(e)}"
        return json.dumps({"error": error_msg})

if __name__ == "__main__":
    mcp.run(transport="stdio")
'''
    return script_content


def create_mcp_client() -> MCPClient:
    """Create MCP client connected to local server via stdio subprocess."""
    global _mcp_client, _server_script_path
    
    if _mcp_client is None:
        try:
            # Create temporary script file for MCP server
            import tempfile
            server_script = create_mcp_server_script()
            
            # Write server script to a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(server_script)
                _server_script_path = f.name
            
            # Create MCP client that connects to server via stdio
            def create_client():
                return stdio_client(
                    StdioServerParameters(
                        command=sys.executable,
                        args=[_server_script_path]
                    )
                )
            
            _mcp_client = MCPClient(create_client)
            logger.info("MCP client created and connected to local server")
            
        except Exception as e:
            logger.error(f"Failed to create MCP client: {str(e)}")
            raise RuntimeError(f"MCP connection failed - {str(e)}")
    
    return _mcp_client


def initialize_mcp_tools():
    """Initialize MCP client and get tools, keeping context open."""
    global _mcp_client, _mcp_context
    
    if _mcp_client is None:
        _mcp_client = create_mcp_client()
    
    # Enter context and keep it open
    if _mcp_context is None:
        try:
            _mcp_context = _mcp_client.__enter__()
            tools = _mcp_client.list_tools_sync()
            logger.info(f"Retrieved {len(tools)} tools from MCP server")
            return tools
        except Exception as e:
            logger.error(f"Failed to get tools from MCP: {str(e)}")
            raise RuntimeError(f"MCP connection failed - {str(e)}")
    else:
        # Context already open, just get tools
        try:
            tools = _mcp_client.list_tools_sync()
            return tools
        except Exception as e:
            logger.error(f"Failed to get tools from MCP: {str(e)}")
            raise RuntimeError(f"MCP connection failed - {str(e)}")


def get_or_create_agent() -> Agent:
    """Get or create the Strands agent with BedrockModel and MCP tools."""
    global _agent
    
    if _agent is None:
        try:
            # Get Bedrock model ID from environment or use default
            model_id = os.getenv(
                "BEDROCK_MODEL_ID",
                "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
            )
            
            # Create BedrockModel
            bedrock_model = BedrockModel(
                model_id=model_id,
                temperature=0.3,
                top_p=0.8
            )
            
            # Initialize MCP and get tools
            # The MCP context will remain open for tool execution
            tools = initialize_mcp_tools()
            
            # Create agent with model and MCP tools
            _agent = Agent(model=bedrock_model, tools=tools)
            
            logger.info(f"Strands agent created with model {model_id} and {len(tools)} MCP tools")
            
        except RuntimeError:
            # Re-raise RuntimeError (MCP errors)
            raise
        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            raise RuntimeError(f"Agent creation failed - {str(e)}")
    
    return _agent


@app.entrypoint
def agent_handler(payload: dict) -> dict:
    """
    Entry point for the AgentCore Runtime.
    This function is called by the runtime when the agent is invoked.
    Uses Strands Agent with BedrockModel and MCP tools.
    """
    try:
        user_input = payload.get("prompt", "")
        
        if not user_input:
            return {
                "response": ["Error: No prompt provided"]
            }
        
        # Get or create agent
        agent = get_or_create_agent()
        
        # Track messages before agent call to detect tool usage
        messages_before = []
        try:
            # Try to access agent messages if available
            if hasattr(agent, 'messages'):
                messages_before = list(agent.messages) if agent.messages else []
        except:
            pass
        
        # Use agent to process the input
        # The agent will automatically use tools when needed
        logger.info(f"Processing user input: {user_input}")
        response = agent(user_input)
        
        # Extract response text
        if isinstance(response, str):
            response_text = response
        else:
            # Handle different response types
            response_text = str(response)
        
        logger.info(f"Agent response received (length: {len(response_text)} chars)")
        
        # Detect if tools were used by checking if messages changed
        tools_used = False
        try:
            if hasattr(agent, 'messages') and agent.messages:
                # Check if we have more messages after the call (indicating tool usage)
                messages_after = list(agent.messages) if agent.messages else []
                if len(messages_after) > len(messages_before):
                    tools_used = True
                # Also check message content for tool-related indicators
                for msg in messages_after:
                    msg_str = str(msg).lower()
                    if any(indicator in msg_str for indicator in ['tool', 'function_call', 'tool_call', 'mcp']):
                        tools_used = True
                        break
        except:
            # If we can't detect, check response content for tool indicators
            response_lower = response_text.lower()
            # Check for JSON responses (common in tool results) or specific patterns
            if any(indicator in response_lower for indicator in ['{"code"', '"name"', '"capital"', '"currency"', 'graphql']):
                tools_used = True
        
        # Add indicator to response based on tool usage
        # Note: The final response text is ALWAYS generated by the model LLM
        # "[Using tool]" means: the model used a tool to get data, then generated the response
        # "[Model response]" means: the model answered directly without using tools
        if tools_used:
            final_response = f"[Model response using tool data] {response_text}"
        else:
            final_response = f"[Model response] {response_text}"
        
        return {
            "response": [final_response]
        }
        
    except RuntimeError as e:
        # MCP or agent creation errors - return clear error message
        error_msg = str(e)
        logger.error(f"Runtime error in agent_handler: {error_msg}", exc_info=True)
        return {
            "response": [f"Error: {error_msg}"]
        }
    except Exception as e:
        # Other unexpected errors
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error in agent_handler: {error_msg}", exc_info=True)
        return {
            "response": [error_msg]
        }


if __name__ == "__main__":
    # Run the AgentCore Runtime
    app.run()
