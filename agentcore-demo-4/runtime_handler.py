"""
Agent handler: entrypoint logic for invocations.
"""

import logging
import time
from datetime import datetime

from runtime_agent import create_agent
from runtime_metrics import find_graphql_queries, log_metrics, metrics
from runtime_mcp import initialize_mcp_tools

logger = logging.getLogger(__name__)


def agent_handler_impl(payload: dict) -> dict:
    """
    Entry point logic for the AgentCore Runtime.
    Uses Strands Agent with BedrockModel and MCP tools.
    """
    invocation_start_time = time.time()
    request_id = payload.get("requestId", "unknown")
    session_id = payload.get("sessionId", "unknown")

    metrics["invocations"] += 1

    try:
        user_input = payload.get("prompt", "")

        logger.info("=" * 80)
        logger.info("AGENT INVOCATION START")
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"User Input: {user_input}")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        logger.info("=" * 80)

        if not user_input:
            metrics["errors"] += 1
            logger.warning("Empty prompt received")
            return {"response": ["Error: No prompt provided"]}

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

            try:
                if hasattr(agent, "messages"):
                    messages_before = list(agent.messages) if agent.messages else []
                    logger.debug(f"Messages before agent call: {len(messages_before)}")
            except Exception as e:
                logger.debug(f"Could not access messages before: {e}")

            agent_call_start = time.time()
            logger.info("Calling agent with user input...")
            response = agent(user_input)
            agent_call_time = time.time() - agent_call_start
            logger.info(f"Agent call completed in {agent_call_time:.3f}s")

        if isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)

        tools_used = False
        tool_call_count = 0
        graphql_queries: list[str] = []
        try:
            if hasattr(agent, "messages") and agent.messages:
                messages_after = list(agent.messages) if agent.messages else []
                message_count_diff = len(messages_after) - len(messages_before)

                if message_count_diff > 0:
                    tools_used = True
                    tool_call_count = message_count_diff
                    logger.info(
                        f"Detected {tool_call_count} tool call(s) based on message count"
                    )

                for i, msg in enumerate(messages_after[len(messages_before) :], 1):
                    msg_str = str(msg).lower()
                    if any(
                        indicator in msg_str
                        for indicator in [
                            "tool",
                            "function_call",
                            "tool_call",
                            "mcp",
                        ]
                    ):
                        tools_used = True
                        if "executeGraphQLQuery" in str(msg):
                            tools_used_list.append(
                                "countries-graphql-target___executeGraphQLQuery"
                            )
                        logger.debug(
                            f"Tool usage detected in message {i}: {msg_str[:100]}"
                        )

                for msg in messages_after[len(messages_before) :]:
                    graphql_queries.extend(find_graphql_queries(msg))
        except Exception as e:
            logger.debug(f"Could not analyze messages for tool usage: {e}")
            response_lower = response_text.lower()
            if any(
                indicator in response_lower
                for indicator in [
                    '{"code"',
                    '"name"',
                    '"capital"',
                    '"currency"',
                    "graphql",
                ]
            ):
                tools_used = True
                tools_used_list.append("countries-graphql-target (detected from response)")
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

        if tools_used:
            metrics["tool_calls"] += tool_call_count if tool_call_count > 0 else 1

        total_time = time.time() - invocation_start_time
        metrics["total_response_time"] += total_time

        logger.info("=" * 80)
        logger.info("AGENT INVOCATION COMPLETE")
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

        if tools_used:
            final_response = f"[Model response using tool data] {response_text}"
        else:
            final_response = f"[Model response] {response_text}"

        return {"response": [final_response]}

    except RuntimeError as e:
        error_msg = str(e)
        metrics["errors"] += 1
        total_time = time.time() - invocation_start_time

        logger.error("=" * 80)
        logger.error("RUNTIME ERROR")
        logger.error(f"Request ID: {request_id}")
        logger.error(f"Error: {error_msg}")
        logger.error(f"Time to Error: {total_time:.3f}s")
        logger.error("=" * 80, exc_info=True)

        return {"response": [f"Error: {error_msg}"]}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        metrics["errors"] += 1
        total_time = time.time() - invocation_start_time

        logger.error("=" * 80)
        logger.error("UNEXPECTED ERROR")
        logger.error(f"Request ID: {request_id}")
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error: {error_msg}")
        logger.error(f"Time to Error: {total_time:.3f}s")
        logger.error("=" * 80, exc_info=True)

        return {"response": [error_msg]}
    finally:
        if metrics["invocations"] % 10 == 0:
            log_metrics()
