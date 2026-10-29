# Data V3 acquisition, sampling, reproducibility, and experiment handoff

**Document type:** post-run derived documentation  
**Dataset state described:** Step 001–005 completed; `results/RUN_READY` present  
**Scope:** how Data V3 was obtained, what the final sample means, and how to
transfer it for the GPT/EvoSuite experiment without changing the frozen data

This document does not replace the step markers or their checksums. It was written
after Step 005 from the frozen artifacts. The authoritative machine-readable
evidence remains in `state/*.done.json`, `results/SHA256SUMS.csv`,
`BUILD_EVIDENCE_SHA256SUMS.csv`, the manifests, recipes, and raw logs.

## 1. Decision summary

1. The sampling data are ready: Step 005 is PASS and `results/RUN_READY` exists.
2. Do not reuse the V2 Docker setup unchanged. Its scripts/configuration implement
   V2 rules, including NLOC 30 and a CC 5–10 gate, whereas V3 uses NLOC 5–500
   with no CC eligibility gate.
3. A source/data archive is required even when Docker is used. Docker provides
   the environment; it does not replace exact commits, manifests, recipes, logs,
   or generated experimental outputs.
4. For the easiest handoff, transfer the complete frozen `data_v3` plus
   `research_pipeline_v3` and the study documents. Keep the Docker image separate
   and mount the frozen data read-only.
5. A ZIP alone can work when the teammate uses a compatible Windows/JDK setup and
   has network access. It does not guarantee that old Maven/Gradle dependencies
   or wrapper distributions will still download.
6. Before claiming a Docker-based reproduction, a new V3 experiment image must be
   built and all 48 winning build scopes must be replayed inside it. This has not
   yet been done.

## 2. Study and sampling unit

The project is a sampled replication of AgoneTest 2025 on CLASSES2TEST, with
GPT-4o-mini zero-shot and an EvoSuite baseline. It is not a census replication of
all 147,473 class-level instances reported by the reference study.

The operational V3 unit is one physical focal Java source file identified by:

```text
class_key = repo_id + ":" + casefold(normalized focal path)
```

Multiple CLASSES2TEST JSON mappings may refer to the same physical focal file.
V3 therefore aggregates those mappings instead of counting each JSON as a
different class. This physical-file operationalization is an amendment to the
proposal's original tuple-oriented reconstruction and must be disclosed in the
paper.

## 3. Input and frozen protocol

Primary input:

```text
classes2test/dataset/<repo_id>/*.json
```

Protocol/configuration:

```text
research_pipeline_v3/config_v3.yaml
```

Important frozen decisions:

- repository target: 30;
- minimum unique eligible buildable classes per repository: 12;
- main classes per repository: 10;
- backup classes per repository: 2;
- seed: 42;
- NLOC gate: 5–500;
- no CC eligibility gate;
- require at least one public non-constructor method;
- exclude interfaces, enums, test sources, and generated code;
- declared Java 5/6/7/8 or unknown may be tried on effective JDK 8;
- evidence of a Java version above 8 is rejected;
- no source/build/dependency file may be edited to force a baseline build.

The CLASSES2TEST input content hash recorded by Step 001 is:

```text
2ffd4c14a62a33f1a6b20ba265838a1ce3c49a5d08c0da684e1ce7a5b4f4138d
```

The frozen config hash used by Steps 001–005 is:

```text
a05265fe992df1165865c9619b35f6e4f9f5fb90f3ccfb642962c3bb5d7813b5
```

## 4. Actual Data V3 acquisition flow

### Step 001 — reconstruct the physical focal-class frame

The pipeline enumerated all 9,410 repository metadata directories and parsed
362,414 JSON mapping files with zero parse errors. It normalized focal paths and
aggregated mappings that referred to the same physical Java source.

Observed result:

```text
362,414 JSON mappings
→ 85,810 unique physical focal classes
→ 1,248 repository candidates with at least 12 unique mapped focal paths
```

No Java version, class name, complexity, or downstream outcome filter was applied
at this step.

Principal outputs:

- `raw_mapping_index.csv`;
- `unique_focal_class_frame.csv`;
- `repo_candidate_summary.csv`;
- `state/step001.done.json`.

### Step 002 — deterministic repository queue

The 1,248 candidate repositories were ordered with
`sha256-v3-repo-order`, seed 42. Canonical identifiers are used before hashing,
so queue order does not depend on filesystem enumeration order.

Principal outputs:

- `repo_processing_order_seed42.csv`;
- `state/repo_processing_order_seed42.initial.csv`;
- `state/step002.done.json`.

