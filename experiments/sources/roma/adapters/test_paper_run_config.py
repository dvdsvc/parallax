from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_run_archive import PaperRunArchive
from run_isolated_seal0 import (
    MODEL_VISIBLE_PATH_POLICY,
    TOOL_ORDER_POLICY,
    WORKER_PYTHONHASHSEED,
    IsolatedController,
    condition_audit,
    new_worker_root,
    parse_args,
    worker_shell,
)


def make_config(*, condition: str = "11", legacy_org_bool: bool = False) -> dict:
    interventions = {
        "organization_awareness_v2": True,
        "second_order": {"enabled": True, "layers": {"executor": False}},
    }
    if legacy_org_bool:
        interventions["organization_awareness"] = False
    return {
        "schema_version": 1,
        "condition": condition,
        "task_indices": [0, 3],
        "workers": 4,
        "max_depth": 3,
        "model": "openai/qwen3.7-flash",
        "temperature": 0.0,
        "interventions": interventions,
    }


class PaperRunConfigTests(unittest.TestCase):
    def parse_config(self, config: dict):
        with tempfile.TemporaryDirectory(prefix="roma-paper-config-") as temp:
            path = Path(temp) / "run.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch.object(
                sys, "argv", ["runner", "--paper-run-config", str(path)]
            ):
                args = parse_args()
                relevant_env = {
                    key: os.environ.get(key)
                    for key in (
                        "ROMA_ORG_AWARENESS_V2",
                        "ROMA_PROXY_ORG_AWARENESS_V2",
                        "ROMA_PROXY_SECOND_ORDER",
                        "ROMA_PROXY_SECOND_ORDER_LAYERS",
                    )
                }
                return args, relevant_env

    def test_one_config_sets_all_run_factors(self) -> None:
        args, effective_env = self.parse_config(make_config())
        self.assertTrue(args.paper_run)
        self.assertEqual(args.benchmark, "SEAL-0")
        self.assertEqual(args.condition, "11")
        self.assertEqual(args.selected_indices, [0, 3])
        self.assertEqual(args.workers, 4)
        self.assertEqual(effective_env["ROMA_ORG_AWARENESS_V2"], "1")
        self.assertEqual(effective_env["ROMA_PROXY_ORG_AWARENESS_V2"], "0")
        self.assertEqual(effective_env["ROMA_PROXY_SECOND_ORDER"], "1")

    def test_rejects_three_bit_legacy_condition(self) -> None:
        with self.assertRaises(SystemExit):
            self.parse_config(make_config(condition="101"))

    def test_legacy_org_switch_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            self.parse_config(make_config(legacy_org_bool=True))

    def test_v2_audit_requires_exact_pre_litellm_block_when_on(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace_dir = Path(temp)
            (trace_dir / "pre_call.jsonl").write_text(
                json.dumps({
                    "condition_requested": "BASE",
                    "organization_awareness_v2": {"status": "present_pre_litellm"},
                }) + "\n",
                encoding="utf-8",
            )
            audit = condition_audit(trace_dir, "BASE", True)
        self.assertEqual(audit["condition_validation"], "validated")
        self.assertEqual(audit["organization_awareness_v2_validation"], "validated")

    def test_v2_audit_rejects_missing_or_unexpected_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace_dir = Path(temp)
            (trace_dir / "pre_call.jsonl").write_text(
                json.dumps({
                    "condition_requested": "BASE",
                    "organization_awareness_v2": {"status": "absent"},
                }) + "\n",
                encoding="utf-8",
            )
            on_audit = condition_audit(trace_dir, "BASE", True)
            off_audit = condition_audit(trace_dir, "BASE", False)
        self.assertEqual(on_audit["organization_awareness_v2_validation"], "mismatch")
        self.assertEqual(off_audit["organization_awareness_v2_validation"], "validated")

    def test_explicit_worker_root_is_unique_and_refuses_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "paper-run-unique.workers"
            args = type("Args", (), {
                "output": str(Path(temp) / "fallback.csv"),
                "condition": "BASE",
                "max_depth": 3,
                "workers": 1,
            })()
            controller = IsolatedController(args, [], worker_root=root)
            self.assertEqual(controller.root, root.resolve())
            with self.assertRaises(FileExistsError):
                IsolatedController(args, [], worker_root=root)

    def test_default_worker_paths_do_not_inherit_output_condition_labels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="roma-neutral-path-") as temp:
            output_root = Path(temp) / "runs"
            roots = []
            with patch("run_isolated_seal0.DEFAULT_OUTPUT_ROOT", output_root):
                for label in ("base", "v2"):
                    args = type("Args", (), {
                        "output": str(Path(temp) / f"seal0-{label}-repeat1.csv"),
                        "condition": "BASE",
                        "max_depth": 3,
                        "workers": 1,
                    })()
                    controller = IsolatedController(args, [])
                    self.assertEqual(controller.root.parent, output_root.resolve())
                    self.assertRegex(controller.root.name, r"^run-[0-9a-f]{32}\.workers$")
                    roots.append(controller.root)
            self.assertNotEqual(*roots)

    def test_neutral_paths_keep_worker_command_difference_at_v2_switch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="roma-neutral-path-") as temp:
            with patch("run_isolated_seal0.DEFAULT_OUTPUT_ROOT", Path(temp)):
                root = new_worker_root()
            trace = root / "q-0025" / "trace"
            commands = []
            for enabled in ("0", "1"):
                with patch.dict(os.environ, {"ROMA_ORG_AWARENESS_V2": enabled}, clear=True):
                    command = worker_shell(
                        python=Path("/usr/bin/python3"),
                        project_root=Path("/agent"),
                        benchmark_data=Path("/data/seal-0.parquet"),
                        original_index=25,
                        max_depth=3,
                        condition="BASE",
                        proxy_port=4000,
                        trace_dir=trace,
                        result_path=root / "q-0025" / "result.csv",
                        run_id="offline-check",
                    )[-1]
                storage_lines = [s for s in command.splitlines() if s.startswith("export STORAGE_BASE_PATH=")]
                self.assertEqual(len(storage_lines), 1)
                self.assertNotIn("seal0-base", storage_lines[0])
                self.assertNotIn("seal0-v2", storage_lines[0])
                commands.append(command.replace(f"export ROMA_ORG_AWARENESS_V2={enabled}", "export ROMA_ORG_AWARENESS_V2=[SWITCH]"))
            self.assertEqual(*commands)

    def test_archive_records_neutral_worker_mapping_and_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="roma-neutral-path-") as temp:
            archive_root = Path(temp) / "seal0-v2-repeat1"
            archive_root.mkdir()
            manifest_path = archive_root / "manifest.json"
            manifest_path.write_text(json.dumps({"execution": {"max_depth": 3}}))
            archive = PaperRunArchive(archive_root, "v2-repeat1", None, [])
            with patch("run_isolated_seal0.DEFAULT_OUTPUT_ROOT", Path(temp) / "runs"):
                root = new_worker_root()
            archive.set_worker_root(root, model_visible_path_policy=MODEL_VISIBLE_PATH_POLICY)
            execution = json.loads(manifest_path.read_text())["execution"]
            self.assertEqual(execution["worker_root"], str(root.resolve()))
            self.assertEqual(execution["model_visible_path_policy"], "opaque_run_id_v1")
            self.assertEqual(execution["max_depth"], 3)
            self.assertEqual(archive.run_id, "v2-repeat1")

    def test_worker_hash_seed_overrides_all_bootstrap_sources(self) -> None:
        # Execute only a local env probe. No provider, benchmark or tool calls.
        with tempfile.TemporaryDirectory(prefix="roma-hash-seed-") as temp:
            root = Path(temp)
            bootstrap = root / "bootstrap.env"
            bootstrap.write_text("export PYTHONHASHSEED=random\n", encoding="utf-8")
            probe = root / "probe.py"
            probe.write_text(
                "import os\nprint(os.environ['PYTHONHASHSEED'])\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {"PYTHONHASHSEED": "123"}, clear=True), \
                 patch("run_isolated_seal0.CREDENTIAL_FILE", bootstrap), \
                 patch("run_isolated_seal0.ENV_FILE", bootstrap), \
                 patch("run_isolated_seal0.E2B_CREDENTIAL_FILE", bootstrap), \
                 patch("run_isolated_seal0.RUNNER", probe):
                command = worker_shell(
                    python=Path(sys.executable), project_root=root,
                    benchmark_data=root / "unused.parquet", original_index=0,
                    max_depth=3, condition="BASE", proxy_port=4000,
                    trace_dir=root / "trace", result_path=root / "unused.csv",
                    run_id="offline-hash-probe",
                )
                result = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), WORKER_PYTHONHASHSEED)

    def test_archive_records_fixed_tool_order_protocol(self) -> None:
        with tempfile.TemporaryDirectory(prefix="roma-hash-seed-") as temp:
            root = Path(temp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({"execution": {}}))
            archive = PaperRunArchive(root, "offline", None, [])
            archive.set_worker_root(
                root / "workers", worker_python_hash_seed=WORKER_PYTHONHASHSEED,
                tool_order_policy=TOOL_ORDER_POLICY,
            )
            execution = json.loads(manifest_path.read_text())["execution"]
            self.assertEqual(execution["worker_python_hash_seed"], "0")
            self.assertEqual(execution["tool_order_policy"], "fixed_python_hash_seed_v1")


if __name__ == "__main__":
    unittest.main()
