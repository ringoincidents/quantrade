"""Fixed synthetic inference pilot. No private input, tools, retries, or public listener."""
import json
import os
import urllib.error
import urllib.request
import unittest
from unittest.mock import MagicMock
from metadata_probe import NoRedirect, probe

PROMPT = "Synthetic QA only. A portfolio starts at 100, deposits 20, and ends at 130. Reply with just the investment profit as an integer."
MODELS = {
    "OPENAI": ("gpt-4o-mini", "https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
    "ANTHROPIC": ("claude-haiku-4-5-20251001", "https://api.anthropic.com/v1/messages", "ANTHROPIC_API_KEY"),
    "GEMINI": ("gemini-2.5-flash-lite", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent", "GEMINI_API_KEY"),
}
MAX_OUTPUT = 24
MAX_RESPONSE = 128 * 1024

def build(name, secret):
    model, url, _ = MODELS[name]
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    messages = [{"role": "user", "content": PROMPT}]
    if name == "OPENAI":
        headers["Authorization"] = "Bearer " + secret
        payload = {"model": model, "messages": messages, "max_completion_tokens": MAX_OUTPUT, "temperature": 0}
    elif name == "ANTHROPIC":
        headers.update({"x-api-key": secret, "anthropic-version": "2023-06-01"})
        payload = {"model": model, "messages": messages, "max_tokens": MAX_OUTPUT, "temperature": 0}
    else:
        headers["x-goog-api-key"] = secret
        payload = {"contents": [{"parts": [{"text": PROMPT}]}], "generationConfig": {"maxOutputTokens": MAX_OUTPUT, "temperature": 0, "thinkingConfig": {"thinkingBudget": 0}}}
    return urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")

def unpack(name, data):
    if name == "OPENAI":
        text = data["choices"][0]["message"]["content"]
        u = data["usage"]
        counts = (u["prompt_tokens"], u["completion_tokens"])
    elif name == "ANTHROPIC":
        text = "".join(p["text"] for p in data["content"] if p["type"] == "text")
        u = data["usage"]
        counts = (u["input_tokens"], u["output_tokens"])
    else:
        text = "".join(p["text"] for p in data["candidates"][0]["content"]["parts"] if not p.get("thought"))
        u = data["usageMetadata"]
        counts = (u["promptTokenCount"], u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0))
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError("bad usage")
    return ("PASS_INFERENCE" if text.strip() == "10" else "OUTPUT_MISMATCH", *counts)

def run(name, env=None, opener=None):
    env = os.environ if env is None else env
    secret = env.get(MODELS[name][2])
    if not secret:
        return ("MISSING_KEY", None, None)
    try:
        req = build(name, secret)
        if opener is None:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=15) as response:
            if response.status != 200:
                return ("HTTP_" + str(response.status), None, None)
            body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            return ("RESPONSE_TOO_LARGE", None, None)
        return unpack(name, json.loads(body))
    except urllib.error.HTTPError as e:
        return ("HTTP_" + str(e.code), None, None)
    except (OSError, urllib.error.URLError, TimeoutError):
        return ("TRANSPORT_ERROR", None, None)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return ("SCHEMA_OR_USAGE_INVALID", None, None)
    except Exception:
        return ("UNEXPECTED_ERROR", None, None)

def main():
    # Source-pinned one-shot image, one fixed request per provider, no retries.
    print("INFERENCE_PILOT synthetic only maximum 3 calls output cap 24 each", flush=True)
    for name in MODELS:
        status, inp, out = run(name)
        print(name, status, "input_tokens", inp, "output_tokens", out, flush=True)
    print("FINISHED no ongoing worker; inspect each provider status", flush=True)

class Tests(unittest.TestCase):
    def test_request_contract(self):
        for name in MODELS:
            req = build(name, "fake")
            self.assertEqual(req.method, "POST")
            payload = json.loads(req.data)
            self.assertIn(PROMPT, str(payload))
            self.assertNotIn("fake", str(payload))
            self.assertNotIn("tools", payload)
            cap = payload.get("max_completion_tokens", payload.get("max_tokens", payload.get("generationConfig", {}).get("maxOutputTokens")))
            self.assertEqual(cap, MAX_OUTPUT)
    def test_openai(self):
        self.assertEqual(unpack("OPENAI", {"choices":[{"message":{"content":"10"}}],"usage":{"prompt_tokens":32,"completion_tokens":1}}), ("PASS_INFERENCE",32,1))
    def test_anthropic(self):
        self.assertEqual(unpack("ANTHROPIC", {"content":[{"type":"text","text":"10"}],"usage":{"input_tokens":32,"output_tokens":1}}), ("PASS_INFERENCE",32,1))
    def test_gemini(self):
        self.assertEqual(unpack("GEMINI", {"candidates":[{"content":{"parts":[{"text":"10"}]}}],"usageMetadata":{"promptTokenCount":32,"candidatesTokenCount":1}}), ("PASS_INFERENCE",32,1))
    def test_bad_answer(self):
        self.assertEqual(unpack("OPENAI", {"choices":[{"message":{"content":"30"}}],"usage":{"prompt_tokens":32,"completion_tokens":1}})[0], "OUTPUT_MISMATCH")
    def test_missing_secret(self):
        opener = MagicMock()
        self.assertEqual(run("OPENAI", {}, opener)[0], "MISSING_KEY")
        opener.open.assert_not_called()
    def test_no_retry(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError("https://example.invalid", 429, "private", {}, None)
        self.assertEqual(run("OPENAI", {"OPENAI_API_KEY":"fake"}, opener)[0], "HTTP_429")
        opener.open.assert_called_once()

if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--test"]:
        unittest.main(argv=[sys.argv[0]])
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit(2)