### Step 003 — clone, freeze, build, measure, and qualify

Repositories were processed in the frozen queue order until exactly 30 final
repositories qualified. For each candidate, the pipeline:

1. cloned the repository and submodules;
2. checked out and recorded the exact commit;
3. resolved only the exact mapped focal paths;
4. detected Maven/Gradle scopes nearest each focal class;
5. separated declared Java evidence from the effective runtime;
6. ran eligible Java 5–8/unknown projects on effective JDK 8;
7. tried a predeclared wrapper/global/module/reactor build-recipe ladder;
8. compiled baseline and test sources without executing the test suite;
9. rejected any successful attempt that modified tracked source/build/dependency
   files;
10. measured NLOC and CC and applied structural eligibility;
11. counted only eligible classes in a build scope that passed;
12. retained the repository only if at least 12 unique classes remained.

Observed result:

```text
30 final-qualified repositories
678 unique structurally eligible classes in PASS build scopes
48 unique winning build scopes
43 Maven scopes + 5 Gradle scopes
effective runtime JDK 8 for every winning scope
0 winning recipes that modified source/dependency files
```

The attempt audit includes candidates that were later rejected. It must not be
confused with the final winning recipes. Only `build_recipes.jsonl` and
`build_recipes_portable.csv` define the 48 final recipes.

Principal outputs:

- `successful_repos_manifest.csv`;
- `build_recipes.jsonl`;
- `build_recipes_portable.csv`;
- `build_attempts.csv`;
- `class_metrics_all.csv`;
- `excluded_classes_log.csv`;
- `logs/build/*`;
- `state/step003.done.json`;
- `BUILD_EVIDENCE_SHA256SUMS.csv`.

### Step 004 — repo-balanced deterministic class selection

Within each of the 30 repositories, eligible buildable classes were ranked using
a SHA-256 key derived from seed 42 and the stable class key:

```text
SHA256("v3-class-selection|42|" + class_key)
```

The first 10 classes in each repository became main observations and the next two
became backups.

Observed result:

```text
30 × 10 = 300 unique main classes
30 × 2  = 60 unique backup classes
main/backup overlap = 0
```

CC was not an inclusion or selection variable. The sample is repository-balanced,
not a uniform class-level sample of the 678-class frame: every repository
contributes 10 main observations even though eligible pool sizes range from 12
to 71.

Principal outputs:

- `class_sampling_manifest_seed42.csv`;
- `class_backup_manifest_seed42.csv`;
- `repo_sampling_summary.csv`;
- `state/step004.done.json`.

### Step 005 — independent reconstruction and final complexity labels

Step 005 reconstructed main and backup selection from the eligible frame and
verified:

- exactly 30 repositories;
- 300 unique main and 60 unique backup classes;
- exactly 10 main and two backup classes per repository;
- zero duplicates and zero main/backup overlap;
- all selected keys belong to the eligible buildable frame;
- exact focal paths exist at the frozen snapshots;
- all 30 repositories have validated recipes;
- no winning recipe modified source/dependency files;
- storage records are valid;
- deterministic main and backup reconstruction have zero mismatches.

Only after the 300 main observations were frozen were they ordered by:

1. `max_method_cc`;
2. `sum_method_cc`;
3. `selection_hash`;
4. `class_key`.

The first 150 were labeled `lower_complexity_half` and the next 150
`higher_complexity_half`. These are relative halves, not universal Java CC
thresholds. The boundary is tied at `max_method_cc = 4`.

Observed main-class CC summary:

| Set | N | Min | Q1 | Median | Mean | Q3 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Main | 300 | 1 | 2 | 4 | 5.52 | 7 | 37 |
| Lower-relative | 150 | 1 | 1 | 2 | 2.42 | 3 | 4 |
| Higher-relative | 150 | 4 | 5 | 7 | 8.62 | 10 | 37 |

Principal outputs:

- `class_sampling_manifest_final_seed42.csv`;
- `results/validation_report.md`;
- `results/sampling_methodology.md`;
- `results/data_integrity_report.md`;
- `results/complexity_halves_summary.json`;
- `results/SHA256SUMS.csv`;
- `results/RUN_READY`;
- `state/step005.done.json`.

## 5. Paper-ready methodology wording

### English

