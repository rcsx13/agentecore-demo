"""
Amazon Bedrock AgentCore Runtime - Production Ready
Using Strands Agents with BedrockModel and MCP tools via AgentCore Gateway
Based on: https://github.com/awslabs/amazon-bedrock-agentcore-samples

Observability Features:
- Structured logging with request/session tracking
- Performance metrics (response times, tool usage)
- Error tracking and reporting
- MCP connection monitoring
- Token refresh tracking
- Detailed tool discovery logging
"""

import os
import sys
import logging
import json
import base64
import time
from typing import Optional, Dict, Any, Iterator
from datetime import datetime
from contextlib import contextmanager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.services.identity import IdentityClient
from strands import Agent
from strands.models import BedrockModel
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient
import boto3
import httpx
import requests

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Observability metrics
_metrics: Dict[str, Any] = {
    'invocations': 0,
    'tool_calls': 0,
    'errors': 0,
    'total_response_time': 0.0,
    'mcp_connection_time': 0.0,
    'token_refresh_count': 0
}

# Initialize the AgentCore Runtime App
app = BedrockAgentCoreApp()

# Initialize MCP client (will be set up on first use)
_mcp_client: Optional[MCPClient] = None
_boto_session: Optional[boto3.Session] = None
_bedrock_model: Optional[BedrockModel] = None


def get_aws_session() -> boto3.Session:
    """Get or create AWS boto3 session."""
    global _boto_session
    
    if _boto_session is None:
        region = os.getenv("AWS_REGION", "us-east-1")
        _boto_session = boto3.Session(region_name=region)
        logger.info(f"AWS session created for region: {region}")
    
    return _boto_session


