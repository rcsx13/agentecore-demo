"""
Runtime observability: metrics and logging utilities.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

_metrics: Dict[str, Any] = {
    "invocations": 0,
    "tool_calls": 0,
    "errors": 0,
    "total_response_time": 0.0,
    "mcp_connection_time": 0.0,
    "token_refresh_count": 0,
}


def get_metrics() -> Dict[str, Any]:
    """Return the metrics dict (for use by other modules)."""
    return _metrics


# Alias for direct mutation access
metrics = _metrics


def log_metrics() -> None:
    """Log current observability metrics."""
    if _metrics["invocations"] <= 0:
        return
    avg_response_time = _metrics["total_response_time"] / _metrics["invocations"]
    tool_usage_rate = (
        (_metrics["tool_calls"] / _metrics["invocations"]) * 100
        if _metrics["invocations"] > 0
        else 0
    )
    error_rate = (
        (_metrics["errors"] / _metrics["invocations"]) * 100
        if _metrics["invocations"] > 0
        else 0
    )

    logger.info("=" * 80)
    logger.info("OBSERVABILITY METRICS")
    logger.info("=" * 80)
    logger.info(f"Total Invocations: {_metrics['invocations']}")
    logger.info(
        f"Tool Calls: {_metrics['tool_calls']} ({tool_usage_rate:.1f}% usage rate)"
    )
    logger.info(f"Errors: {_metrics['errors']} ({error_rate:.1f}% error rate)")
    logger.info(f"Average Response Time: {avg_response_time:.3f}s")
    logger.info(f"MCP Connection Time: {_metrics['mcp_connection_time']:.3f}s")
    logger.info(f"Token Refreshes: {_metrics['token_refresh_count']}")
    logger.info("=" * 80)


def find_graphql_queries(value: Any) -> list[str]:
    """Best-effort extraction of GraphQL query strings from nested data."""
    queries: list[str] = []

    if isinstance(value, str):
        lower = value.lower()
        if ("query" in lower or "mutation" in lower) and "{" in value and "}" in value:
            queries.append(value)
        return queries

    if isinstance(value, dict):
        query_value = value.get("query")
        if isinstance(query_value, str):
            queries.append(query_value)
        for item in value.values():
            queries.extend(find_graphql_queries(item))
        return queries

    if isinstance(value, (list, tuple)):
        for item in value:
            queries.extend(find_graphql_queries(item))
        return queries

    if hasattr(value, "__dict__"):
        queries.extend(find_graphql_queries(value.__dict__))

    return queries
