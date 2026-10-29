# Data V3 build handoff

## 1. Scope and principles

This directory is an independent handoff tool. It is not Step 006 and does not modify
`research_pipeline_v3` or any frozen artifact in `data_v3`.

The runner only replays the 48 winning build recipes for the final 30 repositories. It
does not run JaCoCo, PIT, or EvoSuite, generate tests, or change the sampling criteria.

Frozen source is always read from:

```text
data_v3/repos/successful/<repo_id>
```

Every build runs on a writable copy under `build_work`. New logs and result tables are
written to `build_replay_results`. Neither directory is original pipeline evidence.

## 2. Required archive layout

Place the following three directories under the same parent directory:

```text
data/
  data_v3/
  research_pipeline_v3/
  v3_build_handoff/
```

Do not change these relative locations while using the default `handoff_config.json`.
`build_work`, `build_replay_results`, and old caches do not belong in the archive.

A complete handoff includes `research_pipeline_v3` because the verifier checks the Step
005 source-inventory checksum. An archival handoff must preserve `.git` inside all 30
repositories so the verifier can check the exact commit and detect tracked-file drift.
A normal GitHub source snapshot usually does not retain nested `.git` directories; in
that case, use the recorded manifests and checksums until the full provenance archive is
published.

From the parent `data` directory, prefer TAR.GZ when handing the bundle to Docker or
Linux:

```bat
tar.exe -czf V3_BUILD_HANDOFF.tar.gz data_v3 research_pipeline_v3 v3_build_handoff
certutil -hashfile V3_BUILD_HANDOFF.tar.gz SHA256
```

If the team requires ZIP:

```bat
tar.exe -a -cf V3_BUILD_HANDOFF.zip data_v3 research_pipeline_v3 v3_build_handoff
certutil -hashfile V3_BUILD_HANDOFF.zip SHA256
```

Send the archive SHA-256 over a channel separate from the archive. After extraction, the
verifier performs file-level checks; the archive checksum only establishes that the
transferred archive did not change in transit.

## 3. Relative configuration

`handoff_config.json` contains no path from the data-producing machine. Every path is
resolved relative to the configuration file itself:

```text
data_root   = ../data_v3
work_root   = ../build_work
result_root = ../build_replay_results
```

In a recipe, `${REPO_DIR}` is a portable placeholder, not text that a user should type
directly in CMD. The runner replaces it with the real workspace path and selects the
Windows or POSIX command column. Seven recipes have a `build_root_relative` other than
`.`; for those recipes, the runner also applies the recorded build-scope path from the
same CSV row. This reconstructs the original working directory and command without
modifying the sealed portable artifact.

For example, the recipe:

```text
v3:46450575:maven:contrib/flo-bigquery
```

is converted to a Maven command whose `-f` option points to the writable copy of
repository `46450575`. Users do not edit the CSV or copy a path from the original data
machine. Builds always use the copy under `build_work`; Maven and Gradle never run
directly against `data_v3`.

## 4. Verify the bundle without building

From `v3_build_handoff`, run:

```bat
py scripts\verify_bundle.py --config handoff_config.json
py scripts\verify_bundle.py --config handoff_config.json --full-checksums
```

The first command checks the layout, `RUN_READY`, the Step 005 source inventory, 30
commits, 300 main classes, 60 backup classes, the 10+2 balance per repository, zero
overlap, 48 recipes, and their evidence logs. `--full-checksums` rehashes the entire build
evidence inventory and therefore takes longer.

`verify_bundle.py` and `replay_builds.py --check-only` do not create a workspace, run
Maven or Gradle, or write a summary.

## 5. Native Windows execution

Requirements:

- Python 3.9 or later.
- A complete JDK 8u172 or compatible JDK 8 installation containing both `java` and
  `javac`.
- Maven 3.9.15.
- Git.
- Network access or a dependency cache for missing dependencies and wrappers.

The data-producing machine used these tool locations:

```text
C:\Program Files\Java\jdk1.8.0_172
C:\Program Files\apache-maven-3.9.15
```

These are external tool-installation examples, not project paths. On a different machine,
set `JDK8_HOME` and `MAVEN_3915_HOME` to the actual local installations.

From the repository root, open a new CMD window and run:

```bat
cd data\v3_build_handoff
call native_windows\setup_jdk8.cmd
native_windows\preflight.cmd
```

For tools installed elsewhere:

```bat
set "JDK8_HOME=<path-to-jdk8>"
set "MAVEN_3915_HOME=<path-to-maven-3.9.15>"
call native_windows\setup_jdk8.cmd
```

Do not set `JDK8_HOME` to a JRE such as `jre1.8.0_172`: a JRE provides `java` but not
`javac`. After setup, `mvn -version` must report Java 8 from the selected JDK.

Preflight every recipe without building:

```bat
py scripts\replay_builds.py --config handoff_config.json --check-only
```

Build one repository:

```bat
py scripts\replay_builds.py --config handoff_config.json --repo-id 46450575
```

Build one exact recipe:

