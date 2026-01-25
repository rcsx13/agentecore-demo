#!/bin/bash
#
# Script para recrear AgentCore Gateway con autenticación CUSTOM_JWT (Cognito)
# Basado en: https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/02-AgentCore-gateway/02-transform-apis-into-mcp-tools/01-transform-openapi-into-mcp-tools/01-openapis-into-mcp-api-key.ipynb
#
# Uso:
#   ./setup-gateway-jwt.sh [GATEWAY_NAME] [REGION]
#

set -e

GATEWAY_NAME=${1:-countries-gateway}
AWS_REGION=${2:-${AWS_REGION:-us-east-1}}
TARGET_NAME="countries-graphql-target"
OPENAPI_SCHEMA_FILE="gateway-config.json"

echo "Configurando AgentCore Gateway con JWT (Cognito): $GATEWAY_NAME"
echo "Región: $AWS_REGION"
echo ""

# Verificar que el archivo OpenAPI existe
if [ ! -f "$OPENAPI_SCHEMA_FILE" ]; then
    echo "Error: No se encontró el archivo $OPENAPI_SCHEMA_FILE"
    exit 1
fi

# Verificar que AWS CLI está configurado
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS CLI no está configurado o las credenciales no son válidas"
    exit 1
fi

# Obtener Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_NAME="AgentCoreGatewayRole-${GATEWAY_NAME}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo "1. Creando/verificando rol IAM para el Gateway..."
# El rol ya debería existir del setup anterior, pero verificamos
if ! aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    echo "   Creando rol IAM..."
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' \
        --description "Rol para AgentCore Gateway"
    
    # Agregar políticas para el Gateway
    # Política para hacer llamadas HTTP
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "GatewayHTTPPolicy" \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["execute-api:Invoke"],
                "Resource": "*"
            }]
        }'
    
    # Política para credential providers (necesaria para targets con API keys)
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "GatewayCredentialProviderPolicy" \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetResourceApiKey"
                    ],
                    "Resource": "*"
                }
            ]
        }'
    
    # Política para Secrets Manager (necesaria para obtener API keys)
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "GatewaySecretsManagerPolicy" \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret"
                    ],
                    "Resource": "arn:aws:secretsmanager:*:*:secret:bedrock-agentcore*"
                }
            ]
        }'
    echo "   ✓ Rol creado"
else
    echo "   ✓ Rol ya existe"
fi

echo ""
echo "2. Creando/verificando Cognito User Pool..."

# Crear Cognito User Pool usando Python
python3 << EOF
import boto3
import json
import sys

cognito = boto3.client('cognito-idp', region_name='${AWS_REGION}')
gateway_client = boto3.client('bedrock-agentcore-control', region_name='${AWS_REGION}')

USER_POOL_NAME = "agentcore-gateway-pool-${GATEWAY_NAME}"
RESOURCE_SERVER_ID = "agentcore-gateway-${GATEWAY_NAME}"
RESOURCE_SERVER_NAME = "AgentCore Gateway ${GATEWAY_NAME}"
CLIENT_NAME = "agentcore-gateway-client-${GATEWAY_NAME}"
SCOPES = [
    {"ScopeName": "gateway:read", "ScopeDescription": "Read access"},
    {"ScopeName": "gateway:write", "ScopeDescription": "Write access"}
]

# Helper functions (simplified versions)
def get_or_create_user_pool(cognito_client, pool_name):
    """Get or create Cognito User Pool."""
    try:
        pools = cognito_client.list_user_pools(MaxResults=50)
        for pool in pools.get('UserPools', []):
            if pool['Name'] == pool_name:
                return pool['Id']
        
        # Create new pool
        response = cognito_client.create_user_pool(
            PoolName=pool_name,
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8,
                    'RequireUppercase': False,
                    'RequireLowercase': False,
                    'RequireNumbers': False,
                    'RequireSymbols': False
                }
            },
            AutoVerifiedAttributes=['email']
        )
        return response['UserPool']['Id']
    except Exception as e:
        print(f"Error creating user pool: {e}")
        raise

