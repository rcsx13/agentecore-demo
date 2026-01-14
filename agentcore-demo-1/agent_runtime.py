"""
Amazon Bedrock AgentCore Runtime - Production Ready
Based on: https://github.com/awslabs/amazon-bedrock-agentcore-samples
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Initialize the AgentCore Runtime App
app = BedrockAgentCoreApp()


# Define tools
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


@app.entrypoint
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
    # Run the AgentCore Runtime
    app.run()
