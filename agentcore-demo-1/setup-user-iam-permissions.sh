#!/bin/bash
#
# Script para configurar permisos IAM del usuario que despliega Bedrock AgentCore Runtime
# Crea y adjunta una política IAM con permisos de ECR, IAM, CodeBuild, S3, Logs y Bedrock
# 
# Uso:
#   ./setup-user-iam-permissions.sh <USER_NAME>
#
# Ejemplo:
#   ./setup-user-iam-permissions.sh rcabrera-admin
#

set -e

USER_NAME=${1:-rcabrera-admin}
POLICY_NAME="BedrockAgentCoreDeploymentPolicy"
POLICY_FILE="iam-policy.json"

if [ ! -f "$POLICY_FILE" ]; then
    echo "Error: No se encontró el archivo $POLICY_FILE"
    exit 1
fi

echo "Creando política IAM: $POLICY_NAME"
echo "Para usuario: $USER_NAME"
echo ""

# Verificar que el usuario existe
if ! aws iam get-user --user-name "$USER_NAME" &> /dev/null; then
    echo "Error: El usuario '$USER_NAME' no existe"
    exit 1
fi

# Obtener Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

# Crear la política
echo "1. Creando o actualizando política IAM..."
CREATE_OUTPUT=$(aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://$POLICY_FILE" \
    --description "Permisos necesarios para desplegar Bedrock AgentCore Runtime" \
    2>&1) || CREATE_ERROR=$?

if [[ -z "$CREATE_ERROR" ]]; then
    # Política creada exitosamente
    POLICY_ARN=$(echo "$CREATE_OUTPUT" | grep -oP 'arn:aws:iam::[^"]+')
    if [[ -z "$POLICY_ARN" ]]; then
        POLICY_ARN=$(aws iam create-policy \
            --policy-name "$POLICY_NAME" \
            --policy-document "file://$POLICY_FILE" \
            --description "Permisos necesarios para desplegar Bedrock AgentCore Runtime" \
            --query 'Policy.Arn' \
            --output text)
    fi
    echo "   ✓ Política creada: $POLICY_ARN"
elif aws iam get-policy --policy-arn "$POLICY_ARN" &> /dev/null; then
    echo "   La política ya existe, actualizando con el contenido de $POLICY_FILE..."
    # Intentar crear una nueva versión de la política
    VERSION_OUTPUT=$(aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document "file://$POLICY_FILE" \
        --set-as-default 2>&1) || VERSION_ERROR=$?
    
    if [[ -z "$VERSION_ERROR" ]]; then
        echo "   ✓ Política actualizada: $POLICY_ARN"
    elif [[ "$VERSION_OUTPUT" == *"LimitExceeded"* ]] || [[ "$VERSION_OUTPUT" == *"too many versions"* ]]; then
        echo "   ⚠ Hay demasiadas versiones (máximo 5). Eliminando versión más antigua..."
        # Obtener la versión más antigua (excluyendo la versión por defecto)
        OLDEST_VERSION=$(aws iam list-policy-versions \
            --policy-arn "$POLICY_ARN" \
            --query 'Versions[?IsDefaultVersion==`false`].VersionId | [0]' \
            --output text)
        if [[ "$OLDEST_VERSION" != "None" ]] && [[ -n "$OLDEST_VERSION" ]]; then
            aws iam delete-policy-version \
                --policy-arn "$POLICY_ARN" \
                --version-id "$OLDEST_VERSION" > /dev/null 2>&1
            # Intentar crear la nueva versión nuevamente
            aws iam create-policy-version \
                --policy-arn "$POLICY_ARN" \
                --policy-document "file://$POLICY_FILE" \
                --set-as-default > /dev/null 2>&1
            echo "   ✓ Política actualizada: $POLICY_ARN"
        else
            echo "   ✗ Error: No se pudo eliminar una versión anterior. Elimina manualmente una versión."
            exit 1
        fi
    else
        echo "   ✗ Error actualizando la política: $VERSION_OUTPUT"
        exit 1
    fi
else
    echo "   ✗ Error: $CREATE_OUTPUT"
    echo "   Verifica que tengas permisos de IAM."
    exit 1
fi

echo ""

# Adjuntar política al usuario
echo "2. Adjuntando política al usuario '$USER_NAME'..."
if aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn "$POLICY_ARN" 2>&1; then
    echo "   ✓ Política adjuntada exitosamente"
else
    # Verificar si ya está adjuntada
    if aws iam list-attached-user-policies --user-name "$USER_NAME" --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN']" --output text | grep -q "$POLICY_ARN"; then
        echo "   ✓ La política ya estaba adjuntada (actualizada con nueva versión)"
    else
        echo "   ✗ Error adjuntando la política."
        exit 1
    fi
fi

echo ""
echo "✓ Proceso completado"
echo ""
echo "Nota: Los cambios de permisos pueden tardar algunos segundos en propagarse."
echo "Puedes verificar los permisos con:"
echo "  aws iam list-attached-user-policies --user-name $USER_NAME"
