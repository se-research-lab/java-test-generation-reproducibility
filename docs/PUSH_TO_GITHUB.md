# Push this folder in stages

No Git repository or remote was initialized during packaging. Choose your own GitHub repository. Commands below are manual examples; `<REMOTE_URL>` is a placeholder, not an existing artifact URL.

## Suggested commits

1. README, current docs, `.gitignore`, `.gitattributes` and `tools/`.
2. Original historical runner, AgoneTest, data_new and optional UI source.
3. E49 source, exact helper snapshots and policy metadata.
4. E1 src/adapters/config/admission/completion policies.
5. Frozen analysis tables, source/provenance index and manifests.

Do not add the original D:/A_ThucNghiem folder as a whole. This source bundle omits real environment files/settings, dependency binaries and caches. Review the staged files and the file list again before making a repository public. Copied archived code includes unused/older versions and machine-bound paths; docs explain their role.

Example from this folder:

```powershell
git init -b main
git add README.md docs tools .gitignore .gitattributes
git commit -m "Document experiment source and run guide"
git add workspace/scripts_v2
git commit -m "Add historical GPT and EvoSuite pipeline source"
git add workspace/camera_ready_minimal/paired49_20261023
git commit -m "Add fixed49 source and configuration history"
git add workspace/camera_ready_minimal/b1_full300_20261026 workspace/review_reports workspace/output
git commit -m "Add E1 source policies and frozen analysis tables"
git add manifests
git commit -m "Add source copy map and checksums"
git remote add origin <REMOTE_URL>
git push -u origin main
```

Run `python tools/verify_bundle.py` before a reviewed push. If you intentionally edit a copied file, its original-copy checksum will change; record the change in Git and retain the original source provenance. Do not reuse a historical result hash for modified bytes.

No license is invented by this bundle. Determine licenses/third-party notices before public release. An actual, accessible repository/release can later be cited in the manuscript; no public availability statement should be made solely because this local folder exists.
