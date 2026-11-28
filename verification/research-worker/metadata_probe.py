"""One-shot metadata-only connectivity check; not a model gateway or inference."""
import concurrent.futures
import json
import os
import urllib.error
import urllib.request
import unittest
from unittest.mock import MagicMock

PROVIDERS = {
    "OPENAI": ("https://api.openai.com/v1/models", "OPENAI_API_KEY", "Authorization", "Bearer ", {}, "data"),
    "ANTHROPIC": ("https://api.anthropic.com/v1/models?limit=1", "ANTHROPIC_API_KEY", "x-api-key", "", {"anthropic-version": "2023-06-01"}, "data"),
    "GEMINI": ("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", "GEMINI_API_KEY", "x-goog-api-key", "", {}, "models"),
    "XAI": ("https://api.x.ai/v1/models", "XAI_API_KEY", "Authorization", "Bearer ", {}, "data"),
}
MAX_BODY = 4 * 1024 * 1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def probe(name, env=None, opener=None):
    env = os.environ if env is None else env
    url, key, header, prefix, extras, field = PROVIDERS[name]
    secret = env.get(key)
    if not secret:
        return "MISSING_KEY"
    try:
        req = urllib.request.Request(url, headers={**extras, header: prefix + secret, "Accept": "application/json"}, method="GET")
        if opener is None:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=8) as resp:
            if resp.status != 200:
                return "HTTP_" + str(resp.status)
            body = resp.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            return "RESPONSE_TOO_LARGE"
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get(field), list):
            return "SCHEMA_INVALID"
        if not data[field] or not all(isinstance(item, dict) for item in data[field]):
            return "NO_MODEL_METADATA"
        return "PASS_METADATA_ONLY"
    except urllib.error.HTTPError as e:
        return "HTTP_" + str(e.code)
    except (TimeoutError, urllib.error.URLError, OSError):
        return "TRANSPORT_ERROR"
    except (ValueError, TypeError):
        return "INVALID_RESPONSE"
    except Exception:
        return "UNEXPECTED_ERROR"

def main():
    print("RESEARCH_WORKER_METADATA_ONLY no inference no account data", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = dict(zip(PROVIDERS, executor.map(probe, PROVIDERS)))
    for provider, status in results.items():
        print(provider, status, flush=True)
    ok = all(value == "PASS_METADATA_ONLY" for value in results.values())
    print("FINISHED", "PASS_METADATA_ONLY" if ok else "BLOCKED_OR_PARTIAL", flush=True)
    return 0 if ok else 2

class ProbeTests(unittest.TestCase):
    def test_missing_key_no_request(self):
        opener = MagicMock()
        self.assertEqual(probe("OPENAI", {}, opener), "MISSING_KEY")
        opener.open.assert_not_called()

    def test_all_provider_metadata_requests(self):
        for name, (url, key, header, prefix, extras, field) in PROVIDERS.items():
            with self.subTest(provider=name):
                opener = MagicMock()
                response = opener.open.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = json.dumps({field: [{"id": "test"}]}).encode()
                self.assertEqual(probe(name, {key: "fixture"}, opener), "PASS_METADATA_ONLY")
                req = opener.open.call_args.args[0]
                self.assertEqual(req.full_url, url)
                self.assertEqual(req.get_method(), "GET")
                self.assertEqual(req.get_header(header.capitalize()), prefix + "fixture")

    def test_http_failure_no_body(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError("https://example.invalid", 401, "secret", {}, None)
        self.assertEqual(probe("OPENAI", {"OPENAI_API_KEY": "fixture"}, opener), "HTTP_401")

    def test_bad_schema(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"data":[]}'
        self.assertEqual(probe("OPENAI", {"OPENAI_API_KEY": "fixture"}, opener), "NO_MODEL_METADATA")

if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:]:
        raise SystemExit(2)
    else:
        raise SystemExit(main())
