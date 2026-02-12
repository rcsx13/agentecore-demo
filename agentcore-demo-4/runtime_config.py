"""
Runtime configuration: AWS session, environment detection.
"""

import os
import logging

import boto3

logger = logging.getLogger(__name__)

_boto_session: boto3.Session | None = None


def get_aws_session() -> boto3.Session:
    """Get or create AWS boto3 session."""
    global _boto_session

    if _boto_session is None:
        region = os.getenv("AWS_REGION", "us-east-1")
        _boto_session = boto3.Session(region_name=region)
        logger.info(f"AWS session created for region: {region}")

    return _boto_session


def is_local_deployment() -> bool:
    """True when running locally; JWT validation happens via middleware."""
    return os.getenv("JWT_LOCAL_VALIDATION", "false").lower() in ("true", "1", "yes")
