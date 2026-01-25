#!/bin/bash
#
# Script para recrear el target del Gateway con el endpoint /graphql corregido
#
set -e

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GATEWAY_ID=$(cat .gateway-info.json | jq -r '.gatewayId')
REGION=$(cat .gateway-info.json | jq -r '.region')
GATEWAY_URL=$(cat .gateway-info.json | jq -r '.gatewayUrl')
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/AgentCoreGatewayRole-countries-gateway"
GATEWAY_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:gateway/${GATEWAY_ID}"

echo "Recreando target con endpoint /graphql..."
echo "Gateway ID: $GATEWAY_ID"
echo "Region: $REGION"
echo ""

# Eliminar target existente si existe
TARGET_ID=$(aws bedrock-agentcore-control list-gateway-targets \
    --gateway-identifier $GATEWAY_ID \
    --region $REGION \
    --query 'items[0].targetId' \
    --output text 2>/dev/null || echo "")

if [ "$TARGET_ID" != "None" ] && [ -n "$TARGET_ID" ]; then
    echo "Eliminando target existente: $TARGET_ID"
    aws bedrock-agentcore-control delete-gateway-target \
        --gateway-identifier $GATEWAY_ID \
        --target-id $TARGET_ID \
        --region $REGION
    echo "✓ Target eliminado"
    echo "Esperando 5 segundos..."
    sleep 5
else
    echo "No hay target para eliminar"
fi

# Crear payload del target
TARGET_PAYLOAD=$(cat gateway-config.json | jq -c '{inlinePayload: (. | tostring)}')
CREDENTIALS='{"api_key":"public","credential_location":"HEADER","credential_parameter_name":"x-api-key"}'

# Crear nuevo target usando agentcore CLI si está disponible, sino usar AWS API
if command -v agentcore &> /dev/null; then
    echo "Creando target usando agentcore CLI..."
    agentcore gateway create-mcp-gateway-target \
        --gateway-arn "$GATEWAY_ARN" \
        --gateway-url "$GATEWAY_URL" \
        --role-arn "$ROLE_ARN" \
        --region "$REGION" \
        --name "countries-graphql-target" \
        --target-type "openApiSchema" \
        --target-payload "$TARGET_PAYLOAD" \
        --credentials "$CREDENTIALS"
    echo "✓ Target creado"
else
    echo "⚠ agentcore CLI no está disponible"
    echo "Por favor instala: pipx install bedrock-agentcore-starter-toolkit"
    echo "O ejecuta este script desde un entorno donde agentcore esté disponible"
    exit 1
fi

echo ""
echo "✓ Target recreado exitosamente"
echo "El endpoint ahora es /graphql en lugar de /"
