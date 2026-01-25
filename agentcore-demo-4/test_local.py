"""
Test script for local agent testing
Tests the agent logic locally using the same agent_handler from agent_runtime.py
Note: This requires the same dependencies as agent_runtime.py (strands-agents, mcp, etc.)
"""

import json
import sys
import os

# If a local venv exists, re-run using it before importing runtime deps.
VENV_PYTHON = os.path.join(".venv", "bin", "python")
if os.path.exists(VENV_PYTHON) and not sys.executable.endswith(VENV_PYTHON):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

# Import agent_handler from agent_runtime
# Note: This will initialize the agent with Strands and MCP
try:
    from agent_runtime import agent_handler
except ImportError as e:
    print(f"Error importing agent_runtime: {e}")
    print("\nMake sure you have installed all dependencies in the correct environment:")
    print("  python3 -m venv .venv --copies")
    print("  source .venv/bin/activate")
    print("  pip install -r requirements.txt")
    print("\nThen run with the venv Python:")
    print("  .venv/bin/python test_local.py '{\"prompt\":\"Hello\"}'")
    venv_python = os.path.join(".venv", "bin", "python")
    if os.path.exists(venv_python) and not sys.executable.endswith(venv_python):
        print(f"\nDetected .venv but not using it. Current Python: {sys.executable}")
    sys.exit(1)


if __name__ == "__main__":

    print("Testing agent locally with Strands and MCP tools.")
    print("Note: This requires AWS credentials configured for Bedrock.")
    print("Type 'exit' to quit.\n")

    if not os.getenv("AGENTCORE_GATEWAY_URL") or not os.getenv("AWS_REGION"):
        gateway_info_path = ".gateway-info.json"
        if os.path.exists(gateway_info_path):
            try:
                with open(gateway_info_path, "r") as f:
                    gateway_info = json.load(f)
                if not os.getenv("AGENTCORE_GATEWAY_URL"):
                    gateway_url = gateway_info.get("gatewayUrl")
                    if gateway_url:
                        os.environ["AGENTCORE_GATEWAY_URL"] = gateway_url
                if not os.getenv("AWS_REGION"):
                    region = gateway_info.get("region")
                    if region:
                        os.environ["AWS_REGION"] = region
            except Exception as e:
                print(f"Warning: Failed to read {gateway_info_path}: {e}")

    missing_env = []
    if not os.getenv("AGENTCORE_GATEWAY_URL"):
        missing_env.append("AGENTCORE_GATEWAY_URL")
    if not os.getenv("AWS_REGION"):
        missing_env.append("AWS_REGION")
    if missing_env:
        print("Warning: Missing environment variables:")
        print(f"  {', '.join(missing_env)}")
        print("Set them before running, for example:")
        print("  export AGENTCORE_GATEWAY_URL=<gateway-url>")
        print("  export AWS_REGION=us-east-1")
        print()
        sys.exit(1)
    
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
