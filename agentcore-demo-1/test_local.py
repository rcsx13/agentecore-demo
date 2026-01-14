"""
Test script for local agent testing
Tests the agent logic locally without requiring the Bedrock AgentCore SDK
"""

import json
import sys


# Define tools (same as in agent_runtime.py)
def get_weather() -> str:
    """Get current weather information."""
    return "sunny"


def calculate(operation: str, a: float, b: float) -> float:
    """Perform basic arithmetic operations."""
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else 0
    }
    return operations.get(operation, lambda x, y: 0)(a, b)


# Agent handler function (same logic as in agent_runtime.py)
def agent_handler(payload: dict) -> dict:
    """
    Entry point for the AgentCore Runtime.
    This function is called by the runtime when the agent is invoked.
    """
    user_input = payload.get("prompt", "")
    
    # Simple agent logic (replace with actual agent framework like Strands)
    response_text = f"Agent received: {user_input}"
    
    # Example tool usage
    if "weather" in user_input.lower():
        response_text = f"Weather is {get_weather()}"
    elif "calculate" in user_input.lower() or any(op in user_input for op in ["+", "-", "*", "/"]):
        # Simple calculation example
        response_text = "Use calculate tool for math operations"
    
    return {
        "response": [response_text]
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test with command line argument
        payload = json.loads(sys.argv[1])
        response = agent_handler(payload)
        print(response.get("response", [""])[0])
    else:
        # Interactive mode
        print("Testing agent locally. Type 'exit' to quit.\n")
        while True:
            try:
                user_input = input("> ").strip()
                if user_input.lower() in ["exit", "quit"]:
                    break
                if user_input:
                    payload = {"prompt": user_input}
                    response = agent_handler(payload)
                    result = response.get("response", [""])[0]
                    print(result)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
