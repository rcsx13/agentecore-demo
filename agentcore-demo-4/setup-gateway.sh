#!/bin/bash
#
# Script para crear y configurar AgentCore Gateway con target GraphQL
# Crea un Gateway MCP con autenticación IAM y agrega un target OpenAPI para la API GraphQL de countries
#
# Uso:
#   ./setup-gateway.sh [GATEWAY_NAME] [REGION]
#
# Ejemplo:
#   ./setup-gateway.sh countries-gateway us-east-1

set -e

GATEWAY_NAME=${1:-countries-gateway}
AWS_REGION=${2:-${AWS_REGION:-us-east-1}}
TARGET_NAME="countries-graphql-target"
OPENAPI_SCHEMA_FILE="gateway-config.json"

echo "Configurando AgentCore Gateway: $GATEWAY_NAME"
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

# Verificar que agentcore CLI está instalado
if ! command -v agentcore &> /dev/null; then
    echo "Error: agentcore CLI no está instalado"
    echo "Instala con: pip install bedrock-agentcore-starter-toolkit"
    exit 1
fi

# Obtener Account ID y crear ARN del rol
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_NAME="AgentCoreGatewayRole-${GATEWAY_NAME}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# Exportar ACCOUNT_ID para uso en el script Python
export ACCOUNT_ID

echo "1. Creando rol IAM para el Gateway..."

# Crear política para el rol del Gateway (permite hacer llamadas HTTP a la API GraphQL)
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

# Política que permite hacer llamadas HTTP a la API GraphQL externa
GATEWAY_POLICY='{
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

# Crear el rol si no existe
if ! aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    echo "   Creando rol IAM: $ROLE_NAME"
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY" \
        --description "Rol para AgentCore Gateway $GATEWAY_NAME" \
        > /dev/null
    
    # Adjuntar política al rol
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "GatewayPolicy" \
        --policy-document "$GATEWAY_POLICY" \
        > /dev/null
    
    echo "   ✓ Rol creado: $ROLE_ARN"
else
    echo "   ✓ El rol ya existe: $ROLE_ARN"
fi

echo ""
echo "2. Creando AgentCore Gateway..."

# Crear el Gateway usando Python con boto3
# Nota: El secreto se creará después de obtener el gateway_id
python3 << EOF
import boto3
import json
import time
import sys
import subprocess

client = boto3.client('bedrock-agentcore-control', region_name='${AWS_REGION}')
gateway_name = '${GATEWAY_NAME}'
role_arn = '${ROLE_ARN}'
account_id = '${ACCOUNT_ID}'

