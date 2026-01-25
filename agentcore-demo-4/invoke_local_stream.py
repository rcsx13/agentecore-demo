#!/usr/bin/env python3
import sys
import uuid
from typing import Iterable, List, Optional, Tuple

import requests


SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"


def iter_sse_lines(response: requests.Response) -> Iterable[str]:
    """Yield decoded SSE lines from a streaming HTTP response."""
    for raw_line in response.iter_lines(chunk_size=1):
        if not raw_line:
            continue
        yield raw_line.decode("utf-8", errors="replace")


def extract_sse_data(lines: Iterable[str]) -> List[str]:
    """Collect data payloads from SSE lines."""
    chunks: List[str] = []
    for line in lines:
        if line.startswith("data: "):
            chunks.append(line[len("data: "):])
    return chunks


def parse_args(argv: List[str]) -> Tuple[Optional[str], str]:
    """Parse optional --session and a prompt string."""
    session_id = None
    prompt_parts: List[str] = []
    it = iter(argv)
    for item in it:
        if item == "--session":
            session_id = next(it, None)
        else:
            prompt_parts.append(item)
    prompt = " ".join(prompt_parts).strip() if prompt_parts else ""
    return prompt or None, session_id or str(uuid.uuid4())


def invoke(prompt: str, session_id: str, url: str) -> None:
    payload = {"prompt": prompt}
    headers = {SESSION_HEADER: session_id}

    with requests.post(url, json=payload, headers=headers, stream=True, timeout=300) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            print("Procesando respuesta en streaming (SSE):")
            chunks = extract_sse_data(iter_sse_lines(response))
            for chunk in chunks:
                print(f"chunk: {chunk}")
            full_response = " ".join(chunks).strip()
            if full_response:
                print("\nRespuesta completa:\n")
                print(full_response)
            return 0

        # Fallback: respuesta JSON no-streaming
        data = response.json()
        response_list = data.get("response", [])
        if response_list:
            print(response_list[0])
        else:
            print(data)

def main() -> int:
    prompt, session_id = parse_args(sys.argv[1:])
    url = "http://localhost:9001/invocations"

    if prompt:
        invoke(prompt, session_id, url)
        return 0

    print(f"Sesión: {session_id}")
    print("Modo interactivo. Escribe 'exit' para salir.\n")
    while True:
        user_input = input("> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break
        invoke(user_input, session_id, url)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
