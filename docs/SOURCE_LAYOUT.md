# Source layout and version map

See the root README for the current tree and ARTIFACT_INDEX.md for direct links. This page distinguishes dataset provenance, experimental source and manuscript.

| Path | Meaning |
|---|---|
| `data/dataset_result/` | Frozen Data V3 manifests, main/backup membership, metadata summaries, readiness reports and 48 selected baseline-build logs |
| `data/dataset_result/frozen_source/` | Original Data V3 source snapshot; retain its version and hashes |
| `data/research_pipeline_v3/` | Working/portable Data V3 code/configuration; not interchangeable with the frozen snapshot |
| `data/v3_build_handoff/` | Build replay source, Docker/native declarations; not a bundled installed toolchain |
| `data/compiledrepos/<repo_id>/` | Thirty benchmark repository snapshots; frozen commits are recorded in the cohort |
| `data/cohort300.csv` | Convenience main-cohort manifest |
| `workspace/scripts_v2/` | Historical G0/E0 runner, AgoneTest helpers, split manifests, primary metrics and optional interfaces |
| `workspace/camera_ready_minimal/paired49_20261023/` | E49 generation/remeasurement/analysis source, original backups and configuration lineage |
| `workspace/camera_ready_minimal/b1_full300_20261026/` | E1 adapters/controllers, policies/admissions, completion lineage and canonical result tables |
| `paper/camera_ready/` | Revised PDF and all paper-specific LaTeX inputs; no new post-review audit files |
| `manifests/` | File hashes, original copy map and historical source index/assembly receipts |
| `docs/`, `tools/verify_bundle.py` | Current navigation and a standard-library file verification utility |

The original 1,601 copied workspace files remain byte-for-byte unchanged. Earlier audit/history/diagnostic source already present is retained as provenance; it does not imply that every output is admitted into the paper. No new 29 October audit scripts/reports are added by this documentation/manuscript update.

Markdown files previously removed from `workspace/` are not restored. Use current docs, configuration JSON and versioned source rather than links to deleted historical Markdown policy files. Absolute local paths in preserved manifests identify original evidence; the paths do not assert that every target file is publicly available.
