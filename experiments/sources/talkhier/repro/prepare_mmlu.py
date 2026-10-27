"""Download the official dataset at one revision; export all native-domain splits."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from common import DOMAINS, MANIFEST, ROOT, UPSTREAM, digest, workspace_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", help="Official cais/mmlu commit; reuses an existing manifest by default")
    args = parser.parse_args()
    workspace_environment()
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else None
    if previous and not args.revision and all((ROOT / "data" / "mmlu" / d).exists() for d in DOMAINS):
        from common import verify_domain
        for domain in DOMAINS:
            verify_domain(domain)
            print(f"{domain}: existing frozen export verified", flush=True)
        return
    from datasets import load_dataset
    from huggingface_hub import HfApi

    revision = args.revision or (previous["dataset_revision"] if previous else None)
    info = HfApi(token=False).dataset_info("cais/mmlu", revision=revision)
    revision = info.sha
    if previous and previous["dataset_revision"] != revision:
        raise SystemExit("Existing frozen dataset revision differs; prepare a separate workspace to change it")
    manifest = {
        "dataset": "cais/mmlu", "dataset_revision": revision,
        "source": f"https://huggingface.co/datasets/cais/mmlu/tree/{revision}",
        "upstream_agent_commit": UPSTREAM,
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection": "All rows, in original order, for all splits of the five native MMLU domains; no sampling",
        "domains": {},
    }
    for domain in DOMAINS:
        target = ROOT / "data" / "mmlu" / domain
        if previous and target.exists():
            from common import verify_domain
            verify_domain(domain)
            manifest["domains"][domain] = previous["domains"][domain]
            print(f"{domain}: existing frozen export verified", flush=True)
            continue
        dataset = load_dataset("cais/mmlu", domain, revision=revision, token=False)
        target.mkdir(parents=True, exist_ok=True)
        dataset.save_to_disk(str(target / "hf_dataset"))
        split_info = {}
        for split, rows in dataset.items():
            path = target / f"{split}.jsonl"
            with path.open("w", encoding="utf-8") as f:
                for row in rows:
                    assert isinstance(row["question"], str) and row["question"]
                    assert isinstance(row["choices"], list) and len(row["choices"]) >= 2
                    assert isinstance(row["answer"], int) and 0 <= row["answer"] < len(row["choices"])
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            split_info[split] = {"rows": len(rows), "jsonl_path": str(path.relative_to(ROOT)), "sha256": digest(path)}
        files = [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": digest(p)}
                 for p in sorted(target.rglob("*")) if p.is_file()]
        manifest["domains"][domain] = {"arrow_path": str((target / "hf_dataset").relative_to(ROOT)),
                                       "splits": split_info, "files": files}
        print(f"{domain}: " + ", ".join(f"{k}={v['rows']}" for k, v in split_info.items()), flush=True)
    if previous:
        if previous["domains"] != manifest["domains"]:
            raise SystemExit("Rebuilt files differ from the committed data hashes; the manifest has not been overwritten")
    else:
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Manifest: {MANIFEST}", flush=True)


if __name__ == "__main__":
    main()