> We reconstructed a repository-level candidate frame from the CLASSES2TEST
> metadata by aggregating JSON mappings that referred to the same physical focal
> Java source file. The operational class identity combined repository ID with a
> normalized, case-folded focal path. Across 9,410 repository metadata
> directories, 362,414 mappings yielded 85,810 unique physical focal classes.
> Repositories with fewer than 12 unique mapped focal paths were removed by a
> metadata-only prefilter. The remaining 1,248 candidates were screened in a
> deterministic SHA-256 order generated with seed 42. At frozen source
> revisions, repositories were retained only if their relevant Maven or Gradle
> scopes compiled on the effective JDK 8 runtime without source or dependency
> modifications and contained at least 12 unique structurally eligible focal
> classes. Screening continued until 30 repositories qualified, producing a
> final eligible buildable frame of 678 classes. Within each repository, classes
> were ranked using a SHA-256 key derived from seed 42 and the stable class key;
> the first 10 were selected as main observations and the next two as
> predeclared backups. The resulting sample contained 300 unique main classes
> and 60 non-overlapping backups with equal repository contribution.
> Cyclomatic complexity did not affect eligibility or selection. After the main
> sample was frozen, the 300 classes were ordered by maximum method cyclomatic
> complexity, summed method complexity, deterministic selection hash, and class
> key, and divided into lower- and higher-complexity halves of 150 classes each.
> These labels denote relative halves of the study sample rather than absolute
> complexity categories.

### Required disclosure

The paper must disclose all of the following:

- this is a sampled replication, not the full CLASSES2TEST census;
- the operational unit is a physical focal source file;
- buildability and structural eligibility restrict the operational frame;
- sampling is balanced by repository, so class-level inclusion probabilities
  vary by repository size;
- the complexity halves are globally balanced 150/150 but are not balanced
  within every repository;
- backups may replace only pre-experiment technical failures;
- GPT/EvoSuite compilation or metric failures are experimental outcomes and
  must never trigger replacement.

## 6. Experiment handoff package

### 6.1 Two different reproducibility goals

Do not mix these packages:

**Experiment execution package:** lets a teammate run GPT/EvoSuite on the already
frozen 300 classes. It does not need all 9,410 CLASSES2TEST metadata directories.

**Sampling reconstruction package:** lets a researcher rerun Step 001 from the
original CLASSES2TEST input. It additionally requires the exact upstream dataset
snapshot and its content hash. This package is much larger and is not required
for ordinary experiment execution.

### 6.2 Recommended experiment package contents

Create a new staging directory; never clean or alter the frozen originals in
place.

```text
V3_EXPERIMENT_HANDOFF/
  HANDOFF_README.md
  research_pipeline_v3/
    000_preflight_and_backup.py
    001_reconstruct_unique_frame.py
    002_create_repo_queue.py
    003_screen_and_build_repositories.py
    004_sample_classes.py
    005_validate_and_report.py
    v3_core.py
    pipeline_v3.py
    config_v3.yaml
    requirements-v3.txt
    maven-settings-v3.xml
    gradle-init-v3.gradle
    README.md
    tests/
  data_v3/
    repos/successful/<30 frozen repositories>
    class_sampling_manifest_final_seed42.csv
    class_sampling_manifest_seed42.csv
    class_backup_manifest_seed42.csv
    successful_repos_manifest.csv
    repo_sampling_summary.csv
    build_recipes.jsonl
    build_recipes_portable.csv
    build_attempts.csv
    class_metrics_all.csv
    excluded_classes_log.csv
    repo_processing_order_seed42.csv
    ARTIFACT_READING_GUIDE.md
    BUILD_EVIDENCE_SHA256SUMS.csv
    logs/
    state/
    results/
  study_docs/
    proposal (2).md
    context.md
```

Do not include V2 data, V2 Docker/configuration, backups, `.uv-cache`,
`.uv-python`, editor settings, or unrelated delivery bundles.

`STATUS.md` currently describes an earlier pre-run state. If retained for history,
place it under `study_docs/historical/` and label it stale; do not present it as
the current status.

### 6.3 Observed package size

Current uncompressed `data_v3` inventory:

| Area | Files | Bytes |
|---|---:|---:|
| Complete `data_v3` | 78,369 | 3,844,604,550 |
| `repos/` | 76,565 | 3,551,507,916 |
| Git data inside successful clones | 840 | 2,468,688,514 |
| Detected `target`/`build`/`.gradle` output | 21,977 | 174,449,344 |
| Logs | 1,567 | 23,576,348 |
| State | 210 | 5,696,640 |
| Root CSV/JSON/Markdown artifacts | 16 | 263,596,484 |

