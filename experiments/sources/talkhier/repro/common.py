"""Workspace-local paths and immutable native-benchmark data access."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "842a62160bcd326c5f8bb11c6cd1f3da7ced00f6"
DOMAINS = ("moral_scenarios", "college_physics", "machine_learning", "formal_logic", "us_foreign_policy")
MANIFEST = ROOT / "repro" / "mmlu_manifest.json"


def workspace_environment(offline=False):
    os.environ["HF_HOME"] = str(ROOT / ".cache" / "huggingface")
    os.environ["HF_DATASETS_CACHE"] = str(ROOT / ".cache" / "datasets")
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_TRACING"] = "false"
    os.environ["LANGSMITH_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_domain(domain):
    if domain not in DOMAINS:
        raise ValueError(f"Unsupported native MMLU domain: {domain}")
    manifest = json.loads(MANIFEST.read_text())
    item = manifest["domains"][domain]
    for record in item["files"]:
        path = ROOT / record["path"]
        if not path.is_file() or digest(path) != record["sha256"]:
            raise RuntimeError(f"Missing or changed frozen data: {record['path']}")
    return manifest, item


def load_frozen(domain):
    workspace_environment(offline=True)
    _, item = verify_domain(domain)
    from datasets import load_from_disk
    return load_from_disk(str(ROOT / item["arrow_path"]))


def native_dataset_loader(original_loader, domain, dataset):
    def load_dataset(path, *args, **kwargs):
        if path == "cais/mmlu":
            requested = args[0] if args else kwargs.get("name")
            if requested != domain:
                raise ValueError(f"Expected frozen {domain}, got {requested}")
            return dataset
        return original_loader(path, *args, **kwargs)
    return load_dataset
