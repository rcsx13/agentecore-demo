#!/bin/bash
#
# Script para agregar permisos de Gateway al rol de ejecución del runtime
#

set -e

echo "Agregando permisos de Gateway al rol de ejecución..."
echo ""

# Obtener el nombre del rol de ejecución (el primero que encuentre)
ROLE_NAME=$(aws iam list-roles --query "Roles[?contains(RoleName, 'AmazonBedrockAgentCoreSDKRuntime')].RoleName" --output text | tr '\t' '\n' | head -1)

if [ -z "$ROLE_NAME" ]; then
    echo "✗ Error: No se encontró el rol de ejecución del runtime"
    echo "   Asegúrate de que el runtime esté desplegado primero"
    exit 1
fi

echo "✓ Rol encontrado: $ROLE_NAME"
echo ""

# Crear política para Gateway
POLICY_NAME="GatewayInvokePolicy"
POLICY_DOC='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:InvokeGateway"
      ],
      "Resource": "*"
    }
  ]
}'

echo "Agregando política al rol..."
aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document "$POLICY_DOC"

echo ""
echo "✓ Permisos de Gateway agregados al rol: $ROLE_NAME"
echo ""
echo "La política permite invocar el AgentCore Gateway."
echo "El runtime debería poder conectarse al Gateway ahora."
