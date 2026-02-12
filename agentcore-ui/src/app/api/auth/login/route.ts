/**
 * Login API: intercambia usuario/contraseña por un JWT de Cognito.
 *
 * Requiere variables de entorno:
 *   COGNITO_CLIENT_ID
 *   COGNITO_CLIENT_SECRET
 *   COGNITO_DOMAIN (ej: us-east-1-xxx.auth.us-east-1.amazoncognito.com)
 *
 * El cliente de Cognito debe tener ALLOW_USER_PASSWORD_AUTH en ExplicitAuthFlows.
 */

export const runtime = "nodejs";

export async function POST(request: Request) {
  const clientId = process.env.COGNITO_CLIENT_ID;
  const clientSecret = process.env.COGNITO_CLIENT_SECRET;
  const cognitoDomain = process.env.COGNITO_DOMAIN;

  if (!clientId || !clientSecret || !cognitoDomain) {
    return Response.json(
      {
        error: "Server misconfigured",
        detail:
          "Missing COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET, or COGNITO_DOMAIN",
      },
      { status: 500 },
    );
  }

  let body: { username?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "Invalid JSON body" },
      { status: 400 },
    );
  }

  const username = body.username?.trim();
  const password = body.password;

  if (!username || !password) {
    return Response.json(
      { error: "username and password are required" },
      { status: 400 },
    );
  }

  const tokenUrl = `https://${cognitoDomain}/oauth2/token`;
  const auth = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  const params = new URLSearchParams({
    grant_type: "password",
    username,
    password,
    client_id: clientId,
  });

  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: `Basic ${auth}`,
    },
    body: params.toString(),
  });

  const data = await response.json();

  if (!response.ok) {
    return Response.json(
      {
        error: data.error ?? "Authentication failed",
        detail: data.error_description ?? undefined,
      },
      { status: response.status },
    );
  }

  return Response.json({
    access_token: data.access_token,
    expires_in: data.expires_in,
    token_type: data.token_type ?? "Bearer",
  });
}