# Verificar si el Gateway ya existe
try:
    gateway_id = None
    gateway_url = None
    
    gateways = client.list_gateways()
    existing_gateway = None
    
    # La respuesta usa 'items' no 'gateways'
    all_gateways = gateways.get('items', [])
    print(f"   Buscando Gateway '{gateway_name}' entre {len(all_gateways)} gateways encontrados...")
    
    for gw in all_gateways:
        gw_name = gw.get('name', 'N/A')
        if gw_name == gateway_name:
            existing_gateway = gw
            print(f"   ✓ Gateway encontrado en la búsqueda inicial: {gw_name}")
            break
        else:
            print(f"   - Gateway encontrado: '{gw_name}' (no coincide con '{gateway_name}')")
    
    if existing_gateway:
        gateway_id = existing_gateway.get('gatewayId') or existing_gateway.get('gatewayIdentifier') or existing_gateway.get('id')
        print(f"   ✓ Gateway ya existe: {gateway_id}")
        # Obtener la URL del Gateway usando get_gateway
        gateway_info = client.get_gateway(gatewayIdentifier=gateway_id)
        gateway_url = gateway_info.get('gatewayUrl') or gateway_info.get('url') or gateway_info.get('endpoint')
        if gateway_url:
            print(f"   Gateway URL: {gateway_url}")
    else:
        # Crear el Gateway con autenticación IAM
        print(f"   Creando Gateway: {gateway_name}")
        try:
            response = client.create_gateway(
                name=gateway_name,
                roleArn=role_arn,
                protocolType='MCP',
                authorizerType='AWS_IAM',
                description='Gateway para API GraphQL de countries'
            )
            # La respuesta puede tener diferentes nombres de campo, intentar ambos
            gateway_id = response.get('gatewayId') or response.get('gatewayIdentifier') or response.get('id')
            gateway_url = response.get('gatewayUrl') or response.get('url') or response.get('endpoint')
            
            if not gateway_id:
                print(f"   ✗ Error: No se pudo obtener el ID del Gateway de la respuesta")
                print(f"   Respuesta: {json.dumps(response, indent=2, default=str)}")
                sys.exit(1)
            
            # Si no hay URL en la respuesta, obtenerla usando get_gateway
            if not gateway_url:
                gateway_info = client.get_gateway(gatewayIdentifier=gateway_id)
                gateway_url = gateway_info.get('gatewayUrl') or gateway_info.get('url') or gateway_info.get('endpoint')
            
            print(f"   ✓ Gateway creado: {gateway_id}")
            if gateway_url:
                print(f"   Gateway URL: {gateway_url}")
        except client.exceptions.ConflictException:
            # El Gateway ya existe, buscarlo nuevamente
            print(f"   Gateway ya existe, buscando información...")
            gateways = client.list_gateways()
            gateway_id = None
            gateway_url = None
            
            # La respuesta usa 'items' no 'gateways'
            all_gateways = gateways.get('items', [])
            print(f"   Gateways encontrados: {len(all_gateways)}")
            for gw in all_gateways:
                gw_name = gw.get('name', 'N/A')
                print(f"   - Gateway: {gw_name} (buscando: {gateway_name})")
                if gw_name == gateway_name:
                    gateway_id = gw.get('gatewayId') or gw.get('gatewayIdentifier') or gw.get('id')
                    # Obtener la URL del Gateway usando get_gateway
                    gateway_info = client.get_gateway(gatewayIdentifier=gateway_id)
                    gateway_url = gateway_info.get('gatewayUrl') or gateway_info.get('url') or gateway_info.get('endpoint')
                    print(f"   ✓ Gateway encontrado: {gateway_id}")
                    if gateway_url:
                        print(f"   Gateway URL: {gateway_url}")
                    break
            
            if not gateway_id:
                print(f"   ✗ Error: No se pudo encontrar el Gateway existente")
                print(f"   Estructura de gateways: {json.dumps(gateways, indent=2, default=str)}")
                sys.exit(1)
    
    # Esperar a que el Gateway esté listo
    print("   Esperando a que el Gateway esté listo...")
    max_wait = 300  # 5 minutos máximo
    wait_time = 0
    while wait_time < max_wait:
        gateway_info = client.get_gateway(gatewayIdentifier=gateway_id)
        status = gateway_info.get('status', 'UNKNOWN')
        
        if status == 'READY':
            print(f"   ✓ Gateway está listo (status: {status})")
            gateway_url = gateway_info.get('gatewayUrl', gateway_url)
            break
        elif status == 'FAILED':
            print(f"   ✗ Gateway falló (status: {status})")
            sys.exit(1)
        else:
            print(f"   Status: {status} - esperando...")
            time.sleep(5)
            wait_time += 5
    
    if wait_time >= max_wait:
        print("   ⚠ Tiempo de espera agotado, pero continuando...")
    
    # Verificar si el target ya existe
    targets = client.list_gateway_targets(gatewayIdentifier=gateway_id)
    target_exists = False
    for target in targets.get('targets', []):
        if target.get('name') == '${TARGET_NAME}':
            target_exists = True
            print(f"   ✓ Target ya existe: ${TARGET_NAME}")
            break
    
    if not target_exists:
        # Crear el target usando agentcore CLI en lugar de boto3
        print(f"   Creando target usando agentcore CLI: ${TARGET_NAME}")
        
        # Obtener el ARN del Gateway
        gateway_info = client.get_gateway(gatewayIdentifier=gateway_id)
        gateway_arn = gateway_info.get('gatewayArn') or gateway_info.get('arn')
        
        if not gateway_arn:
            # Construir el ARN manualmente si no está en la respuesta
            gateway_arn = f'arn:aws:bedrock-agentcore:${AWS_REGION}:{account_id}:gateway/{gateway_id}'
        
        # Leer el esquema OpenAPI y convertirlo a JSON string para el CLI
        with open('${OPENAPI_SCHEMA_FILE}', 'r') as f:
            openapi_schema = json.load(f)
        
        # Crear el payload para --target-payload con formato inlinePayload
        # El formato debe ser: {"inlinePayload": "<json_esquema>"}
        target_payload = json.dumps({
            'inlinePayload': json.dumps(openapi_schema)
        })
        
        # Crear credenciales para API pública (usar valor dummy ya que AWS requiere min length: 1)
        # El CLI requiere --credentials para targets OpenAPI
        # Para APIs públicas, usamos un valor dummy que no se enviará realmente
        credentials = json.dumps({
            'api_key': 'public',
            'credential_location': 'HEADER',
            'credential_parameter_name': 'x-api-key'
        })
        
        # Usar agentcore CLI para crear el target
        print(f"   Usando agentcore CLI para crear el target...")
        print(f"   Gateway ARN: {gateway_arn}")
        print(f"   Gateway URL: {gateway_url}")
        try:
            result = subprocess.run(
                ['agentcore', 'gateway', 'create-mcp-gateway-target',
                 '--gateway-arn', gateway_arn,
                 '--gateway-url', gateway_url,
                 '--role-arn', role_arn,
                 '--region', '${AWS_REGION}',
                 '--name', '${TARGET_NAME}',
                 '--target-type', 'openApiSchema',
                 '--target-payload', target_payload,
                 '--credentials', credentials],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"   ✓ Target creado usando agentcore CLI")
            if result.stdout:
                print(f"   Salida: {result.stdout}")
        except subprocess.CalledProcessError as e:
            # Verificar si el error es porque el target ya existe
            if 'ConflictException' in e.stderr or 'already exists' in e.stderr.lower():
                print(f"   ⚠ Target ya existe (detectado por error del CLI)")
                print(f"   ✓ Continuando con el target existente: ${TARGET_NAME}")
                # Verificar nuevamente que el target existe
                targets = client.list_gateway_targets(gatewayIdentifier=gateway_id)
                for target in targets.get('targets', []):
                    if target.get('name') == '${TARGET_NAME}':
                        print(f"   ✓ Confirmado: Target existe en el Gateway")
                        break
            else:
                print(f"   ✗ Error creando target con agentcore CLI")
                print(f"   stderr: {e.stderr}")
                print(f"   stdout: {e.stdout}")
                raise Exception(f"agentcore CLI falló: {e.stderr}")
    
    # Guardar información del Gateway en un archivo para uso posterior
    gateway_info = {
        'gatewayId': gateway_id,
        'gatewayUrl': gateway_url,
        'gatewayName': gateway_name,
        'region': '${AWS_REGION}'
    }
    
    with open('.gateway-info.json', 'w') as f:
        json.dump(gateway_info, f, indent=2)
    
    print("")
    print("✓ Configuración completada")
    print("")
    print("Gateway ID: " + gateway_id)
    print("Gateway URL: " + gateway_url)
    print("")
    print("Configura las variables de entorno ejecutando:")
    print("")
    print(f"  export AGENTCORE_GATEWAY_URL={gateway_url}")
    print(f"  export AWS_REGION=${AWS_REGION}")
    print("")
    print("O automáticamente desde .gateway-info.json:")
    print("")
    print("  export AGENTCORE_GATEWAY_URL=$(jq -r '.gatewayUrl' .gateway-info.json)")
    print("  export AWS_REGION=$(jq -r '.region' .gateway-info.json)")

except Exception as e:
    print(f"   ✗ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

EOF

echo ""
echo "✓ Proceso completado"
echo ""
echo "La información del Gateway se guardó en .gateway-info.json"
