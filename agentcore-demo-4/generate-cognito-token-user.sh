#!/bin/bash
#
# Genera token JWT con usuario/contraseña (InitiateAuth) - mismo flujo que la UI.
# Guarda en .cognito-token.json para usar con agentcore invoke.
#
# Uso: ./generate-cognito-token-user.sh [USERNAME] [PASSWORD]
#   o:  USER=user PASS=pass ./generate-cognito-token-user.sh
#

set -euo pipefail

INFO_FILE=".cognito-info.json"
OUT_FILE=".cognito-token.json"

if [ ! -f "$INFO_FILE" ]; then
  echo "Error: no se encontró $INFO_FILE"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq no está instalado"
  exit 1
fi

USERNAME="${1:-${USER:-}}"
PASSWORD="${2:-${PASS:-}}"

if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ]; then
  echo "Uso: $0 USERNAME PASSWORD"
  echo "  o: USER=mi_usuario PASS=mi_pass $0"
  exit 1
fi

CLIENT_ID=$(jq -r '.clientId' "$INFO_FILE")
CLIENT_SECRET=$(jq -r '.clientSecret' "$INFO_FILE")
USER_POOL_ID=$(jq -r '.userPoolId' "$INFO_FILE")
REGION="${USER_POOL_ID%%_*}"

if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "null" ]; then
  echo "Error: clientId vacío en $INFO_FILE"
  exit 1
fi

# SECRET_HASH para InitiateAuth si hay client secret
AUTH_PARAMS="USERNAME=$USERNAME,PASSWORD=$PASSWORD"
if [ -n "$CLIENT_SECRET" ] && [ "$CLIENT_SECRET" != "null" ]; then
  SECRET_HASH=$(echo -n "${USERNAME}${CLIENT_ID}" | openssl dgst -sha256 -hmac "$CLIENT_SECRET" -binary | base64)
  AUTH_PARAMS="${AUTH_PARAMS},SECRET_HASH=$SECRET_HASH"
fi

echo "Obteniendo token con InitiateAuth (USER_PASSWORD_AUTH)..."
RESP=$(aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters "$AUTH_PARAMS" \
  --region "$REGION" 2>&1) || true

ACCESS_TOKEN=$(echo "$RESP" | jq -r '.AuthenticationResult.AccessToken // empty')
ID_TOKEN=$(echo "$RESP" | jq -r '.AuthenticationResult.IdToken // empty')

if [ -z "$ACCESS_TOKEN" ] && [ -z "$ID_TOKEN" ]; then
  echo "Error: no se pudo obtener token"
  echo "$RESP" | jq -r '.message // .__type // .' 2>/dev/null || echo "$RESP"
  exit 1
fi

TOKEN="${ACCESS_TOKEN:-$ID_TOKEN}"
echo "{\"access_token\": \"$TOKEN\"}" | jq . > "$OUT_FILE"
echo "Token guardado en $OUT_FILE"
echo "Usar: export TOKEN=\$(jq -r '.access_token' $OUT_FILE)"
echo "      agentcore invoke '{\"prompt\":\"Hola\"}' --bearer-token \$TOKEN"
