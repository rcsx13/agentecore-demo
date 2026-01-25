#!/bin/bash
#
# Script para otorgar permisos ECR al rol de ejecución del runtime de Bedrock AgentCore
# Permite que el runtime acceda a imágenes Docker en ECR durante su ejecución
#
# Uso:
#   ./grant-runtime-ecr-permissions.sh
#

set -e

ROLE_NAME="AmazonBedrockAgentCoreSDKRuntime-us-east-1-a3dcd2f108"
POLICY_NAME="BedrockAgentCoreExecutionRoleECRPolicy"

# Obtener Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo "Agregando permisos de ECR al rol de ejecución: $ROLE_NAME"
echo ""

# Verificar que el rol existe
if ! aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    echo "Error: El rol '$ROLE_NAME' no existe"
    echo "Ejecuta primero el despliegue para crear el rol."
    exit 1
fi

echo "✓ Rol encontrado: $ROLE_ARN"
echo ""

# Crear política inline directamente en el script
POLICY_DOCUMENT=$(cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

# Adjuntar política inline al rol
echo "Adjuntando política de ECR al rol..."
aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document "$POLICY_DOCUMENT"

echo "✓ Permisos de ECR agregados al rol de ejecución"
echo ""
echo "Ahora puedes reintentar el despliegue con: ./deploy.sh"

