from __future__ import annotations

import json
import os
from typing import Any, Callable

import requests

from .employee_agent import ModelAction


EMPLOYEE_SYSTEM_PROMPT = """You are an employee inside QuanTrade, a controlled virtual investment firm.

You receive a role, authority, WorkOrder, current Task, persistent Workspace,
messages, recent tool results, and the exact tools currently granted to you.

Rules:
- Interpret the objective and decide the next useful work step.
- Use only tools listed in available_tools. Never invent a capability or data source.
- When deterministic calculation/data retrieval is available as a tool, use it instead of guessing.
- You may revise your plan as evidence changes.
- You may request bounded work from another office when useful.
- Do not submit trades, change policy, expand your authority, or claim unavailable data.
- Artifacts are work products, not automatically Evidence or Decisions.
- If required data is unavailable, record the limitation or request clarification/work.
- Return exactly ONE next action as JSON. Do not include chain-of-thought, analysis, markdown, or prose outside the JSON.\n- If context.allowed_actions is present, choose only from that subset.

Allowed action shapes:
{"kind":"TOOL","payload":{"tool_name":"...","arguments":{},"label":"optional"}}
{"kind":"UPDATE_PLAN","payload":{"plan":{}}}
{"kind":"REQUEST_WORK","payload":{"recipient_office":"...","objective":"...","recipient_employee_id":"optional","context_refs":[]}}
{"kind":"SAVE_WORKSPACE","payload":{"state":{}}}
{"kind":"CREATE_ARTIFACT","payload":{"artifact_type":"...","title":"...","content_ref":"optional","metadata":{}}}
{"kind":"FINISH","payload":{"summary":"..."}}
"""


class AnthropicEmployeeProvider:
    """Production-capable Anthropic adapter for the provider-neutral employee loop.

    Construction/calls require an explicit API key. CI tests inject a fake HTTP
    function and never spend external API budget.
    """

    provider_name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int = 1200,
        timeout: int = 45,
        http_post: Callable[..., Any] = requests.post,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("CLAUDE_API_KEY", "")
        self.model_name = model or os.environ.get(
            "QUANTRADE_EMPLOYEE_MODEL", "claude-sonnet-4-6"
        )
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.http_post = http_post

    def _parse_action(self, text: str) -> ModelAction:
        cleaned = text.strip().replace("```json", "").replace("```", "").strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise ValueError("model response did not contain a JSON object")
        try:
            obj = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid structured action JSON: "
                f"{exc}; response_preview={cleaned[:500]!r}"
            ) from exc
        if not isinstance(obj, dict) or not isinstance(obj.get("kind"), str):
            raise ValueError("model action must contain string kind")
        payload = obj.get("payload", {})
        if not isinstance(payload, dict):
            raise ValueError("model action payload must be an object")
        return ModelAction(obj["kind"], payload)

    def next_action(self, context: dict) -> ModelAction:
        if not self.api_key:
            raise RuntimeError(
                "CLAUDE_API_KEY is not configured; live employee model call refused"
            )
        response = self.http_post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model_name,
                "max_tokens": self.max_tokens,
                "system": EMPLOYEE_SYSTEM_PROMPT,
                "messages": [{
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False),
                }],
            },
            timeout=self.timeout,
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        data = response.json()
        blocks = data.get("content") or []
        text_blocks = [
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if not text_blocks:
            raise ValueError("Anthropic response contained no text action")
        action = self._parse_action("\n".join(text_blocks))
        raw_usage = data.get("usage")
        usage = None
        if isinstance(raw_usage, dict) and raw_usage:
            usage = {"provider_raw": raw_usage}
            usage.update({
                "input_tokens": raw_usage.get("input_tokens"),
                "output_tokens": raw_usage.get("output_tokens"),
                "total_tokens": (
                    raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0)
                    if isinstance(raw_usage.get("input_tokens"), int)
                    and isinstance(raw_usage.get("output_tokens"), int)
                    else None
                ),
            })
        return ModelAction(action.kind, action.payload, usage)



class GeminiEmployeeProvider:
    """Gemini adapter for low-cost/free-tier employee evaluation.

    Uses generateContent because QuanTrade requires only one structured JSON
    action per turn. Live calls require GEMINI_API_KEY and never run in CI.
    """

    provider_name = "google"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 45,
        http_post: Callable[..., Any] = requests.post,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get(
            "GEMINI_API_KEY", ""
        )
        self.model_name = model or os.environ.get(
            "QUANTRADE_GEMINI_MODEL", "gemini-3.8-flash"
        )
        self.timeout = timeout
        self.http_post = http_post

    @staticmethod
    def _parse_action(text: str) -> ModelAction:
        cleaned = text.strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise ValueError("model response did not contain a JSON object")
        try:
            obj, _end_index = json.JSONDecoder().raw_decode(cleaned[start:])
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid structured action JSON: "
                f"{exc}; response_preview={cleaned[:500]!r}"
            ) from exc
        if not isinstance(obj, dict) or not isinstance(obj.get("kind"), str):
            raise ValueError("model action must contain string kind")
        payload = obj.get("payload", {})
        if not isinstance(payload, dict):
            raise ValueError("model action payload must be an object")
        return ModelAction(obj["kind"], payload)

    def next_action(self, context: dict) -> ModelAction:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured; live employee model call refused"
            )
        response = self.http_post(
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model_name}:generateContent"
            ),
            headers={
                "x-goog-api-key": self.api_key,
                "content-type": "application/json",
            },
            json={
                "systemInstruction": {
                    "parts": [{"text": EMPLOYEE_SYSTEM_PROMPT}]
                },
                "contents": [{
                    "role": "user",
                    "parts": [{
                        "text": json.dumps(context, ensure_ascii=False)
                    }],
                }],
                "generationConfig": {
                    "responseMimeType": "application/json",
                },
            },
            timeout=self.timeout,
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini response contained no candidate")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(
            p.get("text", "") for p in parts
            if isinstance(p, dict) and p.get("text")
        )
        if not text:
            raise ValueError("Gemini response contained no text action")
        action = self._parse_action(text)
        raw_usage = data.get("usageMetadata")
        usage = None
        if isinstance(raw_usage, dict) and raw_usage:
            usage = {"provider_raw": raw_usage}
            usage.update({
                "input_tokens": raw_usage.get("promptTokenCount"),
                "output_tokens": raw_usage.get("candidatesTokenCount"),
                "total_tokens": raw_usage.get("totalTokenCount"),
                "cached_input_tokens": raw_usage.get("cachedContentTokenCount"),
                "thoughts_tokens": raw_usage.get("thoughtsTokenCount"),
            })
        return ModelAction(action.kind, action.payload, usage)
