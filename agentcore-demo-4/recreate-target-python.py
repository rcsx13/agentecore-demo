#!/usr/bin/env python3
"""
Script para recrear el target del Gateway usando boto3 directamente
"""
import json
import boto3
import time
import sys

# Leer información del Gateway
with open('.gateway-info.json', 'r') as f:
    gateway_info = json.load(f)

gateway_id = gateway_info['gatewayId']
region = gateway_info['region']

# Obtener Account ID
sts = boto3.client('sts', region_name=region)
account_id = sts.get_caller_identity()['Account']
role_arn = f'arn:aws:iam::{account_id}:role/AgentCoreGatewayRole-countries-gateway'

# Inicializar cliente
gateway_client = boto3.client('bedrock-agentcore-control', region_name=region)

print("Recreando target con endpoint /graphql...")
print(f"Gateway ID: {gateway_id}")
print(f"Region: {region}")
print("")

# Eliminar target existente si existe
try:
    targets = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
    for target in targets.get('items', []):
        if target.get('name') == 'countries-graphql-target':
            target_id = target.get('targetId') or target.get('targetIdentifier')
            print(f"Eliminando target existente: {target_id}")
            gateway_client.delete_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target_id
            )
            print("✓ Target eliminado")
            print("Esperando 10 segundos para que se complete la eliminación...")
            time.sleep(10)
            break
except Exception as e:
    print(f"⚠ Error eliminando target: {e}")

# Leer esquema OpenAPI
with open('gateway-config.json', 'r') as f:
    openapi_schema = json.load(f)

# Crear configuración del target
# Nota: La API de AWS requiere un formato específico para OpenAPI schemas
# Usamos inlinePayload como string JSON
target_configuration = {
    "mcp": {
        "openApiSchema": {
            "inlinePayload": json.dumps(openapi_schema)
        }
    }
}

# Configuración de credenciales (API pública, pero AWS requiere configuración)
credential_provider_configurations = [
    {
        "credentialProviderType": "API_KEY",
        "apiKeyCredentialProvider": {
            "credentialParameterName": "x-api-key",
            "credentialLocation": "HEADER",
            "apiKey": "public"  # Valor dummy para API pública
        }
    }
]

# Crear nuevo target
try:
    print("Creando nuevo target con endpoint /graphql...")
    response = gateway_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="countries-graphql-target",
        description="GraphQL API target for countries.trevorblades.com with /graphql endpoint",
        targetConfiguration=target_configuration,
        credentialProviderConfigurations=credential_provider_configurations
    )
    
    target_id = response.get('targetId')
    print(f"✓ Target creado: {target_id}")
    print(f"Status: {response.get('status', 'UNKNOWN')}")
    
    # Esperar a que esté listo
    print("Esperando a que el target esté listo...")
    max_wait = 120
    wait_time = 0
    while wait_time < max_wait:
        target_info = gateway_client.get_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id
        )
        status = target_info.get('status', 'UNKNOWN')
        
        if status == 'READY':
            print(f"✓ Target está listo (status: {status})")
            break
        elif status == 'FAILED':
            print(f"✗ Target falló (status: {status})")
            sys.exit(1)
        else:
            print(f"Status: {status} - esperando...")
            time.sleep(5)
            wait_time += 5
    
    print("")
    print("✓ Target recreado exitosamente")
    print("El endpoint ahora es /graphql en lugar de /")
    
except Exception as e:
    print(f"✗ Error creando target: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