```bat
py scripts\replay_builds.py --config handoff_config.json --recipe-id v3:46450575:maven:contrib/flo-bigquery
```

Build everything and resume safely after interruption:

```bat
py scripts\replay_builds.py --config handoff_config.json --all --resume --jobs 1
```

`--resume` skips an earlier passing attempt only when both the original-command hash and
environment fingerprint match. A pass from another environment is not treated as a valid
replacement result.

## 6. Docker execution

### 6.1 Role of the V2 image

The Dockerfile uses the V2 image only as a **JDK 8 base toolchain**. It does not run V2
scripts or configuration. It replaces global Maven with exactly version 3.9.15. Every
final Gradle recipe uses the repository wrapper, so the runner does not use a global
Gradle installation from the V2 image.

The default base image is:

```text
minhquy266/classes2test-pipeline:pilot-v1
```

The image reference is retained to document the original environment. It is not a
credential. If that image is unavailable or a compatible JDK 8 base image is preferred,
set `V2_BASE_IMAGE` before building:

```bat
set "V2_BASE_IMAGE=<compatible-jdk8-base-image>"
docker compose build
```

An alternative base image is a portability environment, not an exact reproduction of the
original environment. If the V2 image was loaded from a TAR file under another tag, set
`V2_BASE_IMAGE` to that tag in the same way.

### 6.2 Build and preflight

Start Docker Desktop, then run from `v3_build_handoff`:

```bat
docker compose build
docker compose run --rm build-handoff
```

The default command is `--check-only`. Compose mounts:

- `data_v3` and `research_pipeline_v3` as read-only;
- `build_work`, `build_replay_results`, the Maven cache, and the Gradle cache as
  read-write.

Build one sample recipe:

```bat
docker compose run --rm build-handoff python3 scripts/replay_builds.py --config handoff_config.json --recipe-id v3:46450575:maven:contrib/flo-bigquery
```

Replay everything:

```bat
docker compose run --rm build-handoff python3 scripts/replay_builds.py --config handoff_config.json --all --resume --jobs 1
```

Use `--jobs 1` for the first validation run. Increase parallelism only after measuring
available memory because some Maven reactors and Gradle daemons consume substantial RAM.
The runner parallelizes repositories and never runs two scopes from the same repository
at the same time.

The container uses a Temurin JDK 8 on Linux, while the original collection run used Oracle
JDK 8u172 on Windows. Docker therefore provides a portability environment and must not be
claimed as a successful reproduction until all 48 recipes pass.

## 7. Outputs and interpretation

Every new attempt creates:

```text
build_replay_results/
  environment.json
  build_replay_summary.csv
  logs/<repo_id>/<recipe-id>.stdout.log
  logs/<repo_id>/<recipe-id>.stderr.log
```

`build_replay_summary.csv` records the recipe, commit, resolved command, duration, exit
code, failure category, tracked changes, log paths, and environment fingerprint. It is an
append-only audit table: resuming a failed recipe appends a new attempt instead of
deleting prior history. To calculate 48/48, use the latest attempt for every `recipe_id`
within the same environment fingerprint.

`resolved_command` and log paths in the summary intentionally use absolute paths from the
machine that performed the replay as evidence. They are outputs, not portable
configuration. Another machine must reconstruct commands from
`build_recipes_portable.csv` through the runner.

`v3_build_handoff/output` is reserved for archive checksums and handoff notes. The runner
does not put build logs there, keeping handoff outputs separate from
`build_replay_results`.

A valid pass requires all of the following:

- Process exit code 0.
- `HEAD` equals the recorded `commit_sha`.
- No tracked file changed during the build.

`test-compile` and `testClasses -x test` compile baseline, main, and test source; they do
not run every repository test.

If a dependency server, DNS, TLS, or wrapper download fails, preserve the log and classify
the result as a replay or environment failure. Do not change a dependency, build file,
commit, or recipe to force a pass.

## 8. Team acceptance procedure

1. Verify the SHA-256 of the received ZIP or TAR archive.
2. Extract it with the required three-directory layout.
3. Run `verify_bundle.py --full-checksums`.
4. Run `replay_builds.py --check-only`.
5. Smoke-test recipe `v3:46450575:maven:contrib/flo-bigquery`.
6. Run `--all --resume --jobs 1`.
7. Accept the environment only when the new summary contains 48/48 passing recipes,
   30/30 exact commits, and an empty `tracked_changes` field.
8. Seal the image by digest and store separate checksums for the archive, any transferred
   cache, the summary, and the new logs.

Do not modify `results/SHA256SUMS.csv`, Step 001-005 markers, or original evidence
checksums to include handoff results. Replay results are a separate evidence layer.

## 9. Storage and caches

Writable workspace copies can require several additional gigabytes because
`data_v3/repos/successful` is approximately 3.55 GB. Maven and Gradle caches improve
replay reliability, but they must be generated by this replay and sealed separately. Do
not distribute an entire global cache containing unrelated artifacts.

After the team preserves the required logs, `build_work` can be removed separately to
recover disk space. Never delete or clean `data_v3/repos/successful` directly.
