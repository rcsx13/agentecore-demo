#!/bin/bash
#
# Configura el agente con JWT (Cognito) - valores hardcodeados desde .cognito-info.json
# Ejecutar desde agentcore-demo-4
#

set -e

AGENT_NAME=${AGENT_NAME:-agent_runtime_demo_4}

# Usar agentcore del venv si existe
AGENTCORE_CMD="agentcore"
if [ -f ".venv/bin/agentcore" ]; then
    AGENTCORE_CMD=".venv/bin/agentcore"
fi

# Valores de .cognito-info.json (us-east-1_Dklrwiv8d)
DISCOVERY_URL="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Dklrwiv8d/.well-known/openid-configuration"
CLIENT_ID="5sbkks0505507jlg917ifl8gsp"

echo "Configurando $AGENT_NAME con Cognito JWT..."
$AGENTCORE_CMD configure -e agent_runtime.py --name "$AGENT_NAME" \
  --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$CLIENT_ID\"]}}"

echo "✓ Configuración completada"
echo ""
echo "Para desplegar: $AGENTCORE_CMD launch --agent $AGENT_NAME"
