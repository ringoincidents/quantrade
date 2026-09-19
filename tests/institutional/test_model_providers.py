from __future__ import annotations

import unittest

from quantrade.institutional.model_providers import AnthropicEmployeeProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raised = False

    def raise_for_status(self):
        self.raised = True

    def json(self):
        return self.payload


class AnthropicEmployeeProviderTests(unittest.TestCase):
    def test_missing_api_key_refuses_live_call(self):
        provider = AnthropicEmployeeProvider(api_key="", http_post=lambda *a, **k: None)
        with self.assertRaises(RuntimeError):
            provider.next_action({"available_tools": []})

    def test_structured_action_is_parsed_without_reasoning_text(self):
        calls = []

        def fake_post(url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse({
                "content": [{
                    "type": "text",
                    "text": '{"kind":"TOOL","payload":{"tool_name":"data.catalog","arguments":{}}}',
                }]
            })

        provider = AnthropicEmployeeProvider(
            api_key="test-only",
            model="fixture-model",
            http_post=fake_post,
        )
        action = provider.next_action({"available_tools": [{"name": "data.catalog"}]})
        self.assertEqual("TOOL", action.kind)
        self.assertEqual("data.catalog", action.payload["tool_name"])
        self.assertEqual("fixture-model", calls[0][1]["json"]["model"])
        self.assertIn("available_tools", calls[0][1]["json"]["messages"][0]["content"])
        self.assertNotIn("chain_of_thought", calls[0][1]["json"])

    def test_markdown_fence_is_tolerated_but_only_json_action_is_returned(self):
        provider = AnthropicEmployeeProvider(api_key="test-only")
        action = provider._parse_action(
            '```json\n{"kind":"FINISH","payload":{"summary":"done"}}\n```'
        )
        self.assertEqual("FINISH", action.kind)
        self.assertEqual("done", action.payload["summary"])

    def test_non_json_response_is_rejected(self):
        provider = AnthropicEmployeeProvider(api_key="test-only")
        with self.assertRaises(ValueError):
            provider._parse_action("I think the next step is to query data.")

    def test_payload_must_be_object(self):
        provider = AnthropicEmployeeProvider(api_key="test-only")
        with self.assertRaises(ValueError):
            provider._parse_action('{"kind":"TOOL","payload":"bad"}')


if __name__ == "__main__":
    unittest.main()
