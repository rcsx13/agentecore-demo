#!/usr/bin/env python3
"""
Script para actualizar las variables de entorno del runtime desplegado
"""

import boto3
import json
import os
import sys

AGENT_NAME = os.getenv('AGENT_NAME', 'agent_runtime_demo_4')

# Cargar variables desde .gateway-info.json
gateway_url = None
aws_region = None

if os.path.exists('.gateway-info.json'):
    with open('.gateway-info.json', 'r') as f:
        gateway_info = json.load(f)
        gateway_url = gateway_info.get('gatewayUrl')
        aws_region = gateway_info.get('region', 'us-east-1')

# Usar variables de entorno si están disponibles
gateway_url = os.getenv('AGENTCORE_GATEWAY_URL', gateway_url)
aws_region = os.getenv('AWS_REGION', aws_region or 'us-east-1')

if not gateway_url:
    print("✗ Error: AGENTCORE_GATEWAY_URL no está configurada")
    sys.exit(1)

print(f"Actualizando variables de entorno para: {AGENT_NAME}")
print(f"AGENTCORE_GATEWAY_URL={gateway_url}")
print(f"AWS_REGION={aws_region}")
print("")

# Crear cliente
client = boto3.client('bedrock-agentcore-control', region_name=aws_region)

# Listar runtimes para encontrar el nuestro
try:
    response = client.list_agent_runtimes()
    runtime_id = None
    
    for runtime in response.get('agentRuntimes', []):
        if runtime.get('agentRuntimeName') == AGENT_NAME:
            runtime_id = runtime.get('agentRuntimeId')
            break
    
    if not runtime_id:
        print(f"✗ Error: No se encontró el runtime '{AGENT_NAME}'")
        sys.exit(1)
    
    print(f"✓ Runtime encontrado: {runtime_id}")
    print("")
    
    # Intentar actualizar el runtime
    # Nota: update_agent_runtime puede no estar disponible en todas las versiones
    try:
        client.update_agent_runtime(
            agentRuntimeId=runtime_id,
            environmentVariables={
                'AGENTCORE_GATEWAY_URL': gateway_url,
                'AWS_REGION': aws_region
            }
        )
        print("✓ Variables de entorno actualizadas exitosamente")
    except Exception as e:
        print(f"⚠ No se pudo actualizar el runtime: {e}")
        print("")
        print("El runtime necesita ser recreado con las variables de entorno.")
        print("Ejecuta:")
        print(f"  export AGENTCORE_GATEWAY_URL={gateway_url}")
        print(f"  export AWS_REGION={aws_region}")
        print("  ./deploy.sh")
        sys.exit(1)
        
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
