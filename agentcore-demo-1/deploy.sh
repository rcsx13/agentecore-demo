#!/bin/bash
#
# Deployment script for Amazon Bedrock AgentCore Runtime
#
# NOTA: Para despliegue en producción, usa el CLI tool 'agentcore'
# Ver: https://github.com/awslabs/amazon-bedrock-agentcore-samples
#

set -e

# Configuration
REGION=${AWS_REGION:-us-east-2}
AGENT_NAME=${AGENT_NAME:-agent_runtime_demo_1}

echo "Desplegando agente: $AGENT_NAME"
echo "Región: $REGION"
echo ""

# Check if agentcore CLI is installed
if ! command -v agentcore &> /dev/null; then
    echo "✗ CLI tool 'agentcore' no encontrado"
    echo ""
    echo "Instala el CLI tool con:"
    echo "  pip install bedrock-agentcore-starter-toolkit"
    exit 1
fi

echo "✓ CLI tool 'agentcore' encontrado"
echo ""

# Configure
echo "Configurando despliegue para el agente: $AGENT_NAME"
agentcore configure -e agent_runtime.py --name $AGENT_NAME

# Launch
echo ""
echo "Lanzando agente..."
agentcore launch --agent $AGENT_NAME

echo ""
echo "✓ Despliegue completado"

