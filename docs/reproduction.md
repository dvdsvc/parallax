# Reproduce existing evidence

[Home](../README.md) · [Runtime setup](runtime.md)

## Offline aggregate verification

From the repository root, use an installed Python 3.12+ interpreter:

```sh
uv run --offline --no-project --python python3.12 scripts/reproduce_paper.py
uv run --offline --no-project --python python3.12 scripts/check_repository.py
```

There are no third-party dependencies for these commands. `--no-project` deliberately avoids installing framework dependencies; `--offline` prevents uv package retrieval. The scripts themselves use only the standard library and do not call provider services. Substitute an absolute interpreter path if needed. A direct Python invocation is also supported.

`reproduce_paper.py` executes the existing historical verifier in a subprocess, checks all 882 entries in `experiments/SHA256SUMS`, and recomputes utility, behavior, reliability and collaboration aggregates from retained panels. Its JSON output maps historical labels to semantic keys:

| New semantic key | Historical script label | Current manuscript |
|---|---|---|
| `behavior` | Table 3 | Table 1 |
| `utility` | Table 2 | Table 2 |
| `ratings` | Table 4 | Table 3 |

`check_repository.py` checks the copied-file manifest, eight core evidence artifacts across versions (exact values, with narrowly allowed anonymized locator differences), 260/69 index counts, all 19 selected report links, new documentation links, and high-confidence credential/private-path patterns. Frozen historical docs contain archival locators and are not promised as live local links. The original SHA256 index excludes itself; the source-copy manifest additionally protects that index.

## What this verifies

It verifies byte identity of preserved source/evidence snapshots and reproducibility of archived aggregates. It does not re-grade answers, re-run agents, reconstruct omitted raw transcripts or independently validate the external model judge. Frozen supporting R/Python snapshots may require their historical environments and external records; they are provenance, not additional commands silently executed by the quick start.

CI runs only these offline scripts on Python 3.12. No model keys are required. This repository is a local candidate; no hosted CI execution is asserted until it is published separately.

The root `SHA256SUMS` covers the complete showcase payload except itself. The checker verifies its exact file inventory and hashes; regenerate this inventory after intentional local edits. [Local validation record](validation.md).