def get_or_create_resource_server(cognito_client, user_pool_id, identifier, name, scopes):
    """Get or create Cognito Resource Server."""
    try:
        servers = cognito_client.list_resource_servers(UserPoolId=user_pool_id, MaxResults=50)
        for server in servers.get('ResourceServers', []):
            if server['Identifier'] == identifier:
                return server
        
        # Create new resource server
        response = cognito_client.create_resource_server(
            UserPoolId=user_pool_id,
            Identifier=identifier,
            Name=name,
            Scopes=scopes
        )
        return response['ResourceServer']
    except Exception as e:
        print(f"Error creating resource server: {e}")
        raise

def get_or_create_m2m_client(cognito_client, user_pool_id, client_name, resource_server_id):
    """Get or create Machine-to-Machine client."""
    try:
        clients = cognito_client.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=50)
        for client in clients.get('UserPoolClients', []):
            if client['ClientName'] == client_name:
                    client_details = cognito_client.describe_user_pool_client(
                        UserPoolId=user_pool_id,
                        ClientId=client['ClientId']
                    )
                    client_secret = client_details['UserPoolClient'].get('ClientSecret', None)
                    # Check if AllowedOAuthFlowsUserPoolClient is True, if not, update it
                    allowed_flows_user_pool = client_details['UserPoolClient'].get('AllowedOAuthFlowsUserPoolClient', False)
                    if not allowed_flows_user_pool:
                        print(f"   Actualizando cliente para habilitar OAuth flows...")
                        # When updating, we need to provide AllowedOAuthFlows and AllowedOAuthScopes
                        cognito_client.update_user_pool_client(
                            UserPoolId=user_pool_id,
                            ClientId=client['ClientId'],
                            AllowedOAuthFlows=['client_credentials'],
                            AllowedOAuthScopes=[f'{resource_server_id}/gateway:read', f'{resource_server_id}/gateway:write'],
                            AllowedOAuthFlowsUserPoolClient=True
                        )
                    return client['ClientId'], client_secret
        
        # Create new client (M2M for client credentials flow)
        # Note: For client_credentials flow, AllowedOAuthFlowsUserPoolClient must be True
        # This enables OAuth 2.0 authorization server features
        response = cognito_client.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName=client_name,
            GenerateSecret=True,
            ExplicitAuthFlows=['ALLOW_REFRESH_TOKEN_AUTH'],  # Only valid flows
            AllowedOAuthFlows=['client_credentials'],
            AllowedOAuthScopes=[f'{resource_server_id}/gateway:read', f'{resource_server_id}/gateway:write'],
            AllowedOAuthFlowsUserPoolClient=True  # Required for client_credentials flow
        )
        client_id = response['UserPoolClient']['ClientId']
        client_secret = response['UserPoolClient'].get('ClientSecret', None)
        return client_id, client_secret
    except Exception as e:
        print(f"Error creating client: {e}")
        raise

# Create or get user pool
print(f"   Creando/obteniendo User Pool: {USER_POOL_NAME}")
user_pool_id = get_or_create_user_pool(cognito, USER_POOL_NAME)
print(f"   ✓ User Pool ID: {user_pool_id}")

# Create or get resource server
print(f"   Creando/obteniendo Resource Server: {RESOURCE_SERVER_ID}")
get_or_create_resource_server(cognito, user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES)
print(f"   ✓ Resource Server creado")

# Create or get M2M client
print(f"   Creando/obteniendo M2M Client: {CLIENT_NAME}")
client_id, client_secret = get_or_create_m2m_client(cognito, user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID)
print(f"   ✓ Client ID: {client_id}")
if client_secret:
    print(f"   ✓ Client Secret: {client_secret[:20]}...")

# Create or get domain for User Pool (required for OAuth2 endpoints)
# Use User Pool ID as domain prefix (replace _ with -)
domain_prefix = user_pool_id.replace('_', '-').lower()
print(f"   Creando/obteniendo dominio para User Pool: {domain_prefix}")
domain_created = False
try:
    # Try to create domain
    try:
        cognito.create_user_pool_domain(
            Domain=domain_prefix,
            UserPoolId=user_pool_id
        )
        print(f"   ✓ Dominio creado: {domain_prefix}")
        domain_created = True
        # Wait a bit for domain to be available
        print(f"   Esperando a que el dominio esté disponible...")
        import time
        time.sleep(10)
    except cognito.exceptions.ResourceConflictException:
        print(f"   ✓ Dominio ya existe: {domain_prefix}")
        domain_created = True
    except Exception as e:
        # If domain creation fails, try to use existing domain or continue
        print(f"   ⚠ No se pudo crear dominio: {e}")
        print(f"   Intentando continuar sin dominio...")
