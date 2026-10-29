# Run guide using the existing code

All commands below are instructions, not actions performed during packaging. Paths start at this folder unless stated otherwise. Use an existing Python/runtime installation; no dependency download is part of this guide.

## 1 Check this source bundle

```powershell
python tools/verify_bundle.py
```

Reads and hashes files only, without importing the archived source. It works without Java, API credentials or third-party Python libraries.

## 2 Read the frozen results

```text
workspace/camera_ready_minimal/b1_full300_20261026/completion_amendment_v1/final300_offline_v1/
  class_summary300.csv
  class_results300.csv
  class_results300.json
  statistics.json
  statistics_summary.csv
  FORMULA_AUDIT.json
```

Historical G0/E0 tables are also copied under `workspace/scripts_v2/results/runs/full300_merged_20260724_paper/` and the protected original-source backup path used by the fixed49 analyzer.

The detailed JSON references raw evidence in the original workspace. These files are copied unchanged, so the paths and original hashes remain historical. Opening a CSV/JSON is sufficient to inspect the reported outcomes.

## 3 Verify the 300-class statistics with the existing verifier

The existing `verify_final300_offline_v1.py` requires NumPy and the original raw/pinned evidence at its recorded paths. It does not call API/Java/Maven/Gradle. If that evidence remains on this machine, run:

```powershell
New-Item -ItemType Directory -Path .\reproduction_out -ErrorAction SilentlyContinue
python -B workspace/camera_ready_minimal/b1_full300_20261026/src/verify_final300_offline_v1.py --directory workspace/camera_ready_minimal/b1_full300_20261026/completion_amendment_v1/final300_offline_v1 --receipt reproduction_out/verification_first.json
```

Use a new receipt filename for each invocation. Missing raw evidence is an input availability failure, not a class score of zero. This bundle does not claim to include all files required by that full-evidence verifier.

## 4 Historical GPT and E0 pipeline

Entry point: `workspace/scripts_v2/rbl4_v2_runner.py`.

From `workspace/scripts_v2`, the existing CLI supports:

```powershell
python rbl4_v2_runner.py --mode dry_run
python rbl4_v2_runner.py --mode baseline_only
python rbl4_v2_runner.py --mode full_run --workers 1
```

`dry_run` prepares/checks input metadata and can write output; it is not a pure read-only file inspection. `baseline_only` runs project builds. `full_run` is a new GPT/EvoSuite experiment and may call the API. These commands are shown to document usage; they have not been run while creating this folder.

Use the existing `data_new/` manifests/recipes and the existing benchmark repositories. The original README supports `RBL4_COMPILED_REPOS` for the repository location. Existing Java tools and a private local environment configuration are required. Review the runner's output/run-directory configuration and never reuse frozen result output directories. Copying a source tree is not an instruction to regenerate the historical G0/E0 results.

## 5 EvoSuite fixed49 E1

- Generation driver: `workspace/camera_ready_minimal/paired49_20261023/src/run_e49_supplement.py` (`verify` / `run`).
- Patched generation/measurement functions: `.../evo_patch/working/AgoneTest/`.
- Native-suite measurement/compatibility lineage: relevant scripts in `.../src/`, including `analyze_measurement_compat49_v3.py` for offline analysis.
- Original analytics: `.../src/analyze49.py --out <new-output-directory>`.

Historical invocation form:

```text
python -B workspace/camera_ready_minimal/paired49_20261023/src/run_e49_supplement.py verify
python -B workspace/camera_ready_minimal/paired49_20261023/src/run_e49_supplement.py run
```

These require the original readiness locks, audit registries, source snapshots and existing tool/cache assets. `verify` checks those external inputs; `run` creates a generation batch and uses exclusive output/admission files. A new experiment needs a new stage/admission/output version rather than deleting old files to make it run again.

## 6 E1 Maven, Gradle and completion source

Directory: `workspace/camera_ready_minimal/b1_full300_20261026/`.

| Area | Existing source entry points | Inputs / meaning |
|---|---|---|
| Initial Maven | `src/run_maven_b1_v1.py`, `run_maven_b1_v2.py`, `run_maven_b1_v3.py` | Original admission, manifest300, snapshots and code hashes; initial CLI uses `--max-jobs` |
| Maven V6 continuation | `src/run_remaining_maven153_v6.py` | Existing V6 admission/launch plan and completed-class guards; finite historical continuation |
| Gradle40 | `src/run_gradle_full40_v2.py` | Frozen Gradle admission, per-class contexts/wrappers and offline cache metadata |
| Completion Maven | `src/complete_maven_groups_v2.py`, `run_remaining2_final_v1.py` | POM/JUnit3-specific admissions and suite reuse rules |
| Completion sequencing | `src/run_completion_maven_sequence_v3.py` | Qualifications/seals/finite queue; can start multiple stages, not an analysis command |
| Offline reconciliation | `src/reconcile300_checkpoint_v3.py`, `compute_checkpoint300_statistics_v1.py` | Existing audited source/result metadata; creates a new output set only if guards allow |
| Independent offline check | `src/verify_final300_offline_v1.py` | Frozen300 tables and pinned external evidence |

A historical command has the form `python -B -X utf8 <entry-point.py>`; use the static CLI inventory for arguments. Initial Maven's bounded form is `python .../run_maven_b1_v1.py --max-jobs 1`. This is **not** the recommended way to resume a completed study. V6/Gradle/completion entry points bind to particular historical admissions and output versions. They are not a portable one-command fresh300 launcher.

Before an intentional new E1 run: map existing local tools and source snapshots; select the intended policy; use a fresh output/admission version with pinned hashes; verify raw/config/source guards; launch one bounded invocation; inspect its archive. Do not remove lock/receipt/checkpoint files or repair dependencies opportunistically to force a passing result. The original source is preserved here so those choices remain reviewable.

## 7 Optional local interfaces

Original backend source is in `workspace/scripts_v2/experiment_tool/`; frontend in `react-ui/`; E1 monitor in `.../b1_full300_20261026/monitor/`. Their source and package declarations describe the local ports and commands. This folder includes source and declarations but not node_modules/dist. No web server was started during packaging. Some experimental backend endpoints can launch runs; the read-only monitor has a different purpose.

## 8 Outputs and limits

Generation, compile, native execution, JaCoCo, PIT and process gate are separate stages. See `RESULTS_AND_POLICIES.md` before interpreting failures. Native JUnit support or selectors differ between historical policies; source versions must not be presented as one uniform experiment. Repeated-subset source is archived, but no unfinished repeated output is part of the paper results.

Only the copied bundle integrity check is self-contained. Full raw-evidence verification/replay uses assets that remain in the original workspace. No full generation/measurement was validated from a fresh checkout in this copying task.


## Data V3 and benchmark source

The published input/provenance tree is under `data/`: final main/backup manifests and readiness evidence in `dataset_result/`, historical frozen pipeline in `dataset_result/frozen_source/`, working/portable source in `research_pipeline_v3/`, thirty snapshots in `compiledrepos/`, and build replay source in `v3_build_handoff/`. Read their README/configuration before an intentional new run. The complete upstream CLASSES2TEST dump and private local inputs are not bundled. Baseline Data V3 logs are not generated-test/PIT evidence.

## Build the manuscript

`paper/camera_ready/README_BUILD.md` describes building `main.tex` with a compatible existing LaTeX installation. This is separate from running Java experiments. The updated paper distinguishes49/49 G0 focal PIT reports from unknown native-suite success. Additional post-review diagnostic code/evidence remains local; the public source package does not certify full regeneration of every supplementary diagnostic.
