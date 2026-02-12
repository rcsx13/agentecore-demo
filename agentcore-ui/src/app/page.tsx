"use client";

import { FormEvent, useEffect, useState } from "react";

const DEFAULT_ENDPOINT = "/api/invoke";
const LOGIN_ENDPOINT = "/api/auth/login";
const SESSION_STORAGE_KEY = "agentcore-session-id";
const TOKEN_STORAGE_KEY = "agentcore-token";
const THEME_STORAGE_KEY = "agentcore-ui-theme";
const SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id";

const createSessionId = () => {
  if (typeof window === "undefined") {
    return "";
  }
  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const fallback = `session-${Date.now()}-${Math.random()
    .toString(16)
    .slice(2)}`;
  const nextId = crypto?.randomUUID?.() ?? fallback;
  window.localStorage.setItem(SESSION_STORAGE_KEY, nextId);
  return nextId;
};

const persistSessionId = (sessionId: string) => {
  if (!sessionId || typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
};

const readSseStream = async (
  response: Response,
  onChunk: (chunk: string) => void,
  onLine?: (line: string) => void,
) => {
  const reader = response.body?.getReader();
  if (!reader) {
    return;
  }
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      onLine?.(line);
      if (line.startsWith("data: ")) {
        onChunk(line.slice(6));
      }
    }
  }
  if (buffer) {
    onLine?.(buffer);
    if (buffer.startsWith("data: ")) {
      onChunk(buffer.slice(6));
    }
  }
};

