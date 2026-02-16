"""
Amazon Bedrock AgentCore Runtime - Orquestador principal.

Entry point para despliegue local (Docker) y AWS AgentCore.
Usa Strands Agents con BedrockModel y MCP tools via AgentCore Gateway.

Módulos:
- runtime_config: AWS session, detección local/AWS
- runtime_metrics: Métricas y logging
- runtime_mcp: Cliente MCP Gateway (JWT auth)
- runtime_agent: BedrockModel, Strands Agent
- runtime_handler: Lógica del entrypoint
"""

import logging
import os
import sys

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext

from runtime_auth import inbound_token, setup_local_auth_middleware
from runtime_handler import agent_handler_impl

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Middleware JWT solo en modo local (JWT_LOCAL_VALIDATION=true)
_middleware: list = []
if mw := setup_local_auth_middleware():
    _middleware.append(mw)
elif os.getenv("JWT_LOCAL_VALIDATION", "").lower() not in ("true", "1", "yes"):
    logger.info("Auth: AWS mode - JWT handled by AgentCore infrastructure")

app = BedrockAgentCoreApp(middleware=_middleware)


@app.entrypoint
def agent_handler(payload: dict, context: RequestContext | None = None) -> dict:
    """Entry point registrado en el runtime."""
    if context and context.request_headers:
        auth = context.request_headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            inbound_token.set(auth[7:].strip())
    try:
        return agent_handler_impl(payload)
    finally:
        inbound_token.set(None)


def log_startup_info() -> None:
    """Log startup information for observability."""
    logger.info("=" * 80)
    logger.info("AGENTCORE RUNTIME STARTUP")
    logger.info("=" * 80)
    logger.info(f"Python Version: {sys.version.split()[0]}")
    logger.info(f"Region: {os.getenv('AWS_REGION', 'us-east-1')}")
    logger.info(
        f"Model ID: {os.getenv('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')}"
    )

    config_files = {
        ".gateway-info.json": "Gateway configuration",
        ".cognito-info.json": "Cognito configuration",
        ".cognito-token.json": "JWT token",
    }

    logger.info("Configuration Files:")
    for file, desc in config_files.items():
        exists = os.path.exists(file)
        status = "✓" if exists else "✗"
        logger.info(f"  {status} {file}: {desc} {'(found)' if exists else '(not found)'}")

    logger.info("=" * 80)


if __name__ == "__main__":
    log_startup_info()
    app.run()
