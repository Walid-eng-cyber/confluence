from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class OllamaResponse:
    """The two attributes the pipeline reads off a model response."""

    content: str
    response_metadata: dict[str, Any] = field(default_factory=dict)


class DirectChatOllama:
    """Minimal /api/chat client that can switch off qwen3-style reasoning.

    Why this exists rather than ChatOllama: langchain-ollama 0.2.2 has no `think`
    parameter, and because ChatOllama is a permissive pydantic model it *accepts*
    `think=False` and silently drops it — which looks like it works and does not. The
    installed `ollama` package (0.4.5) has no such parameter either. Calling the endpoint
    directly is the only way to send it without upgrading both.

    It is deliberately duck-typed to the one method the pipeline uses, `invoke(messages)`
    returning an object with `.content` and `.response_metadata`, so it drops into
    `_invoke_with_retry` in place of ChatOllama with no other changes.

    Measured on qwen3:8b, one Stage 2 match call: 9.3s and 310 generated tokens with
    thinking on, 3.4s and 52 tokens with it off, for equivalent parsed output.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.1,
        num_ctx: int = 4096,
        num_predict: int | None = None,
        keep_alive: str = "10m",
        think: bool | None = False,
        timeout: float = 180.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.keep_alive = keep_alive
        self.think = think
        self.timeout = timeout

    def _payload(self, messages: Sequence[Any]) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": self.temperature, "num_ctx": self.num_ctx}
        if self.num_predict is not None:
            options["num_predict"] = self.num_predict

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": getattr(m, "role", "user"), "content": m.content} for m in messages
            ],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": options,
        }
        if self.think is not None:
            payload["think"] = self.think
        return payload

    def invoke(self, messages: Sequence[Any]) -> OllamaResponse:
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(self._payload(messages)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            # "code:500" keeps the retry classifier in _invoke_with_retry working.
            raise RuntimeError(f"ollama code:{exc.code} {detail}") from exc

        message = body.get("message") or {}
        return OllamaResponse(
            content=message.get("content") or "",
            response_metadata={
                "done_reason": body.get("done_reason", ""),
                "eval_count": body.get("eval_count"),
                "prompt_eval_count": body.get("prompt_eval_count"),
                # Present when thinking was NOT suppressed; useful for diagnosing cost.
                "thinking_chars": len(message.get("thinking") or ""),
            },
        )
