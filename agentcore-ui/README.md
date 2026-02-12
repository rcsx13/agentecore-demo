# UI para AgentCore Runtime (Demo 4)

Interfaz web en Next.js para consumir el runtime local que expone
`http://localhost:9001/invocations` y soporta streaming SSE.

## Requisitos

- Runtime local levantado (Docker) en `http://localhost:9001/invocations`.
- Node.js 18+.

## Configuración

El UI usa un proxy interno (`/api/invoke`) para evitar CORS. El destino real
se configura con `AGENTCORE_URL` (solo del lado servidor).

Ejemplo con `.env.local`:

```bash
AGENTCORE_URL=http://localhost:9001/invocations

# Login con Cognito (usuario/contraseña)
COGNITO_CLIENT_ID=<client_id de .cognito-info.json>
COGNITO_CLIENT_SECRET=<client_secret de .cognito-info.json>
COGNITO_DOMAIN=<cognitoDomain de .cognito-info.json, ej: us-east-1-xxx.auth.us-east-1.amazoncognito.com>
```

**Cognito**: El cliente debe tener `ALLOW_USER_PASSWORD_AUTH` en ExplicitAuthFlows.
Para habilitarlo:

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-id <CLIENT_ID> \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH
```

Necesitas un usuario creado en el User Pool (p. ej. con `admin-create-user`).

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

Ejecutar contenedor:

```bash
docker run --rm -p 3000:3000 \
  -e AGENTCORE_URL=http://host.docker.internal:9001/invocations \
  agentcore-ui
```

## Cómo funciona

- Envía `POST` con JSON `{"prompt":"..."}`.
- Usa el header de sesión `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`.
- Si la respuesta es `text/event-stream`, se procesa y muestra en tiempo real.
