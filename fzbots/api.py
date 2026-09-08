"""Cliente mínimo dos endpoints do llama-server (stdlib só)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


def health(porta: int, host: str = "127.0.0.1", timeout: float = 5) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{porta}/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def get_json(porta: int, caminho: str, host: str = "127.0.0.1", timeout: float = 10):
    with urllib.request.urlopen(f"http://{host}:{porta}{caminho}", timeout=timeout) as r:
        return json.loads(r.read().decode())


def post_json(porta: int, caminho: str, corpo: dict, host: str = "127.0.0.1", timeout: float = 120):
    req = urllib.request.Request(f"http://{host}:{porta}{caminho}", data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def chat_stream(porta: int, mensagens: list[dict], host: str = "127.0.0.1", max_tokens: int = 1024,
                timeout: float = 600):
    """Gera (tipo, pedaço) do /v1/chat/completions com stream=true (SSE).
    tipo = "texto" (resposta) ou "raciocinio" (modelos que pensam antes, ex.: Qwen3)."""
    corpo = {"messages": mensagens, "stream": True, "max_tokens": max_tokens}
    req = urllib.request.Request(f"http://{host}:{porta}/v1/chat/completions",
                                 data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for linha in r:
            linha = linha.decode("utf-8", errors="replace").strip()
            if not linha.startswith("data:"):
                continue
            dado = linha[5:].strip()
            if dado == "[DONE]":
                return
            try:
                ev = json.loads(dado)
            except json.JSONDecodeError:
                continue
            for esc in ev.get("choices", []):
                delta = esc.get("delta") or {}
                if delta.get("reasoning_content"):
                    yield ("raciocinio", delta["reasoning_content"])
                if delta.get("content"):
                    yield ("texto", delta["content"])


def embeddings(porta: int, textos: list[str], host: str = "127.0.0.1") -> list[list[float]]:
    d = post_json(porta, "/v1/embeddings", {"input": textos}, host=host)
    return [x["embedding"] for x in d.get("data", [])]


def modelos(porta: int, host: str = "127.0.0.1") -> list[str]:
    try:
        return [m["id"] for m in get_json(porta, "/v1/models", host=host).get("data", [])]
    except Exception:
        return []
