#!/usr/bin/env python3
"""Read-only verifier for the frozen Data V3 build handoff bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


EXPECTED_REPOSITORIES = 30
EXPECTED_MAIN_CLASSES = 300
EXPECTED_BACKUP_CLASSES = 60
EXPECTED_RECIPES = 48
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_DRIVE_PATTERN = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")


class VerificationError(RuntimeError):
    """Raised when the handoff bundle violates a required invariant."""


@dataclass(frozen=True)
class HandoffContext:
    config_path: Path
    handoff_root: Path
    data_root: Path
    pipeline_root: Path
    repository_manifest: Path
    final_sample_manifest: Path
    backup_manifest: Path
    portable_recipes: Path
    repository_storage_root: Path
    work_root: Path
    result_root: Path
    config: dict[str, Any]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise VerificationError(f"Required JSON file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise VerificationError(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(payload, dict):
        raise VerificationError(f"Expected a JSON object in {path}")
    return payload


def _relative_config_path(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise VerificationError(f"Config key {key!r} must be a non-empty relative path")
    candidate = Path(value)
    if candidate.is_absolute() or WINDOWS_DRIVE_PATTERN.search(value):
        raise VerificationError(f"Config key {key!r} must not contain an absolute path: {value}")
    return value


def _resolve_relative(base: Path, value: str) -> Path:
    return (base / value).resolve()


def load_context(config_path: str | Path) -> HandoffContext:
    resolved_config = Path(config_path).expanduser().resolve()
    config = _load_json(resolved_config)
    if config.get("schema_version") != 1:
        raise VerificationError(
            f"Unsupported handoff schema_version: {config.get('schema_version')!r}"
        )
    handoff_root = resolved_config.parent
    data_root = _resolve_relative(handoff_root, _relative_config_path(config, "data_root"))
    pipeline_root = _resolve_relative(
        handoff_root, _relative_config_path(config, "pipeline_root")
    )
    repository_manifest = data_root / _relative_config_path(
        config, "repository_manifest"
    )
    final_sample_manifest = data_root / _relative_config_path(
        config, "final_sample_manifest"
    )
    backup_manifest = data_root / _relative_config_path(config, "backup_manifest")
    portable_recipes = data_root / _relative_config_path(config, "portable_recipes")
    repository_storage_root = data_root / _relative_config_path(
        config, "repository_storage_root"
    )
    work_root = _resolve_relative(handoff_root, _relative_config_path(config, "work_root"))
    result_root = _resolve_relative(
        handoff_root, _relative_config_path(config, "result_root")
    )
    return HandoffContext(
        config_path=resolved_config,
        handoff_root=handoff_root,
        data_root=data_root,
        pipeline_root=pipeline_root,
        repository_manifest=repository_manifest,
        final_sample_manifest=final_sample_manifest,
        backup_manifest=backup_manifest,
        portable_recipes=portable_recipes,
        repository_storage_root=repository_storage_root,
        work_root=work_root,
        result_root=result_root,
        config=config,
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError as error:
        raise VerificationError(f"Required CSV file is missing: {path}") from error


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: str, label: str) -> Path:
    normalized = value.replace("\\", "/").strip("/")
    candidate = Path(normalized)
    if (
        not normalized
        or candidate.is_absolute()
        or WINDOWS_DRIVE_PATTERN.search(normalized)
        or ".." in candidate.parts
    ):
        raise VerificationError(f"Unsafe {label}: {value!r}")
    return candidate


def _path_inside(root: Path, relative: Path, label: str) -> Path:
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise VerificationError(f"{label} escapes its allowed root: {resolved}")
    return resolved


def git_head(repository: Path) -> str:
    safe = repository.resolve().as_posix()
    command = [
        "git",
        "-c",
        f"safe.directory={safe}",
        "-C",
        str(repository),
        "rev-parse",
        "HEAD",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError as error:
        raise VerificationError("git is required but was not found on PATH") from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise VerificationError(f"Cannot read HEAD for {repository}: {detail}")
    return completed.stdout.strip()


def _verify_file_hash_rows(
    root: Path, rows: Iterable[dict[str, str]], label: str
) -> tuple[int, list[str]]:
    checked = 0
    errors: list[str] = []
    for row in rows:
        raw_path = row.get("path", "")
        expected = row.get("sha256", "").lower()
        if not SHA256_PATTERN.fullmatch(expected):
            errors.append(f"{label}: invalid expected SHA-256 for {raw_path!r}")
            continue
        try:
            relative = _safe_relative_path(raw_path, f"{label} path")
            path = _path_inside(root, relative, f"{label} path")
        except VerificationError as error:
            errors.append(str(error))
            continue
        if not path.is_file():
            errors.append(f"{label}: missing file {raw_path}")
            continue
        actual = sha256_file(path)
        checked += 1
        if actual != expected:
            errors.append(
                f"{label}: hash mismatch for {raw_path}: expected {expected}, got {actual}"
            )
    return checked, errors


def verify_bundle(
    context: HandoffContext, full_checksums: bool = False
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for label, path in (
        ("data_root", context.data_root),
        ("pipeline_root", context.pipeline_root),
        ("repository_storage_root", context.repository_storage_root),
    ):
        if not path.is_dir():
            errors.append(f"{label} is missing or is not a directory: {path}")

    run_ready_path = context.data_root / "results" / "RUN_READY"
    try:
        run_ready = _load_json(run_ready_path)
        if run_ready.get("status") != "READY":
            errors.append(f"RUN_READY status is not READY: {run_ready.get('status')!r}")
    except VerificationError as error:
        errors.append(str(error))
        run_ready = {}

    try:
        repositories = read_csv(context.repository_manifest)
        main_rows = read_csv(context.final_sample_manifest)
        backup_rows = read_csv(context.backup_manifest)
        recipes = read_csv(context.portable_recipes)
    except VerificationError as error:
        errors.append(str(error))
        repositories, main_rows, backup_rows, recipes = [], [], [], []

    repository_ids = [row.get("repo_id", "") for row in repositories]
    repository_id_set = set(repository_ids)
    if len(repositories) != EXPECTED_REPOSITORIES:
        errors.append(
            f"Expected {EXPECTED_REPOSITORIES} repository rows, found {len(repositories)}"
        )
    if len(repository_id_set) != EXPECTED_REPOSITORIES or "" in repository_id_set:
        errors.append("Repository IDs are missing or are not exactly 30 unique values")

    manifest_by_repo: dict[str, dict[str, str]] = {}
    head_matches = 0
    for row in repositories:
        repo_id = row.get("repo_id", "")
        if not repo_id:
            continue
        manifest_by_repo[repo_id] = row
        expected_relative = Path("repos") / "successful" / repo_id
        try:
            recorded_relative = _safe_relative_path(
                row.get("repository_storage_path", ""), "repository_storage_path"
            )
        except VerificationError as error:
            errors.append(str(error))
            continue
        if recorded_relative.as_posix().casefold() != expected_relative.as_posix().casefold():
            errors.append(
                f"Repo {repo_id} has unexpected storage path: {recorded_relative.as_posix()}"
            )
            continue
        repository = _path_inside(
            context.data_root, recorded_relative, f"repository {repo_id}"
        )
        if not repository.is_dir():
            errors.append(f"Repo {repo_id} storage is missing: {repository}")
            continue
        expected_commit = row.get("commit_sha", "")
        try:
            observed_commit = git_head(repository)
        except VerificationError as error:
            errors.append(str(error))
            continue
        if observed_commit != expected_commit:
            errors.append(
                f"Repo {repo_id} HEAD mismatch: expected {expected_commit}, got {observed_commit}"
            )
        else:
            head_matches += 1

    main_keys = [row.get("class_key", "") for row in main_rows]
    backup_keys = [row.get("class_key", "") for row in backup_rows]
    if len(main_rows) != EXPECTED_MAIN_CLASSES:
        errors.append(f"Expected 300 final main rows, found {len(main_rows)}")
    if len(set(main_keys)) != EXPECTED_MAIN_CLASSES or "" in set(main_keys):
        errors.append("Final main class keys are missing or are not exactly 300 unique values")
    if len(backup_rows) != EXPECTED_BACKUP_CLASSES:
        errors.append(f"Expected 60 backup rows, found {len(backup_rows)}")
    if len(set(backup_keys)) != EXPECTED_BACKUP_CLASSES or "" in set(backup_keys):
        errors.append("Backup class keys are missing or are not exactly 60 unique values")
    overlap = set(main_keys) & set(backup_keys)
    if overlap:
        errors.append(f"Main/backup overlap is not zero: {len(overlap)}")

    main_counts = Counter(row.get("repo_id", "") for row in main_rows)
    backup_counts = Counter(row.get("repo_id", "") for row in backup_rows)
    if set(main_counts) != repository_id_set:
        errors.append("Main manifest repository IDs do not match repository manifest")
    if set(backup_counts) != repository_id_set:
        errors.append("Backup manifest repository IDs do not match repository manifest")
    for repo_id in sorted(repository_id_set):
        if main_counts[repo_id] != 10:
            errors.append(f"Repo {repo_id} has {main_counts[repo_id]} main rows, expected 10")
        if backup_counts[repo_id] != 2:
            errors.append(f"Repo {repo_id} has {backup_counts[repo_id]} backup rows, expected 2")

    missing_focal_paths = 0
    for row in main_rows + backup_rows:
        repo_id = row.get("repo_id", "")
        manifest = manifest_by_repo.get(repo_id)
        if manifest is None:
            continue
        try:
            storage_relative = _safe_relative_path(
                manifest.get("repository_storage_path", ""), "repository_storage_path"
            )
            focal_relative = _safe_relative_path(
                row.get("focal_path", ""), "focal_path"
            )
            repository = _path_inside(context.data_root, storage_relative, "repository")
            focal = _path_inside(repository, focal_relative, "focal path")
        except VerificationError as error:
            errors.append(str(error))
            continue
        if not focal.is_file():
            missing_focal_paths += 1
    if missing_focal_paths:
        errors.append(f"Missing focal paths in main/backup manifests: {missing_focal_paths}")

    recipe_ids = [row.get("recipe_id", "") for row in recipes]
    recipe_repo_ids = {row.get("repo_id", "") for row in recipes}
    if len(recipes) != EXPECTED_RECIPES:
        errors.append(f"Expected 48 portable recipes, found {len(recipes)}")
    if len(set(recipe_ids)) != EXPECTED_RECIPES or "" in set(recipe_ids):
        errors.append("Portable recipe IDs are missing or are not exactly 48 unique values")
    if recipe_repo_ids != repository_id_set:
        errors.append("Portable recipe repositories do not match the final 30 repositories")

    absolute_recipe_commands = 0
    missing_recipe_logs = 0
    invalid_recipe_log_hashes = 0
    for row in recipes:
        repo_id = row.get("repo_id", "")
        if repo_id not in repository_id_set:
            errors.append(f"Recipe refers to non-final repository: {repo_id}")
        for field in ("portable_command_windows", "portable_command_posix"):
            command = row.get(field, "")
            if "${REPO_DIR}" not in command:
                errors.append(
                    f"Recipe {row.get('recipe_id')} is missing ${{REPO_DIR}} in {field}"
                )
            if WINDOWS_DRIVE_PATTERN.search(command):
                absolute_recipe_commands += 1
        log_relative_raw = row.get("validation_log_relative", "")
        try:
            log_relative = _safe_relative_path(log_relative_raw, "validation log path")
            log_path = _path_inside(context.data_root, log_relative, "validation log")
        except VerificationError as error:
            errors.append(str(error))
            continue
        if not log_path.is_file():
            missing_recipe_logs += 1
            continue
        expected_log_hash = row.get("validation_log_sha256", "").lower()
        if not SHA256_PATTERN.fullmatch(expected_log_hash):
            invalid_recipe_log_hashes += 1
        elif full_checksums and sha256_file(log_path) != expected_log_hash:
            errors.append(
                f"Recipe validation log hash mismatch: {log_relative.as_posix()}"
            )
    if absolute_recipe_commands:
        errors.append(
            f"Portable recipes still contain Windows absolute paths: {absolute_recipe_commands}"
        )
    if missing_recipe_logs:
        errors.append(f"Portable recipe validation logs missing: {missing_recipe_logs}")
    if invalid_recipe_log_hashes:
        errors.append(
            f"Portable recipe validation log hashes invalid: {invalid_recipe_log_hashes}"
        )

    step005_checked = 0
    try:
        step005 = _load_json(context.data_root / "state" / "step005.done.json")
        step005_rows = step005.get("outputs", [])
        if not isinstance(step005_rows, list):
            raise VerificationError("step005.done.json outputs must be a list")
        step005_checked, step005_errors = _verify_file_hash_rows(
            context.data_root, step005_rows, "Step 005 marker"
        )
        errors.extend(step005_errors)
    except VerificationError as error:
        errors.append(str(error))

    final_manifest_hash = (
        sha256_file(context.final_sample_manifest)
        if context.final_sample_manifest.is_file()
        else ""
    )
    if run_ready.get("main_manifest_sha256") != final_manifest_hash:
        errors.append("RUN_READY final manifest hash does not match the final manifest")

    evidence_checked = 0
    if full_checksums:
        evidence_path = context.data_root / "BUILD_EVIDENCE_SHA256SUMS.csv"
        try:
            evidence_rows = read_csv(evidence_path)
            evidence_checked, evidence_errors = _verify_file_hash_rows(
                context.data_root, evidence_rows, "Build evidence"
            )
            errors.extend(evidence_errors)
        except VerificationError as error:
            errors.append(str(error))
    else:
        warnings.append(
            "Build-evidence files were not rehashed; pass --full-checksums for the 1,583-file audit"
        )

    report = {
        "status": "PASS" if not errors else "FAIL",
        "config_path": str(context.config_path),
        "data_root": str(context.data_root),
        "pipeline_root": str(context.pipeline_root),
        "repositories": len(repositories),
        "repository_heads_matching": head_matches,
        "main_classes": len(main_rows),
        "backup_classes": len(backup_rows),
        "main_backup_overlap": len(overlap),
        "portable_recipes": len(recipes),
        "missing_focal_paths": missing_focal_paths,
        "step005_outputs_hashed": step005_checked,
        "build_evidence_files_hashed": evidence_checked,
        "errors": errors,
        "warnings": warnings,
    }
    return report


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "handoff_config.json"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the frozen Data V3 handoff without building repositories or "
            "modifying the bundle."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_default_config_path(),
        help="Path to handoff_config.json (default: handoff root config)",
    )
    parser.add_argument(
        "--full-checksums",
        action="store_true",
        help="Rehash the complete BUILD_EVIDENCE_SHA256SUMS.csv inventory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete verification report as JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        context = load_context(args.config)
        report = verify_bundle(context, full_checksums=args.full_checksums)
    except VerificationError as error:
        report = {
            "status": "FAIL",
            "errors": [str(error)],
            "warnings": [],
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"{report['status']}: repos={report.get('repositories', 0)}, "
            f"main={report.get('main_classes', 0)}, "
            f"backup={report.get('backup_classes', 0)}, "
            f"recipes={report.get('portable_recipes', 0)}"
        )
        for warning in report.get("warnings", []):
            print(f"WARNING: {warning}")
        for error in report.get("errors", []):
            print(f"ERROR: {error}")
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
