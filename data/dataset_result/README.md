# Data V3 core provenance bundle

This directory publishes the compact, reviewable provenance for the final Data V3
sample. It preserves the authoritative manifests, step markers, validation reports,
winning build recipes, winning build logs, and the exact pipeline source snapshot used
for the original run.

The 30 published repository snapshots live in `../compiledrepos`. The convenience file
`../cohort300.csv` is byte-for-byte identical to
`class_sampling_manifest_final_seed42.csv` (SHA-256
`904a53dc6ed7741c91765cd2ca3d38929a10f8b34d10d6019b8175b5f514af3b`).

## Authoritative readiness evidence

- `results/RUN_READY` records the final `READY` state.
- `state/step000.done.json` through `state/step005.done.json` record the pipeline steps.
- `successful_repos_manifest.csv` identifies the final 30 repositories and commits.
- `class_sampling_manifest_final_seed42.csv` contains the final 300 main classes.
- `class_backup_manifest_seed42.csv` contains the 60 non-overlapping backup classes.
- `build_recipes_portable.csv` contains the 48 winning portable build recipes.
- `logs/build/` contains exactly the 48 validation logs referenced by those recipes.
- `results/SHA256SUMS.csv` records the original principal output and source hashes.

## Recommended reading order

1. Read `results/RUN_READY` and `results/validation_report.md` to confirm that the
   final validation passed.
2. Read `results/sampling_methodology.md` and
   `results/DATA_ACQUISITION_AND_EXPERIMENT_HANDOFF.md` for the acquisition and
   sampling design.
3. Use `class_sampling_manifest_final_seed42.csv` as the final 300-class main sample
   and `class_backup_manifest_seed42.csv` as the 60-class backup sample.
4. Use `successful_repos_manifest.csv` to map repository IDs to URLs and frozen
   commits. Published repository contents are under `../compiledrepos/<repo_id>`;
   `repository_storage_path` retains the original run location for provenance.
5. Use `build_recipes_portable.csv` for replay on another machine. Every row points to
   one included log under `logs/build/`.
6. Read the six `state/step*.done.json` markers in order to audit the pipeline history.
7. Use `frozen_source/` only to inspect the exact original implementation. Use
   `../research_pipeline_v3/` for a new portable run.

## File reference

### Root manifests and audit tables

| Path | Purpose |
|---|---|
| `successful_repos_manifest.csv` | Final 30 repositories, URLs, exact commits, buildable-class counts, and original storage records. |
| `class_sampling_manifest_seed42.csv` | Deterministic 300-class main sample before final relative-complexity labels. |
| `class_sampling_manifest_final_seed42.csv` | Authoritative final 300-class sample after Step 005 validation and labeling. |
| `class_backup_manifest_seed42.csv` | Sixty preregistered backups, exactly two per repository, with no overlap with the main sample. |
| `repo_sampling_summary.csv` | Compact per-repository counts for the 10-main and 2-backup allocation. |
| `repo_candidate_summary.csv` | Metadata-stage repository candidate summary produced by Step 001. |
| `repo_processing_order_seed42.csv` | Final deterministic repository queue and screening state. |
| `class_metrics_all.csv` | Structural and complexity measurements for focal classes in the final qualified repositories. |
| `excluded_classes_log.csv` | Reasons focal classes were excluded from the buildable sampling frame. |
| `build_attempts.csv` | Append-only audit of repository build attempts, including failed ladder attempts and retries. It is not the final recipe list. |
| `build_recipes.jsonl` | Exact winning commands and original working directories from the data-producing machine. |
| `build_recipes_portable.csv` | Forty-eight winning recipes rewritten with `${REPO_DIR}` for cross-machine replay. |
| `BUILD_EVIDENCE_SHA256SUMS.csv` | Hash inventory for the complete local evidence archive, including files deliberately omitted from this compact publication subset. |

### `results/`

| Path | Purpose |
|---|---|
| `RUN_READY` | Machine-readable final readiness marker and final-manifest hash. |
| `SHA256SUMS.csv` | Hashes of the original principal outputs and frozen pipeline source. |
| `validation_report.md` | Step 005 checks and observed pass counts. |
| `sampling_methodology.md` | Concise methodology and integrity rules for reporting the sample. |
| `data_integrity_report.md` | Summary of machine-checked safeguards. |
| `complexity_halves_summary.json` | Descriptive statistics for the relative 150/150 complexity halves. |
| `environment_versions.json` | Original OS, Python, JDK, Maven, Gradle, Git, and source-inventory evidence. |
| `DATA_ACQUISITION_AND_EXPERIMENT_HANDOFF.md` | Detailed acquisition narrative, disclosure requirements, and experiment handoff guidance. |

### `state/`

| Path | Purpose |
|---|---|
| `step000.done.json` | JDK/build-environment preflight and source inventory. |
| `step001.done.json` | Upstream dataset digest and physical focal-class reconstruction counts. |
| `step002.done.json` | Seed-42 deterministic repository queue. |
| `step003.done.json` | Thirty qualified repositories, 678 eligible buildable classes, and principal build artifacts. |
| `step004.done.json` | Deterministic 300-main and 60-backup selection. |
| `step005.done.json` | Independent reconstruction, integrity validation, and final result hashes. |
| `repo_processing_order_seed42.initial.csv` | Immutable initial queue before Step 003 updated processing states. |
| `config_snapshots/` | The exact frozen configuration recorded for every official step. The six files are intentionally identical. |
| `source_amendments/` | Hash-chained source inventory changes between Step 002 and Step 003. |

