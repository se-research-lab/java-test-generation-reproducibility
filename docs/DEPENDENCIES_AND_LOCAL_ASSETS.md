# Existing dependencies and local assets

No library installer or dependency downloader was run to prepare this folder. Experimental tool JARs, installed executables, virtual environments, node_modules and dependency caches are not bundled by this source update. Benchmark snapshots can retain upstream wrapper/resources subject to their own layout.

## Existing package declarations

- `workspace/scripts_v2/AgoneTest/requirements.txt`: existing Python requirements for the original AgoneTest helper stack.
- `workspace/scripts_v2/experiment_tool/requirements.txt`: existing local web backend requirements.
- `workspace/scripts_v2/react-ui/package.json` and `package-lock.json`: existing frontend declarations.

These are copied declarations, not a newly validated universal lockfile for every script. Analysis additionally uses NumPy and, for historical tests, SciPy; orchestration uses psutil; some report utilities use pandas, matplotlib, python-docx or PDF libraries. See imports and the source index. Use the already installed environment appropriate to the script; do not install all optional packages merely to inspect the code.

The historical analytics receipts record Python 3.10.6, NumPy 1.26.4, pandas 2.0.3 and SciPy 1.15.3. This describes recorded versions rather than asserting that every script used the same environment. `tools/verify_bundle.py` only needs Python standard library.

## Java tools and inputs remain in the original local environment

- Existing EvoSuite `scripts_v2/evosuite-1.2.0.jar` and standalone runtime JAR.
- Existing TestSmellDetector JAR where used by historical code.
- Existing JDK8 installation, Maven installation and repository-specific Gradle wrappers.
- Published benchmark snapshots are now under `data/compiledrepos/`; private execution snapshots, caches and source/bytecode locks remain local.
- Existing historical `scripts_v2/results/runs/` raw logs, generated tests, PIT and JaCoCo reports.
- Existing E49 and E1 `jobs/` output archives, runtime/checkpoint evidence and sqlite input snapshots.

Exact locations, command lines and hashes are in copied tool/admission/input metadata. Examples of machine bindings retained by the original code include `C:/Program Files/Java/jdk1.8.0_172`, `C:/Program Files/Apache/maven`, and `D:/A_ThucNghiem`. Path guards cannot be bypassed by pointing at an arbitrary similar file.

Java measurement versions vary by arm and build tool. Maven uses the documented PIT1.16.0/JaCoCo0.8.7 lineage; some Gradle completion cases retain PIT1.3.1/plugin1.3.0. Read the policy and selected command metadata rather than assuming one environment for all classes.

Real `.env`, Maven `settings.xml`, credentials and authorization headers are intentionally excluded. The original source's example environment files may be retained after signature scanning. Supply local credentials only when intentionally running a new API experiment; offline analysis needs no API key.

## Replay versus copying source

A source archive preserves how the experiment was implemented. Replaying E1 on another machine also requires rebinding the input snapshots/tool paths and issuing a new admission with fresh hashes and new output paths. Those execution assets are not libraries that this bundle installs. This copying task does not modify the locked historical code to make those checks pass elsewhere.


## Data declarations and publication scope

`data/research_pipeline_v3/requirements-v3.txt` and the frozen counterpart record existing Data V3 declarations. `data/v3_build_handoff/` has Docker/compose/native setup declarations; none was executed during this update. The selected main/backup cohort, Data V3 source and readiness evidence are public; raw upstream CLASSES2TEST and the full GPT/E1 execution archive are not. The Data V3 config's relative dataset_root identifies an external input, not a folder silently bundled here.

The source/data snapshot cited by the paper is `86799597262e21749ef92fd0253c08a24619978d`. Additional post-review diagnostic programs/evidence remain local and are not added to this repository. See ARTIFACT_INDEX.md for the scope of each published file category.
