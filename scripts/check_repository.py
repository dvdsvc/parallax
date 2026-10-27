"""Check copied artifacts, reading links and high-confidence sensitive patterns.

This is a bounded release-preparation check, not proof of absence of every
possible secret or a legal determination about data redistribution.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
CORE = (
    "seal0_results.json", "roma_recursion.json", "frames_aligned.json",
    "talkhier_summary.json", "collaboration_derivation.json",
    "reliability_derivation.json", "morphology_results.json", "pls_full_results.json",
)
SECRET = re.compile(
    r"sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{25,}|"
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"
)
PRIVATE_PATH = re.compile(r"/" + r"Users/[^/\s]+/|/private/" + r"var/folders/")
HASH_MAPS = {
    "seal0_results.json": {"/sources_sha256"},
    "roma_recursion.json": {"/source_hashes"},
    "talkhier_summary.json": {"/secondary_scoring/input_sha256"},
    "collaboration_derivation.json": {"/source_sha256"},
}
TALKHIER_LOCATORS = {
    "/secondary_scoring/batch", "/primary/batch", "/secondary/batch",
    "/official_scoring/parameters/parent_batch", "/secondary/failures/0/directory",
    *(f"/primary/failures/{i}/directory" for i in range(6)),
}


def evidence_differences(a, b, name: str, pointer: str = "") -> list[str]:
    """Allow only audited locator changes, never numeric/statistical changes."""
    if pointer in HASH_MAPS.get(name, set()):
        if isinstance(a, dict) and isinstance(b, dict) and sorted(a.values()) == sorted(b.values()):
            return []
        return [pointer + " (source hash values differ)"]
    if name == "talkhier_summary.json" and pointer in TALKHIER_LOCATORS:
        if isinstance(a, str) and isinstance(b, str) and a.startswith(("archives/", "external_archive/")) and re.fullmatch(r"archive-ref-[a-f0-9]{16}", b):
            return []
        return [pointer + " (unexpected locator transformation)"]
    if type(a) is not type(b):
        return [pointer + " (type)"]
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return [pointer + " (keys)"]
        return [d for key in a for d in evidence_differences(a[key], b[key], name, pointer + "/" + key)]
    if isinstance(a, list):
        if len(a) != len(b):
            return [pointer + " (length)"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in evidence_differences(x, y, name, pointer + "/" + str(i))]
    return [] if a == b else [pointer + " (value)"]


def read_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    errors: list[str] = []
    manifest = read_json("provenance/source_manifest.json")
    for record in manifest:
        path = ROOT / record["path"]
        if not path.is_file() or sha(path) != record["packaged_sha256"]:
            errors.append("Copied artifact mismatch: " + record["path"])
    alignment = []
    for name in CORE:
        a, b = ROOT / "experiments/data" / name, ROOT / "paper_evidence/data" / name
        differences = evidence_differences(json.loads(a.read_text()), json.loads(b.read_text()), name)
        alignment.append({"artifact": name, "byte_identical": sha(a) == sha(b),
                          "equivalent_after_audited_locator_mapping": not differences})
        if differences:
            errors.append("Cross-version semantic evidence differs: " + name + " " + ", ".join(differences[:3]))

    reports = read_json("index/catalog.json")
    runs = read_json("index/run_archive_index.json")
    if len(reports) != 260 or len(runs) != 69:
        errors.append("Historical catalogue counts changed")
    packaged = [r for r in reports if r.get("repository_path")]
    if len(packaged) != 19:
        errors.append("Expected 19 selected report bodies")
    for row in packaged:
        path = ROOT / row["repository_path"]
        if not path.is_file() or sha(path) != row["packaged_sha256"]:
            errors.append("Selected report mismatch: " + row["id"])
        if row.get("source_verified_now") is not True:
            errors.append("Original no longer matches curated index hash: " + row["id"])

    # Frozen source documentation deliberately retains old archival locators.
    # All newly authored guidance, curated report bodies and reading lists must
    # instead resolve their local Markdown targets within this repository.
    guidance = [ROOT / "README.md", ROOT / "README.zh-CN.md",
                ROOT / "THIRD_PARTY_NOTICES.md", ROOT / "LICENSE_PENDING.md",
                ROOT / "paper/README.md", ROOT / "index/reports.md", ROOT / "index/runs.md"]
    guidance += sorted((ROOT / "docs").glob("*.md"))
    guidance += sorted((ROOT / "reports").rglob("*.md"))
    checked_links = 0
    for path in guidance:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"!?\[[^\]]*\]\(([^\n)]+)\)", text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                errors.append("Unresolved guidance link: " + str(path.relative_to(ROOT)))
            checked_links += 1

    scanned = 0
    all_files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    inventory = ROOT / "SHA256SUMS"
    inventory_count = 0
    if inventory.is_file():
        expected = set()
        for line in inventory.read_text().splitlines():
            digest, relative = line.split("  ", 1)
            expected.add(relative)
            path = ROOT / relative
            if not path.is_file() or sha(path) != digest:
                errors.append("Showcase inventory mismatch: " + relative)
        actual = {str(p.relative_to(ROOT)) for p in all_files if p != inventory}
        if expected != actual:
            errors.append("Showcase file inventory changed; regenerate SHA256SUMS after intentional edits")
        inventory_count = len(expected)
    else:
        errors.append("Showcase SHA256SUMS missing")
    for path in all_files:
        rel = path.relative_to(ROOT)
        if path.is_symlink():
            errors.append("Unexpected symlink: " + str(rel))
        if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
            errors.append("Unapproved environment file: " + str(rel))
        if any(part in {".venv", "__pycache__", "node_modules", "mlruns"} for part in rel.parts):
            errors.append("Runtime or dependency artifact: " + str(rel))
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        scanned += 1
        # Never print a matching value; only identify the affected file.
        if SECRET.search(text):
            errors.append("Possible provider/private key: " + str(rel))
        if PRIVATE_PATH.search(text):
            errors.append("Personal filesystem locator: " + str(rel))

    result = {
        "copied_artifacts_verified": len(manifest),
        "showcase_inventory_verified": inventory_count,
        "cross_version_core_artifacts_verified": len(CORE),
        "cross_version_alignment": alignment,
        "report_metadata": len(reports), "run_metadata": len(runs),
        "selected_reports_verified": len(packaged),
        "guidance_links_checked": checked_links,
        "text_files_scanned": scanned,
        "files": len(all_files),
        "bytes": sum(p.stat().st_size for p in all_files),
        "limitations": [
            "No fresh agent execution or external scoring",
            "Frozen archival source docs may reference omitted external records",
            "Licensing and benchmark redistribution checks remain before publication",
        ],
        "errors": errors,
        "passed": not errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
