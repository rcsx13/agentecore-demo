"""
MCP Gateway client: connection to AgentCore Gateway with JWT auth.
"""

import base64
import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator, Optional

import httpx
import requests
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient

from runtime_auth import inbound_token
from runtime_config import get_aws_session, is_local_deployment
from runtime_metrics import metrics

logger = logging.getLogger(__name__)

_mcp_client: Optional[MCPClient] = None


def create_gateway_mcp_client() -> MCPClient:
    """Create MCP client connected to AgentCore Gateway via HTTP with JWT token auth."""
    global _mcp_client

    if _mcp_client is not None:
        return _mcp_client

    try:
        gateway_url = os.getenv("AGENTCORE_GATEWAY_URL")

        if not gateway_url:
            gateway_info_path = ".gateway-info.json"
            if os.path.exists(gateway_info_path):
                try:
                    with open(gateway_info_path, "r") as f:
                        gateway_info = json.load(f)
                        gateway_url = gateway_info.get("gatewayUrl")
                except Exception as e:
                    logger.warning(f"No se pudo leer .gateway-info.json: {e}")

        if not gateway_url:
            gateway_url = "https://countries-gateway-fdvmwzb8ln.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
            logger.info("Usando URL del Gateway hardcodeada (fallback)")

        if not gateway_url:
            raise RuntimeError(
                "No se pudo obtener la URL del Gateway. "
                "Configura AGENTCORE_GATEWAY_URL o ejecuta './setup-gateway.sh'"
            )

        session = get_aws_session()
        region = session.region_name or "us-east-1"

        def create_client():
            try:
                logger.info(f"Creating streamablehttp_client for URL: {gateway_url}")

                token = None
                token_source = "none"

                # Local mode: usar token del request (mismo que inbound)
                if is_local_deployment():
                    req_token = inbound_token.get()
                    if req_token:
                        token = req_token
                        token_source = "request (inbound)"

                # Fallback: archivo o Cognito
                token_file = ".cognito-token.json"
                if not token and os.path.exists(token_file):
                    try:
                        with open(token_file, "r") as f:
                            token_data = json.load(f)
                            token = token_data.get("access_token")
                            if token:
                                token_length = len(token)
                                token_preview = (
                                    f"{token[:20]}...{token[-10:]}"
                                    if token_length > 30
                                    else token[:30]
                                )
                                logger.info(
                                    f"JWT token loaded from .cognito-token.json (length: {token_length}, preview: {token_preview})"
                                )
                                token_source = "file"
                    except Exception as e:
                        logger.warning(f"Failed to read token from {token_file}: {e}")

                if not token:
                    try:
                        cognito_info_file = ".cognito-info.json"
                        if os.path.exists(cognito_info_file):
                            with open(cognito_info_file, "r") as f:
                                cognito_info = json.load(f)

                            user_pool_id = cognito_info.get("userPoolId")
                            client_id = cognito_info.get("clientId")
                            client_secret = cognito_info.get("clientSecret")
                            scope_string = cognito_info.get("scopeString", "")

                            if user_pool_id and client_id:
                                cognito_domain = cognito_info.get("cognitoDomain")
                                if not cognito_domain:
                                    domain_prefix = user_pool_id.replace("_", "-").lower()
                                    cognito_domain = (
                                        f"{domain_prefix}.auth.{region}.amazoncognito.com"
                                    )

                                token_url = f"https://{cognito_domain}/oauth2/token"

                                auth_string = (
                                    f"{client_id}:{client_secret}"
                                    if client_secret
                                    else client_id
                                )
                                auth_bytes = auth_string.encode("utf-8")
                                auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")

                                headers = {
                                    "Content-Type": "application/x-www-form-urlencoded",
                                    "Authorization": f"Basic {auth_b64}",
                                }

                                data = {"grant_type": "client_credentials"}
                                response = requests.post(
                                    token_url, headers=headers, data=data, timeout=30
                                )

                                if response.status_code != 200 and scope_string:
                                    data["scope"] = scope_string
                                    response = requests.post(
                                        token_url, headers=headers, data=data, timeout=30
                                    )

                                response.raise_for_status()
                                token_data = response.json()
                                token = token_data.get("access_token")

                                if token:
                                    metrics["token_refresh_count"] += 1
                                    token_length = len(token)
                                    token_preview = (
                                        f"{token[:20]}...{token[-10:]}"
                                        if token_length > 30
                                        else token[:30]
                                    )
                                    logger.info(
                                        f"JWT token obtained from Cognito (length: {token_length}, preview: {token_preview})"
                                    )
                                    logger.info(
                                        f"Token refresh count: {metrics['token_refresh_count']}"
                                    )
                                    token_source = "cognito"
                    except Exception as e:
                        logger.warning(
                            f"Failed to get token from Cognito: {str(e)}",
                            exc_info=True,
                        )

                def create_httpx_client(*args, **kwargs):
                    client_headers = kwargs.get("headers") or {}
                    client_headers = dict(client_headers)
                    timeout = kwargs.get("timeout", httpx.Timeout(60.0))

                    if token:
                        client_headers["Authorization"] = f"Bearer {token}"
                        logger.info("✓ JWT token added to Authorization header")
                        logger.debug(
                            f"Authorization header: Bearer {token[:20]}...{token[-10:]}"
                        )
                    else:
                        logger.warning(
                            "⚠ No JWT token available - Gateway may reject the request"
                        )
                        logger.warning(
                            "Run ./setup-gateway-jwt.sh to configure Gateway with CUSTOM_JWT"
                        )

                    return httpx.AsyncClient(
                        headers=client_headers,
                        timeout=timeout,
                    )

                client = streamablehttp_client(
                    gateway_url,
                    httpx_client_factory=create_httpx_client,
                )
                logger.info("=" * 80)
                logger.info("MCP CLIENT CONFIGURATION")
                logger.info(f"Gateway URL: {gateway_url}")
                logger.info("Authentication: JWT Bearer Token")
                logger.info(f"Token Source: {token_source}")
                logger.info(f"Region: {region}")
                logger.info("=" * 80)
                logger.info(
                    "✓ streamablehttp_client created successfully with JWT token authentication"
                )
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
            logger.info(
                "Note: Gateway should be configured with CUSTOM_JWT authentication for JWT token to work"
            )
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
            metrics["mcp_connection_time"] = mcp_connection_time
            logger.info(
                f"✓ MCP client context entered successfully ({mcp_connection_time:.3f}s)"
            )

            logger.info("Listing tools from MCP server...")
            tools = _mcp_client.list_tools_sync()

            logger.info("=" * 80)
            logger.info(f"MCP TOOLS DISCOVERED: {len(tools)} tool(s)")
            for i, tool in enumerate(tools, 1):
                tool_name = getattr(tool, "name", "unknown")
                tool_desc = getattr(tool, "description", "No description")
                logger.info(f"  {i}. {tool_name}")
                logger.info(f"     Description: {tool_desc[:100]}...")
            logger.info("=" * 80)

            yield tools
    except Exception as e:
        logger.error(f"Failed to get tools from MCP: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback

        logger.error(traceback.format_exc())
        raise RuntimeError(f"MCP connection failed - {str(e)}")
