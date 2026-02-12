"""
Agent factory: BedrockModel and Strands Agent creation.
"""

import logging
import os
from typing import Optional

from strands import Agent
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

_bedrock_model: Optional[BedrockModel] = None


def get_or_create_bedrock_model() -> BedrockModel:
    """Get or create the Bedrock model instance."""
    global _bedrock_model

    if _bedrock_model is None:
        model_id = os.getenv(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        )
        _bedrock_model = BedrockModel(
            model_id=model_id,
            temperature=0.3,
            top_p=0.8,
        )
        logger.info("=" * 80)
        logger.info("BEDROCK MODEL INITIALIZED")
        logger.info(f"Model: {model_id}")
        logger.info("Temperature: 0.3")
        logger.info("Top P: 0.8")
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
        tool_name = getattr(tool, "name", "unknown")
        logger.info(f"  - {tool_name}")
    logger.info("=" * 80)

    return agent