Git pack files are already compressed, so a ZIP/TAR.GZ may remain several
gigabytes. Ensure the transfer medium and destination filesystem support files
larger than 4 GB.

Keeping `.git` is recommended because it preserves exact commit evidence and
supports isolated clones/workspaces. Removing all `.git` directories saves about
2.47 GB but weakens provenance and may break builds that derive versions from Git.

Do not delete every directory named `build` or `target` in the original data:
some repositories may track unusual paths. If a clean package is desired, clean
only a verified staging copy with Git-aware commands and then rerun all 48
baseline recipes on that staged copy.

### 6.4 Archive format

For Windows-to-Windows transfer, ZIP or 7z is acceptable. For Docker/Linux
handoff, TAR.GZ/TAR.ZST is preferred because it preserves executable bits and
symlink semantics more reliably.

The archive must be generated from the common parent directory so that paths are
relative. After creation, record:

- archive filename and byte size;
- SHA-256 of the archive;
- creation timestamp;
- included/excluded paths;
- creator/tool version.

Do not modify `results/SHA256SUMS.csv` or the step markers to add the archive.
Create a separate handoff checksum next to the archive.

## 7. Docker decision for V3

### 7.1 Why V2 Docker is not reusable unchanged

The V2 Dockerfile uses `eclipse-temurin:8-jdk-jammy`, installs Maven from the
distribution package manager, installs global Gradle 7.5.1, and copies V2 scripts
and `config.docker.yaml`. The V2 Docker config also uses different eligibility
rules. Reusing it would silently change both the environment and the protocol.

The original V3 winning builds were observed on:

- Windows;
- Oracle JDK 8u172;
- Maven 3.9.15 for 41 winning scopes;
- Maven wrappers 3.9.5 and 3.6.3 for two scopes;
- Gradle wrappers 2.13, 5.2.1, 6.9.4, and 8.14.4 for five scopes.

A Linux Temurin JDK 8 container is therefore a portability environment, not a
byte-identical reproduction of the Windows/Oracle environment. It must pass all
48 recipes before it is declared supported.

At the time of this audit, the Docker client and Compose plugin are installed,
but the Docker daemon is not running. No V3 image has been built or validated.

### 7.2 Recommended V3 container architecture

Do not copy the 3.8 GB dataset into the image. Use:

```text
immutable environment image
  + read-only frozen bundle mount
  + read-write experiment workspace mount
  + read-write results mount
```

Example conceptual mounts:

```text
./V3_EXPERIMENT_HANDOFF/data_v3  → /bundle/data_v3:ro
./experiment_work                → /work
./experiment_results             → /results
```

The V3 image should pin:

- JDK 8 distribution and exact image digest;
- Maven 3.9.15;
- Git, curl, unzip, certificates, locale, and timezone;
- Python/orchestrator version and dependencies;
- EvoSuite 1.2.0;
- exact JaCoCo version within the proposed 0.8.x range;
- exact PIT/pitest version within the proposed 1.15.x range;
- experiment scripts and their checksums.

The proposal currently specifies JaCoCo 0.8.x and PIT 1.15.x as ranges. Exact
minor/patch versions must be frozen before the first outcome-producing run.

### 7.3 Dependency cache risk

Docker alone does not make old Maven/Gradle dependencies available. Wrapper
distributions and dependencies may disappear or become unreachable. If reliable
offline replay is required:

1. build the final V3 image;
2. create fresh Maven and Gradle caches dedicated to this study;
3. replay all 48 winning recipes inside the container;
4. seal the caches with an inventory/checksum;
5. export the image by digest and package the validated caches separately;
6. repeat a cold/offline smoke test where feasible.

Do not package the user's existing global Maven cache as-is: it contains unrelated
history and does not define which artifacts are required by this experiment.

## 8. Teammate acceptance and baseline replay

After extraction:

1. Verify the handoff archive checksum.
2. Verify `data_v3/results/RUN_READY`.
3. Run the checksum procedure in `data_v3/ARTIFACT_READING_GUIDE.md`.
4. Confirm 30 rows in `successful_repos_manifest.csv`.
5. Confirm each repository directory exists and `HEAD` equals `commit_sha`.
6. Configure JDK 8 before any manual Maven command.
7. Replay only the 48 rows in `build_recipes_portable.csv`.
8. Do not replay all rows in `build_attempts.csv`; it includes rejected
repositories and failed recipe-ladder attempts.
9. Save new stdout/stderr, exit code, start/end time, OS, Java, Maven/Gradle
version, and recipe ID.
10. Verify no tracked files changed after each baseline build.

