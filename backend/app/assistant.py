"""Optional AI assistant backed by an OpenAI-compatible chat endpoint.

Nebius exposes NVIDIA Nemotron models behind an OpenAI-compatible API, so we
target that interface. The assistant is fully optional: if no API key /
opt-in is configured, the app still works (deterministic checks) and the
assistant simply reports that no provider is configured.

Privacy:
- We only ever send content that the operator has explicitly opted into
  (``ACCESSPILOT_AI_ENABLED`` and ``ACCESSPILOT_AI_USER_CONFIRMED`` both
  true) and only what the request supplies.
- No file contents are ever transmitted automatically. The caller decides
  how much context to include, and the report/assistant endpoints surface a
  clear notice when AI is off.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings

_SYSTEM_PROMPT = (
    "You are an accessibility advisor for university course materials. "
    "You help lecturers and students understand and remediate accessibility "
    "issues in PDF, DOCX and PPTX documents. Be concrete and actionable. "
    "Clearly separate facts from advice. If you are unsure or the evidence "
    "is insufficient, say so. You never claim WCAG or PDF/UA conformance "
    "from a limited set of checks."
)


class Assistant:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def _configured(self) -> bool:
        return self.s.ai_configured()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.s.ai_api_key}",
            "Content-Type": "application/json",
        }

    def ask(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a question to the configured provider and return the answer.

        Returns a dict shaped like ``AssistantResponse``. On any provider or
        network error, returns ``ok=False`` with a readable ``error`` rather
        than raising, so the UI can degrade gracefully.
        """
        if not self._configured():
            return {
                "ok": False,
                "answer": "",
                "model": None,
                "provider_configured": False,
                "error": (
                    "No AI provider is configured. Basic accessibility analysis "
                    "still works without it. To enable AI suggestions, set "
                    "ACCESSPILOT_AI_ENABLED=true, ACCESSPILOT_AI_API_KEY, and "
                    "ACCESSPILOT_AI_USER_CONFIRMED=true in your environment."
                ),
            }

        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        if context:
            # Keep context compact: JSON-dumped, truncated to avoid huge payloads.
            import json

            ctx = json.dumps(context, ensure_ascii=False)
            if len(ctx) > 20000:
                ctx = ctx[:20000] + " ... (truncated)"
            messages.append(
                {"role": "user", "content": f"Context from the document analysis:\n{ctx}"}
            )
        messages.append({"role": "user", "content": question})

        payload = {
            "model": self.s.ai_model,
            "messages": messages,
            "temperature": 0.2,
        }
        url = self.s.ai_base_url.rstrip("/") + "/chat/completions"

        try:
            with httpx.Client(timeout=self.s.ai_timeout_seconds) as client:
                resp = client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
                answer = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if not answer:
                    return {
                        "ok": False,
                        "answer": "",
                        "model": self.s.ai_model,
                        "provider_configured": True,
                        "error": "The provider returned an empty response.",
                    }
                return {
                    "ok": True,
                    "answer": answer,
                    "model": data.get("model", self.s.ai_model),
                    "provider_configured": True,
                    "error": None,
                }
        except httpx.HTTPStatusError as exc:
            return {
                "ok": False,
                "answer": "",
                "model": self.s.ai_model,
                "provider_configured": True,
                "error": (
                    f"AI provider returned HTTP {exc.response.status_code}. "
                    f"Check that the model name and endpoint are correct for "
                    f"your Nebius-compatible API."
                ),
            }
        except httpx.TimeoutException:
            return {
                "ok": False,
                "answer": "",
                "model": self.s.ai_model,
                "provider_configured": True,
                "error": f"AI provider request timed out after {self.s.ai_timeout_seconds:.0f}s.",
            }
        except Exception as exc:  # pragma: no cover - network/parse edge cases
            return {
                "ok": False,
                "answer": "",
                "model": self.s.ai_model,
                "provider_configured": True,
                "error": f"AI provider request failed: {exc.__class__.__name__}: {exc}",
            }
