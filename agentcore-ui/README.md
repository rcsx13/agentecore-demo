# UI para AgentCore Runtime (Demo 4)

Interfaz web en Next.js para consumir el AgentCore Runtime con login via Cognito.
El token JWT se obtiene de Cognito y se envía al runtime en cada invocación.

## Requisitos

- Node.js 18+.
- Runtime local (Docker) o desplegado en AWS.

## Configuración

El UI usa un proxy interno (`/api/invoke`) para evitar CORS. El destino real
se configura con `AGENTCORE_URL` (solo del lado servidor).

### Variables de entorno (`.env.local`)

Configuración rápida desde agentcore-demo-4:

```bash
./setup-env.sh
```

O manualmente:

```bash
# Destino del runtime (invoke)
AGENTCORE_URL=http://localhost:9001/invocations

# Cognito para login (usuario/contraseña)
# Valores desde agentcore-demo-4/.cognito-info.json
COGNITO_CLIENT_ID=<clientId>
COGNITO_CLIENT_SECRET=<clientSecret>
COGNITO_REGION=us-east-1
```

### Runtime local

Cuando el runtime corre en Docker localmente:
```bash
AGENTCORE_URL=http://localhost:9001/invocations
```

Para Docker desde otra máquina:
```bash
AGENTCORE_URL=http://host.docker.internal:9001/invocations
```

### Runtime desplegado en AWS

Cuando el agente está desplegado en AgentCore (no Docker), la UI invoca
directamente el endpoint HTTP de AWS con el JWT de Cognito:

```bash
cd agentcore-ui
./setup-env.sh --aws
```

Esto lee el `agent_arn` de `.bedrock_agentcore.yaml` y genera la URL:
`https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{agentArn}/invocations?qualifier=DEFAULT`

**Requisitos:**
- Agente desplegado con `agentcore launch` (en `agentcore-demo-4`)
- `customJWTAuthorizer` y `requestHeaderAllowlist: [Authorization]` (deploy.sh ya lo configura)

## Cognito

El cliente de Cognito debe tener `ALLOW_USER_PASSWORD_AUTH`:

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-id <CLIENT_ID> \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH
```

Necesitas un usuario creado en el User Pool (ej. con `admin-create-user`).

## Ejecutar en desarrollo

```bash
npm install
npm run dev
```

Luego abre `http://localhost:3000`.

## Docker

Construir imagen:

```bash
docker build -t agentcore-ui .
```

Ejecutar contenedor (con variables de entorno para Cognito y AGENTCORE_URL):

```bash
docker run --rm -p 3000:3000 \
  -e AGENTCORE_URL=http://host.docker.internal:9001/invocations \
  -e COGNITO_CLIENT_ID=<client_id> \
  -e COGNITO_CLIENT_SECRET=<client_secret> \
  -e COGNITO_REGION=us-east-1 \
  agentcore-ui
```

## Cómo funciona

1. **Login**: Usuario/contraseña → API `/api/auth/login` → `InitiateAuth` en Cognito.
2. **Token**: Se obtiene el JWT (IdToken); se guarda en sessionStorage.
3. **Invocación**: Cada `POST` a `/api/invoke` incluye `Authorization: Bearer <token>`.
4. **Proxy**: El proxy reenvía el header `Authorization` al runtime.
5. **Validación**: El runtime de AgentCore valida el JWT contra Cognito (customJWTAuthorizer).
6. **Streaming**: Si la respuesta es `text/event-stream`, se muestra en tiempo real.
