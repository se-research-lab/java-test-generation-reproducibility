# Artifact index for the FISAT 2026 paper

Frozen experimental source/data snapshot: `86799597262e21749ef92fd0253c08a24619978d`. The root README describes current manuscript/documentation additions. Paper page numbers below refer to the 15-page revised camera-ready PDF.

| Paper content | Files and directories |
|---|---|
| Data V3 and Table 1, sections 3.1–3.2 | [Data V3 README](../data/dataset_result/README.md), [final300](../data/dataset_result/class_sampling_manifest_final_seed42.csv), [backup60](../data/dataset_result/class_backup_manifest_seed42.csv), [cohort300](../data/cohort300.csv), [repo provenance](../data/dataset_result/successful_repos_manifest.csv) |
| Sampling pipeline and baseline readiness | [frozen source](../data/dataset_result/frozen_source/), [working/portable source](../data/research_pipeline_v3/), [winning recipes](../data/dataset_result/build_recipes_portable.csv), [48 baseline build logs](../data/dataset_result/logs/build/), [build handoff](../data/v3_build_handoff/README_BUILD_HANDOFF.md) |
| Benchmark focal source | [thirty repository snapshots](../data/compiledrepos/); repository commits/focal paths are in the final main manifest |
| G0/E0 and prompt, section 3.3 | [runner/template](../workspace/scripts_v2/rbl4_v2_runner.py), [prompt manifest](../workspace/scripts_v2/prompt_manifest.json), [AgoneTest helpers](../workspace/scripts_v2/AgoneTest/) |
| Pilot60 and remaining240 | [split manifests and recipes](../workspace/scripts_v2/data_new/) |
| G0/E0 primary tables, sections 4.1–4.4 | [historical exports](../workspace/scripts_v2/results/runs/full300_merged_20260724_paper/) including metrics_long.csv, metrics_wide.csv and manifest.json |
| Fixed49 and E49 source | [E49 source lineage](../workspace/camera_ready_minimal/paired49_20261023/src/) |
| E1 configuration/integration, section 3.5 | [E1 source](../workspace/camera_ready_minimal/b1_full300_20261026/src/), [adapters](../workspace/camera_ready_minimal/b1_full300_20261026/adapters/), [configuration freeze](../workspace/camera_ready_minimal/b1_full300_20261026/EXPERIMENT_CONFIGURATION_FREEZE_20261026.json), [manifest300](../workspace/camera_ready_minimal/b1_full300_20261026/manifest300.json) |
| E1 canonical outcomes, Table 6 and section 4.6 | [final300 ledger and statistics](../workspace/camera_ready_minimal/b1_full300_20261026/completion_amendment_v1/final300_offline_v1/) |
| Existing attempt/error history | [previously published execution tables](../workspace/camera_ready_minimal/b1_full300_20261026/audit_e1_execution_20261028_v2/) |

## Scope and missing evidence

CLASSES2TEST is the upstream dataset linked by the paper; its complete raw metadata/mapping dump is not bundled. Methods2Test and GitBug-Java are cited background datasets, not additional experimental cohorts. Data V3 includes 300 main classes, 60 backups and 30 repositories; class_metrics_all.csv contains the processed 1,420 rows rather than every upstream class/mapping record.

Data V3 build logs establish baseline readiness provenance. They do not supply raw generated-test/PIT evidence. All selected raw suites, PIT/JaCoCo/native XML, per-call API/command logs, local toolchains/caches and pinned execution inputs are not publicly complete. Additional post-review diagnostic code/evidence is deliberately retained locally; no new 29 October audit files are added here. Existing source/audit/history files published earlier remain unchanged.

The canonical ledger has 221 observed PIT scores, 58 conventional failure zeros and 21 unresolved scores; process gates are 222 pass, 58 fail and 20 unknown. Missing raw evidence does not turn an outcome into an observed zero. The package supports source/result inspection but does not claim that every reported diagnostic can be fully regenerated from a fresh checkout.