except Exception as e:
    print(f"   ⚠ Error con dominio: {e}")

# Get discovery URL
# The discovery URL on the Cognito domain (.auth.amazoncognito.com) may not work
# The cognito-idp endpoint works and is the standard way to access OpenID configuration
# For AgentCore Gateway CUSTOM_JWT, we'll use the cognito-idp endpoint
cognito_domain = f'{domain_prefix}.auth.${AWS_REGION}.amazoncognito.com'
cognito_discovery_url = f'https://cognito-idp.${AWS_REGION}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration'

print(f"   Discovery URL: {cognito_discovery_url}")
print(f"   (Usando endpoint de cognito-idp, que es el estándar para OpenID configuration)")

# Save Cognito info
cognito_info = {
    'userPoolId': user_pool_id,
    'clientId': client_id,
    'clientSecret': client_secret,
    'discoveryUrl': cognito_discovery_url,
    'domainPrefix': domain_prefix,
    'cognitoDomain': cognito_domain,
    'resourceServerId': RESOURCE_SERVER_ID,
    'scopeString': f'{RESOURCE_SERVER_ID}/gateway:read {RESOURCE_SERVER_ID}/gateway:write'
}

with open('.cognito-info.json', 'w') as f:
    json.dump(cognito_info, f, indent=2)

print(f"   ✓ Información de Cognito guardada en .cognito-info.json")
EOF

echo ""
echo "3. Recreando Gateway con CUSTOM_JWT..."

# Leer información de Cognito
COGNITO_INFO=$(cat .cognito-info.json)
CLIENT_ID=$(echo "$COGNITO_INFO" | jq -r '.clientId')
DISCOVERY_URL=$(echo "$COGNITO_INFO" | jq -r '.discoveryUrl')

# Eliminar Gateway existente si existe (primero eliminar targets)
python3 << EOF
import boto3
import json
import sys
import time

gateway_client = boto3.client('bedrock-agentcore-control', region_name='${AWS_REGION}')
gateway_name = '${GATEWAY_NAME}'

# Buscar Gateway existente
try:
    gateways = gateway_client.list_gateways()
    for gw in gateways.get('items', []):
        if gw.get('name') == gateway_name:
            gateway_id = gw.get('gatewayId') or gw.get('gatewayIdentifier')
            print(f"   Gateway existente encontrado: {gateway_id}")
            
            # Primero eliminar todos los targets
            try:
                targets = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                # La respuesta usa 'items' no 'targets'
                target_list = targets.get('items', [])
                
                if target_list:
                    print(f"   Eliminando {len(target_list)} target(s)...")
                    for target in target_list:
                        target_name = target.get('name')
                        target_id = target.get('targetId') or target.get('targetIdentifier')
                        try:
                            gateway_client.delete_gateway_target(
                                gatewayIdentifier=gateway_id,
                                targetIdentifier=target_id or target_name
                            )
                            print(f"   ✓ Target eliminado: {target_name}")
                            # Esperar un poco entre eliminaciones
                            time.sleep(2)
                        except Exception as e:
                            print(f"   ⚠ Error eliminando target {target_name}: {e}")
                else:
                    print(f"   No hay targets para eliminar")
            except Exception as e:
                print(f"   ⚠ Error listando targets: {e}")
            
            # Ahora eliminar el Gateway
            print(f"   Eliminando Gateway: {gateway_id}")
            try:
                gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
                print(f"   ✓ Gateway eliminado")
                # Esperar un poco para que se complete la eliminación
                time.sleep(5)
            except Exception as e:
                error_msg = str(e)
                if 'has targets associated' in error_msg:
                    print(f"   ✗ Error: El Gateway aún tiene targets asociados")
                    print(f"   Intenta eliminar los targets manualmente o espera unos segundos")
                else:
                    print(f"   ⚠ Error eliminando Gateway: {e}")
            break
except Exception as e:
    print(f"   ⚠ Error buscando Gateway: {e}")
EOF

# Crear nuevo Gateway con CUSTOM_JWT
python3 << EOF
import boto3
import json
import time
import sys

gateway_client = boto3.client('bedrock-agentcore-control', region_name='${AWS_REGION}')
cognito = boto3.client('cognito-idp', region_name='${AWS_REGION}')

