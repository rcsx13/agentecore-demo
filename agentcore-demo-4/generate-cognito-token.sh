#!/bin/bash
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

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl no está instalado"
  exit 1
fi

CLIENT_ID=$(jq -r '.clientId' "$INFO_FILE")
CLIENT_SECRET=$(jq -r '.clientSecret' "$INFO_FILE")
COGNITO_DOMAIN=$(jq -r '.cognitoDomain' "$INFO_FILE")
SCOPE=$(jq -r '.scopeString' "$INFO_FILE")

if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "null" ]; then
  echo "Error: clientId vacío en $INFO_FILE"
  exit 1
fi

if [ -z "$COGNITO_DOMAIN" ] || [ "$COGNITO_DOMAIN" = "null" ]; then
  echo "Error: cognitoDomain vacío en $INFO_FILE"
  exit 1
fi

TOKEN_URL="https://${COGNITO_DOMAIN}/oauth2/token"
BASIC_AUTH=$(printf "%s:%s" "$CLIENT_ID" "$CLIENT_SECRET" | base64)

response=$(curl -s -w "\n%{http_code}" -X POST "$TOKEN_URL" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic $BASIC_AUTH" \
  -d "grant_type=client_credentials")

body=$(printf "%s" "$response" | sed '$d')
status=$(printf "%s" "$response" | tail -n 1)

if [ "$status" != "200" ] && [ -n "$SCOPE" ] && [ "$SCOPE" != "null" ]; then
  scope_encoded=$(printf "%s" "$SCOPE" | sed 's/ /%20/g')
  response=$(curl -s -w "\n%{http_code}" -X POST "$TOKEN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "Authorization: Basic $BASIC_AUTH" \
    -d "grant_type=client_credentials&scope=${scope_encoded}")
  body=$(printf "%s" "$response" | sed '$d')
  status=$(printf "%s" "$response" | tail -n 1)
fi

if [ "$status" != "200" ]; then
  echo "Error: HTTP $status"
  echo "$body"
  exit 1
fi

access_token=$(printf "%s" "$body" | jq -r '.access_token')
if [ -z "$access_token" ] || [ "$access_token" = "null" ]; then
  echo "Error: la respuesta no contiene access_token"
  echo "$body"
  exit 1
fi

printf "%s\n" "{\"access_token\": \"${access_token}\"}" > "$OUT_FILE"
echo "Token guardado en $OUT_FILE"
