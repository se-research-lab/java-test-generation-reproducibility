#!/usr/bin/env python3
"""Replay the 48 frozen Data V3 baseline build recipes in disposable workspaces."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import csv
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from verify_bundle import (
    HandoffContext,
    VerificationError,
    git_head,
    load_context,
    read_csv,
    verify_bundle,
)


SUMMARY_FIELDS = [
    "recipe_id",
    "repo_id",
    "commit_sha",
    "scope_key",
    "recipe",
    "command_source",
    "command_platform",
    "original_command_sha256",
    "resolved_command",
    "workspace",
    "build_working_directory",
    "started_at",
    "finished_at",
    "duration_seconds",
    "exit_code",
    "status",
    "failure_category",
    "tracked_changes",
    "stdout_log_path",
    "stderr_log_path",
    "environment_fingerprint",
]

PRINT_LOCK = threading.Lock()
SUMMARY_LOCK = threading.Lock()


class ReplayError(RuntimeError):
    """Raised for a controlled handoff replay failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    with PRINT_LOCK:
        print(f"[{datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "recipe"


def _capture(command: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"Command timed out: {' '.join(command)}"
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    return completed.returncode, output


def collect_environment(context: HandoffContext) -> dict[str, Any]:
    maven_command = "mvn.cmd" if os.name == "nt" else "mvn"
    commands = {
        "java": ["java", "-version"],
        "javac": ["javac", "-version"],
        "maven": [maven_command, "-version"],
        "git": ["git", "--version"],
    }
    tools: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name, command in commands.items():
        exit_code, output = _capture(command)
        tools[name] = {
            "command": command,
            "exit_code": exit_code,
            "output": output,
        }
        if exit_code != 0:
            errors.append(f"{name} preflight failed: {output}")

    required_java = int(context.config.get("required_java_major", 8))
    java_output = tools["java"]["output"]
    javac_output = tools["javac"]["output"]
    maven_output = tools["maven"]["output"]
    java_8_pattern = re.compile(r'(?:version\s+")?1\.8(?:[._"\s]|$)', re.IGNORECASE)
    if required_java == 8:
        if not java_8_pattern.search(java_output):
            errors.append(f"java is not Java 8: {java_output}")
        if not java_8_pattern.search(javac_output):
            errors.append(f"javac is not Java 8 or is missing: {javac_output}")
        if not re.search(r"Java version:\s*1\.8", maven_output, re.IGNORECASE):
            errors.append(f"Maven is not running on JDK 8: {maven_output}")

    required_maven = str(context.config.get("required_maven_version", "")).strip()
    if required_maven and not re.search(
        rf"Apache Maven\s+{re.escape(required_maven)}(?:\s|$)", maven_output
    ):
        errors.append(
            f"Expected global Maven {required_maven}, observed: "
            f"{maven_output.splitlines()[0] if maven_output else 'missing'}"
        )
    if re.search(r"[\\/]jre1\.8", maven_output, re.IGNORECASE):
        errors.append(
            "Maven is using a standalone JRE instead of a JDK; javac will be unavailable"
        )

    payload = {
        "captured_at": utc_now(),
        "platform": platform.platform(),
        "python": sys.version,
        "tools": tools,
        "errors": errors,
    }
    canonical = json.dumps(
        {
            "platform": payload["platform"],
            "python": payload["python"],
            "tools": tools,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def _ensure_inside(root: Path, path: Path, label: str) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise ReplayError(f"{label} is outside its owned root: {resolved}")
    return resolved


def _remove_readonly(function: Any, path: str, _: Any) -> None:
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    function(path)


def _safe_remove_tree(root: Path, target: Path) -> None:
    resolved = _ensure_inside(root, target, "temporary workspace")
    if resolved.exists():
        shutil.rmtree(resolved, onerror=_remove_readonly)


def _git(repository: Path, arguments: list[str], timeout: int = 120) -> tuple[int, str]:
    safe = repository.resolve().as_posix()
    return _capture(
        [
            "git",
            "-c",
            f"safe.directory={safe}",
            "-C",
            str(repository),
            *arguments,
        ],
        timeout=timeout,
    )


def _require_git_success(
    repository: Path, arguments: list[str], label: str, timeout: int = 120
) -> str:
    exit_code, output = _git(repository, arguments, timeout=timeout)
    if exit_code != 0:
        raise ReplayError(f"{label} failed in {repository}: {output}")
    return output


def tracked_changes(repository: Path) -> str:
    return _require_git_success(
        repository,
        [
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--ignore-submodules=untracked",
        ],
        "git status",
    ).strip()


def _clean_workspace(repository: Path, commit_sha: str) -> None:
    _require_git_success(repository, ["reset", "--hard", commit_sha], "git reset")
    _require_git_success(repository, ["clean", "-fdx"], "git clean", timeout=300)
    # Cleaning a disposable handoff workspace is allowed. Submodule commands are
    # no-ops when the repository has no initialized submodules.
    _require_git_success(
        repository,
        ["submodule", "foreach", "--recursive", "git reset --hard"],
        "submodule reset",
        timeout=300,
    )
    _require_git_success(
        repository,
        ["submodule", "foreach", "--recursive", "git clean -fdx"],
        "submodule clean",
        timeout=300,
    )
    observed = git_head(repository)
    if observed != commit_sha:
        raise ReplayError(
            f"Workspace HEAD mismatch after reset: expected {commit_sha}, got {observed}"
        )
    dirty = tracked_changes(repository)
    if dirty:
        raise ReplayError(f"Workspace has tracked changes before build:\n{dirty}")


def prepare_workspace(
    context: HandoffContext, manifest: dict[str, str], reuse_existing: bool
) -> Path:
    repo_id = manifest["repo_id"]
    source = (
        context.data_root / manifest["repository_storage_path"].replace("/", os.sep)
    ).resolve()
    if not source.is_dir():
        raise ReplayError(f"Frozen source repository is missing: {source}")
    if git_head(source) != manifest["commit_sha"]:
        raise ReplayError(f"Frozen source HEAD does not match manifest for repo {repo_id}")

    repositories_root = context.work_root / "repos"
    repositories_root.mkdir(parents=True, exist_ok=True)
    workspace = _ensure_inside(
        repositories_root, repositories_root / repo_id, "repository workspace"
    )
    if workspace.exists():
        try:
            git_head(workspace)
        except Exception:
            log(f"Repo {repo_id}: removing incomplete handoff workspace")
            _safe_remove_tree(repositories_root, workspace)
    if workspace.exists() and not reuse_existing:
        # Do not delete an existing potentially valuable workspace implicitly.
        # Reset/clean it in-place because this path is dedicated to the handoff.
        log(f"Repo {repo_id}: reusing and cleaning existing handoff workspace")
    if not workspace.exists():
        log(f"Repo {repo_id}: copying frozen repository to writable workspace")
        try:
            # Docker Desktop bind mounts backed by NTFS can reject an atomic
            # rename of a populated directory even when source and destination
            # share the same mount. Copy directly to the final handoff-owned
            # path and roll it back on failure instead.
            shutil.copytree(source, workspace, symlinks=True, copy_function=shutil.copy2)
        except Exception:
            _safe_remove_tree(repositories_root, workspace)
            raise
    _clean_workspace(workspace, manifest["commit_sha"])
    return workspace


def _recipe_build_directory(recipe: dict[str, str], repository_root: Path) -> Path:
    relative_text = (recipe.get("build_root_relative") or ".").replace("\\", "/")
    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReplayError(
            f"Unsafe build_root_relative in {recipe.get('recipe_id')}: {relative_text}"
        )
    build_directory = (repository_root / relative).resolve()
    resolved_root = repository_root.resolve()
    if build_directory != resolved_root and resolved_root not in build_directory.parents:
        raise ReplayError(
            f"Build directory escapes repository in {recipe.get('recipe_id')}"
        )
    if not build_directory.is_dir():
        raise ReplayError(
            f"Build directory is missing in {recipe.get('recipe_id')}: "
            f"{build_directory}"
        )
    return build_directory


def _resolve_command(
    recipe: dict[str, str], repository_root: Path
) -> tuple[str, str]:
    command_platform = "windows" if os.name == "nt" else "posix"
    field = (
        "portable_command_windows"
        if command_platform == "windows"
        else "portable_command_posix"
    )
    template = recipe.get(field, "")
    if "${REPO_DIR}" not in template:
        raise ReplayError(f"Recipe {recipe.get('recipe_id')} has no REPO_DIR placeholder")
    # The sealed portable CSV stores nested scope location separately in
    # build_root_relative. Reconstruct the exact original build scope here
    # without rewriting that artifact.
    build_directory = _recipe_build_directory(recipe, repository_root)
    replacement = (
        str(build_directory)
        if command_platform == "windows"
        else build_directory.as_posix()
    )
    command = template.replace("${REPO_DIR}", replacement)
    if "${REPO_DIR}" in command:
        raise ReplayError(f"Unresolved REPO_DIR placeholder in {recipe.get('recipe_id')}")
    return command_platform, command


def _wrapper_path(command_platform: str, command: str) -> Path | None:
    try:
        tokens = shlex.split(command, posix=command_platform != "windows")
    except ValueError:
        return None
    if not tokens:
        return None
    executable = tokens[0].strip('"')
    lowered = executable.lower()
    if lowered.endswith(("mvnw", "mvnw.cmd", "gradlew", "gradlew.bat")):
        return Path(executable)
    return None


def validate_recipe_command(recipe: dict[str, str], workspace: Path) -> None:
    command_platform, command = _resolve_command(recipe, workspace)
    wrapper = _wrapper_path(command_platform, command)
    if wrapper is not None and not wrapper.is_file():
        raise ReplayError(
            f"Repository wrapper is missing for {recipe.get('recipe_id')}: {wrapper}"
        )


def _command_arguments(command_platform: str, command: str) -> list[str]:
    if command_platform == "windows":
        return ["cmd.exe", "/d", "/s", "/c", command]
    arguments = shlex.split(command, posix=True)
    if not arguments:
        raise ReplayError("Resolved build command is empty")
    executable = arguments[0].lower()
    if executable.endswith(("/mvnw", "/gradlew")):
        # This also works when a ZIP transfer lost the executable bit, and it
        # avoids changing tracked file modes in the disposable repository.
        return ["bash", *arguments]
    return arguments


def _terminate_process_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)


def run_logged_command(
    arguments: list[str],
    workspace: Path,
    stdout_log_path: Path,
    stderr_log_path: Path,
    timeout_seconds: int,
) -> tuple[int, bool]:
    creation_flags = 0
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        popen_kwargs["start_new_session"] = True
    with (
        stdout_log_path.open("w", encoding="utf-8", newline="\n") as stdout_handle,
        stderr_log_path.open("w", encoding="utf-8", newline="\n") as stderr_handle,
    ):
        header = (
            f"cwd: {workspace}\n"
            f"argv: {json.dumps(arguments, ensure_ascii=False)}\n\n"
        )
        stdout_handle.write(header)
        stderr_handle.write(header)
        stdout_handle.flush()
        stderr_handle.flush()
        process = subprocess.Popen(
            arguments,
            cwd=workspace,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
            **popen_kwargs,
        )
        try:
            exit_code = process.wait(timeout=timeout_seconds)
            return exit_code, False
        except subprocess.TimeoutExpired:
            stderr_handle.write(f"\nTIMEOUT after {timeout_seconds} seconds\n")
            stderr_handle.flush()
            _terminate_process_tree(process)
            return 124, True


def _read_resume_passes(
    summary_path: Path, environment_fingerprint: str
) -> set[tuple[str, str]]:
    if not summary_path.is_file():
        return set()
    rows = read_csv(summary_path)
    latest_status: dict[tuple[str, str], str] = {}
    for row in rows:
        if row.get("environment_fingerprint") != environment_fingerprint:
            continue
        key = (row.get("recipe_id", ""), row.get("original_command_sha256", ""))
        latest_status[key] = row.get("status", "")
    return {key for key, status in latest_status.items() if status == "PASS"}


def append_summary(summary_path: Path, row: dict[str, Any]) -> None:
    with SUMMARY_LOCK:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        exists = summary_path.is_file() and summary_path.stat().st_size > 0
        if exists:
            with summary_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
            if header != SUMMARY_FIELDS:
                raise ReplayError(
                    f"Existing summary has an incompatible header: {summary_path}"
                )
        encoding = "utf-8" if exists else "utf-8-sig"
        with summary_path.open("a", encoding=encoding, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})
            handle.flush()
            os.fsync(handle.fileno())


def run_one_recipe(
    context: HandoffContext,
    manifest: dict[str, str],
    recipe: dict[str, str],
    workspace: Path,
    environment_fingerprint: str,
    summary_path: Path,
) -> dict[str, Any]:
    recipe_id = recipe["recipe_id"]
    started_at = utc_now()
    start = time.monotonic()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    logs_root = context.result_root / "logs" / recipe["repo_id"]
    logs_root.mkdir(parents=True, exist_ok=True)
    log_stem = f"{safe_name(recipe_id)}_{stamp}"
    stdout_log_path = logs_root / f"{log_stem}.stdout.log"
    stderr_log_path = logs_root / f"{log_stem}.stderr.log"
    status = "FAIL"
    failure_category = ""
    exit_code = 1
    command_platform = ""
    resolved_command = ""
    build_working_directory = workspace
    dirty_after = ""
    try:
        _clean_workspace(workspace, manifest["commit_sha"])
        build_working_directory = _recipe_build_directory(recipe, workspace)
        command_platform, resolved_command = _resolve_command(recipe, workspace)
        validate_recipe_command(recipe, workspace)
        arguments = _command_arguments(command_platform, resolved_command)
        log(f"{recipe_id}: START")
        exit_code, timed_out = run_logged_command(
            arguments,
            build_working_directory,
            stdout_log_path,
            stderr_log_path,
            int(context.config.get("build_timeout_seconds", 900)),
        )
        dirty_after = tracked_changes(workspace)
        if timed_out:
            failure_category = "timeout"
        elif exit_code != 0:
            failure_category = "build_failed"
        elif dirty_after:
            failure_category = "tracked_files_modified"
        else:
            status = "PASS"
    except Exception as error:
        failure_category = "runner_exception"
        with stderr_log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"\nRUNNER EXCEPTION: {type(error).__name__}: {error}\n")
        log(f"{recipe_id}: runner exception: {error}")
    finished_at = utc_now()
    duration = round(time.monotonic() - start, 3)
    result = {
        "recipe_id": recipe_id,
        "repo_id": recipe["repo_id"],
        "commit_sha": manifest["commit_sha"],
        "scope_key": recipe.get("scope_key", ""),
        "recipe": recipe.get("recipe", ""),
        "command_source": recipe.get("command_source", ""),
        "command_platform": command_platform,
        "original_command_sha256": recipe.get("original_command_sha256", ""),
        "resolved_command": resolved_command,
        "workspace": str(workspace),
        "build_working_directory": str(build_working_directory),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "exit_code": exit_code,
        "status": status,
        "failure_category": failure_category,
        "tracked_changes": dirty_after.replace("\r", "\\r").replace("\n", "\\n"),
        "stdout_log_path": str(stdout_log_path),
        "stderr_log_path": str(stderr_log_path),
        "environment_fingerprint": environment_fingerprint,
    }
    append_summary(summary_path, result)
    log(f"{recipe_id}: {status} exit={exit_code} duration={duration}s")
    return result


def _select_recipes(
    recipes: list[dict[str, str]],
    all_recipes: bool,
    repo_ids: list[str],
    recipe_ids: list[str],
    check_only: bool,
) -> list[dict[str, str]]:
    known_repo_ids = {row["repo_id"] for row in recipes}
    known_recipe_ids = {row["recipe_id"] for row in recipes}
    unknown_repos = sorted(set(repo_ids) - known_repo_ids)
    unknown_recipes = sorted(set(recipe_ids) - known_recipe_ids)
    if unknown_repos:
        raise ReplayError(
            "Requested repository IDs are not in the final recipe set: "
            + ", ".join(unknown_repos)
        )
    if unknown_recipes:
        raise ReplayError(
            "Requested recipe IDs are not in the final recipe set: "
            + ", ".join(unknown_recipes)
        )
    if all_recipes or (check_only and not repo_ids and not recipe_ids):
        selected = list(recipes)
    else:
        selected = [
            row
            for row in recipes
            if row["repo_id"] in set(repo_ids)
            or row["recipe_id"] in set(recipe_ids)
        ]
    return sorted(selected, key=lambda row: (int(row["repo_id"]), row["recipe_id"]))


def _check_recipe_sources(
    context: HandoffContext,
    recipes: Iterable[dict[str, str]],
    manifest_by_repo: dict[str, dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    for recipe in recipes:
        repo_id = recipe["repo_id"]
        manifest = manifest_by_repo.get(repo_id)
        if manifest is None:
            errors.append(f"{recipe['recipe_id']}: repository is not in final manifest")
            continue
        if recipe.get("commit_sha") != manifest.get("commit_sha"):
            errors.append(f"{recipe['recipe_id']}: commit differs from repository manifest")
            continue
        repository = (
            context.data_root
            / manifest["repository_storage_path"].replace("/", os.sep)
        ).resolve()
        try:
            validate_recipe_command(recipe, repository)
        except Exception as error:
            errors.append(f"{recipe['recipe_id']}: {error}")
    return errors


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay frozen Data V3 winning build recipes in writable handoff "
            "workspaces. No GPT/EvoSuite/JaCoCo/PIT tools are involved."
        )
    )
    default_config = Path(__file__).resolve().parents[1] / "handoff_config.json"
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config,
        help="Path to handoff_config.json",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify bundle, toolchain, commits, wrappers, and commands without copying or building",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Replay all 48 final winning recipes",
    )
    parser.add_argument(
        "--repo-id",
        action="append",
        default=[],
        help="Replay every final recipe for this repository ID (repeatable)",
    )
    parser.add_argument(
        "--recipe-id",
        action="append",
        default=[],
        help="Replay one exact recipe ID (repeatable)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip prior PASS rows with the same command hash and environment fingerprint",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="Maximum repositories built concurrently (default from config, normally 1)",
    )
    parser.add_argument(
        "--full-checksums",
        action="store_true",
        help="Rehash the complete Step 003 build-evidence inventory before replay",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    if not args.check_only and not (args.all or args.repo_id or args.recipe_id):
        parser.error("Choose --all, --repo-id, --recipe-id, or --check-only")
    try:
        context = load_context(args.config)
        verification = verify_bundle(context, full_checksums=args.full_checksums)
        if verification["status"] != "PASS":
            for error in verification["errors"]:
                log(f"BUNDLE ERROR: {error}")
            raise ReplayError("Frozen bundle verification failed")

        environment = collect_environment(context)
        if environment["errors"]:
            for error in environment["errors"]:
                log(f"ENVIRONMENT ERROR: {error}")
            raise ReplayError("Build toolchain preflight failed")
        log(
            "Environment PASS: "
            f"fingerprint={environment['fingerprint'][:12]}, "
            f"Java={environment['tools']['java']['output'].splitlines()[0]}, "
            f"Maven={environment['tools']['maven']['output'].splitlines()[0]}"
        )

        repositories = read_csv(context.repository_manifest)
        manifest_by_repo = {row["repo_id"]: row for row in repositories}
        recipes = read_csv(context.portable_recipes)
        selected = _select_recipes(
            recipes,
            all_recipes=args.all,
            repo_ids=args.repo_id,
            recipe_ids=args.recipe_id,
            check_only=args.check_only,
        )
        source_errors = _check_recipe_sources(context, selected, manifest_by_repo)
        if source_errors:
            for error in source_errors:
                log(f"RECIPE ERROR: {error}")
            raise ReplayError("Recipe source validation failed")
        log(
            f"Recipe selection PASS: {len(selected)} recipes across "
            f"{len({row['repo_id'] for row in selected})} repositories"
        )
        if args.check_only:
            log("CHECK-ONLY PASS: no repositories copied and no builds executed")
            return 0

        jobs = (
            args.jobs
            if args.jobs is not None
            else int(context.config.get("default_jobs", 1))
        )
        if jobs < 1:
            raise ReplayError("--jobs must be at least 1")
        context.result_root.mkdir(parents=True, exist_ok=True)
        environment_path = context.result_root / "environment.json"
        environment_path.write_text(
            json.dumps(environment, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary_path = context.result_root / "build_replay_summary.csv"
        resume_passes = (
            _read_resume_passes(summary_path, environment["fingerprint"])
            if args.resume
            else set()
        )

        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        skipped = 0
        for recipe in selected:
            key = (recipe["recipe_id"], recipe.get("original_command_sha256", ""))
            if key in resume_passes:
                skipped += 1
                log(f"{recipe['recipe_id']}: SKIP prior PASS under same environment")
                continue
            grouped[recipe["repo_id"]].append(recipe)

        results: list[dict[str, Any]] = []

        def run_repository(repo_id: str) -> list[dict[str, Any]]:
            manifest = manifest_by_repo[repo_id]
            workspace = prepare_workspace(context, manifest, reuse_existing=args.resume)
            repository_results = []
            for recipe in grouped[repo_id]:
                repository_results.append(
                    run_one_recipe(
                        context,
                        manifest,
                        recipe,
                        workspace,
                        environment["fingerprint"],
                        summary_path,
                    )
                )
            return repository_results

        if grouped:
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                futures = {
                    executor.submit(run_repository, repo_id): repo_id
                    for repo_id in sorted(grouped, key=int)
                }
                for future in concurrent.futures.as_completed(futures):
                    repo_id = futures[future]
                    try:
                        results.extend(future.result())
                    except Exception as error:
                        log(f"Repo {repo_id}: workspace/runner failure: {error}")
                        for recipe in grouped[repo_id]:
                            fallback = {
                                "recipe_id": recipe["recipe_id"],
                                "repo_id": repo_id,
                                "commit_sha": manifest_by_repo[repo_id]["commit_sha"],
                                "scope_key": recipe.get("scope_key", ""),
                                "recipe": recipe.get("recipe", ""),
                                "command_source": recipe.get("command_source", ""),
                                "command_platform": "",
                                "original_command_sha256": recipe.get(
                                    "original_command_sha256", ""
                                ),
                                "resolved_command": "",
                                "workspace": "",
                                "build_working_directory": "",
                                "started_at": utc_now(),
                                "finished_at": utc_now(),
                                "duration_seconds": 0,
                                "exit_code": 1,
                                "status": "FAIL",
                                "failure_category": "workspace_prepare_failed",
                                "tracked_changes": "",
                                "stdout_log_path": "",
                                "stderr_log_path": "",
                                "environment_fingerprint": environment["fingerprint"],
                            }
                            append_summary(summary_path, fallback)
                            results.append(fallback)

        passed = sum(row["status"] == "PASS" for row in results)
        failed = sum(row["status"] != "PASS" for row in results)
        log(
            f"REPLAY COMPLETE: passed={passed}, failed={failed}, skipped={skipped}, "
            f"summary={summary_path}"
        )
        return 0 if failed == 0 and passed + skipped == len(selected) else 1
    except (ReplayError, VerificationError) as error:
        log(f"STOP: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