export default function Home() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [token, setToken] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [output, setOutput] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === "light" || savedTheme === "dark") {
      setTheme(savedTheme);
      return;
    }
    const prefersLight =
      window.matchMedia?.("(prefers-color-scheme: light)")?.matches ?? false;
    setTheme(prefersLight ? "light" : "dark");
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = sessionStorage.getItem(TOKEN_STORAGE_KEY);
    if (saved) setToken(saved);
  }, []);

  useEffect(() => {
    if (token && typeof window !== "undefined") {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else if (!token && typeof window !== "undefined") {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }, [token]);

  useEffect(() => {
    const initialSessionId = createSessionId();
    setSessionId(initialSessionId);
  }, []);

  const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const username = (form.elements.namedItem("username") as HTMLInputElement)
      ?.value?.trim();
    const password = (form.elements.namedItem("password") as HTMLInputElement)
      ?.value;
    if (!username || !password) {
      setLoginError("Usuario y contraseña son obligatorios");
      return;
    }
    setIsLoggingIn(true);
    setLoginError(null);
    try {
      const res = await fetch(LOGIN_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setLoginError(data.detail ?? data.error ?? "Error al iniciar sesión");
        return;
      }
      setToken(data.access_token);
    } catch (err) {
      setLoginError(
        err instanceof Error ? err.message : "Error de conexión",
      );
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setOutput("");
    setLogs([]);
    setError(null);
  };

  useEffect(() => {
    persistSessionId(sessionId);
  }, [sessionId]);

  const formatLog = (message: string) =>
    `[${new Date().toISOString()}] ${message}`;

  const appendLog = (message: string) => {
    setLogs((previous) => [...previous, formatLog(message)]);
  };

  const resetSession = () => {
    const fallback = `session-${Date.now()}-${Math.random()
      .toString(16)
      .slice(2)}`;
    const nextId = crypto?.randomUUID?.() ?? fallback;
    setSessionId(nextId);
    setOutput("");
    setLogs([]);
    setError(null);
  };

  const ensureSessionId = () => {
    if (sessionId) {
      return sessionId;
    }
    const nextId = createSessionId();
    setSessionId(nextId);
    return nextId;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!prompt.trim()) {
      return;
    }
    setIsLoading(true);
    setOutput("");
    setLogs([]);
    setError(null);

    const startedAt = performance.now();
    let outputBuffer = "";
    let chunkCount = 0;

    try {
      const activeSessionId = ensureSessionId();
      appendLog(`request.start POST ${DEFAULT_ENDPOINT}`);
      appendLog(`request.session=${activeSessionId}`);
      appendLog(`request.prompt_chars=${prompt.trim().length}`);
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        [SESSION_HEADER]: activeSessionId,
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch(DEFAULT_ENDPOINT, {
        method: "POST",
        headers,
        body: JSON.stringify({ prompt: prompt.trim() }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const contentType = response.headers.get("content-type") ?? "";
      const headerSummary = Array.from(response.headers.entries())
        .map(([key, value]) => `${key}=${value}`)
        .join(" | ");
      appendLog(`response.status=${response.status}`);
      appendLog(`response.content_type=${contentType || "desconocido"}`);
      if (headerSummary) {
        appendLog(`response.headers=${headerSummary}`);
      }
      if (contentType.includes("text/event-stream")) {
        await readSseStream(
          response,
          (chunk) => {
            outputBuffer += chunk;
            setOutput((previous) => previous + chunk);
          },
          (line) => {
            if (line.startsWith(":")) {
              return;
            }
            chunkCount += line.startsWith("data: ") ? 1 : 0;
            appendLog(`sse.line=${line}`);
          },
        );
      } else {
        const data = await response.json();
        if (Array.isArray(data?.response) && data.response[0]) {
          outputBuffer = String(data.response[0]);
          setOutput(outputBuffer);
        } else {
          outputBuffer = JSON.stringify(data, null, 2);
          setOutput(outputBuffer);
        }
        appendLog("response.json=recibida");
      }
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Error inesperado";
      setError(message);
      appendLog(`error.message=${message}`);
      if (caught instanceof Error && caught.stack) {
        appendLog(`error.stack=${caught.stack.split("\n")[0]}`);
      }
    } finally {
      const elapsedMs = Math.round(performance.now() - startedAt);
      appendLog(`response.time_ms=${elapsedMs}`);
      if (chunkCount > 0) {
        appendLog(`response.sse_chunks=${chunkCount}`);
      }
      appendLog(`response.output_chars=${outputBuffer.length}`);
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div
        className={`min-h-screen px-6 py-12 flex items-center justify-center ${
          theme === "dark"
            ? "bg-slate-950 text-slate-100"
            : "bg-slate-50 text-slate-900"
        }`}
      >
        <div
          className={`w-full max-w-sm rounded-2xl border p-8 shadow-lg ${
            theme === "dark"
              ? "border-slate-800 bg-slate-900/60"
              : "border-slate-200 bg-white"
          }`}
        >
          <h1 className="text-xl font-semibold mb-6">Iniciar sesión</h1>
          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            <div>
              <label
                className={`block text-sm font-medium mb-1 ${
                  theme === "dark" ? "text-slate-200" : "text-slate-800"
                }`}
              >
                Usuario
              </label>
              <input
                name="username"
                type="text"
                autoComplete="username"
                required
                className={`w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-slate-500 ${
                  theme === "dark"
                    ? "border-slate-700 bg-slate-950 text-slate-100"
                    : "border-slate-200 bg-slate-50 text-slate-900"
                }`}
                placeholder="Usuario"
              />
            </div>
            <div>
              <label
                className={`block text-sm font-medium mb-1 ${
                  theme === "dark" ? "text-slate-200" : "text-slate-800"
                }`}
              >
                Contraseña
              </label>
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className={`w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-slate-500 ${
                  theme === "dark"
                    ? "border-slate-700 bg-slate-950 text-slate-100"
                    : "border-slate-200 bg-slate-50 text-slate-900"
                }`}
                placeholder="Contraseña"
              />
            </div>
            {loginError && (
              <p className="text-sm text-rose-500">{loginError}</p>
            )}
            <button
              type="submit"
              disabled={isLoggingIn}
              className={`inline-flex justify-center rounded-full px-5 py-2 text-sm font-semibold text-white transition disabled:opacity-50 ${
                theme === "dark"
                  ? "bg-indigo-500 hover:bg-indigo-400"
                  : "bg-indigo-600 hover:bg-indigo-500"
              }`}
            >
              {isLoggingIn ? "Entrando..." : "Entrar"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`min-h-screen px-6 py-12 ${
        theme === "dark"
          ? "bg-slate-950 text-slate-100"
          : "bg-slate-50 text-slate-900"
      }`}
    >
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-10">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <p
              className={`text-sm uppercase tracking-[0.3em] ${
                theme === "dark" ? "text-slate-400" : "text-slate-500"
              }`}
            >
              AgentCore Runtime
            </p>
            <h1 className="text-3xl font-semibold">
              Consola local para tu agente
            </h1>
            <p
              className={`text-base ${
                theme === "dark" ? "text-slate-300" : "text-slate-600"
              }`}
            >
              Envía prompts al runtime Docker y recibe respuesta en streaming.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleLogout}
              className={`inline-flex items-center rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-wide transition ${
                theme === "dark"
                  ? "border-slate-700 text-slate-200 hover:border-slate-500"
                  : "border-slate-200 text-slate-700 hover:border-slate-300"
              }`}
            >
              Salir
            </button>
            <button
            type="button"
              onClick={() =>
                setTheme((current) => (current === "dark" ? "light" : "dark"))
              }
              className={`inline-flex items-center justify-center rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-wide transition ${
                theme === "dark"
                  ? "border-slate-700 text-slate-200 hover:border-slate-500"
                  : "border-slate-200 text-slate-700 hover:border-slate-300"
              }`}
            >
              {theme === "dark" ? "Modo claro" : "Modo oscuro"}
            </button>
          </div>
        </header>

        <section
          className={`rounded-2xl border p-6 shadow-lg ${
            theme === "dark"
              ? "border-slate-800 bg-slate-900/60"
              : "border-slate-200 bg-white"
          }`}
        >
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            <div className="grid gap-3">
              <p
                className={`text-xs ${
                  theme === "dark" ? "text-slate-500" : "text-slate-400"
                }`}
              >
                Proxy fijo: <span className="font-mono">{DEFAULT_ENDPOINT}</span>
                {" • "}Header de sesión: {SESSION_HEADER}
              </p>
              <label
                className={`text-sm font-medium ${
                  theme === "dark" ? "text-slate-200" : "text-slate-800"
                }`}
              >
                Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={4}
                placeholder="Escribe una pregunta para el agente..."
                className={`w-full resize-none rounded-lg border px-3 py-2 text-sm outline-none focus:border-slate-500 ${
                  theme === "dark"
                    ? "border-slate-700 bg-slate-950 text-slate-100"
                    : "border-slate-200 bg-slate-50 text-slate-900"
                }`}
              />
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="submit"
                disabled={isLoading || !prompt.trim()}
                className={`inline-flex items-center justify-center rounded-full px-5 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed ${
                  theme === "dark"
                    ? "bg-indigo-500 hover:bg-indigo-400 disabled:bg-slate-700"
                    : "bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-300"
                }`}
              >
                {isLoading ? "Consultando..." : "Enviar prompt"}
              </button>
              <button
                type="button"
                onClick={resetSession}
                className={`inline-flex items-center justify-center rounded-full border px-5 py-2 text-sm font-semibold transition ${
                  theme === "dark"
                    ? "border-slate-700 text-slate-200 hover:border-slate-500"
                    : "border-slate-200 text-slate-700 hover:border-slate-300"
                }`}
              >
                Nueva sesión
              </button>
              <div
                className={`text-xs ${
                  theme === "dark" ? "text-slate-400" : "text-slate-500"
                }`}
              >
                Sesión activa:{" "}
                <span
                  className={`font-mono ${
                    theme === "dark" ? "text-slate-200" : "text-slate-700"
                  }`}
                >
                  {sessionId || "creando..."}
                </span>
              </div>
            </div>
          </form>
        </section>

        <section
          className={`rounded-2xl border p-6 ${
            theme === "dark"
              ? "border-slate-800 bg-slate-900/60"
              : "border-slate-200 bg-white"
          }`}
        >
          <div className="flex items-center justify-between">
            <h2
              className={`text-lg font-semibold ${
                theme === "dark" ? "text-slate-100" : "text-slate-900"
              }`}
            >
              Respuesta
            </h2>
            {isLoading ? (
              <span
                className={`text-xs ${
                  theme === "dark" ? "text-slate-400" : "text-slate-500"
                }`}
              >
                Streaming activo
              </span>
            ) : null}
          </div>
          {error ? (
            <div
              className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
                theme === "dark"
                  ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
                  : "border-rose-500/50 bg-rose-500/10 text-rose-700"
              }`}
            >
              {error}
            </div>
          ) : (
            <pre
              className={`mt-4 min-h-[180px] whitespace-pre-wrap rounded-lg px-4 py-3 text-sm ${
                theme === "dark"
                  ? "bg-slate-950 text-slate-200"
                  : "bg-slate-100 text-slate-800"
              }`}
            >
              {output || "Aún no hay respuesta."}
            </pre>
          )}
        </section>

        <section
          className={`rounded-2xl border p-6 ${
            theme === "dark"
              ? "border-slate-800 bg-slate-900/60"
              : "border-slate-200 bg-white"
          }`}
        >
          <div className="flex items-center justify-between">
            <h2
              className={`text-lg font-semibold ${
                theme === "dark" ? "text-slate-100" : "text-slate-900"
              }`}
            >
              Console log
            </h2>
            <button
              type="button"
              onClick={() => setLogs([])}
              className={`text-xs font-semibold uppercase tracking-wide transition ${
                theme === "dark"
                  ? "text-slate-400 hover:text-slate-200"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Limpiar
            </button>
          </div>
          <pre
            className={`mt-4 min-h-[160px] whitespace-pre-wrap rounded-lg px-4 py-3 text-xs ${
              theme === "dark"
                ? "bg-slate-950 text-slate-300"
                : "bg-slate-100 text-slate-700"
            }`}
          >
            {logs.length ? logs.join("\n") : "Aún no hay eventos."}
          </pre>
        </section>
      </main>
    </div>
  );
}
