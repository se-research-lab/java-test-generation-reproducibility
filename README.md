# FISAT 2026 Java Test Generation Experiment Source

Source bundle for **Buildability and Mutation Strength in Java Unit Test Generation: GPT-4o-mini vs EvoSuite**.

This folder copies and organizes the existing experimental source, configuration history, and small frozen result tables. The copied source files are byte-for-byte unchanged. No dependency was downloaded, no experiment was launched, and nothing was pushed to GitHub while preparing this folder.

## Start here

- [Hướng dẫn tiếng Việt](docs/START_HERE_VI.md)
- [Run guide and actual entry points](docs/RUN_GUIDE.md)
- [Source layout and version map](docs/SOURCE_LAYOUT.md)
- [Existing dependencies and local assets](docs/DEPENDENCIES_AND_LOCAL_ASSETS.md)
- [Result meanings and limitations](docs/RESULTS_AND_POLICIES.md)
- [Push the folder in stages](docs/PUSH_TO_GITHUB.md)
- [Complete Python source index](manifests/PYTHON_SOURCE_INDEX.csv)
- [Preserved backup/development syntax issues](docs/ARCHIVED_CODE_NOTES.md)

## Layout

```text
FISAT2026_GITHUB_SOURCE/
  README.md
  docs/                         # Current navigation and run instructions
  tools/verify_bundle.py        # Standard-library-only package verification
  manifests/                    # Copy map, file hashes and source index
  workspace/                    # Mirrors the original relative source layout
    scripts_v2/                 # Historical G0/E0 runner, AgoneTest, API/UI source
    camera_ready_minimal/
      paired49_20261023/         # E49 source, patches, original-source backups
      b1_full300_20261026/       # E1 Maven/Gradle/completion source and policies
    review_reports/             # Frozen-input guards
    output/camera_ready_review/ # Historical offline analytics
```

The layout preserves relative module relationships; it does **not** convert the historical experiment to a new portable treatment. Some archived runners retain absolute paths and require the original input snapshots, toolchains, admissions and raw evidence. See the run guide before executing them. Archived README/status files inside `workspace/` reflect their dates; the docs in this top-level folder describe this bundle.

## Verify the copy without installing anything

From this folder, with an existing Python 3 installation:

```powershell
python tools/verify_bundle.py
```

This checks local hashes only. It does not import experimental code, install packages or start workers.

## Scientific scope

G0 is frozen zero-shot GPT. E0 is the historical assertion-disabled EvoSuite pipeline. E1 is the assertion-enabled extension with documented integration amendments. The E1 ledger has 300 class records: **221 observed PIT scores, 58 conventional failure zeros, and 21 unresolved scores**. Process gates are **222 pass, 58 fail, 20 unresolved**. The five RQs and GPT cohorts 61/45/300 remain unchanged.

This is a **source and small-results bundle**, not an image of the complete experimental workspace. Tool JARs, installed libraries, dependency caches, benchmark clones, sqlite snapshots, all generated suites and full raw report/log archives remain in the existing local workspace. No secrets or real `.env` files are intentionally included. A common-signature scan is documented in the manifest; this is not a guarantee that public redistribution needs no further review.

Repository owner, publication URL, software/data licenses and paper DOI have not been assigned here. The source snapshot is ready for the author's staged review and push; it is not a claim of a public artifact release or a fully measured E1-full300 evaluation.
