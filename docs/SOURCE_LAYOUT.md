# Source layout and version map

Every copied file retains its path relative to the old workspace under `workspace/`. `manifests/COPY_MAP.csv` records the original relative path, copied path, category, SHA256 and byte count. Copied historical documentation is retained for context and can contain stale progress statements. Use the top-level docs for current navigation.

| Area | Purpose |
|---|---|
| `workspace/scripts_v2/rbl4_v2_runner.py` | Original paired G0/E0 pipeline and statistical decision code |
| `workspace/scripts_v2/AgoneTest/` | Java generation/build/measurement helpers, Maven/Gradle integration and existing requirements |
| `workspace/scripts_v2/data_new/` | Main/pilot/remaining class manifests and build recipes |
| `workspace/scripts_v2/experiment_tool/`, `react-ui/` | Original local backend/frontend source; node_modules and frontend build output excluded |
| `workspace/camera_ready_minimal/paired49_20261023/audit.py` | Historical audit wrapper used by E49 and E1 |
| `.../paired49_20261023/src/` | Fixed49 analysis, E49 execution/remeasurement, guards and historical utilities |
| `.../paired49_20261023/evo_patch/working/AgoneTest/` | EvoSuite-specific modified helper source used by the E49 lineage |
| `.../paired49_20261023/e49_driver/` | Preserved earlier source snapshots; current entry points are in `src/` |
| `.../paired49_20261023/backup/original/scripts_v2/` | Protected original source snapshots; binaries/generated-test outputs not bundled |
| `.../b1_full300_20261026/src/` | All existing E1 controllers, runners, offline analyzers, guards, preparation and packaging scripts |
| `.../b1_full300_20261026/adapters/` | Extracted E49 generation/profile/measurement functions imported by E1 |
| `.../b1_full300_20261026/backups/` | Earlier source snapshots, copied unchanged for provenance |
| `.../b1_full300_20261026/inputs/` | JSON input metadata only; sqlite snapshots/Git bundles remain local |
| `.../b1_full300_20261026/completion_amendment_v1/` | Existing completion admissions, policies and final300 tables |
| `.../b1_full300_20261026/monitor/` | Read-only local dashboard source |
| `.../b1_full300_20261026/audit_e1_execution_20261028_v2/` | Accepted execution/history/error tables and audit summaries |
| `workspace/review_reports/minimal_camera_ready_20261023/` | Existing guards used by the archived runner |

Repeated-subset scripts, historical fixtures and manuscript/package utilities remain in the source index because they are part of the existing source tree. Their presence does not authorize their execution or admit their outputs into the paper. The source index is an inventory, not a recommended batch execution list.

No historical source is refactored here. In particular, original configuration-lock statuses and `benchmark_replacement_admitted` fields retain their original bytes. Later decisions are found in admissions/result-map metadata, not by rewriting earlier receipts.