### `logs/build/`

This directory contains only the 48 successful validation logs referenced by
`build_recipes_portable.csv`. They establish that each published winning recipe passed
on the original machine. All rejected-candidate and non-winning logs remain outside this
compact Git bundle.

## Frozen source and portable source

`frozen_source/` contains the exact source and configuration bytes used by the original
Data V3 run. Their hashes match the source hashes recorded in
`results/SHA256SUMS.csv` and the source-amendment records.

`../research_pipeline_v3/` is the publication-friendly version. Its machine-specific
paths were converted to config-relative paths and its documentation was translated to
English. Those portability edits intentionally give it different hashes from the frozen
source. Scientific claims about the completed run refer to `frozen_source/`; new runs may
use the portable source.

`frozen_source/000_preflight_and_backup.py` through
`frozen_source/005_validate_and_report.py` are the six official step entry points.
`frozen_source/v3_core.py` contains their implementation. `pipeline_v3.py` is a retained
historical prototype and is not imported by the step-based pipeline. The YAML,
requirements, Maven settings, and Gradle init script record the exact configuration and
build fallback files used by the original run.

| Frozen path | Role in the original run |
|---|---|
| `000_preflight_and_backup.py` | Step 000 entry point: validates the environment, records the source inventory, and handles the optional immutable V2 recovery copy. |
| `001_reconstruct_unique_frame.py` | Step 001 entry point: reconstructs and deduplicates the focal-class frame. |
| `002_create_repo_queue.py` | Step 002 entry point: creates the deterministic seed-42 repository queue. |
| `003_screen_and_build_repositories.py` | Step 003 entry point: screens repositories and records JDK 8 build evidence. |
| `004_sample_classes.py` | Step 004 entry point: selects 10 main and 2 backup classes per qualified repository. |
| `005_validate_and_report.py` | Step 005 entry point: independently validates the sample and writes the final reports. |
| `v3_core.py` | Shared implementation used by the six official step entry points. |
| `pipeline_v3.py` | Earlier monolithic prototype retained for history; not used by the official step-based run. |
| `config_v3.yaml` | Exact machine-local protocol and path configuration used by the completed run. |
| `requirements-v3.txt` | Frozen Python dependency declaration. |
| `maven-settings-v3.xml` | Maven settings and preregistered repository fallback configuration. |
| `gradle-init-v3.gradle` | Gradle initialization and preregistered repository fallback configuration. |

## Relationship to V2

Data V3 is a new sampling protocol, not a rerun of V2 rules. It intentionally retains a
limited V2 lineage for provenance:

- Step 000 checks or records the frozen V2 recovery state and never modifies V2.
- `data_v2` and `research_pipeline` paths identify historical inputs and comparison
  material used during preflight.
- Maven and Gradle fallback repository lists were preregistered from V2 repair evidence
  before V3 screening. The 48 final winning recipes did not need the external-repository
  fallback.
- The Docker handoff may use a V2 image only as a JDK 8 base toolchain; it does not run
  V2 scripts or apply V2 eligibility rules.

V3 itself uses NLOC 5-500, no cyclomatic-complexity eligibility gate, seed 42, exactly 30
qualified repositories, and repository-balanced selection of 10 main plus 2 backup
classes per repository.

## Why original machine paths remain

Hard-coded paths in `frozen_source/config_v3.yaml`, `state/config_snapshots/`, exact
recipes, audit tables, and build logs describe where the completed run actually occurred.
They are historical evidence and must not be used as portable configuration or edited in
place. Changing them would invalidate recorded hashes.

For a new run, use `../research_pipeline_v3/config_v3.yaml`; its paths are relative to
the config file. For replay, use `build_recipes_portable.csv`, whose commands replace the
original workspace with `${REPO_DIR}`.

## Deliberately excluded from Git

The following files are not required for ordinary experiment execution and were omitted
to keep the repository small and reviewable:

- `raw_mapping_index.csv` (about 188 MB) and `unique_focal_class_frame.csv` (about
  70 MB). Their original sizes and hashes remain in `state/step001.done.json`; publish
  them separately through Git LFS or a release archive if full sampling reconstruction
  is required.
- The complete `logs/` tree. Only the 48 winning validation logs are included.
- `state/repo_metrics/`, which is detailed screening audit material rather than final
  sample evidence.
- `Full_run_pilot60/` and `Full_run_pilot60.zip`, which are downstream pilot artifacts.
- `results/build_smoke/` and the V2 build-log reclassification files.
- `state/effective_config.json`, `state/preflight.json`, and
  `state/preflight.done.json`, which belong to the superseded V3.0 prototype and
  conflict with the authoritative V3.1 step markers.
- `repos/`, because the 30 source snapshots are already published once under
  `../compiledrepos`.

`BUILD_EVIDENCE_SHA256SUMS.csv` is retained as the inventory of the complete frozen
archive. A full check against that file will report deliberately omitted audit files as
missing; this compact bundle is not a byte-for-byte copy of the complete 3.8 GB local
archive.

## Privacy and integrity notes

The included files were scanned for common credential patterns. No token, password, API
key, authorization header, or private key was found. Original evidence is not rewritten:
some environment and build-log records contain the Windows profile name `quyt2` and
machine-local paths. Editing those records would invalidate their recorded checksums.

The original config snapshots and step markers must remain unchanged. New publication
notes or checksums should be added as separate files rather than overwriting frozen
evidence.
