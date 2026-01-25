# Amazon Bedrock AgentCore Runtime - Demo 4

Agente desplegable a producción con Strands Agents, BedrockModel y AgentCore Gateway para acceder a herramientas GraphQL mediante MCP.

## Características

- ✅ **Amazon Bedrock AgentCore Runtime**: Usa el SDK oficial de AWS
- ✅ **Strands Agents con BedrockModel**: Integración con Claude 3.7 Sonnet
- ✅ **AgentCore Gateway**: Gateway MCP que expone herramientas como servidor MCP
- ✅ **Cliente MCP HTTP**: El agente se conecta al Gateway usando cliente MCP HTTP
- ✅ **Herramienta GraphQL**: Acceso a la API pública de países (https://countries.trevorblades.com) a través del Gateway
- ✅ **Autenticación IAM**: El Gateway usa autenticación IAM para seguridad
- ✅ **Listo para producción**: Desplegable en AWS
- ✅ **Patrón estándar**: Sigue el patrón del tutorial oficial
- ✅ **Entrypoint decorator**: Usa `@app.entrypoint` como requerido

## Arquitectura

```
┌─────────────────┐
│  Agent Runtime  │
│  (Strands)      │
└────────┬────────┘
         │ MCP Client (HTTP)
         │ (con autenticación IAM)
         ▼
┌─────────────────┐
│ AgentCore       │
│ Gateway         │
│ (MCP Server)    │
└────────┬────────┘
         │ HTTP/GraphQL
         ▼
┌─────────────────┐
│ GraphQL API     │
│ (countries API) │
└─────────────────┘
```

## Estructura

```
agent_runtime.py      # Runtime principal con @app.entrypoint
test_local.py         # Script para probar localmente
deploy.sh             # Script bash para desplegar a AWS
setup-gateway.sh      # Script para crear y configurar el Gateway
gateway-config.json   # Esquema OpenAPI para el target GraphQL
requirements.txt      # Dependencias
README.md             # Esta documentación
```

## Requisitos

- Python 3.10+
- AWS Credentials configuradas (para despliegue y Gateway)
- `bedrock-agentcore` SDK instalado (para despliegue)
- `jq` instalado (para el script de setup del Gateway)
- **Permisos IAM necesarios** (crítico para el despliegue y Gateway):

  ### Permisos del Usuario IAM (para despliegue y Gateway)

  - **ECR** (Elastic Container Registry):
    - `ecr:CreateRepository` - Para crear repositorios ECR
    - `ecr:GetAuthorizationToken` - Para autenticar con ECR
    - `ecr:BatchCheckLayerAvailability` - Para verificar capas de imagen
    - `ecr:BatchGetImage` - Para obtener imágenes
    - `ecr:GetDownloadUrlForLayer` - Para descargar capas de imagen
    - `ecr:PutImage` - Para subir imágenes Docker
    - `ecr:InitiateLayerUpload` - Para iniciar subida de capas
    - `ecr:UploadLayerPart` - Para subir partes de capas
    - `ecr:CompleteLayerUpload` - Para completar subida de capas
    - `ecr:DescribeRepositories` - Para describir repositorios
    - `ecr:GetRepositoryPolicy` - Para obtener políticas de repositorio
    - `ecr:ListImages` - Para listar imágenes

  - **IAM** (requerido por el CLI tool y Gateway):
    - `iam:CreateRole` - Para crear el rol de ejecución del runtime y Gateway
    - `iam:AttachRolePolicy` - Para adjuntar políticas managed al rol
    - `iam:PutRolePolicy` - Para adjuntar políticas inline al rol
    - `iam:GetRole` - Para obtener información del rol
    - `iam:GetPolicy` - Para obtener información de políticas
    - `iam:ListRolePolicies` - Para listar políticas inline del rol
    - `iam:ListAttachedRolePolicies` - Para listar políticas managed adjuntadas
    - `iam:PassRole` - Para pasar el rol al servicio (con condiciones para CodeBuild y Bedrock AgentCore)
    - `iam:CreatePolicy` - Para crear políticas personalizadas
    - `iam:TagRole` - Para etiquetar roles

  - **CodeBuild** (requerido para construir imágenes Docker):
    - `codebuild:CreateProject` - Para crear proyectos de CodeBuild
    - `codebuild:DeleteProject` - Para eliminar proyectos
    - `codebuild:StartBuild` - Para iniciar builds
    - `codebuild:StopBuild` - Para detener builds
    - `codebuild:BatchGetBuilds` - Para obtener información de builds
    - `codebuild:BatchGetProjects` - Para obtener información de proyectos
    - `codebuild:GetProject` - Para obtener información del proyecto
    - `codebuild:UpdateProject` - Para actualizar proyectos
    - `codebuild:ListBuilds` - Para listar builds
    - `codebuild:ListBuildsForProject` - Para listar builds de un proyecto
    - `codebuild:ListProjects` - Para listar proyectos

  - **S3** (para almacenar artefactos):
    - `s3:CreateBucket` - Para crear buckets
    - `s3:GetObject` - Para leer objetos
    - `s3:PutObject` - Para escribir objetos
    - `s3:DeleteObject` - Para eliminar objetos
    - `s3:ListBucket` - Para listar objetos

  - **CloudWatch Logs** (para logs de CodeBuild):
    - `logs:CreateLogGroup` - Para crear grupos de logs
    - `logs:CreateLogStream` - Para crear streams de logs
    - `logs:PutLogEvents` - Para escribir eventos de log

  - **Bedrock AgentCore**:
    - `bedrock-agentcore:CreateAgentRuntime` - Para crear runtimes
    - `bedrock-agentcore:GetAgentRuntime` - Para obtener información de runtimes
    - `bedrock-agentcore:UpdateAgentRuntime` - Para actualizar runtimes
    - `bedrock-agentcore:DeleteAgentRuntime` - Para eliminar runtimes
    - `bedrock-agentcore:ListAgentRuntimes` - Para listar runtimes
    - `bedrock-agentcore:InvokeAgentRuntime` - Para invocar runtimes
    - `bedrock-agentcore-control:*` - Para control completo de AgentCore (incluyendo Gateway)

  ### Permisos del Rol de Ejecución (para el runtime en ejecución)

  El rol de ejecución (`AmazonBedrockAgentCoreSDKRuntime-*`) necesita permisos adicionales:

  - **ECR** (para acceder a imágenes Docker durante la ejecución):
    - `ecr:GetAuthorizationToken` - Para autenticar con ECR
    - `ecr:BatchGetImage` - Para obtener imágenes del repositorio
    - `ecr:GetDownloadUrlForLayer` - Para descargar capas de imagen

  - **AgentCore Gateway** (para invocar el Gateway):
    - `bedrock-agentcore:InvokeGateway` - Para invocar el Gateway MCP

  **Nota**: Si el runtime falla al ejecutarse con errores de ECR, ejecuta `./grant-runtime-ecr-permissions.sh` para agregar estos permisos al rol de ejecución.

  **Nota general**: Si no tienes estos permisos, contacta a tu administrador de AWS para obtenerlos o usar un rol IAM con los permisos necesarios.

## Configuración del AgentCore Gateway

Antes de desplegar el agente, necesitas crear y configurar el AgentCore Gateway:

### 1. Crear el Gateway

```bash
# Configurar la región de AWS
export AWS_REGION=us-east-2

# Crear y configurar el Gateway
./setup-gateway.sh [GATEWAY_NAME] [REGION]
```

Ejemplo:
```bash
./setup-gateway.sh countries-gateway us-east-2
```

Este script:
1. Crea un rol IAM para el Gateway
2. Crea el AgentCore Gateway con autenticación IAM
3. Agrega un target OpenAPI que apunta a la API GraphQL de countries
4. Espera a que el Gateway esté listo
5. Muestra la URL del Gateway

### 2. Configurar Variables de Entorno

Después de crear el Gateway, configura las variables de entorno:

```bash
# La URL del Gateway se muestra al final del script setup-gateway.sh
export AGENTCORE_GATEWAY_URL=<gateway-url>
export AWS_REGION=us-east-2
```

También puedes leer la URL desde el archivo `.gateway-info.json` que se crea automáticamente:

```bash
export AGENTCORE_GATEWAY_URL=$(jq -r '.gatewayUrl' .gateway-info.json)
export AWS_REGION=$(jq -r '.region' .gateway-info.json)
```

### 3. Verificar el Gateway

Puedes verificar que el Gateway esté funcionando:

```bash
# Listar gateways
aws bedrock-agentcore-control list-gateways --region us-east-2

# Obtener información del Gateway
aws bedrock-agentcore-control get-gateway \
    --gateway-identifier <gateway-id> \
    --region us-east-2
```

## Probar el Agente Localmente

### Verificar Python (3.10+)

```bash
python3 --version
```

### Configurar Variables de Entorno

Asegúrate de tener configuradas las variables de entorno del Gateway:

```bash
export AGENTCORE_GATEWAY_URL=<gateway-url>
export AWS_REGION=us-east-2
```

### Probar con argumento JSON (una sola prueba)

```bash
python3 test_local.py '{"prompt": "Hello, how are you?"}'
```

**Ejemplos:**

```bash
# Mensaje simple
python3 test_local.py '{"prompt": "Hello"}'

# Consultar información de un país (usará el Gateway)
python3 test_local.py '{"prompt": "What is the capital of Brazil?"}'

# Consultar información de países
python3 test_local.py '{"prompt": "Tell me about Spain"}'

# Consultar países de un continente
python3 test_local.py '{"prompt": "What countries are in South America?"}'
```

### Probar en modo interactivo (múltiples pruebas)

```bash
python3 test_local.py
```

Esto abrirá un modo interactivo donde puedes escribir múltiples mensajes:

```
Testing agent locally. Type 'exit' to quit.

> Hello, how are you?
[Respuesta del agente]

> What is the capital of France?
[El agente usará el Gateway para consultar información sobre Francia]

> exit
```

Para salir del modo interactivo, escribe `exit` o `quit`, o presiona `Ctrl+C`.

### Verificar sintaxis

```bash
python3 -m py_compile test_local.py
python3 -m py_compile agent_runtime.py
```

## Despliegue a AWS

### Instalar dependencias

```bash
pip install -r requirements.txt
```

### Configurar permisos IAM

Antes de desplegar, necesitas configurar los permisos IAM necesarios:

**Opción 1: Usar el script proporcionado (recomendado)**

```bash
# Ejecutar el script con tu nombre de usuario IAM
./setup-user-iam-permissions.sh rcabrera-admin
```

**Opción 2: Crear la política manualmente**

```bash
# Crear la política IAM
aws iam create-policy \
    --policy-name BedrockAgentCoreDeploymentPolicy \
    --policy-document file://iam-policy.json \
    --description "Permisos necesarios para desplegar Bedrock AgentCore Runtime"

# Obtener el ARN de la política (reemplaza ACCOUNT_ID)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/BedrockAgentCoreDeploymentPolicy"

# Adjuntar la política a tu usuario
aws iam attach-user-policy \
    --user-name tu-usuario-iam \
    --policy-arn $POLICY_ARN
```

**Verificar permisos:**

```bash
aws iam list-attached-user-policies --user-name tu-usuario-iam
```

### Configuración básica

```bash
export AWS_REGION=us-east-2
export AGENT_NAME=agent-runtime-demo-4
export AGENTCORE_GATEWAY_URL=<gateway-url>  # Obtener del script setup-gateway.sh
```

### Desplegar

```bash
./deploy.sh
```

O ejecutar directamente con bash:

```bash
bash deploy.sh
```

El script de despliegue:
1. Verifica que el CLI tool 'agentcore' esté instalado
2. Configura el despliegue con `agentcore configure`
3. Lanza el agente con `agentcore launch`

**Nota importante**: Asegúrate de que la variable de entorno `AGENTCORE_GATEWAY_URL` esté configurada antes de desplegar, ya que el runtime la necesita para conectarse al Gateway.

### Configurar permisos del rol de ejecución (si es necesario)

Si después del despliegue el runtime falla al ejecutarse con errores relacionados con ECR o Gateway, es probable que el rol de ejecución no tenga los permisos necesarios.

Para solucionarlo:

1. **Permisos ECR**: Ejecuta `./grant-runtime-ecr-permissions.sh`

2. **Permisos Gateway**: Agrega permisos para invocar el Gateway al rol de ejecución:

```bash
# Obtener el nombre del rol de ejecución
ROLE_NAME=$(aws iam list-roles --query "Roles[?contains(RoleName, 'AmazonBedrockAgentCoreSDKRuntime')].RoleName" --output text | head -1)

# Crear política para Gateway
cat > /tmp/gateway-policy.json << EOF
{
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
}
EOF

# Adjuntar política al rol
aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "GatewayInvokePolicy" \
    --policy-document file:///tmp/gateway-policy.json
```

### Verificar estado del despliegue

El script `deploy.sh` ejecutará los comandos de despliegue. Una vez completado, recibirás información sobre:
- **Agent ARN**: Identificador único del agente
- **Agent ID**: ID del agente
- **ECR URI**: URI del repositorio ECR

### Troubleshooting

Si el despliegue falla, verifica:

1. **Ver logs de CodeBuild** (si el error es durante el build):
   ```bash
   # Listar proyectos de CodeBuild
   aws codebuild list-projects --region us-east-1
   
   # Ver logs del build (reemplaza PROJECT_NAME)
   aws codebuild batch-get-builds --ids <BUILD_ID> --region us-east-1
   ```

2. **Ver logs de CloudWatch**:
   ```bash
   # Ver logs del agente
   aws logs tail /aws/bedrock-agentcore/runtime --follow --region us-east-1
   ```

3. **Verificar estado del runtime**:
   ```bash
   agentcore status --agent agent_runtime_demo_4
   ```

4. **Problemas comunes**:
   - **Error de build**: Verifica que el código Python sea válido y que las dependencias estén en `requirements.txt`
   - **Error de permisos de despliegue**: Asegúrate de tener todos los permisos IAM necesarios para el usuario (ejecuta `./setup-user-iam-permissions.sh`)
   - **Error de permisos ECR durante ejecución**: Si el runtime falla al acceder a imágenes Docker, ejecuta `./grant-runtime-ecr-permissions.sh` para agregar permisos al rol de ejecución
   - **Error de Gateway**: Verifica que `AGENTCORE_GATEWAY_URL` esté configurada y que el Gateway esté en estado `READY`
   - **Error de conexión al Gateway**: Verifica que el rol de ejecución tenga permisos para invocar el Gateway
   - **Error de plataforma**: Verifica que la plataforma (`linux/arm64` o `linux/amd64`) sea correcta
   - **Error de Docker**: Verifica que el Dockerfile se genere correctamente

5. **Reintentar despliegue**:
   ```bash
   # Limpiar recursos parciales si es necesario
   # Luego reintentar
   ./deploy.sh
   ```

## Herramientas Disponibles

Este agente accede a herramientas a través del AgentCore Gateway, que actúa como servidor MCP. Las herramientas están expuestas por el Gateway y el agente las usa mediante el cliente MCP HTTP.

### Herramienta GraphQL de Países

El Gateway expone una herramienta para consultar información de países desde la API pública GraphQL de https://countries.trevorblades.com.

**Tipos de consulta disponibles:**
- `country`: Consultar información de un país específico por código (ej: "US", "BR", "ES")
- `countries`: Listar todos los países
- `continent`: Consultar países de un continente por código (ej: "NA", "SA", "EU")
- `filter_by_currency`: Filtrar países por moneda

**Información disponible:**
- Nombre y nombre nativo del país
- Capital
- Emoji
- Moneda
- Idiomas
- Continente

**Ejemplos de uso:**
- "¿Cuál es la capital de Brasil?"
- "Dime información sobre España"
- "¿Qué países hay en Sudamérica?"
- "¿Qué idiomas se hablan en México?"

## Modelo LLM

Este agente usa **Strands Agents** con **BedrockModel** (Claude 3.7 Sonnet) para generar respuestas inteligentes. El agente puede usar automáticamente las herramientas disponibles a través del Gateway cuando sea necesario para responder a las preguntas del usuario.

**Configuración del modelo:**
- Modelo por defecto: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- Temperature: 0.3
- Top-p: 0.8

Puedes cambiar el modelo usando la variable de entorno `BEDROCK_MODEL_ID`.

## Diferencias con Demo 3

Este demo (Demo 4) introduce los siguientes cambios respecto a Demo 3:

1. **AgentCore Gateway**: En lugar de usar un servidor MCP local, el agente se conecta a un AgentCore Gateway que actúa como servidor MCP centralizado.

2. **Cliente MCP HTTP**: El agente usa un cliente MCP HTTP (`streamablehttp_client`) para conectarse al Gateway en lugar de un cliente stdio para un servidor local.

3. **Autenticación IAM**: El Gateway usa autenticación IAM en lugar de conexiones locales sin autenticación.

4. **Sin llamadas directas a GraphQL**: El código del agente ya no contiene llamadas directas a la API GraphQL. Todas las llamadas pasan a través del Gateway.

5. **Configuración del Gateway**: Se requiere ejecutar `setup-gateway.sh` antes de desplegar el agente para crear y configurar el Gateway.

## Referencias

- [Tutorial oficial](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/runtime_with_strands_and_bedrock_models.ipynb)
- [Amazon Bedrock AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
- [AgentCore Gateway Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building.html)
