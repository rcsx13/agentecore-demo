# Amazon Bedrock AgentCore Runtime

Agente desplegable a producción 
Este ejemplo mínimo no incluye un modelo LLM. Para producción, considerar agregar un framework como Strands Agents con BedrockModel (Claude, etc.) posteriormente.

## Características

- ✅ **Amazon Bedrock AgentCore Runtime**: Usa el SDK oficial de AWS
- ✅ **Listo para producción**: Desplegable en AWS
- ✅ **Patrón estándar**: Sigue el patrón del tutorial oficial
- ✅ **Entrypoint decorator**: Usa `@app.entrypoint` como requerido

## Estructura

```
agent_runtime.py    # Runtime principal con @app.entrypoint
test_local.py       # Script para probar localmente
deploy.sh           # Script bash para desplegar a AWS
requirements.txt    # Dependencias
README.md           # Esta documentación
```

## Requisitos

- Python 3.10+
- AWS Credentials configuradas (para despliegue)
- `bedrock-agentcore` SDK instalado (para despliegue)
- **Permisos IAM necesarios** (crítico para el despliegue):

  ### Permisos del Usuario IAM (para despliegue)

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

  - **IAM** (requerido por el CLI tool):
    - `iam:CreateRole` - Para crear el rol de ejecución del runtime
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
    - `bedrock-agentcore-control:*` - Para control completo de AgentCore

  ### Permisos del Rol de Ejecución (para el runtime en ejecución)

  El rol de ejecución (`AmazonBedrockAgentCoreSDKRuntime-*`) necesita permisos adicionales de ECR que normalmente no se configuran automáticamente:

  - **ECR** (para acceder a imágenes Docker durante la ejecución):
    - `ecr:GetAuthorizationToken` - Para autenticar con ECR
    - `ecr:BatchGetImage` - Para obtener imágenes del repositorio
    - `ecr:GetDownloadUrlForLayer` - Para descargar capas de imagen

  **Nota**: Si el runtime falla al ejecutarse con errores de ECR, ejecuta `./grant-runtime-ecr-permissions.sh` para agregar estos permisos al rol de ejecución.

  **Nota general**: Si no tienes estos permisos, contacta a tu administrador de AWS para obtenerlos o usar un rol IAM con los permisos necesarios.

## Probar el Agente Localmente

### Verificar Python (3.10+)

```bash
python3 --version
```

### Probar con argumento JSON (una sola prueba)

```bash
python3 test_local.py '{"prompt": "Hello, how are you?"}'
```

**Ejemplos:**

```bash
# Mensaje simple
python3 test_local.py '{"prompt": "Hello"}'

# Consultar clima
python3 test_local.py '{"prompt": "What is the weather?"}'

# Operación matemática
python3 test_local.py '{"prompt": "Calculate 5 + 3"}'
```

### Probar en modo interactivo (múltiples pruebas)

```bash
python3 test_local.py
```

Esto abrirá un modo interactivo donde puedes escribir múltiples mensajes:

```
Testing agent locally. Type 'exit' to quit.

> Hello, how are you?
Agent received: Hello, how are you?

> What is the weather?
Weather is sunny

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
export AGENT_NAME=agent-runtime-demo-1
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

### Configurar permisos del rol de ejecución (si es necesario)

Si después del despliegue el runtime falla al ejecutarse con errores relacionados con ECR (por ejemplo, "AccessDenied" al intentar acceder a imágenes Docker), es probable que el rol de ejecución no tenga los permisos ECR necesarios.

Para solucionarlo, ejecuta:

```bash
./grant-runtime-ecr-permissions.sh
```

Este script:
1. Identifica el rol de ejecución creado automáticamente (`AmazonBedrockAgentCoreSDKRuntime-*`)
2. Agrega una política inline con permisos ECR necesarios:
   - `ecr:GetAuthorizationToken`
   - `ecr:BatchGetImage`
   - `ecr:GetDownloadUrlForLayer`

**Nota**: Si el nombre del rol no coincide con el patrón esperado, edita el script y actualiza la variable `ROLE_NAME` con el nombre correcto de tu rol.

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
   agentcore status --agent agent_runtime_demo_1
   ```

4. **Problemas comunes**:
   - **Error de build**: Verifica que el código Python sea válido y que las dependencias estén en `requirements.txt`
   - **Error de permisos de despliegue**: Asegúrate de tener todos los permisos IAM necesarios para el usuario (ejecuta `./setup-user-iam-permissions.sh`)
   - **Error de permisos ECR durante ejecución**: Si el runtime falla al acceder a imágenes Docker, ejecuta `./grant-runtime-ecr-permissions.sh` para agregar permisos al rol de ejecución
   - **Error de plataforma**: Verifica que la plataforma (`linux/arm64` o `linux/amd64`) sea correcta
   - **Error de Docker**: Verifica que el Dockerfile se genere correctamente

5. **Reintentar despliegue**:
   ```bash
   # Limpiar recursos parciales si es necesario
   # Luego reintentar
   ./deploy.sh
   ```

## Notas sobre el Modelo LLM

Este ejemplo mínimo **no incluye un modelo LLM**. El código funciona y es válido para Bedrock AgentCore Runtime, pero usa lógica simple basada en palabras clave.

**Para producción real**, deberías:
- Usar un framework de agentes como **Strands Agents** con **BedrockModel** (Claude, Llama, etc.)
- Integrar el modelo LLM en la función `agent_handler` para generar respuestas inteligentes
- Ver el [tutorial oficial](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/runtime_with_strands_and_bedrock_models.ipynb) para un ejemplo completo con modelo

El patrón `@app.entrypoint` funciona tanto con lógica simple como con modelos LLM complejos.

## Referencias

- [Tutorial oficial](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/runtime_with_strands_and_bedrock_models.ipynb)
- [Amazon Bedrock AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
