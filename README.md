# Java test generation reproducibility for FISAT 2026

Artifacts for **Buildability and Mutation Strength in Java Unit Test Generation: GPT-4o-mini vs EvoSuite**.

Repository: https://github.com/se-research-lab/java-test-generation-reproducibility

The experimental source and Data V3 content were checked at snapshot `86799597262e21749ef92fd0253c08a24619978d`. This snapshot is cited in the camera-ready paper. The manuscript and navigation below are prepared locally for the author's next push; no commit or push was performed while updating them. A later documentation/manuscript commit does not change that frozen source/data snapshot.

## Start here

- [Artifact index and links from the paper](docs/ARTIFACT_INDEX.md)
- [Hướng dẫn tiếng Việt](docs/START_HERE_VI.md)
- [Source and version layout](docs/SOURCE_LAYOUT.md)
- [Run guide and actual entry points](docs/RUN_GUIDE.md)
- [Dependencies and assets required for replay](docs/DEPENDENCIES_AND_LOCAL_ASSETS.md)
- [Result definitions and limitations](docs/RESULTS_AND_POLICIES.md)
- [Manual push instructions for this checkout](docs/PUSH_TO_GITHUB.md)
- [Historical workspace Python source index](manifests/PYTHON_SOURCE_INDEX.csv)
- [Notes on preserved development and backup source](docs/ARCHIVED_CODE_NOTES.md)

## Directory structure

```text
java-test-generation-reproducibility/
  README.md
  data/
    cohort300.csv                 # Convenience copy of the final main manifest
    compiledrepos/<repo_id>/      # Thirty published benchmark repository snapshots
    dataset_result/               # Data V3 manifests, frozen pipeline, readiness evidence
    research_pipeline_v3/         # Working/portable Data V3 source and configuration
    v3_build_handoff/             # Build replay source and environment declarations
  workspace/
    scripts_v2/                   # Historical G0/E0 runner, AgoneTest helpers and tables
    camera_ready_minimal/
      paired49_20261023/          # E49 source and original configuration lineage
      b1_full300_20261026/        # E1 policies, adapters, controllers and final300 tables
    review_reports/              # Previously published guards and legacy analysis source
    output/camera_ready_review/  # Previously published offline analysis files
  docs/
  manifests/
  tools/verify_bundle.py
```

The source under `workspace/` preserves historical paths and versions. The working Data V3 code and `dataset_result/frozen_source/` are different snapshots; do not substitute one for the other when describing the historical run. Some original controllers retain absolute paths and finite admissions. This is not a newly validated one-command fresh experiment.

## Dataset and cohorts

- Data V3 final sample: **300 unique focal classes, 30 repositories, ten classes each**; **60 non-overlapping backup classes**. Main keys, frozen commits and focal paths agree with the experimental manifest.
- `data/cohort300.csv` and `data/dataset_result/class_sampling_manifest_final_seed42.csv` identify the same published main manifest.
- The selected sample contains 260 Maven and 40 Gradle classes, split into relative complexity halves of 150 each.
- The Data V3 provenance contains 48 baseline-build logs/recipes. These are readiness evidence, not E1 PIT/test execution logs.
- CLASSES2TEST is the upstream dataset linked by the paper. The complete upstream raw metadata/mapping dump is not bundled. `class_metrics_all.csv` contains the processed 1,420 rows, not all 85,810 upstream unique focal classes.
- Methods2Test and GitBug-Java are related-work dataset references; they are not additional cohorts evaluated here.

## Experimental results and scope

G0 is the frozen zero-shot GPT arm. E0 is historical EvoSuite with assertions disabled. E1 is the assertion-enabled extension with disclosed integration amendments. GPT's RQ1/RQ2/RQ3 observations remain 61/45/300; labels and interpretation use fixed-reference comparisons. All five research questions remain.

The canonical E1 ledger has **221 observed PIT scores, 58 conventional pipeline-failure zeros and 21 unresolved scores**. Recorded process gates are **222 pass, 58 fail and 20 unknown**. The 279 determinate mutation pairs include the 58 policy zeros; they are not 279 observed PIT reports. Fixed49 is the original common-gate cohort and is not replaced by a new intersection.

Table 5 of the revised paper records 49/49 attributable focal PIT reports for G0 and E1 on fixed49. Native selected-suite execution is 48/49 for E1, with one placeholder among the passes. G0/E0 native-suite pass and E0 focal report ownership are not independently certified. Historical E0-specific NI is not transferred to E1. Unequal integration support prevents generator-only attribution.

The public package includes source, configuration/cohort provenance and primary derived tables. It does **not** include the complete generated-suite, raw PIT/JaCoCo/native XML, per-call API payload/log, toolchain/cache or local pinned-input archive. Additional post-review diagnostic programs/evidence remain local and are not added to this repository. Existing legacy audit/history files already published remain unchanged. Repeated-run variance, equalized budgets and hybrid/repair evaluation remain unquantified or untested.

## Verify the packaged files without running experiments

```powershell
python tools/verify_bundle.py
```

This standard-library check reads the explicit `FILE_MANIFEST.json` entries. It does not run experimental code, contact APIs or install dependencies. Its scope is the packaged source/docs/manuscript and selected Data V3 files; it is not a full build/replay or a hash audit of every file in `data/compiledrepos/`.

`COPY_MAP.csv` and `PYTHON_SOURCE_INDEX.csv` retain provenance for the original 1,601-file workspace source bundle. Historical assembly/exclusion receipts retain their dates; the current directory structure above and artifact index describe the later Data V3/manuscript additions. Credentials, real environment files and dependency caches are excluded. No software/data license or paper DOI is invented here.
