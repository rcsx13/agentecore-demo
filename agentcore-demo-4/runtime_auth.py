"""
Local JWT authentication: valida el token del header Authorization.

Solo activo cuando JWT_LOCAL_VALIDATION=true (despliegue local).
En AWS, la validación la hace AgentCore Identity.
"""

import json
import logging
import os
from contextvars import ContextVar
from typing import Optional

from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Token del request actual (para que MCP client lo reutilice)
inbound_token: ContextVar[Optional[str]] = ContextVar(
    "inbound_token", default=None
)


def _load_auth_config() -> tuple[str, list[str]]:
    """Carga discoveryUrl y allowedClients desde .cognito-info.json."""
    path = ".cognito-info.json"
    if not os.path.exists(path):
        return "", []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        discovery_url = data.get("discoveryUrl")
        client_id = data.get("clientId")
        if discovery_url and client_id:
            return discovery_url, [client_id]
    except Exception as e:
        logger.debug(f"Could not load auth config from {path}: {e}")
    return "", []


def _resolve_jwks_uri(discovery_url: str) -> str:
    """Obtiene jwks_uri desde el discovery document."""
    import urllib.request

    with urllib.request.urlopen(discovery_url, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    jwks_uri = data.get("jwks_uri")
    if not jwks_uri:
        raise ValueError("No jwks_uri in discovery document")
    return jwks_uri


class LocalJWTAuthMiddleware(BaseHTTPMiddleware):
    """Valida JWT inbound solo en despliegue local."""

    def __init__(self, app, discovery_url: str, allowed_clients: list[str]):
        super().__init__(app)
        self._discovery_url = discovery_url
        self._allowed_clients = allowed_clients
        self._jwks_client = None

    def _get_jwks_client(self):
        if self._jwks_client is None:
            try:
                from jwt import PyJWKClient

                jwks_uri = _resolve_jwks_uri(self._discovery_url)
                self._jwks_client = PyJWKClient(jwks_uri, cache_keys=True)
                logger.info("JWKS client initialized for JWT validation")
            except Exception as e:
                logger.error(f"Failed to create JWKS client: {e}")
                raise
        return self._jwks_client

    async def dispatch(self, request: Request, call_next) -> Response:
        # /ping no requiere auth
        if request.url.path.rstrip("/") in ("/ping", ""):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:].strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={"error": "Empty Bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            import jwt

            jwks = self._get_jwks_client()
            signing_key = jwks.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_exp": True, "verify_aud": False},
            )

            # Validar client_id
            client_id = payload.get("client_id")
            if self._allowed_clients and (
                not client_id or client_id not in self._allowed_clients
            ):
                logger.warning(f"Token client_id {client_id!r} not in allowed list")
                return JSONResponse(
                    status_code=403,
                    content={"error": "Token client_id not allowed"},
                )

            # Token válido: guardar para MCP y continuar
            inbound_token.set(token)
            try:
                return await call_next(request)
            finally:
                inbound_token.set(None)

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return JSONResponse(
                status_code=401,
                content={"error": "Token expired"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT: {e}")
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.exception(f"JWT validation error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Authentication error"},
            )


def setup_local_auth_middleware() -> Optional[Middleware]:
    """Devuelve Middleware para JWT si estamos en modo local."""
    if not os.getenv("JWT_LOCAL_VALIDATION", "").lower() in ("true", "1", "yes"):
        return None

    discovery_url, allowed_clients = _load_auth_config()
    if not discovery_url or not allowed_clients:
        logger.warning(
            "JWT_LOCAL_VALIDATION=true but no discoveryUrl/allowedClients in .cognito-info.json"
        )
        return None

    logger.info("Auth: Local mode - JWT validation via middleware")
    return Middleware(
        LocalJWTAuthMiddleware,
        discovery_url=discovery_url,
        allowed_clients=allowed_clients,
    )
