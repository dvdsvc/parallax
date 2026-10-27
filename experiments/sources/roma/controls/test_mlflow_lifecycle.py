from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mlflow_archive import log_archive, start_mlflow_run


class MlflowLifecycleTests(unittest.TestCase):
    def test_precreated_run_is_finalized_with_the_same_archive(self) -> None:
        import mlflow
        from mlflow.tracking import MlflowClient

        with tempfile.TemporaryDirectory(prefix="roma-mlflow-lifecycle-") as temp:
            root = Path(temp)
            tracking_uri = "sqlite:///" + str(root / "tracking.db")
            archive = root / "paper-run"
            archive.mkdir()
            (archive / "outputs.jsonl").write_text(
                json.dumps({"status": "COMPLETED"}) + "\n", encoding="utf-8"
            )
            (archive / "manifest.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "archive_type": "roma_seal0_paper_run",
                    "run_id": "smoke-run-001",
                    "condition": "BASE",
                    "status": "completed",
                    "agent": {},
                    "benchmark": {"name": "SEAL-0"},
                    "execution": {},
                    "model": {},
                    "context_interventions": {},
                }),
                encoding="utf-8",
            )

            mlflow_run_id = start_mlflow_run(
                experiment="paper-run-lifecycle-smoke",
                run_name="smoke-run-001",
                tracking_uri=tracking_uri,
            )
            client = MlflowClient(tracking_uri=tracking_uri)
            self.assertEqual(client.get_run(mlflow_run_id).info.status, "RUNNING")

            logged_id = log_archive(
                archive,
                experiment="paper-run-lifecycle-smoke",
                run_name="smoke-run-001",
                tracking_uri=tracking_uri,
                existing_run_id=mlflow_run_id,
            )
            self.assertEqual(logged_id, mlflow_run_id)
            run = client.get_run(mlflow_run_id)
            self.assertEqual(run.info.status, "FINISHED")
            self.assertEqual(run.data.tags["paper_run_status"], "completed")
            artifacts = client.list_artifacts(mlflow_run_id, "paper_archive")
            self.assertIn("manifest.json", {item.path.rsplit("/", 1)[-1] for item in artifacts})


if __name__ == "__main__":
    unittest.main()