Native Windows JDK preflight:

```bat
set "JAVA_HOME=C:\Program Files\Java\jdk1.8.0_172"
set "PATH=%JAVA_HOME%\bin;%PATH%"
where java
where javac
javac -version
mvn -version
```

Expected Maven runtime:

```text
C:\Program Files\Java\jdk1.8.0_172\jre
```

The standalone path `C:\Program Files\Java\jre1.8.0_172` is insufficient because
it has no `javac`.

Full baseline acceptance requires:

```text
48/48 winning recipes exit 0
30/30 repository HEAD values match the manifest
0 tracked source/build/dependency modifications
all focal paths in the final manifest exist
```

Maven `test-compile` and Gradle `testClasses -x test` compile baseline and test
sources but do not execute the repository's complete unit-test suite.

If a recipe fails only because a dependency server, DNS, TLS, or wrapper download
is unavailable, record it as a pre-experiment replay/environment failure. Do not
silently edit dependency declarations or switch the repository to a newer commit.

## 9. Experiment execution flow

The frozen repository copy must never receive generated tests directly. For each
`(repo_id, class_key, tool)`:

1. create a separate disposable clone/copy under the writable experiment
   workspace;
2. verify the exact commit and focal path;
3. replay the relevant baseline build scope;
4. generate exactly one GPT zero-shot test class for the GPT arm;
5. record raw prompt, raw response, model ID, parameters, timestamp, token usage,
   retries, and generated source;
6. compile the generated test and record the binary outcome/failure stage;
7. for compiled instances, run JaCoCo and PIT and preserve raw outputs;
8. independently run EvoSuite 1.2.0 with 60-second search budget and branch
   criterion in another workspace;
9. preserve every failure as an outcome rather than deleting or replacing it;
10. write one normalized per-instance result row for each arm.

The proposal freezes the GPT configuration as:

```text
model = gpt-4o-mini-2024-07-18
temperature = 0
top_p = 1
max_output_tokens = 2048
frequency_penalty = 0
presence_penalty = 0
prompting = zero-shot
```

Backups may be used only when a technical precheck fails before any GPT/EvoSuite
outcome is observed. Replacement must use the next backup from the same
repository and record `replacement_of`, `replacement_reason`, timestamp, and raw
evidence. Generated-test failure, low coverage, low mutation, or an unfavorable
result never permits replacement.

Minimum per-instance evidence:

- repository ID, URL, and exact commit;
- class key and focal path;
- build scope and recipe ID;
- tool/model version, prompt/config/seed/budget;
- generated test source;
- compile/build logs and normalized failure stage;
- JaCoCo, PIT, and EvoSuite raw output;
- timing and environment versions;
- compiled-only metrics where defined;
- strict whole-sample zero-filled metrics for the extension layer.

The GPT and EvoSuite arms for the same class must use separate workspaces.
Combining generated tests for all 10 classes of a repository in one checkout is
not allowed because one invalid generated test could contaminate other instances.

## 10. Statistical and integrity notes

The 300-main sample is exactly repository-balanced, but the two global complexity
halves are not balanced inside every repository. Repository `3847504`, for
example, contributes 10 higher-relative and zero lower-relative observations,
whereas repositories `46450575` and `97822421` contribute nine lower-relative and
one higher-relative observation each.

Comparisons between complexity halves should therefore account for repository
clustering or repository effects. This analysis decision must be frozen before
downstream outcomes are inspected.

The experiment must report two layers:

- AgoneTest-compatible compiled-only coverage/mutation summaries;
- strict whole-sample results where failures that prevent a metric receive zero
  for the affected metric and retain an explicit failure stage.

Do not describe the sample as a simple random sample of all 147,473 instances.
The operational frame is filtered by physical-file deduplication, repository
prequalification, JDK/buildability, exact-path existence, and structural class
eligibility.

## 11. Remaining work before team handoff is called complete

- create the V3 experiment runner;
- freeze exact JaCoCo and PIT patch versions;
- create a V3 Dockerfile/Compose definition rather than reuse V2;
- start Docker and build the image;
- replay 48/48 winning scopes inside the image;
- decide whether to distribute a sealed dependency cache;
- create the staging handoff directory and archive;
- compute and independently verify the archive SHA-256;
- perform extraction and baseline smoke testing on the teammate's machine;
- freeze the final prompt/config and analysis plan before outcome generation.

Until these items are completed, the **dataset** is ready, but the
**containerized experiment handoff** is not yet validated.
