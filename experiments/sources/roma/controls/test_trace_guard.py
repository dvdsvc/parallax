from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trace_guard import validate_trace
from conditions import resolve
from mlflow_archive import _manifest_metadata


class TraceGuardTests(unittest.TestCase):
    def test_named_conditions_have_unambiguous_factor_values(self) -> None:
        item = resolve("intent_off__architecture_on")
        self.assertEqual(item["condition_code"], "01")
        self.assertFalse(item["global_intent_visible"])
        self.assertTrue(item["static_global_architecture_visible"])
        self.assertEqual(resolve("intent_on__architecture_on")["condition_code"], "11")

    def test_v2_condition_name_is_derived_from_both_switches(self) -> None:
        params, tags = _manifest_metadata({
            "condition": "11",
            "context_interventions": {"organization_awareness_v2": True},
            "agent": {
                "git": {"commit": "agent-sha", "dirty": False},
                "control_layer": {"commit": "control-sha"},
            },
        })
        self.assertEqual(params["condition_name"], "intent_on__architecture_on")
        self.assertEqual(params["control_layer_commit"], "control-sha")
        self.assertEqual(tags["condition_name"], "intent_on__architecture_on")

    def _trace(self, root: Path, event: dict) -> Path:
        trace = root / "trace"
        trace.mkdir()
        (trace / "pre_call.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
        return trace

    def test_accepts_expected_off_condition(self) -> None:
        event = {
            "condition_requested": "11",
            "effective_condition": "11",
            "layer": "atomizer",
            "organization_awareness": {"enabled": False, "injected": False, "status": "disabled", "role": "atomizer"},
            "second_order": {"master_enabled": False, "injected": False},
        }
        with tempfile.TemporaryDirectory() as directory:
            result = validate_trace(self._trace(Path(directory), event), "11", False)
        self.assertEqual(result["status"], "validated")

    def test_rejects_wrong_effective_condition(self) -> None:
        event = {
            "condition_requested": "11",
            "effective_condition": "01",
            "organization_awareness": {"injected": False, "status": "disabled"},
            "second_order": {"master_enabled": False, "injected": False},
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate_trace(self._trace(Path(directory), event), "11", True)

    def test_rejects_missing_node_position_injection(self) -> None:
        event = {
            "condition_requested": "11",
            "effective_condition": "11",
            "organization_awareness": {"injected": False, "status": "missing_node_snapshot"},
            "second_order": {"master_enabled": False, "injected": False},
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate_trace(self._trace(Path(directory), event), "11", True)


if __name__ == "__main__":
    unittest.main()
