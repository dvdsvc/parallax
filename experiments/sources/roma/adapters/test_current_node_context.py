"""Tests for the external DSPy request bridge and V2 prompt switch."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import current_node_context as bridge


class CurrentNodeContextTests(unittest.TestCase):
    def test_v2_off_leaves_chat_context_unchanged(self) -> None:
        messages = [{"role": "user", "content": "question"}]
        with patch.dict(os.environ, {"ROMA_ORG_AWARENESS_V2": "0"}, clear=False):
            prompt_out, messages_out = bridge._inject_org_awareness_v2("fallback", messages)
        self.assertEqual(prompt_out, "fallback")
        self.assertIs(messages_out, messages)

    def test_v2_alone_does_not_attach_role_or_node_metadata(self) -> None:
        controls = {
            "ROMA_ORG_AWARENESS_V2": "1",
            "ROMA_PROXY_ORG_AWARENESS_V2": "0",
            "ROMA_PROXY_SECOND_ORDER": "0",
            "ROMA_PROXY_SECOND_ORDER_LAYERS": "{}",
            "ROMA_PROXY_LAYER_OVERRIDES": "{}",
        }
        with patch.dict(os.environ, controls, clear=False):
            self.assertFalse(bridge._enabled())
            with bridge.bind_current_node(
                {"task_id": "t", "depth": 1, "agent_type": "Planner", "module_name": "planner"}
            ):
                request = bridge._with_current_node({"temperature": 0.0})
        self.assertEqual(request, {"temperature": 0.0})

    def test_v2_on_prepends_exact_system_text_and_changes_nothing_else(self) -> None:
        messages = [
            {"role": "system", "content": "ROMA role prompt"},
            {"role": "user", "content": "question"},
        ]
        before = [dict(message) for message in messages]
        original = {
            "temperature": 0.0,
            "max_tokens": 77,
            "tools": [{"type": "function", "function": {"name": "search"}}],
        }
        expected = bridge._V2_CONTEXT_PATH.read_text(encoding="utf-8")
        with patch.dict(os.environ, {"ROMA_ORG_AWARENESS_V2": "1"}, clear=False):
            prompt_out, messages_out = bridge._inject_org_awareness_v2(None, messages)

        self.assertIsNone(prompt_out)
        self.assertEqual(messages_out[0], {"role": "system", "content": expected})
        self.assertEqual(messages_out[1:], before)
        self.assertEqual(original, {
            "temperature": 0.0,
            "max_tokens": 77,
            "tools": [{"type": "function", "function": {"name": "search"}}],
        })

    def test_v2_on_converts_plain_prompt_to_user_message(self) -> None:
        expected = bridge._V2_CONTEXT_PATH.read_text(encoding="utf-8")
        with patch.dict(os.environ, {"ROMA_ORG_AWARENESS_V2": "1"}, clear=False):
            prompt_out, messages_out = bridge._inject_org_awareness_v2("question", None)
        self.assertIsNone(prompt_out)
        self.assertEqual(messages_out, [
            {"role": "system", "content": expected},
            {"role": "user", "content": "question"},
        ])

    def test_v2_insertion_is_idempotent_and_rejects_different_block(self) -> None:
        expected = bridge._V2_CONTEXT_PATH.read_text(encoding="utf-8")
        messages = [{"role": "system", "content": expected}, {"role": "user", "content": "q"}]
        with patch.dict(os.environ, {"ROMA_ORG_AWARENESS_V2": "1"}, clear=False):
            _, again = bridge._inject_org_awareness_v2(None, messages)
            with self.assertRaises(ValueError):
                bridge._inject_org_awareness_v2(
                    None,
                    [{"role": "system", "content": expected + " changed"}],
                )
        self.assertEqual(again, messages)


if __name__ == "__main__":
    unittest.main()
