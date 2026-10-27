"""Recompute frozen aggregates; no provider calls or new statistical tests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = ROOT / "experiments/analysis/reproduce_tables.py"
    completed = subprocess.run(
        [sys.executable, "-B", str(source)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    frozen = json.loads(completed.stdout)
    if frozen.get("passed") is not True:
        raise RuntimeError("Historical aggregate verifier did not pass")
    tables = frozen["tables"]
    result = {
        "paper_status": "AAMAS 2027 — Under Review",
        "package_files_verified": frozen["package_files_verified"],
        "difference_direction": frozen["difference_direction"],
        "behavior": tables["Table 3"],
        "utility": tables["Table 2"],
        "ratings": tables["Table 4"],
        "reliability_complete86": frozen["reliability_complete86"],
        "table_mapping": {
            "behavior": "historical Table 3 -> current Table 1",
            "utility": "historical Table 2 -> current Table 2",
            "ratings": "historical Table 4 -> current Table 3",
        },
        "uncertainty": frozen["uncertainty"],
        "fresh_inference_or_scoring": False,
        "passed": True,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