# Leer información de Cognito
with open('.cognito-info.json', 'r') as f:
    cognito_info = json.load(f)

client_id = cognito_info['clientId']
discovery_url = cognito_info['discoveryUrl']
role_arn = '${ROLE_ARN}'

# Crear Gateway con CUSTOM_JWT
print(f"   Creando Gateway con CUSTOM_JWT...")
auth_config = {
    "customJWTAuthorizer": {
        "allowedClients": [client_id],
        "discoveryUrl": discovery_url
    }
}

try:
    response = gateway_client.create_gateway(
        name='${GATEWAY_NAME}',
        roleArn=role_arn,
        protocolType='MCP',
        authorizerType='CUSTOM_JWT',
        authorizerConfiguration=auth_config,
        description='Gateway para API GraphQL de countries con JWT'
    )
    
    gateway_id = response.get('gatewayId') or response.get('gatewayIdentifier')
    gateway_url = response.get('gatewayUrl')
    
    print(f"   ✓ Gateway creado: {gateway_id}")
    print(f"   Gateway URL: {gateway_url}")
    
    # Esperar a que esté listo
    print("   Esperando a que el Gateway esté listo...")
    max_wait = 300
    wait_time = 0
    while wait_time < max_wait:
        gateway_info = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
        status = gateway_info.get('status', 'UNKNOWN')
        
        if status == 'READY':
            print(f"   ✓ Gateway está listo (status: {status})")
            gateway_url = gateway_info.get('gatewayUrl', gateway_url)
            break
        elif status == 'FAILED':
            print(f"   ✗ Gateway falló (status: {status})")
            # Try to get more details about the failure
            try:
                gateway_details = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
                status_reason = gateway_details.get('statusReason', 'No reason provided')
                print(f"   Razón del fallo: {status_reason}")
            except:
                pass
            sys.exit(1)
        else:
            print(f"   Status: {status} - esperando...")
            time.sleep(5)
            wait_time += 5
    
    # Guardar información del Gateway
    gateway_info = {
        'gatewayId': gateway_id,
        'gatewayUrl': gateway_url,
        'gatewayName': '${GATEWAY_NAME}',
        'region': '${AWS_REGION}',
        'authorizerType': 'CUSTOM_JWT'
    }
    
    with open('.gateway-info.json', 'w') as f:
        json.dump(gateway_info, f, indent=2)
    
    print(f"   ✓ Información del Gateway guardada en .gateway-info.json")
    
except Exception as e:
    print(f"   ✗ Error creando Gateway: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

echo ""
echo "4. Esperando a que el cliente de Cognito esté listo..."
sleep 5

echo ""
echo "5. Obteniendo token JWT de Cognito..."

python3 << EOF
import boto3
import requests
import json
import base64
import sys

# Leer información de Cognito
with open('.cognito-info.json', 'r') as f:
    cognito_info = json.load(f)

user_pool_id = cognito_info['userPoolId']
client_id = cognito_info['clientId']
client_secret = cognito_info.get('clientSecret')
scope_string = cognito_info['scopeString']
region = '${AWS_REGION}'

# Obtener token de Cognito
# Para client_credentials flow, usar el dominio del User Pool
# Usar el dominio guardado en cognito_info si está disponible
cognito_domain = cognito_info.get('cognitoDomain')
if not cognito_domain:
    # Fallback: construir dominio desde user_pool_id
    domain_prefix = user_pool_id.replace('_', '-').lower()
    cognito_domain = f'{domain_prefix}.auth.{region}.amazoncognito.com'

token_url = f'https://{cognito_domain}/oauth2/token'

# Crear Basic Auth header (formato correcto para Cognito)
auth_string = f'{client_id}:{client_secret}' if client_secret else client_id
auth_bytes = auth_string.encode('utf-8')
auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': f'Basic {auth_b64}'
}

# Para client_credentials, solo grant_type y scope van en el body
# client_id y client_secret van en el header Authorization
# Nota: scope es opcional, pero si se proporciona debe coincidir con los scopes configurados
# Intentar primero sin scope, luego con scope si falla
data = {
    'grant_type': 'client_credentials'
}

