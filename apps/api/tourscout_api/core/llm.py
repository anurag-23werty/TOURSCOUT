"""LLM layer: Gemini first, Groq as automatic fallback, every call logged.

Why it's hand-written instead of a framework client: the failover rules are the point.
- Main-tier work tries Gemini main → Gemini lite → Groq, each Gemini model with a fast-fail timeout. In Phase 1 and 3 the
  Gemini Flash main models returned 503 / timed out for whole days while lite and Groq kept answering.
- After a failure a per-model circuit breaker skips that model for cooldown_s, so later calls don't each wait for it.
- Groq: honour retry-after on 429 (free tier is 8k tokens/minute); if its server-side JSON-schema check rejects an
  answer, retry in plain JSON mode and validate locally.
- Structured output is validated with Pydantic; an invalid answer counts as a failure and goes to the next provider.
- Images (streaming-dashboard screenshots) are Gemini-only: Groq's gpt-oss is text-only.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypeVar

import anyio
import httpx
from pydantic import BaseModel, ValidationError

from .config import LLMSettings

T = TypeVar("T", bound=BaseModel)
Tier = Literal["main", "lite"]

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMUnavailable(RuntimeError):
    pass


class _ProviderError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _RateLimited(_ProviderError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"HTTP 429, retry after {retry_after:g}s")
        self.retry_after = retry_after


MAX_RETRY_AFTER_S = 15.0


@dataclass
class CallRecord:
    purpose: str
    provider: str
    model: str
    model_version: str | None
    seconds: float
    ok: bool
    error: str | None = None


class LLM:
    def __init__(self, settings: LLMSettings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.s = settings or LLMSettings()
        self.http = httpx.AsyncClient(transport=transport)
        self.calls: list[CallRecord] = []
        self._down_until: dict[str, float] = {}  # model → circuit-breaker reopen time

    async def aclose(self) -> None:
        await self.http.aclose()

    # ------------------------------------------------------------ public API

    async def json(
        self,
        schema: type[T],
        prompt: str,
        system: str = "",
        tier: Tier = "main",
        purpose: str = "",
        image: tuple[bytes, str] | None = None,
        patience_s: float | None = None,
    ) -> T:
        """Structured answer validated against `schema`. image = (bytes, mime type).

        patience_s raises the Gemini timeout and the longest Groq retry-after we wait for (for big, important calls).
        """
        last = "no provider configured"
        for provider, model in self._chain(tier, image is not None):
            try:
                raw = await self._ask(provider, model, prompt, system, purpose or schema.__name__, schema, image, patience_s)
                return schema.model_validate_json(_strip_fences(raw))
            except _ProviderError as exc:
                last = exc.reason
            except ValidationError as exc:
                last = f"invalid JSON for {schema.__name__}: {exc.errors()[0]['msg']}"
                self.calls[-1].ok, self.calls[-1].error = False, last
                if provider == "gemini":
                    self._trip(model)
        raise LLMUnavailable(last)

    async def text(self, prompt: str, system: str = "", tier: Tier = "main", purpose: str = "") -> str:
        last = "no provider configured"
        for provider, model in self._chain(tier, False):
            try:
                return await self._ask(provider, model, prompt, system, purpose or "text", None, None)
            except _ProviderError as exc:
                last = exc.reason
        raise LLMUnavailable(last)

    def usage(self) -> list[dict[str, Any]]:
        return [asdict(c) for c in self.calls]

    # ------------------------------------------------------------ routing

    def _chain(self, tier: Tier, needs_vision: bool) -> list[tuple[str, str]]:
        """Models to try in order. Main-tier work falls back Gemini main → Gemini lite → Groq."""
        geminis: list[tuple[str, str]] = []
        if self.s.gemini_key:
            models = [self.s.gemini_main, self.s.gemini_lite] if tier == "main" else [self.s.gemini_lite]
            geminis = [("gemini", m) for m in dict.fromkeys(models)]
        if needs_vision:
            return geminis  # tried even when the breaker is open: Groq can't read images
        geminis = [(p, m) for p, m in geminis if time.monotonic() >= self._down_until.get(m, 0.0)]
        groq = [("groq", self.s.groq_model)] if self.s.groq_key else []
        return groq + geminis if self.s.primary == "groq" else geminis + groq

    def _trip(self, model: str) -> None:
        self._down_until[model] = time.monotonic() + self.s.cooldown_s

    async def _ask(
        self, provider: str, model: str, prompt: str, system: str, purpose: str,
        schema: type[BaseModel] | None, image: tuple[bytes, str] | None, patience_s: float | None = None,
    ) -> str:
        start = time.perf_counter()
        try:
            if provider == "gemini":
                timeout = max(self.s.primary_timeout_s, patience_s or 0)
                text, version = await self._gemini(model, prompt, system, schema, image, timeout)
            else:
                wait = max(MAX_RETRY_AFTER_S, patience_s or 0)
                text, version = await self._groq(model, prompt, system, schema, self.s.fallback_timeout_s, wait)
        except _ProviderError as exc:
            self.calls.append(CallRecord(purpose, provider, model, None, _since(start), False, exc.reason))
            if provider == "gemini":
                self._trip(model)
            raise _ProviderError(f"{provider}/{model}: {exc.reason}") from None
        self.calls.append(CallRecord(purpose, provider, model, version, _since(start), True))
        return text

    # ------------------------------------------------------------ providers

    async def _gemini(
        self, model: str, prompt: str, system: str, schema: type[BaseModel] | None,
        image: tuple[bytes, str] | None, timeout: float,
    ) -> tuple[str, str | None]:
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if image:
            parts.append({"inline_data": {"mime_type": image[1], "data": base64.b64encode(image[0]).decode()}})
        body: dict[str, Any] = {"contents": [{"role": "user", "parts": parts}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if schema:
            body["generationConfig"] = {"responseMimeType": "application/json", "responseJsonSchema": schema.model_json_schema()}
        data = await self._post(GEMINI_URL.format(model=model), {"x-goog-api-key": self.s.gemini_key}, body, timeout)
        try:
            cand = data["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        except (KeyError, IndexError):
            raise _ProviderError(f"empty response ({data.get('promptFeedback') or 'no candidates'})") from None
        return text, data.get("modelVersion")

    async def _groq(
        self, model: str, prompt: str, system: str, schema: type[BaseModel] | None, timeout: float,
        max_wait_s: float = 15.0,
    ) -> tuple[str, str | None]:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body: dict[str, Any] = {"model": model, "messages": messages}
        if schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema(), "strict": False},
            }
        headers = {"Authorization": f"Bearer {self.s.groq_key}"}
        try:
            data = await self._post(GROQ_URL, headers, body, timeout)
        except _RateLimited as exc:
            if exc.retry_after > max_wait_s:
                raise _ProviderError(f"HTTP 429, retry after {exc.retry_after:g}s") from None
            await anyio.sleep(exc.retry_after)  # free tier: 8k tokens/minute, usually clears in seconds
            data = await self._post(GROQ_URL, headers, body, timeout)
        except _ProviderError as exc:
            if not (schema and "validate JSON" in exc.reason):
                raise
            # Groq checks json_schema server-side and rejects near-misses; ask for plain JSON and validate ourselves.
            body["response_format"] = {"type": "json_object"}
            body["messages"][0:0] = [{"role": "system", "content": "Reply with JSON matching this schema: "
                                      + json.dumps(schema.model_json_schema(), separators=(",", ":"))}]
            data = await self._post(GROQ_URL, headers, body, timeout)
        try:
            return data["choices"][0]["message"]["content"] or "", data.get("model")
        except (KeyError, IndexError):
            raise _ProviderError("empty response") from None

    async def _post(self, url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> dict[str, Any]:
        try:
            resp = await self.http.post(url, headers=headers, json=body, timeout=timeout)
        except httpx.TimeoutException:
            raise _ProviderError(f"timeout after {timeout:g}s") from None
        except httpx.TransportError as exc:
            raise _ProviderError(f"network error {exc.__class__.__name__}") from None
        if resp.status_code == 429 and "retry-after" in resp.headers:
            raise _RateLimited(float(resp.headers["retry-after"]))
        if resp.status_code != 200:
            raise _ProviderError(f"HTTP {resp.status_code} {_error_text(resp)}")
        return resp.json()


def _since(start: float) -> float:
    return round(time.perf_counter() - start, 2)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _error_text(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error")
        return str(err.get("message") if isinstance(err, dict) else err)[:120]
    except (ValueError, AttributeError):
        return resp.text[:120]


def dumps(obj: Any) -> str:
    """Compact JSON for prompts (Groq's free tier is 8k tokens/minute, so every byte counts)."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=str)
