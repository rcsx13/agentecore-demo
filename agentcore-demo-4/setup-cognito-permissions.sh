#!/bin/bash
#
# Script para agregar permisos de Cognito al usuario IAM
# Necesario para crear User Pools y configurar Gateway con CUSTOM_JWT
#

set -e

echo "Agregando permisos de Cognito al usuario IAM..."
echo ""

# Obtener el nombre del usuario actual
USER_NAME=$(aws sts get-caller-identity --query 'Arn' --output text | cut -d'/' -f2)

if [ -z "$USER_NAME" ]; then
    echo "✗ Error: No se pudo obtener el nombre del usuario IAM"
    exit 1
fi

echo "✓ Usuario encontrado: $USER_NAME"
echo ""

# Crear política para Cognito
POLICY_NAME="CognitoUserPoolManagementPolicy"
POLICY_DOC='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:CreateUserPool",
        "cognito-idp:ListUserPools",
        "cognito-idp:DescribeUserPool",
        "cognito-idp:UpdateUserPool",
        "cognito-idp:DeleteUserPool",
        "cognito-idp:CreateUserPoolClient",
        "cognito-idp:ListUserPoolClients",
        "cognito-idp:DescribeUserPoolClient",
        "cognito-idp:UpdateUserPoolClient",
        "cognito-idp:DeleteUserPoolClient",
                    "cognito-idp:CreateResourceServer",
                    "cognito-idp:ListResourceServers",
                    "cognito-idp:DescribeResourceServer",
                    "cognito-idp:UpdateResourceServer",
                    "cognito-idp:DeleteResourceServer",
                    "cognito-idp:CreateUserPoolDomain",
                    "cognito-idp:DescribeUserPoolDomain",
                    "cognito-idp:DeleteUserPoolDomain"
      ],
      "Resource": "*"
    }
  ]
}'

echo "Agregando política al usuario..."
aws iam put-user-policy \
    --user-name "$USER_NAME" \
    --policy-name "$POLICY_NAME" \
    --policy-document "$POLICY_DOC"

echo ""
echo "✓ Permisos de Cognito agregados al usuario: $USER_NAME"
echo ""
echo "La política permite:"
echo "  - Crear y gestionar User Pools"
echo "  - Crear y gestionar User Pool Clients"
echo "  - Crear y gestionar Resource Servers"
echo ""
echo "Ahora puedes ejecutar: ./setup-gateway-jwt.sh"