def create_gateway_mcp_client() -> MCPClient:
    """Create MCP client connected to AgentCore Gateway via HTTP with JWT token auth."""
    global _mcp_client
    
    if _mcp_client is None:
        try:
            # Intentar obtener desde variable de entorno primero
            gateway_url = os.getenv("AGENTCORE_GATEWAY_URL")
            
            # Si no está en variable de entorno, intentar leer desde .gateway-info.json
            if not gateway_url:
                gateway_info_path = ".gateway-info.json"
                if os.path.exists(gateway_info_path):
                    try:
                        with open(gateway_info_path, 'r') as f:
                            gateway_info = json.load(f)
                            gateway_url = gateway_info.get('gatewayUrl')
                    except Exception as e:
                        logger.warning(f"No se pudo leer .gateway-info.json: {e}")
            
            # Si aún no hay URL, usar valor hardcodeado (fallback)
            if not gateway_url:
                gateway_url = "https://countries-gateway-fdvmwzb8ln.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
                logger.info("Usando URL del Gateway hardcodeada (fallback)")
            
            if not gateway_url:
                raise RuntimeError(
                    "No se pudo obtener la URL del Gateway. "
                    "Configura AGENTCORE_GATEWAY_URL o ejecuta './setup-gateway.sh'"
                )
            
            # Get AWS session and region
            session = get_aws_session()
            region = session.region_name or 'us-east-1'
            
            # Get JWT token for authentication
            # The Gateway should be configured with CUSTOM_JWT authorizer (use setup-gateway-jwt.sh)
            def create_client():
                try:
                    logger.info(f"Creating streamablehttp_client for URL: {gateway_url}")
                    
                    # Try to get JWT token from Cognito
                    # First, try to read from .cognito-token.json (created by setup-gateway-jwt.sh)
                    token = None
                    token_file = ".cognito-token.json"
                    
                    if os.path.exists(token_file):
                        try:
                            with open(token_file, 'r') as f:
                                token_data = json.load(f)
                                token = token_data.get('access_token')
                                if token:
                                    token_length = len(token)
                                    token_preview = f"{token[:20]}...{token[-10:]}" if token_length > 30 else token[:30]
                                    logger.info(f"JWT token loaded from .cognito-token.json (length: {token_length}, preview: {token_preview})")
                        except Exception as e:
                            logger.warning(f"Failed to read token from {token_file}: {e}")
                    
                    # If no token file, try to get token dynamically from Cognito
                    if not token:
                        try:
                            cognito_info_file = ".cognito-info.json"
                            if os.path.exists(cognito_info_file):
                                with open(cognito_info_file, 'r') as f:
                                    cognito_info = json.load(f)
                                
                                # Get token from Cognito using client credentials flow
                                user_pool_id = cognito_info.get('userPoolId')
                                client_id = cognito_info.get('clientId')
                                client_secret = cognito_info.get('clientSecret')
                                scope_string = cognito_info.get('scopeString', '')
                                
                                if user_pool_id and client_id:
                                    # Para client_credentials flow, usar el dominio del User Pool
                                    # Usar el dominio guardado en cognito_info si está disponible
                                    cognito_domain = cognito_info.get('cognitoDomain')
                                    if not cognito_domain:
                                        # Fallback: construir dominio desde user_pool_id
                                        domain_prefix = user_pool_id.replace('_', '-').lower()
                                        cognito_domain = f'{domain_prefix}.auth.{region}.amazoncognito.com'
                                    
                                    token_url = f'https://{cognito_domain}/oauth2/token'
                                    
                                    # Create Basic Auth
                                    auth_string = f'{client_id}:{client_secret}' if client_secret else client_id
                                    auth_bytes = auth_string.encode('utf-8')
                                    auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
                                    
                                    headers = {
                                        'Content-Type': 'application/x-www-form-urlencoded',
                                        'Authorization': f'Basic {auth_b64}'
                                    }
                                    
                                    # Try without scope first (Cognito will use configured scopes)
                                    data = {
                                        'grant_type': 'client_credentials'
                                    }
                                    
                                    response = requests.post(token_url, headers=headers, data=data, timeout=30)
                                    
                                    # If fails without scope, try with scope
                                    if response.status_code != 200 and scope_string:
                                        data['scope'] = scope_string
                                        response = requests.post(token_url, headers=headers, data=data, timeout=30)
                                    
                                    response.raise_for_status()
                                    token_data = response.json()
                                    token = token_data.get('access_token')
                                    
                                    if token:
                                        _metrics['token_refresh_count'] += 1
                                        token_length = len(token)
                                        token_preview = f"{token[:20]}...{token[-10:]}" if token_length > 30 else token[:30]
                                        logger.info(f"JWT token obtained from Cognito (length: {token_length}, preview: {token_preview})")
                                        logger.info(f"Token refresh count: {_metrics['token_refresh_count']}")
                        except Exception as e:
                            logger.warning(f"Failed to get token from Cognito: {str(e)}", exc_info=True)
                    
                    # Create client with JWT token in headers
                    def create_httpx_client(*args, **kwargs):
                        """Create httpx.AsyncClient with JWT token authentication."""
                        # Ensure headers is always a dict, not None
                        client_headers = kwargs.get('headers') or {}
                        # Create a copy to avoid modifying the original
                        client_headers = dict(client_headers)
                        timeout = kwargs.get('timeout', httpx.Timeout(60.0))
                        
                        # Add Authorization header with Bearer token if available
                        if token:
                            client_headers['Authorization'] = f'Bearer {token}'
                            logger.info("✓ JWT token added to Authorization header")
                            logger.debug(f"Authorization header: Bearer {token[:20]}...{token[-10:]}")
                        else:
                            logger.warning("⚠ No JWT token available - Gateway may reject the request")
                            logger.warning("Run ./setup-gateway-jwt.sh to configure Gateway with CUSTOM_JWT")
                        
                        return httpx.AsyncClient(
                            headers=client_headers,
                            timeout=timeout
                        )
                    
                    client = streamablehttp_client(
                        gateway_url,
                        httpx_client_factory=create_httpx_client
                    )
                    logger.info("=" * 80)
                    logger.info("MCP CLIENT CONFIGURATION")
                    logger.info(f"Gateway URL: {gateway_url}")
                    logger.info(f"Authentication: JWT Bearer Token")
                    logger.info(f"Token Source: {'File (.cognito-token.json)' if token and os.path.exists('.cognito-token.json') else 'Dynamic (Cognito)' if token else 'None'}")
                    logger.info(f"Region: {region}")
                    logger.info("=" * 80)
                    logger.info("✓ streamablehttp_client created successfully with JWT token authentication")
                    return client
                        
                except Exception as e:
                    logger.error(f"Failed to create streamablehttp_client: {str(e)}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise
            
            try:
                _mcp_client = MCPClient(create_client)
                logger.info(f"MCP client created for AgentCore Gateway: {gateway_url}")
                logger.info("Note: Gateway should be configured with CUSTOM_JWT authentication for JWT token to work")
            except Exception as e:
                logger.error(f"Failed to create MCPClient: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                logger.error(traceback.format_exc())
                raise
            
        except Exception as e:
            logger.error(f"Failed to create Gateway MCP client: {str(e)}")
            raise RuntimeError(f"Gateway MCP connection failed - {str(e)}")
    
    return _mcp_client


@contextmanager
def initialize_mcp_tools() -> Iterator[list]:
    """Initialize MCP client and get tools per invocation."""
    global _mcp_client

    if _mcp_client is None:
        _mcp_client = create_gateway_mcp_client()

    try:
        mcp_start_time = time.time()
        logger.info("Entering MCP client context (per-invocation)...")
        with _mcp_client:
            mcp_connection_time = time.time() - mcp_start_time
            _metrics['mcp_connection_time'] = mcp_connection_time
            logger.info(
                f"✓ MCP client context entered successfully ({mcp_connection_time:.3f}s)"
            )

            logger.info("Listing tools from MCP server...")
            tools = _mcp_client.list_tools_sync()

            logger.info("=" * 80)
            logger.info(f"MCP TOOLS DISCOVERED: {len(tools)} tool(s)")
            for i, tool in enumerate(tools, 1):
                tool_name = getattr(tool, 'name', 'unknown')
                tool_desc = getattr(tool, 'description', 'No description')
                logger.info(f"  {i}. {tool_name}")
                logger.info(f"     Description: {tool_desc[:100]}...")
            logger.info("=" * 80)

            yield tools
    except Exception as e:
        logger.error(f"Failed to get tools from MCP: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        raise RuntimeError(f"MCP connection failed - {str(e)}")


def get_or_create_bedrock_model() -> BedrockModel:
    """Get or create the Bedrock model instance."""
    global _bedrock_model

    if _bedrock_model is None:
        model_id = os.getenv(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        )
        _bedrock_model = BedrockModel(
            model_id=model_id,
            temperature=0.3,
            top_p=0.8
        )
        logger.info("=" * 80)
        logger.info("BEDROCK MODEL INITIALIZED")
        logger.info(f"Model: {model_id}")
        logger.info(f"Temperature: 0.3")
        logger.info(f"Top P: 0.8")
        logger.info("=" * 80)

    return _bedrock_model


def create_agent(tools: list) -> Agent:
    """Create the Strands agent with BedrockModel and MCP tools."""
    bedrock_model = get_or_create_bedrock_model()
    agent = Agent(model=bedrock_model, tools=tools)

    logger.info("=" * 80)
    logger.info("AGENT INITIALIZED (per-invocation MCP context)")
    logger.info(f"MCP Tools: {len(tools)}")
    for i, tool in enumerate(tools, 1):
        tool_name = getattr(tool, 'name', 'unknown')
        logger.info(f"  - {tool_name}")
    logger.info("=" * 80)

    return agent


def log_metrics():
    """Log current observability metrics."""
    if _metrics['invocations'] > 0:
        avg_response_time = _metrics['total_response_time'] / _metrics['invocations']
        tool_usage_rate = (_metrics['tool_calls'] / _metrics['invocations']) * 100 if _metrics['invocations'] > 0 else 0
        error_rate = (_metrics['errors'] / _metrics['invocations']) * 100 if _metrics['invocations'] > 0 else 0
        
        logger.info("=" * 80)
        logger.info("OBSERVABILITY METRICS")
        logger.info("=" * 80)
        logger.info(f"Total Invocations: {_metrics['invocations']}")
        logger.info(f"Tool Calls: {_metrics['tool_calls']} ({tool_usage_rate:.1f}% usage rate)")
        logger.info(f"Errors: {_metrics['errors']} ({error_rate:.1f}% error rate)")
        logger.info(f"Average Response Time: {avg_response_time:.3f}s")
        logger.info(f"MCP Connection Time: {_metrics['mcp_connection_time']:.3f}s")
        logger.info(f"Token Refreshes: {_metrics['token_refresh_count']}")
        logger.info("=" * 80)


def _find_graphql_queries(value: Any) -> list[str]:
    """Best-effort extraction of GraphQL query strings from nested data."""
    queries: list[str] = []

    if isinstance(value, str):
        lower = value.lower()
        if ("query" in lower or "mutation" in lower) and "{" in value and "}" in value:
            queries.append(value)
        return queries

    if isinstance(value, dict):
        # Common GraphQL payload shape: {"query": "...", "variables": {...}}
        query_value = value.get("query")
        if isinstance(query_value, str):
            queries.append(query_value)
        for item in value.values():
            queries.extend(_find_graphql_queries(item))
        return queries

    if isinstance(value, (list, tuple)):
        for item in value:
            queries.extend(_find_graphql_queries(item))
        return queries

    if hasattr(value, "__dict__"):
        queries.extend(_find_graphql_queries(value.__dict__))

    return queries


@app.entrypoint
def agent_handler(payload: dict) -> dict:
    """
    Entry point for the AgentCore Runtime.
    This function is called by the runtime when the agent is invoked.
    Uses Strands Agent with BedrockModel and MCP tools.
    """
    invocation_start_time = time.time()
    request_id = payload.get("requestId", "unknown")
    session_id = payload.get("sessionId", "unknown")
    
    # Update metrics
    _metrics['invocations'] += 1
    
    try:
        user_input = payload.get("prompt", "")
        
        logger.info("=" * 80)
        logger.info(f"AGENT INVOCATION START")
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"User Input: {user_input}")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        logger.info("=" * 80)
        
        if not user_input:
            _metrics['errors'] += 1
            logger.warning("Empty prompt received")
            return {
                "response": ["Error: No prompt provided"]
            }
        
        # Get tools and create agent within MCP context (per invocation)
        agent_init_time = 0.0
        agent_call_time = 0.0
        response = None
        messages_before: list = []
        tools_used_list: list[str] = []

        agent_init_start = time.time()
        with initialize_mcp_tools() as tools:
            agent = create_agent(tools)
            agent_init_time = time.time() - agent_init_start
            logger.info(f"Agent initialization time: {agent_init_time:.3f}s")

            # Track messages before agent call to detect tool usage
            try:
                # Try to access agent messages if available
                if hasattr(agent, 'messages'):
                    messages_before = list(agent.messages) if agent.messages else []
                    logger.debug(f"Messages before agent call: {len(messages_before)}")
            except Exception as e:
                logger.debug(f"Could not access messages before: {e}")

            # Use agent to process the input
            # The agent will automatically use tools when needed
            agent_call_start = time.time()
            logger.info("Calling agent with user input...")
            response = agent(user_input)
            agent_call_time = time.time() - agent_call_start
            logger.info(f"Agent call completed in {agent_call_time:.3f}s")
        
        # Extract response text
        if isinstance(response, str):
            response_text = response
        else:
            # Handle different response types
            response_text = str(response)
        
        # Detect if tools were used by checking if messages changed
        tools_used = False
        tool_call_count = 0
        graphql_queries: list[str] = []
        try:
            if hasattr(agent, 'messages') and agent.messages:
                # Check if we have more messages after the call (indicating tool usage)
                messages_after = list(agent.messages) if agent.messages else []
                message_count_diff = len(messages_after) - len(messages_before)
                
                if message_count_diff > 0:
                    tools_used = True
                    tool_call_count = message_count_diff
                    logger.info(f"Detected {tool_call_count} tool call(s) based on message count")
                
                # Also check message content for tool-related indicators
                for i, msg in enumerate(messages_after[len(messages_before):], 1):
                    msg_str = str(msg).lower()
                    if any(indicator in msg_str for indicator in ['tool', 'function_call', 'tool_call', 'mcp']):
                        tools_used = True
                        # Try to extract tool name
                        if 'executeGraphQLQuery' in str(msg):
                            tools_used_list.append('countries-graphql-target___executeGraphQLQuery')
                        logger.debug(f"Tool usage detected in message {i}: {msg_str[:100]}")

                for msg in messages_after[len(messages_before):]:
                    graphql_queries.extend(_find_graphql_queries(msg))
        except Exception as e:
            logger.debug(f"Could not analyze messages for tool usage: {e}")
            # If we can't detect, check response content for tool indicators
            response_lower = response_text.lower()
            # Check for JSON responses (common in tool results) or specific patterns
            if any(indicator in response_lower for indicator in ['{"code"', '"name"', '"capital"', '"currency"', 'graphql']):
                tools_used = True
                tools_used_list.append('countries-graphql-target (detected from response)')
                logger.info("Tool usage detected from response content")

        if graphql_queries:
            seen = set()
            unique_queries = []
            for q in graphql_queries:
                if q not in seen:
                    seen.add(q)
                    unique_queries.append(q)
            logger.info("=" * 80)
            logger.info("GRAPHQL QUERIES USED")
            logger.info("=" * 80)
            for q in unique_queries[:5]:
                logger.info(q)
            logger.info("=" * 80)
        
        # Update metrics
        if tools_used:
            _metrics['tool_calls'] += tool_call_count if tool_call_count > 0 else 1
        
        total_time = time.time() - invocation_start_time
        _metrics['total_response_time'] += total_time
        
        # Log detailed observability information
        logger.info("=" * 80)
        logger.info(f"AGENT INVOCATION COMPLETE")
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Total Time: {total_time:.3f}s")
        logger.info(f"Agent Init Time: {agent_init_time:.3f}s")
        logger.info(f"Agent Call Time: {agent_call_time:.3f}s")
        logger.info(f"Tools Used: {tools_used}")
        if tools_used_list:
            logger.info(f"Tools Called: {', '.join(tools_used_list)}")
        logger.info(f"Response Length: {len(response_text)} chars")
        logger.info(f"Response Preview: {response_text[:200]}...")
        logger.info("=" * 80)
        
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
        _metrics['errors'] += 1
        total_time = time.time() - invocation_start_time
        
        logger.error("=" * 80)
        logger.error(f"RUNTIME ERROR")
        logger.error(f"Request ID: {request_id}")
        logger.error(f"Error: {error_msg}")
        logger.error(f"Time to Error: {total_time:.3f}s")
        logger.error("=" * 80, exc_info=True)
        
        return {
            "response": [f"Error: {error_msg}"]
        }
    except Exception as e:
        # Other unexpected errors
        error_msg = f"Unexpected error: {str(e)}"
        _metrics['errors'] += 1
        total_time = time.time() - invocation_start_time
        
        logger.error("=" * 80)
        logger.error(f"UNEXPECTED ERROR")
        logger.error(f"Request ID: {request_id}")
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error: {error_msg}")
        logger.error(f"Time to Error: {total_time:.3f}s")
        logger.error("=" * 80, exc_info=True)
        
        return {
            "response": [error_msg]
        }
    finally:
        # Log metrics periodically (every 10 invocations)
        if _metrics['invocations'] % 10 == 0:
            log_metrics()


def log_startup_info():
    """Log startup information for observability."""
    logger.info("=" * 80)
    logger.info("AGENTCORE RUNTIME STARTUP")
    logger.info("=" * 80)
    logger.info(f"Python Version: {sys.version.split()[0]}")
    logger.info(f"Region: {os.getenv('AWS_REGION', 'us-east-1')}")
    logger.info(f"Model ID: {os.getenv('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')}")
    
    # Check for configuration files
    config_files = {
        '.gateway-info.json': 'Gateway configuration',
        '.cognito-info.json': 'Cognito configuration',
        '.cognito-token.json': 'JWT token'
    }
    
    logger.info("Configuration Files:")
    for file, desc in config_files.items():
        exists = os.path.exists(file)
        status = "✓" if exists else "✗"
        logger.info(f"  {status} {file}: {desc} {'(found)' if exists else '(not found)'}")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    # Log startup information
    log_startup_info()
    
    # Run the AgentCore Runtime
    app.run()
