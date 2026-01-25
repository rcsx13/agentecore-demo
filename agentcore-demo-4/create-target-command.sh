#!/bin/bash
#
# Comando para crear el target después de instalar agentcore CLI
#
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GATEWAY_ID=$(cat .gateway-info.json | jq -r '.gatewayId')
REGION=$(cat .gateway-info.json | jq -r '.region')
GATEWAY_URL=$(cat .gateway-info.json | jq -r '.gatewayUrl')
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/AgentCoreGatewayRole-countries-gateway"
GATEWAY_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:gateway/${GATEWAY_ID}"

TARGET_PAYLOAD=$(cat gateway-config.json | jq -c '{inlinePayload: (. | tostring)}')
CREDENTIALS='{"api_key":"public","credential_location":"HEADER","credential_parameter_name":"x-api-key"}'

echo "Creando target con endpoint /graphql..."
agentcore gateway create-mcp-gateway-target \
  --gateway-arn "$GATEWAY_ARN" \
  --gateway-url "$GATEWAY_URL" \
  --role-arn "$ROLE_ARN" \
  --region "$REGION" \
  --name "countries-graphql-target" \
  --target-type "openApiSchema" \
  --target-payload "$TARGET_PAYLOAD" \
  --credentials "$CREDENTIALS"

echo ""
echo "✓ Target creado. El endpoint ahora es /graphql"
