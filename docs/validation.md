# Local validation record

Date: 2026-10-27. Scope: an independent local research-showcase copy. No model inference, new external grading, remote push, deployment or public release was performed.

| Check | Observed result |
|---|---|
| Existing historical aggregate verifier | Passed; all 882 listed historical artifacts verified; task utility, behavior, collaboration means and repeat reliability recomputed |
| Copied-source integrity | 966 copied artifacts have original/package hashes; the complete 883-file historical supplement and 55-file current support bundle are preserved byte for byte |
| Quantitative alignment across versions | Eight core JSON artifacts have the same analysis content; three are byte-identical, others differ only in formatting or explicitly audited archive locators/source-map keys; source hash values agree |
| Curated index consistency | 260 report metadata entries, 69 historical run metadata entries and 19 selected report bodies; all selected originals match their previously indexed hashes |
| Python syntax | 593 Python files compiled in memory under Python 3.12.13; no syntax errors; this does not execute every historical module |
| New guidance and selected report links | 147 local Markdown targets resolved before adding this validation page; the checker reports the current count |
| Sensitive-file scan | No high-confidence provider/private key or personal-home path matches in scanned text; no actual `.env`, dependency directory, new run archive or Git history bundled. Two credential-shaped literals were checked as local offline HTTP-mock placeholders |
| Upstream runtime | Preserved source/locks/configurations and documented entry points; no fresh full agent run validated |
| CI | Offline workflow added; equivalent scripts pass locally. Hosted workflow has not been run |

`SHA256SUMS` covers all showcase files except itself. Run [the repository check](../scripts/check_repository.py) and [aggregate reproduction](../scripts/reproduce_paper.py) from the root. The private owner review outside this candidate retains exact source locations, original-preservation verification and ZIP checks.

The archive intentionally contains earlier report conclusions, historical protocol differences and external references. Current paper results and the labeled reading list define the principal study. Owner license choice, historical ROMA license coverage and benchmark redistribution terms remain release checks. PDF and source files were reused from the existing verified local manuscript; no new PDF layout verification or TeX recompilation is claimed by this preparation.
