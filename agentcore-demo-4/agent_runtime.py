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

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from runtime_auth import setup_local_auth_middleware
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
def agent_handler(payload: dict) -> dict:
    """Entry point registrado en el runtime."""
    return agent_handler_impl(payload)


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