try:
    print(f"   Solicitando token de Cognito...")
    print(f"   Token URL: {token_url}")
    print(f"   Client ID: {client_id}")
    
    # Para client_credentials, cuando el cliente tiene scopes configurados en AllowedOAuthScopes,
    # podemos omitir el scope en la solicitud y Cognito usará todos los scopes permitidos
    # Intentar primero sin scope (Cognito usará los scopes configurados en el cliente)
    print(f"   Intentando sin scope (usará scopes configurados en el cliente)...")
    response = requests.post(token_url, headers=headers, data=data, timeout=30)
    
    # Si falla sin scope, intentar con scope explícito
    if response.status_code != 200:
        print(f"   Intento sin scope falló ({response.status_code})")
        if scope_string and scope_string.strip():
            print(f"   Intentando con scope explícito: {scope_string}")
            data_with_scope = data.copy()
            data_with_scope['scope'] = scope_string
            response = requests.post(token_url, headers=headers, data=data_with_scope, timeout=30)
            data = data_with_scope
    
    # Log response for debugging
    if response.status_code != 200:
        print(f"   ✗ Error HTTP {response.status_code}: {response.text}")
        print(f"   Headers enviados: {headers}")
        print(f"   Data enviada: {data}")
    
    response.raise_for_status()
    
    token_data = response.json()
    access_token = token_data.get('access_token')
    
    if access_token:
        print(f"   ✓ Token obtenido exitosamente")
        # Guardar token en archivo
        with open('.cognito-token.json', 'w') as f:
            json.dump({'access_token': access_token}, f, indent=2)
        print(f"   ✓ Token guardado en .cognito-token.json")
    else:
        print(f"   ✗ No se pudo obtener el token de la respuesta")
        print(f"   Respuesta: {response.text}")
        sys.exit(1)
        
except Exception as e:
    print(f"   ✗ Error obteniendo token: {e}")
    print(f"   URL: {token_url}")
    print(f"   Headers: {headers}")
    print(f"   Data: {data}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

echo ""
echo "6. Creando target OpenAPI en el Gateway..."

# Leer información del Gateway
GATEWAY_INFO=$(cat .gateway-info.json)
GATEWAY_ID=$(echo "$GATEWAY_INFO" | jq -r '.gatewayId')
GATEWAY_URL=$(echo "$GATEWAY_INFO" | jq -r '.gatewayUrl')

# Crear target usando agentcore CLI (similar al setup original)
python3 << EOF
import json
import subprocess
import sys

# Leer esquema OpenAPI
with open('${OPENAPI_SCHEMA_FILE}', 'r') as f:
    openapi_schema = json.load(f)

# Crear payload
target_payload = json.dumps({
    'inlinePayload': json.dumps(openapi_schema)
})

# Crear credenciales
credentials = json.dumps({
    'api_key': 'public',
    'credential_location': 'HEADER',
    'credential_parameter_name': 'x-api-key'
})

gateway_arn = f'arn:aws:bedrock-agentcore:${AWS_REGION}:${ACCOUNT_ID}:gateway/${GATEWAY_ID}'

try:
    print(f"   Creando target usando agentcore CLI...")
    result = subprocess.run(
        ['agentcore', 'gateway', 'create-mcp-gateway-target',
         '--gateway-arn', gateway_arn,
         '--gateway-url', '${GATEWAY_URL}',
         '--role-arn', '${ROLE_ARN}',
         '--region', '${AWS_REGION}',
         '--name', '${TARGET_NAME}',
         '--target-type', 'openApiSchema',
         '--target-payload', target_payload,
         '--credentials', credentials],
        capture_output=True,
        text=True,
        check=True
    )
    print(f"   ✓ Target creado")
except subprocess.CalledProcessError as e:
    if 'ConflictException' in e.stderr or 'already exists' in e.stderr.lower():
        print(f"   ⚠ Target ya existe, continuando...")
    else:
        print(f"   ✗ Error creando target: {e.stderr}")
        sys.exit(1)
EOF

echo ""
echo "✓ Gateway configurado con JWT (Cognito)"
echo ""
echo "Información guardada:"
echo "  - .gateway-info.json: Información del Gateway"
echo "  - .cognito-info.json: Información de Cognito"
echo "  - .cognito-token.json: Token JWT actual"
echo ""
echo "Para usar el token en el código, lee desde .cognito-token.json"
echo "O usa el IdentityClient para obtener tokens dinámicamente"
