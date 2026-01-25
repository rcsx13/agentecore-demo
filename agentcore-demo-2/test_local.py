"""
Test script for local agent testing
Tests the agent logic locally using the same agent_handler from agent_runtime.py
Note: This requires the same dependencies as agent_runtime.py (strands-agents, mcp, etc.)
"""

import json
import sys
import os

# Import agent_handler from agent_runtime
# Note: This will initialize the agent with Strands and MCP
try:
    from agent_runtime import agent_handler
except ImportError as e:
    print(f"Error importing agent_runtime: {e}")
    print("\nMake sure you have installed all dependencies:")
    print("  pip install -r requirements.txt")
    sys.exit(1)


if __name__ == "__main__":
    print("Testing agent locally with Strands and MCP tools.")
    print("Note: This requires AWS credentials configured for Bedrock.")
    print("Type 'exit' to quit.\n")
    
    if len(sys.argv) > 1:
        # Test with command line argument
        try:
            payload = json.loads(sys.argv[1])
            response = agent_handler(payload)
            result = response.get("response", [""])[0]
            print(result)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON - {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # Interactive mode
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
                    print()  # Empty line for readability
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
                print()  # Empty line for readability