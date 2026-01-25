#!/bin/bash
#
# Script para actualizar las variables de entorno del runtime desplegado
#

set -e

AGENT_NAME=${AGENT_NAME:-agent_runtime_demo_4}

# Cargar variables desde .gateway-info.json
if [ -f ".gateway-info.json" ]; then
    GATEWAY_URL=$(jq -r '.gatewayUrl' .gateway-info.json 2>/dev/null)
    AWS_REGION=$(jq -r '.region' .gateway-info.json 2>/dev/null)
    
    if [ -n "$GATEWAY_URL" ] && [ "$GATEWAY_URL" != "null" ]; then
        export AGENTCORE_GATEWAY_URL="$GATEWAY_URL"
    fi
    
    if [ -n "$AWS_REGION" ] && [ "$AWS_REGION" != "null" ]; then
        export AWS_REGION="$AWS_REGION"
    fi
fi

if [ -z "$AGENTCORE_GATEWAY_URL" ]; then
    echo "✗ Error: AGENTCORE_GATEWAY_URL no está configurada"
    exit 1
fi

echo "Actualizando variables de entorno para: $AGENT_NAME"
echo "AGENTCORE_GATEWAY_URL=$AGENTCORE_GATEWAY_URL"
echo "AWS_REGION=${AWS_REGION:-us-east-1}"
echo ""

# Obtener el ID del runtime
RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
    --query "agentRuntimes[?agentRuntimeName=='${AGENT_NAME}'].agentRuntimeId" \
    --output text \
    --region ${AWS_REGION:-us-east-1} | head -1)

if [ -z "$RUNTIME_ID" ] || [ "$RUNTIME_ID" = "None" ]; then
    echo "✗ Error: No se encontró el runtime '$AGENT_NAME'"
    exit 1
fi

echo "✓ Runtime encontrado: $RUNTIME_ID"
echo ""

# Nota: El CLI de agentcore no soporta actualizar variables de entorno directamente
# Necesitas recrear el runtime con las variables de entorno
echo "⚠ El CLI de agentcore no permite actualizar variables de entorno en un runtime existente"
echo ""
echo "Opciones:"
echo ""
echo "1. Recrear el runtime con las variables de entorno:"
echo "   export AGENTCORE_GATEWAY_URL=$AGENTCORE_GATEWAY_URL"
echo "   export AWS_REGION=${AWS_REGION:-us-east-1}"
echo "   ./deploy.sh"
echo ""
echo "2. O usar AWS CLI directamente para actualizar (si está disponible):"
echo "   aws bedrock-agentcore-control update-agent-runtime \\"
echo "     --agent-runtime-id $RUNTIME_ID \\"
echo "     --environment-variables '{\"AGENTCORE_GATEWAY_URL\":\"$AGENTCORE_GATEWAY_URL\",\"AWS_REGION\":\"${AWS_REGION:-us-east-1}\"}' \\"
echo "     --region ${AWS_REGION:-us-east-1}"
echo ""
