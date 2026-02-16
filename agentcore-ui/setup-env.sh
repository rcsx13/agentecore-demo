#!/bin/bash
#
# Configura .env.local del agentcore-ui desde agentcore-demo-4
# Ejecutar desde agentcore-ui/
#
# Uso:
#   ./setup-env.sh           # apunta a runtime local (Docker)
#   ./setup-env.sh --aws     # apunta a runtime desplegado en AgentCore (AWS)
#

set -e

USE_AWS=false
if [ "${1:-}" = "--aws" ]; then
  USE_AWS=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="${SCRIPT_DIR}/../agentcore-demo-4"
ENV_FILE="${SCRIPT_DIR}/.env.local"

if [ ! -f "${DEMO_DIR}/.cognito-info.json" ]; then
  echo "Error: no se encontró ${DEMO_DIR}/.cognito-info.json"
  echo "Ejecuta primero el setup de Cognito en agentcore-demo-4"
  exit 1
fi

COGNITO_CLIENT_ID=$(jq -r '.clientId' "${DEMO_DIR}/.cognito-info.json")
COGNITO_CLIENT_SECRET=$(jq -r '.clientSecret' "${DEMO_DIR}/.cognito-info.json")

# Extraer región del userPoolId (us-east-1_xxx -> us-east-1)
USER_POOL_ID=$(jq -r '.userPoolId' "${DEMO_DIR}/.cognito-info.json")
COGNITO_REGION="${USER_POOL_ID%%_*}"

# AGENTCORE_URL: local o AWS
if [ "$USE_AWS" = true ]; then
  if [ ! -f "${DEMO_DIR}/.bedrock_agentcore.yaml" ]; then
    echo "Error: no se encontró ${DEMO_DIR}/.bedrock_agentcore.yaml"
    echo "Despliega primero el agente con: cd agentcore-demo-4 && ./deploy.sh"
    exit 1
  fi
  DEFAULT_AGENT=$(grep '^default_agent:' "${DEMO_DIR}/.bedrock_agentcore.yaml" | awk '{print $2}')
  if [ -z "$DEFAULT_AGENT" ]; then
    DEFAULT_AGENT="agent_runtime_demo_4"
  fi
  AGENT_ARN=$(grep "agent_arn:.*${DEFAULT_AGENT}" "${DEMO_DIR}/.bedrock_agentcore.yaml" | head -1 | sed 's/.*agent_arn:[[:space:]]*//' | tr -d '"' | tr -d "'")
  if [ -z "$AGENT_ARN" ]; then
    echo "Error: no se encontró agent_arn en .bedrock_agentcore.yaml"
    exit 1
  fi
  AWS_REGION="${COGNITO_REGION}"
  ESCAPED_ARN=$(echo "$AGENT_ARN" | sed 's/:/%3A/g; s|/|%2F|g')
  AGENTCORE_URL="https://bedrock-agentcore.${AWS_REGION}.amazonaws.com/runtimes/${ESCAPED_ARN}/invocations?qualifier=DEFAULT"
  echo "✓ Modo AWS: apuntando a runtime desplegado"
  echo "  Agent ARN: $AGENT_ARN"
else
  AGENTCORE_URL="${AGENTCORE_URL:-http://localhost:9001/invocations}"
  echo "✓ Modo local: apuntando a Docker"
fi

cat > "${ENV_FILE}" << EOF
# Generado por setup-env.sh - agentcore-ui
# Modo: $([ "$USE_AWS" = true ] && echo "AWS (runtime desplegado)" || echo "Local (Docker)")

# Runtime
AGENTCORE_URL=${AGENTCORE_URL}

# Cognito (desde agentcore-demo-4/.cognito-info.json)
COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID}
COGNITO_CLIENT_SECRET=${COGNITO_CLIENT_SECRET}
COGNITO_REGION=${COGNITO_REGION}
EOF

echo ""
echo "✓ .env.local creado en ${ENV_FILE}"
echo ""
if [ "$USE_AWS" = true ]; then
  echo "La UI invocará el runtime desplegado en AgentCore con el JWT de Cognito."
  echo "Asegúrate de que el agente tenga customJWTAuthorizer configurado (deploy.sh lo hace)."
else
  echo "Para desarrollo con runtime local:"
  echo "  1. Levanta el runtime Docker en agentcore-demo-4"
  echo "  2. npm run dev"
fi
echo ""
