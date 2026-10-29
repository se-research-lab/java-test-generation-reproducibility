# CLASSES2TEST Data V3 pipeline

This pipeline constructs the new research sample. The current step-based scripts do not
import or modify `pipeline_v3.py`; that file is retained as a historical prototype. The
pipeline also does not modify `research_pipeline`, `data_v2`, Java source files,
`pom.xml`, `build.gradle`, or repository dependencies.

There is no `all` command. An operator must run each step separately, inspect its output,
and continue only when the preceding step returns exit code `0`.

## Preregistered experimental protocol

- Exactly 30 final-qualified repositories.
- Every repository must contain at least 12 unique, valid physical focal Java classes
  within a build scope that compiled successfully.
- Every repository contributes exactly 10 main classes and 2 backup classes, for a total
  of 300 main and 60 backup classes.
- `class_key = repo_id + ':' + casefold(normalize(focal_path))`.
- Repositories and classes are ranked with SHA-256 and seed 42.
- Cyclomatic complexity is never used to filter, select, or replace a class.
- Only after the 300 main classes have been selected are `MaxCC`, `SumCC`, the selection
  hash, and the class key used to form two relative halves of 150 classes each.
- Declared Java 5, 6, 7, 8, and `unknown` are all attempted with the operator's JDK 8.
  Declared Java and the effective runtime are recorded as separate fields.
- A repository is excluded for Java greater than 8 only when metadata or a build log
  provides clear evidence.
- AI is not used to generate build commands. Source files, build files, and dependency
  declarations are not modified to force a build to pass.
- Backup classes are used only for technical failures before the experiment. A class is
  never replaced because GPT, EvoSuite, compilation, coverage, or mutation produces an
  unfavorable result.

## Environment setup

All relative paths in `config_v3.yaml` are resolved from the directory that contains the
configuration file. With the default configuration, the expected layout is:

```text
data/
  classes2test/
  data_v2/
  research_pipeline/
  research_pipeline_v3/
  data_v3/                 # created as pipeline output
  context.md
  STATUS.md
  HDSD.md
```

From the repository root, open CMD and run:

```bat
cd data\research_pipeline_v3
py -m pip install -r requirements-v3.txt
```

Check that `../research_pipeline/env/local.env` defines `JAVA_HOME` for a JDK 8
installation. Step 000 validates `java`, `javac`, and the JVM used by Maven. Do not
continue if any of them reports a Java version other than 8. The real `local.env` file is
machine-specific and must not be committed.

Before an official run, review and approve `config_v3.yaml`. If the configuration changes
after a step has completed, the pipeline stops because its checksum no longer matches.
For an amendment, preserve the reason, use a new output directory, and restart at Step
000 instead of overwriting an earlier run.

## Step 000 - preflight and V2 backup

```bat
py 000_preflight_and_backup.py --config config_v3.yaml
```

If an immutable V2 recovery copy already exists and another backup is unnecessary, run:

```bat
py 000_preflight_and_backup.py --config config_v3.yaml --skip-backup
```

This mode does not claim that a new backup was completed. The Step 000 marker records
`backup_skipped=true`; later steps still record checksums and provenance and do not modify
V2.

Inputs:

- `config_v3.yaml`.
- The current JDK and build environment.
- `data_v2`, `research_pipeline`, the proposal, and the handoff documents.

Primary outputs:

- `data_v3/results/environment_versions.json`.
- `data_v3/state/step000.done.json`.
- `data_v2_backup_pre_v3_<timestamp>/backup_manifest.csv` and `backup_log.json`.

The step passes when Java, Javac, and Maven use JDK 8, Git is available, at least one of
Maven or Gradle is available, and the backup completes. It also passes when the operator
explicitly uses `--skip-backup` because an immutable recovery copy already exists. The
skip state remains in the marker so the provenance record does not make a false claim.

## Step 001 - reconstruct the unique frame

```bat
py 001_reconstruct_unique_frame.py --config config_v3.yaml
```

This step reads only CLASSES2TEST metadata. It does not clone repositories, run builds,
filter by Java or cyclomatic complexity, or inspect outcomes.

Outputs:

- `raw_mapping_index.csv`: one row for every JSON file, including parse errors.
- `unique_focal_class_frame.csv`: one row for every physical focal class.
- `repo_candidate_summary.csv`: repositories with at least 12 unique mapped focal paths.
- `state/step001.done.json`: the dataset digest and output checksums.

The step passes when every JSON file is accounted for, `class_key` is unique in the frame,
and the total `mapping_count` can be traced back to the raw mappings. Repositories with a
missing or unknown Java version remain eligible for a real build in Step 003.

## Step 002 - deterministic repository queue

```bat
py 002_create_repo_queue.py --config config_v3.yaml
```

Output: `repo_processing_order_seed42.csv`.

The queue is ordered using SHA-256 and seed 42 and does not depend on filesystem order.
Do not rerun Step 002 to obtain a different sample after observing which repositories
build successfully.

## Step 003 - screen and build repositories on JDK 8

```bat
py 003_screen_and_build_repositories.py --config config_v3.yaml --resume
```

`--resume` is the safe default. It preserves qualified repositories and hard rejections
and continues the immutable queue from the first pending repository. This step can take a
long time. It can be interrupted with `Ctrl+C` and resumed with the same command; queue
state is written after every repository. `data_v3/state/pipeline.lock` prevents two
pipeline processes from running concurrently.

On Windows, the pipeline clears read-only attributes on Git pack files while cleaning a
clone and uses bounded retries when promoting a qualified repository from `working` to
`successful`. If Windows still holds a file handle after 20 attempts, the repository
remains `qualified` and is retained at `repos/working/<repo_id>`. The queue and manifest
record `repository_storage_path`, `promotion_status=retained_in_working`, and the error.
Storage bookkeeping is not an eligibility gate. Every Gradle recipe uses `--no-daemon`.

