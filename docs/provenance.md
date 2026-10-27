# Provenance and contribution guide

[Home](../README.md) · [Copied-file manifest](../provenance/source_manifest.json) · [Original source manifests](../experiments/provenance)

## Package layers

`experiments/` is the full historical supplement dated 2026-10-09: 883 files, of which 882 are covered by its own SHA256 index. It retains native sources, adapters, locks, prompt bytes, configs and quantitative panels in their original packaged layout. `paper_evidence/` is the later current-manuscript support bundle (55 files), aligned with the corrected manuscript and retaining selected AI interactions. The PDF and five minimal source files come from the existing author-identified local preprint derivative. The anonymous submission source and all original packages are left in place.

The eight core quantitative artifacts retain the same analysis values across the full supplement and current paper evidence. Three are byte-identical; the others differ in JSON formatting, anonymized archive locators, or the locator keys of source-hash maps (whose hash values are unchanged). The offline checker permits only these explicitly audited locator fields and requires all other JSON content to agree. Old title/table-number differences are retained as version information. New scripts, bilingual front matter and index formatting are showcase additions, distinct from the original research implementation.

## What belongs to this research

Code and records support work on model-input visibility auditing, static informational treatment design/insertion, condition verification, sampling and paired archival workflows, and analysis of task trees, role/tool work, utility, reliability and collaboration. Source ownership is not inferred from repository size. The user's independent-study attribution is retained; Git and manifests establish implementation states rather than authorship of every line. Upstream framework architecture, original benchmark construction, external rubrics and provider SDKs have their own authors.

ROMA's historical native commit is `a6e3bb4f9e0694375fa627fa4b8bf8cae50592a6`; the archived FRAMES source manifest separately identifies adapters `05e07285695a1905647672b76d2a1c6c9c84b11e`, proxy `5b6957290b6a282471a4dd6eebe331312c907de4` and controls `99696f1e2cd338e3f7ee0cdd690b4f4e76d5268b`, including recorded dirty files. These are not assumed to identify every SEAL archive. TalkHier upstream is `842a62160bcd326c5f8bb11c6cd1f3da7ced00f6`; its primary report identifies experimental source `0cddfdc3581bafb969b9d71e68dbeca1c4e6bdde`. Compatibility changes and the treatment adapter are recorded separately.

## Index and report transformations

The existing index supplies 260 report metadata records, 69 run-manifest records, 19 preferred reports and explicit version relations. The 19 report bodies are copied with personal filesystem paths replaced by archive locators, links to other bundled reports made relative, and selected small linked images copied. Unbundled local targets are readable archive references rather than clickable dead links. Original and packaged hashes are recorded. Other 241 reports are metadata only; all raw run directories are not bundled.

`source_verified_now` reports whether a selected original still matches the index's recorded hash. Historical `review_level`, `reviewed_at` and manifest status retain their original meanings. This packaging does not claim new review of all 260 reports or current process status for 69 manifests. Primary, supporting, historical and later-excluded entries are labeled in the reading list.

## Reuse and release

Native source snapshots and original licenses are retained. A later ROMA checkout supplied an MIT license file, preserved separately with its source hash; that file is absent from the pinned historical commit, so historical redistribution coverage needs owner verification. No blanket license is assigned to mixed research code, paper or benchmark data. See [third-party notices](../THIRD_PARTY_NOTICES.md).

The local source-copy manifest records original hashes and transformations without publishing private home paths. The private owner review retains exact local source locations for checking. No Git histories, original experiments, source repositories or submission files were edited by this preparation.
