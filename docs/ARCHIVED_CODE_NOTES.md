# Archived source notes

The source bundle preserves original bytes, including incomplete earlier drafts. These four files failed static Python parsing during inventory. All are backup/development snapshots, not the documented primary entry points. They have not been repaired or executed.

| Preserved file | Issue |
|---|---|
| `workspace/camera_ready_minimal/paired49_20261023/backups/replay_measurement_v3_construction01/replay_fixed49_measurement_v3.py` | SyntaxError at line 33 |
| `workspace/camera_ready_minimal/paired49_20261023/e49_driver/backup/e49_driver_before_timeout_detail_fix.py` | SyntaxError at line 64 |
| `workspace/camera_ready_minimal/paired49_20261023/e49_driver/backup/e49_driver_before_try_block_fix.py` | SyntaxError at line 64 |
| `workspace/camera_ready_minimal/paired49_20261023/e49_driver/observer_v3_dev/archive_e49_final_v3.before01.py` | SyntaxError at line 25 |

Other Python files passed a static parse with the packaging Python runtime. A successful parse is not a dependency, runtime or scientific-validity test. No experimental code was imported during this check.

Scripts named prepare/admit/seal/dispatch/run can alter execution state or start workers. They are included as source history, not an automatic execution sequence. `PYTHON_SOURCE_INDEX.csv` lists CLI strings read from the AST without invoking those scripts.
