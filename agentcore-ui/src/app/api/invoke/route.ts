export const runtime = "nodejs";

const SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id";

export async function POST(request: Request) {
  const targetUrl =
    process.env.AGENTCORE_URL ?? "http://localhost:9001/invocations";

  const sessionId = request.headers.get(SESSION_HEADER) ?? "";
  const contentType = request.headers.get("content-type") ?? "application/json";
  const authorization = request.headers.get("Authorization");

  const response = await fetch(targetUrl, {
    method: "POST",
    headers: {
      "Content-Type": contentType,
      ...(sessionId ? { [SESSION_HEADER]: sessionId } : {}),
      ...(authorization ? { Authorization: authorization } : {}),
    },
    body: await request.text(),
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: {
      "content-type":
        response.headers.get("content-type") ?? "application/octet-stream",
    },
  });
}
