from __future__ import annotations

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROXY_ROOT = Path(__file__).resolve().parents[1] / "roma_litellm_proxy"
sys.path.insert(0, str(PROXY_ROOT))
import custom_hook  # noqa: E402


class OrganizationAwarenessV2Tests(unittest.TestCase):
    def test_proxy_observes_preinjected_static_v2_without_mutating_it(self) -> None:
        import asyncio
        import json

        with tempfile.TemporaryDirectory() as directory:
            env = {
                "ROMA_PROXY_CONDITION": "11",
                "ROMA_PROXY_EXPECTED_CONDITION": "11",
                "ROMA_PROXY_ORG_AWARENESS_V2": "0",
                "ROMA_PROXY_SECOND_ORDER": "0",
                "ROMA_PROXY_TRACE_DIR": directory,
            }
            context = custom_hook.ORG_AWARENESS_V2_CONTEXT_PATH.read_text(encoding="utf-8")
            messages = [
                {"role": "system", "content": context},
                {"role": "user", "content": "task"},
            ]
            data = {"messages": messages, "model": "unmapped-model"}
            with patch.object(custom_hook, "TRACE_DIR", Path(directory)):
                with patch.object(custom_hook, "_load_manifest", return_value=[]):
                    with patch.dict(os.environ, env, clear=False):
                        result = asyncio.run(
                            custom_hook.RomaPreCallHook().async_pre_call_hook(
                                None, None, data, "completion"
                            )
                        )
            expected = custom_hook.ORG_AWARENESS_V2_CONTEXT_PATH.read_text(encoding="utf-8")
            self.assertEqual(result["messages"], messages)
            record = json.loads(
                (Path(directory) / "pre_call.jsonl").read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertEqual(record["layer"], "unknown")
            self.assertEqual(record["organization_awareness_v2"]["status"], "present_pre_litellm")
            self.assertEqual(record["organization_awareness_v2"]["template_sha256"], custom_hook._digest(expected))

    def test_proxy_does_not_inject_when_context_is_absent(self) -> None:
        messages = [{"role": "user", "content": "task"}]
        audit = custom_hook._observe_org_awareness_v2(messages)
        expected = custom_hook.ORG_AWARENESS_V2_CONTEXT_PATH.read_text(encoding="utf-8")
        self.assertEqual(messages, [{"role": "user", "content": "task"}])
        self.assertEqual(audit["status"], "absent")
        self.assertEqual(audit["template_sha256"], custom_hook._digest(expected))

    def test_proxy_detects_prompt_mismatch_and_duplicate_without_role(self) -> None:
        good = custom_hook.ORG_AWARENESS_V2_CONTEXT_PATH.read_text(encoding="utf-8")
        mismatch = custom_hook._observe_org_awareness_v2(
            [{"role": "system", "content": good + "\nchanged"}]
        )
        duplicate = custom_hook._observe_org_awareness_v2(
            [{"role": "system", "content": good}, {"role": "system", "content": good}]
        )
        self.assertEqual(mismatch["status"], "content_mismatch")
        self.assertEqual(duplicate["status"], "duplicate_or_conflicting")

    def test_two_bit_condition_does_not_enable_proxy_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = {
                "ROMA_PROXY_CONDITION": "11",
                "ROMA_PROXY_ORG_AWARENESS_V2": "1",
                "ROMA_PROXY_ORG_AWARENESS": "1",
                "ROMA_PROXY_ORG_AWARENESS_CONTEXT": "/missing/legacy-template.txt",
                "ROMA_PROXY_TRACE_DIR": directory,
            }
            with patch.object(custom_hook, "TRACE_DIR", Path(directory)):
                with patch.dict(os.environ, env, clear=False):
                    import asyncio

                    result = asyncio.run(
                        custom_hook.RomaPreCallHook().async_pre_call_hook(
                            None,
                            None,
                            {"messages": [{"role": "user", "content": "task"}], "model": "roma-planner"},
                            "completion",
                        )
                    )
                    self.assertEqual(result["messages"], [{"role": "user", "content": "task"}])
            self.assertFalse((Path(directory) / "condition_guard.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
