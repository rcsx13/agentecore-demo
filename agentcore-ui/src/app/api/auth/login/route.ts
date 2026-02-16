/**
 * Login API: autentica usuario/contraseña vía Cognito InitiateAuth
 * y devuelve los JWT para usar con el AgentCore Runtime.
 *
 * Cognito NO soporta grant_type=password en el token endpoint.
 * Usamos InitiateAuth con USER_PASSWORD_AUTH.
 *
 * Requiere variables de entorno:
 *   COGNITO_CLIENT_ID
 *   COGNITO_CLIENT_SECRET (opcional si el client es público)
 *   COGNITO_REGION (ej: us-east-1)
 *
 * El cliente de Cognito debe tener ALLOW_USER_PASSWORD_AUTH en ExplicitAuthFlows.
 */

export const runtime = "nodejs";

import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
  AuthFlowType,
} from "@aws-sdk/client-cognito-identity-provider";
import { createHmac } from "crypto";

function computeSecretHash(
  username: string,
  clientId: string,
  clientSecret: string,
): string {
  return createHmac("sha256", clientSecret)
    .update(username + clientId)
    .digest("base64");
}

export async function POST(request: Request) {
  const clientId = process.env.COGNITO_CLIENT_ID;
  const clientSecret = process.env.COGNITO_CLIENT_SECRET;
  const region = process.env.COGNITO_REGION ?? process.env.AWS_REGION ?? "us-east-1";

  if (!clientId) {
    return Response.json(
      {
        error: "Server misconfigured",
        detail: "Missing COGNITO_CLIENT_ID",
      },
      { status: 500 },
    );
  }

  let body: { username?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const username = body.username?.trim();
  const password = body.password;

  if (!username || !password) {
    return Response.json(
      { error: "username and password are required" },
      { status: 400 },
    );
  }

  const authParams: Record<string, string> = {
    USERNAME: username,
    PASSWORD: password,
  };

  if (clientSecret) {
    authParams.SECRET_HASH = computeSecretHash(username, clientId, clientSecret);
  }

  try {
    const client = new CognitoIdentityProviderClient({ region });
    const command = new InitiateAuthCommand({
      AuthFlow: AuthFlowType.USER_PASSWORD_AUTH,
      ClientId: clientId,
      AuthParameters: authParams,
    });

    const response = await client.send(command);

    if (!response.AuthenticationResult) {
      return Response.json(
        {
          error: "Authentication failed",
          detail: response.ChallengeName ?? "No tokens returned",
        },
        { status: 401 },
      );
    }

    const { IdToken, AccessToken, ExpiresIn } = response.AuthenticationResult;

    // El customJWTAuthorizer valida client_id: usar AccessToken (Cognito lo incluye).
    // IdToken tiene aud, AccessToken tiene client_id que es lo que allowedClients verifica.
    const token = AccessToken ?? IdToken;
    if (!token) {
      return Response.json(
        { error: "No token in response" },
        { status: 500 },
      );
    }

    return Response.json({
      access_token: token,
      expires_in: ExpiresIn ?? 3600,
      token_type: "Bearer",
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Authentication failed";
    const name = err instanceof Error ? err.name : "";

    if (name === "NotAuthorizedException" || message.includes("NotAuthorized")) {
      return Response.json(
        { error: "Invalid username or password" },
        { status: 401 },
      );
    }
    if (name === "UserNotFoundException" || message.includes("UserNotFound")) {
      return Response.json(
        { error: "Invalid username or password" },
        { status: 401 },
      );
    }
    if (
      name === "UserNotConfirmedException" ||
      message.includes("UserNotConfirmed")
    ) {
      return Response.json(
        { error: "User not confirmed" },
        { status: 403 },
      );
    }

    console.error("[auth/login]", err);
    return Response.json(
      { error: "Authentication failed", detail: message },
      { status: 500 },
    );
  }
}
