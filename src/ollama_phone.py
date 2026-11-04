"""One local Ollama chat request for the adventure telephone. Standard library only.

The endpoint is deliberately fixed to loopback; world JSON can select a model,
but cannot redirect requests to an external provider or remote host.
"""
from __future__ import annotations

import http.client
import json
import re

HOST = "127.0.0.1"
PORT = 11434
DEFAULT_MODEL = "qwen2.5:3b"
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")


class OllamaPhoneError(RuntimeError):
    """A local model request failed or returned unusable data."""


def chat(model: str, messages: list[dict]) -> str:
    """Call only local Ollama's /api/chat (non-streaming), never a cloud URL."""
    if not isinstance(model, str) or not _MODEL_NAME.fullmatch(model):
        raise OllamaPhoneError("Invalid local Ollama model name.")
    body = json.dumps({"model": model, "messages": messages,
                       "stream": False, "options": {"num_predict": 160}}).encode("utf-8")
    connection = http.client.HTTPConnection(HOST, PORT, timeout=60)
    try:
        connection.request("POST", "/api/chat", body=body,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise OllamaPhoneError("Ollama response was too large.")
        if response.status != 200:
            if response.status == 404:
                raise OllamaPhoneError(f"Model '{model}' unavailable locally. Run: ollama pull {model}")
            raise OllamaPhoneError(f"Local Ollama returned HTTP {response.status}.")
        result = json.loads(data.decode("utf-8"))
        content = result.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaPhoneError("Local Ollama returned an empty reply.")
        return content.strip()
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise OllamaPhoneError(
            "Cannot reach local Ollama (127.0.0.1:11434). Start Ollama and check the model."
        ) from exc
    except (ValueError, UnicodeError, TypeError, AttributeError) as exc:
        raise OllamaPhoneError("Local Ollama returned an invalid chat response.") from exc
    finally:
        connection.close()
