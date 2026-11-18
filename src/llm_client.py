"""Local LLM client: talks to an Ollama server (default model qwen3:8b) and returns parsed JSON."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, Optional

DEFAULT_MODEL = os.getenv("VIBEMATCH_MODEL", "qwen3:8b")
DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


class LLMError(Exception):
    """The model answered, but not with usable JSON."""


class LLMUnavailable(LLMError):
    """The server could not be reached, timed out, or does not have the model."""


class OllamaClient:
    """Minimal Ollama chat client with deterministic settings and schema-constrained JSON output."""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST, timeout: float = 90.0,
                 temperature: float = 0.0, seed: int = 42):
        """Store connection and sampling settings (temperature 0 and a fixed seed for repeatable runs)."""
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.options = {"temperature": temperature, "seed": seed}
        self.last_latency = 0.0

    @property
    def name(self) -> str:
        """Label used in logs and output."""
        return f"ollama:{self.model}"

    def _request(self, path: str, payload: Optional[Dict] = None, timeout: Optional[float] = None) -> Dict:
        """POST (or GET when payload is None) to the Ollama API and decode the JSON reply."""
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.host + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as err:
            raise LLMUnavailable(f"Ollama not reachable at {self.host}: {err}") from err

    def is_available(self) -> bool:
        """True if the server answers and has this model pulled."""
        try:
            tags = self._request("/api/tags", timeout=3)
        except LLMUnavailable:
            return False
        return any(m.get("name") == self.model or m.get("model") == self.model for m in tags.get("models", []))

    def chat_json(self, system: str, user: str, schema: Optional[Dict] = None) -> Dict:
        """Send one system + user turn and return the reply parsed as a JSON object."""
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": schema or "json",
            "options": self.options,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        start = time.perf_counter()
        reply = self._request("/api/chat", payload)
        self.last_latency = time.perf_counter() - start
        if "error" in reply:
            raise LLMUnavailable(str(reply["error"]))
        content = (reply.get("message") or {}).get("content", "")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as err:
            raise LLMError(f"model returned invalid JSON: {content[:120]!r}") from err
        if not isinstance(parsed, dict):
            raise LLMError(f"model returned {type(parsed).__name__}, expected an object")
        return parsed
