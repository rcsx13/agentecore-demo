#!/bin/bash
#
# Deployment script for Amazon Bedrock AgentCore Runtime
#
# NOTA: Para despliegue en producción, usa el CLI tool 'agentcore'
# Ver: https://github.com/awslabs/amazon-bedrock-agentcore-samples
#

set -e

# Configuration
AGENT_NAME=${AGENT_NAME:-agent_runtime_demo_4}

echo "Desplegando agente: $AGENT_NAME"
echo ""

# Verificar que .gateway-info.json existe y cargar variables de entorno
if [ -f ".gateway-info.json" ]; then
    GATEWAY_URL=$(jq -r '.gatewayUrl' .gateway-info.json 2>/dev/null)
    GATEWAY_REGION=$(jq -r '.region' .gateway-info.json 2>/dev/null)
    
    if [ -n "$GATEWAY_URL" ] && [ "$GATEWAY_URL" != "null" ]; then
        export AGENTCORE_GATEWAY_URL="$GATEWAY_URL"
        echo "✓ Gateway URL configurada desde .gateway-info.json: $GATEWAY_URL"
    fi
    
    if [ -n "$GATEWAY_REGION" ] && [ "$GATEWAY_REGION" != "null" ]; then
        export AWS_REGION="$GATEWAY_REGION"
        echo "✓ AWS_REGION configurada desde .gateway-info.json: $GATEWAY_REGION"
    fi
else
    echo "⚠ Advertencia: .gateway-info.json no encontrado"
    echo "  Asegúrate de configurar AGENTCORE_GATEWAY_URL y AWS_REGION manualmente"
fi

# Verificar que AGENTCORE_GATEWAY_URL está configurada
if [ -z "$AGENTCORE_GATEWAY_URL" ]; then
    echo "✗ Error: AGENTCORE_GATEWAY_URL no está configurada"
    echo ""
    echo "Configura la variable de entorno:"
    echo "  export AGENTCORE_GATEWAY_URL=<gateway-url>"
    echo ""
    echo "O ejecuta primero: ./setup-gateway.sh"
    exit 1
fi

# Check if agentcore CLI is installed
if ! command -v agentcore &> /dev/null; then
    echo "✗ CLI tool 'agentcore' no encontrado"
    echo ""
    echo "Instala el CLI tool con:"
    echo "  pip install bedrock-agentcore-starter-toolkit"
    echo ""
    echo "O usando pipx (recomendado):"
    echo "  pipx install bedrock-agentcore-starter-toolkit"
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
echo "⚠ NOTA: Las variables de entorno deben estar disponibles en el runtime"
echo "   El CLI de agentcore no permite configurarlas durante launch"
echo "   Asegúrate de que AGENTCORE_GATEWAY_URL esté disponible en el runtime"
echo ""
agentcore launch --agent $AGENT_NAME

echo ""
echo "✓ Despliegue completado"
echo ""
echo "Para verificar el estado:"
echo "  agentcore status --agent $AGENT_NAME"
echo ""
echo "Para ver logs:"
echo "  aws logs tail /aws/bedrock-agentcore/runtime --follow --region ${AWS_REGION:-us-east-1}"