To intentionally restart all of Step 003, provide both the option and confirmation token:

```bat
py 003_screen_and_build_repositories.py --config config_v3.yaml --restart-from-beginning --confirm-restart RESET_STEP003
```

A restart does not delete history. The current Step 003 queue, clones, logs, and artifacts
are moved to `data_v3/state/step003_restart_archives/<timestamp>_<pid>` before the queue
is reset. Do not use restart mode to change the repository set after observing outcomes.

For each repository, the pipeline:

1. Clones submodules, checks out the dataset commit when metadata specifies one, and
   records the exact observed `HEAD`.
2. Resolves the exact focal paths without searching for another file with the same name.
3. Locates the nearest Maven or Gradle scope and its corresponding reactor or root.
4. Measures NLOC and cyclomatic complexity and checks semantic eligibility. NLOC must be
   between 5 and 500; cyclomatic complexity is not a gate.
5. Reads declared Java from the module or root but runs every Java 5-8 or unknown project
   with the effective JDK 8 runtime.
6. Prefers a repository wrapper and then falls back to the recorded global build tool.
7. For Maven, tries the module directly, reactor `-pl ... -am`, and then ancillary-check
   skip flags.
8. For Gradle, tries the exact `:<module>:testClasses -x test` task and does not skip a
   broad list of tasks that may not exist.
9. Only after dependency failure, uses the external `maven-settings-v3.xml` or
   `gradle-init-v3.gradle`. Their HTTPS repository list comes from V2 repair evidence,
   was frozen before screening, has a checksum, and does not modify dependency
   declarations.
10. Checks tracked files after a successful build. An attempt is rejected if the build
    changed a tracked file.
11. Counts only classes in a passing scope; a repository needs at least 12 such classes.

Outputs:

- `successful_repos_manifest.csv`: exactly 30 repositories when the step passes.
- `class_metrics_all.csv` and `excluded_classes_log.csv`.
- `build_attempts.csv`, `build_recipes.jsonl`, exact commits, and raw logs.
- `state/step003.done.json`.

If execution stops because of a classified transient failure, inspect the log before
running:

```bat
py 003_screen_and_build_repositories.py --config config_v3.yaml --resume --retry-recoverable
```

This option resets only preregistered transient categories. It does not retry hard
failures, relax criteria, or change queue order.

## Step 004 - sample 300 main and 60 backup classes

```bat
py 004_sample_classes.py --config config_v3.yaml
```

Outputs:

- `class_sampling_manifest_seed42.csv`: 300 main classes.
- `class_backup_manifest_seed42.csv`: 60 backup classes.
- `repo_sampling_summary.csv`.

Within each repository, classes are sorted by
`SHA256('v3-class-selection|42|' + class_key)`. The first 10 are main classes and the next
2 are backup classes. Changing cyclomatic-complexity values while preserving class keys
must not change the selection. Main and backup manifests retain
`repository_storage_path` and `promotion_status` from Step 003; storage location does not
participate in hashing or eligibility.

## Step 005 - validation and reporting

```bat
py 005_validate_and_report.py --config config_v3.yaml
```

This step recomputes the selection from the frame instead of trusting existing manifests,
and only then assigns 150 lower-relative and 150 higher-relative classes. For every
repository, the validator accepts only `repos/successful/<repo_id>` or
`repos/working/<repo_id>`, compares storage recorded by the repository and sample
manifests, and checks the exact focal path inside the recorded storage location.

Outputs:

- `class_sampling_manifest_final_seed42.csv`.
- `results/validation_report.md`.
- `results/sampling_methodology.md`.
- `results/data_integrity_report.md`.
- `results/complexity_halves_summary.json`.
- `results/SHA256SUMS.csv`.
- `results/RUN_READY`, created only when every validation passes.

Do not start GPT or EvoSuite if `RUN_READY` is missing or Step 005 returns a nonzero exit
code.

## Safe development checks

The following commands do not scan CLASSES2TEST, clone repositories, or build real
repositories:

```bat
py -m py_compile v3_core.py 000_preflight_and_backup.py 001_reconstruct_unique_frame.py 002_create_repo_queue.py 003_screen_and_build_repositories.py 004_sample_classes.py 005_validate_and_report.py tests\test_v3_fixtures.py
py -m unittest discover -s tests -p "test_*.py" -v
py 000_preflight_and_backup.py --help
py 001_reconstruct_unique_frame.py --help
py 002_create_repo_queue.py --help
py 003_screen_and_build_repositories.py --help
py 004_sample_classes.py --help
py 005_validate_and_report.py --help
```

The fixtures must demonstrate that:

- slash and backslash separators, `./`, and case folding produce the same class identity;
- Java 5, 6, 7, 8, and unknown are admitted to the JDK 8 build attempt, while Java 9 and
  later are excluded;
- the focal Maven module and reactor root are identified correctly;
- the exact result is 30 x (10 main + 2 backup), with no duplicates or overlap;
- changing input order or complexity values does not change selection; and
- complexity halves are assigned only after the 300 main classes have been selected.

## Amendments and scientific-integrity rules

Preserving old files is necessary but insufficient. A result is reproducible only when
the exact configuration, scripts, inputs, commits, and environment are known. Every step
therefore records the configuration hash, output hashes, and a `.done` marker. This does
not prevent development before the full run. Once a run starts, however, every change
must be documented as an amendment with a reason and a separate output directory.

Do not change the seed, gates, recipe policy, prompt, replacement rule, or denominator
after observing GPT, EvoSuite, coverage, or mutation outcomes. Do not describe a frame
that has already passed build and eligibility filters as a direct simple random sample of
all 147,473 instances.
