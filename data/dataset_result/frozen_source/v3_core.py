#!/usr/bin/env python3
"""Shared implementation for the CLASSES2TEST V3 data pipeline.

The module deliberately separates metadata reconstruction from repository
build screening.  Sampling is repository-balanced and hash-ranked; class
complexity is measured only for eligibility reporting and post-selection
relative halves.  Repository source and build files are never edited.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence


PIPELINE_VERSION = "3.1.0-pre-experiment"
SELECTION_ALGORITHM = "sha256_repo_balanced_v3_1"
COMPLEXITY_ALGORITHM = "relative_halves_maxcc_sumcc_v1"
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
STEP003_CLEANUP_AMENDMENT_ID = "windows_generated_tree_cleanup_and_promotion_v2"
STEP003_CLEANUP_AMENDMENT_FROM_HASH = "c318a5fb2d9b824e59c89f79cb58a59060c227886da10235070df9b9f0c98c67"
STEP003_RESTART_CONFIRMATION = "RESET_STEP003"


class PipelineError(RuntimeError):
    """Controlled failure that should stop a pipeline step."""


class CleanupError(PipelineError):
    """Generated repository cleanup failed; stop without reclassifying the repository."""


class PromotionError(PipelineError):
    """A qualified repository could not be promoted; stop without rejecting it."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def natural_key(value: Any) -> tuple[int, str]:
    text = str(value)
    return (int(text), text) if text.isdigit() else (2**63 - 1, text.casefold())


def normalize_relative_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts:
        return ""
    return path.as_posix()


def make_class_key(repo_id: Any, focal_path: Any) -> str:
    normalized = normalize_relative_path(focal_path)
    if not normalized:
        raise ValueError("invalid repository-relative focal path")
    return f"{str(repo_id)}:{normalized.casefold()}"


def stable_hash(namespace: str, seed: int, value: str) -> str:
    return hashlib.sha256(f"{namespace}|{seed}|{value}".encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=path.parent,
        prefix=path.name + ".", suffix=".tmp"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def atomic_write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent,
        prefix=path.name + ".", suffix=".tmp"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})
        temporary = Path(handle.name)
    os.replace(temporary, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    atomic_write_text(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def truthy(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes"}


def load_config(config_path: Path | str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as error:
        raise PipelineError(
            "PyYAML is required. Install research_pipeline_v3/requirements-v3.txt first."
        ) from error
    path = Path(config_path).resolve()
    if not path.is_file():
        raise PipelineError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    validate_config(config)
    config["_config_path"] = str(path)
    return config


def validate_config(config: dict[str, Any]) -> None:
    protocol = config.get("protocol", {})
    expected = {
        "seed": 42,
        "target_repositories": 30,
        "minimum_unique_classes_per_repo": 12,
        "main_classes_per_repo": 10,
        "backup_classes_per_repo": 2,
    }
    for key, value in expected.items():
        if int(protocol.get(key, -1)) != value:
            raise PipelineError(f"Scientific protocol requires protocol.{key}={value}")
    eligibility = config.get("eligibility", {})
    if bool(eligibility.get("complexity_gate_enabled", True)):
        raise PipelineError("V3 forbids cyclomatic complexity as an eligibility/sampling gate")
    java = config.get("java", {})
    if int(java.get("effective_runtime", -1)) != 8:
        raise PipelineError("Every accepted Java <=8 or unknown repository must be tested on JDK 8")
    if not bool(java.get("run_all_accepted_versions_on_jdk8", False)):
        raise PipelineError("java.run_all_accepted_versions_on_jdk8 must remain true")
    build = config.get("build", {})
    for forbidden in ("allow_ai_recipe_suggestion", "allow_source_code_modification", "allow_dependency_modification"):
        if bool(build.get(forbidden, False)):
            raise PipelineError(f"Scientific-integrity guard requires build.{forbidden}=false")
    for key in ("maven_settings_file", "gradle_init_script"):
        value = build.get(key)
        if value and not Path(str(value)).resolve().is_file():
            raise PipelineError(f"Pre-registered build fallback is missing: build.{key}={value}")


def config_path(config: dict[str, Any], name: str) -> Path:
    raw = config.get("paths", {}).get(name)
    if not raw:
        raise PipelineError(f"Missing paths.{name} in config")
    return Path(str(raw)).resolve()


def dataset_directory(config: dict[str, Any]) -> Path:
    root = config_path(config, "dataset_root")
    return root / "dataset" if (root / "dataset").is_dir() else root


def output_directory(config: dict[str, Any]) -> Path:
    return config_path(config, "output_root")


def qualified_repository_storage_path(
    output: Path, row: dict[str, Any], require_exists: bool = True,
) -> Path:
    """Resolve only the two protocol-approved storage locations for a qualified repo."""
    repo_id = str(row.get("repo_id", "")).strip()
    if not repo_id or normalize_relative_path(repo_id) != repo_id or "/" in repo_id or "\\" in repo_id:
        raise PipelineError(f"Invalid repository identity in storage record: {repo_id!r}")
    raw = str(row.get("repository_storage_path") or f"repos/successful/{repo_id}")
    relative = normalize_relative_path(raw)
    allowed = {
        f"repos/successful/{repo_id}".casefold(),
        f"repos/working/{repo_id}".casefold(),
    }
    if not relative or relative.casefold() not in allowed:
        raise PipelineError(f"Unapproved qualified repository storage path for {repo_id}: {raw}")
    resolved = (output / relative).resolve()
    storage_root = (output / "/".join(relative.split("/")[:2])).resolve()
    if storage_root not in resolved.parents:
        raise PipelineError(f"Qualified repository storage escapes its owned root: {resolved}")
    if require_exists and not resolved.is_dir():
        raise PipelineError(f"Qualified repository storage is missing for {repo_id}: {resolved}")
    return resolved


def create_layout(output: Path) -> None:
    for relative in (
        "logs", "logs/build", "logs/clone", "logs/submodules", "repos/working",
        "repos/successful", "repos/failed", "results", "state", "state/repo_metrics",
        "state/config_snapshots",
    ):
        (output / relative).mkdir(parents=True, exist_ok=True)


def script_inventory() -> list[dict[str, Any]]:
    paths = [
        SCRIPT_DIRECTORY / "config_v3.yaml", SCRIPT_DIRECTORY / "requirements-v3.txt",
        SCRIPT_DIRECTORY / "maven-settings-v3.xml", SCRIPT_DIRECTORY / "gradle-init-v3.gradle",
    ]
    paths.extend(sorted(SCRIPT_DIRECTORY.glob("*.py"), key=lambda item: item.name.casefold()))
    return [
        {"path": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in paths if path.is_file()
    ]


def source_inventory_hash() -> str:
    canonical = json.dumps(script_inventory(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def current_config_hash(config: dict[str, Any]) -> str:
    return sha256_file(Path(config["_config_path"]))


def done_path(config: dict[str, Any], step: str) -> Path:
    return output_directory(config) / "state" / f"{step}.done.json"


def verify_previous_step(
    config: dict[str, Any], step: str, mutable_outputs: set[str] | None = None,
    source_amendment_reason: str | None = None,
    source_amendment_from_hash: str | None = None,
) -> dict[str, Any]:
    path = done_path(config, step)
    if not path.is_file():
        raise PipelineError(f"Required prior marker missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("config_sha256") != current_config_hash(config):
        raise PipelineError(
            f"Config changed after {step}. Preserve the old run or formally restart V3 with a new output directory."
        )
    expected_source_hash = payload.get("source_inventory_sha256")
    observed_source_hash = source_inventory_hash()
    if expected_source_hash != observed_source_hash:
        if not source_amendment_reason or expected_source_hash != source_amendment_from_hash:
            raise PipelineError(
                f"Pipeline source changed after {step}. Preserve the old run or formally restart with a new output directory."
            )
        payload["_source_amendment"] = {
            "prior_step": step,
            "prior_source_inventory_sha256": expected_source_hash,
            "amended_source_inventory_sha256": observed_source_hash,
            "reason": source_amendment_reason,
            "amended_script_inventory": script_inventory(),
        }
    mutable_outputs = mutable_outputs or set()
    for item in payload.get("outputs", []):
        if item["path"] in mutable_outputs:
            continue
        artifact = output_directory(config) / item["path"]
        if not artifact.is_file() or sha256_file(artifact) != item["sha256"]:
            raise PipelineError(f"Artifact drift detected after {step}: {artifact}")
    return payload


def mark_done(config: dict[str, Any], step: str, outputs: Sequence[Path], details: dict[str, Any]) -> None:
    root = output_directory(config)
    output_rows = []
    for path in outputs:
        resolved = path.resolve()
        output_rows.append({
            "path": resolved.relative_to(root.resolve()).as_posix(),
            "size": resolved.stat().st_size,
            "sha256": sha256_file(resolved),
        })
    config_hash = current_config_hash(config)
    snapshot = root / "state" / "config_snapshots" / f"{step}_{config_hash[:12]}.yaml"
    if not snapshot.exists():
        shutil.copy2(Path(config["_config_path"]), snapshot)
    payload = {
        "step": step,
        "completed_at": utc_now(),
        "pipeline_version": PIPELINE_VERSION,
        "config_sha256": config_hash,
        "source_inventory_sha256": source_inventory_hash(),
        "outputs": output_rows,
        "details": details,
    }
    atomic_write_json(done_path(config, step), payload)


@contextlib.contextmanager
def pipeline_lock(config: dict[str, Any], step: str) -> Iterator[None]:
    output = output_directory(config)
    create_layout(output)
    lock = output / "state" / "pipeline.lock"
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise PipelineError(f"Pipeline lock exists: {lock}. Verify that no other process is running.") from error
    try:
        os.write(descriptor, json.dumps({"step": step, "pid": os.getpid(), "started_at": utc_now()}).encode("utf-8"))
        os.close(descriptor)
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


class StepLogger:
    def __init__(self, output: Path, step: str) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = output / "logs" / f"{step}_{stamp}.log"

    def log(self, message: str) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
        print(line, flush=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")


def load_environment_file(path: Path) -> dict[str, str]:
    allowed = {"JAVA_HOME", "MAVEN_OPTS", "GRADLE_OPTS", "PATH"}
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key in allowed:
            values[key] = value.strip().strip('"').strip("'")
    return values


def jdk8_environment(config: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    env_path = config.get("paths", {}).get("java_env_file")
    if env_path:
        env.update(load_environment_file(Path(str(env_path)).resolve()))
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["CI"] = "true"
    for key in ("_JAVA_OPTIONS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS"):
        env.pop(key, None)
    java_home = env.get("JAVA_HOME", "")
    if java_home and Path(java_home).is_dir():
        env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", "")
    env.setdefault("MAVEN_OPTS", "-Xmx4g -Dfile.encoding=UTF-8")
    env.setdefault("GRADLE_OPTS", "-Xmx4g -Dfile.encoding=UTF-8")
    return env


def run_process(
    args: Sequence[str], cwd: Path | None, env: dict[str, str], timeout: int
) -> tuple[int, str, str, float]:
    command = [str(value) for value in args]
    if command and not Path(command[0]).is_absolute():
        resolved = shutil.which(command[0], path=env.get("PATH"))
        if resolved:
            command[0] = resolved
    if os.name == "nt" and command and command[0].casefold().endswith((".cmd", ".bat")):
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "call", *command]
    started = time.time()
    try:
        result = subprocess.run(
            command, cwd=str(cwd) if cwd else None, env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=False,
        )
        return result.returncode, result.stdout, result.stderr, time.time() - started
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        stderr = error.stderr if isinstance(error.stderr, str) else ""
        return 124, stdout, stderr + f"\nTIMEOUT_AFTER_{timeout}_SECONDS", time.time() - started
    except OSError as error:
        return 127, "", f"{type(error).__name__}: {error}", time.time() - started


def java_major(text: str) -> int | None:
    # Parse only explicitly labelled Java/JVM versions.  A generic semantic-
    # version fallback is unsafe here because `mvn -version` prints Maven's
    # own version before its `Java version: ...` line.
    patterns = (
        r'\bjava\s+version\s*:?\s*"?(?:1\.)?(\d+)',
        r'\bopenjdk\s+version\s*:?\s*"?(?:1\.)?(\d+)',
        r'\bjavac(?:\s+version)?\s*:?\s*"?(?:1\.)?(\d+)',
        r'\bjvm\s*:\s*"?(?:1\.)?(\d+)',
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def preflight_and_backup(config_path_value: Path | str, skip_backup: bool = False) -> dict[str, Any]:
    config = load_config(config_path_value)
    output = output_directory(config)
    with pipeline_lock(config, "step000"):
        logger = StepLogger(output, "step000")
        env = jdk8_environment(config)
        versions: dict[str, dict[str, Any]] = {}
        for name, command in {
            "java": ["java", "-version"], "javac": ["javac", "-version"],
            "maven": ["mvn", "-version"], "gradle": ["gradle", "-version"],
            "git": ["git", "--version"],
        }.items():
            code, stdout, stderr, duration = run_process(command, SCRIPT_DIRECTORY, env, 60)
            combined = (stdout + "\n" + stderr).strip()
            versions[name] = {"exit_code": code, "output": combined, "duration_seconds": duration}
            logger.log(f"{name}: exit={code}")
        if versions["git"]["exit_code"] != 0:
            raise PipelineError("git is required")
        for name in ("java", "javac"):
            if versions[name]["exit_code"] != 0 or java_major(versions[name]["output"]) != 8:
                raise PipelineError(f"{name} must resolve to JDK 8")
        if versions["maven"]["exit_code"] != 0 and versions["gradle"]["exit_code"] != 0:
            raise PipelineError("At least Maven or Gradle must be available globally")
        if versions["maven"]["exit_code"] == 0 and java_major(versions["maven"]["output"]) != 8:
            raise PipelineError("mvn -version must report Java 8")

        environment_file = output / "results" / "environment_versions.json"
        environment = {
            "captured_at": utc_now(), "platform": platform.platform(),
            "python": sys.version, "python_executable": sys.executable, "tools": versions,
            "scripts": script_inventory(),
        }
        atomic_write_json(environment_file, environment)
        backup_root: Path | None = None
        backup_manifest_hash = ""
        if not skip_backup:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_root = config_path(config, "backup_parent") / f"data_v2_backup_pre_v3_{stamp}"
            if backup_root.exists():
                raise PipelineError(f"Backup destination already exists: {backup_root}")
            backup_root.mkdir(parents=True)
            manifest_rows: list[dict[str, Any]] = []
            sources = ("v2_data", "v2_pipeline", "proposal", "context", "status", "history_guide")
            for name in sources:
                source = config_path(config, name)
                destination = backup_root / name
                logger.log(f"Backing up {source} -> {destination}")
                if source.is_dir():
                    shutil.copytree(source, destination, copy_function=shutil.copy2)
                    files = sorted((item for item in destination.rglob("*") if item.is_file()), key=lambda p: p.as_posix())
                elif source.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    files = [destination]
                else:
                    raise PipelineError(f"Backup source missing: {source}")
                for file_path in files:
                    manifest_rows.append({
                        "source_group": name,
                        "relative_path": file_path.relative_to(backup_root).as_posix(),
                        "size": file_path.stat().st_size,
                        "modified_ns": file_path.stat().st_mtime_ns,
                        "sha256": sha256_file(file_path),
                    })
            backup_manifest = backup_root / "backup_manifest.csv"
            atomic_write_csv(backup_manifest, manifest_rows, ["source_group", "relative_path", "size", "modified_ns", "sha256"])
            backup_log = backup_root / "backup_log.json"
            atomic_write_json(backup_log, {
                "created_at": utc_now(), "files": len(manifest_rows),
                "bytes": sum(int(row["size"]) for row in manifest_rows), "status": "complete",
            })
            backup_manifest_hash = sha256_file(backup_manifest)
        details = {
            "backup_skipped": skip_backup, "backup_root": str(backup_root or ""),
            "backup_manifest_sha256": backup_manifest_hash, "effective_java": 8,
        }
        mark_done(config, "step000", [environment_file], details)
        logger.log("Step 000 PASS")
        return details


RAW_FIELDS = [
    "repo_id", "repo_url", "dataset_commit_sha", "json_file", "parse_status", "error",
    "class_key", "focal_class", "focal_path", "test_class", "test_path", "focal_method", "test_case",
    "declared_java_hint", "maven_version_hint", "gradle_version_hint",
]
UNIQUE_FIELDS = [
    "repo_id", "repo_url", "dataset_commit_sha", "class_key", "focal_class", "focal_path",
    "mapping_count", "source_json_files", "focal_methods", "test_cases", "test_classes", "test_paths",
    "public_method_count_metadata", "declared_java_hints", "maven_version_hints", "gradle_version_hints",
]


def reconstruct_unique_frame(config_path_value: Path | str) -> dict[str, Any]:
    config = load_config(config_path_value)
    verify_previous_step(config, "step000")
    output = output_directory(config)
    with pipeline_lock(config, "step001"):
        logger = StepLogger(output, "step001")
        dataset = dataset_directory(config)
        repo_dirs = sorted((path for path in dataset.iterdir() if path.is_dir() and path.name != ".git"), key=lambda p: natural_key(p.name))
        limit = config.get("execution", {}).get("repository_limit")
        if limit is not None:
            repo_dirs = repo_dirs[: int(limit)]
        workers = int(config.get("execution", {}).get("metadata_workers", 16))
        logger.log(f"Enumerating {len(repo_dirs)} repository metadata directories")

        def json_paths(directory: Path) -> list[Path]:
            return sorted(directory.glob("*.json"), key=lambda item: item.name.casefold())

        with ThreadPoolExecutor(max_workers=workers) as executor:
            repo_files = list(executor.map(json_paths, repo_dirs))

        raw_rows: list[dict[str, Any]] = []
        groups: dict[str, dict[str, Any]] = {}
        dataset_digest = hashlib.sha256()
        parse_errors = 0
        for repo_dir, paths in zip(repo_dirs, repo_files):
            for path in paths:
                raw: dict[str, Any] = {"repo_id": repo_dir.name, "json_file": path.name, "parse_status": "error", "error": ""}
                try:
                    content = path.read_bytes()
                    dataset_digest.update(repo_dir.name.encode() + b"\0" + path.name.encode() + b"\0" + content)
                    data = json.loads(content.decode("utf-8-sig"))
                    repository = data.get("repository") or {}
                    focal = data.get("focal_class") or {}
                    test = data.get("test_class") or {}
                    focal_method = data.get("focal_method") or {}
                    test_case = data.get("test_case") or {}
                    repo_id = str(repository.get("repo_id") or repo_dir.name)
                    focal_path = normalize_relative_path(focal.get("file"))
                    focal_class = str(focal.get("identifier") or "").strip()
                    if not focal_path or not focal_class:
                        raise ValueError("missing focal_class.identifier or focal_class.file")
                    key = make_class_key(repo_id, focal_path)
                    raw.update({
                        "repo_id": repo_id, "repo_url": str(repository.get("url") or "").strip(),
                        "dataset_commit_sha": str(repository.get("commit_sha") or repository.get("commit") or "").strip(),
                        "parse_status": "ok", "class_key": key, "focal_class": focal_class,
                        "focal_path": focal_path, "test_class": str(test.get("identifier") or ""),
                        "test_path": normalize_relative_path(test.get("file")),
                        "focal_method": focal_method.get("class_method_signature") or focal_method.get("full_signature") or focal_method.get("signature") or "",
                        "test_case": test_case.get("class_method_signature") or test_case.get("full_signature") or test_case.get("signature") or "",
                        "declared_java_hint": repository.get("java_version", ""),
                        "maven_version_hint": repository.get("maven_version", ""),
                        "gradle_version_hint": repository.get("gradle_version", ""),
                    })
                    group = groups.setdefault(key, {
                        "repo_id": repo_id, "repo_url": raw["repo_url"], "dataset_commit_sha": raw["dataset_commit_sha"],
                        "class_key": key, "focal_class": focal_class, "focal_path": focal_path,
                        "source_json_files": set(), "focal_methods": set(), "test_cases": set(),
                        "test_classes": set(), "test_paths": set(), "declared_java_hints": set(),
                        "maven_version_hints": set(), "gradle_version_hints": set(), "public_method_count_metadata": 0,
                    })
                    for field in ("repo_url", "dataset_commit_sha"):
                        if raw[field] and not group[field]:
                            group[field] = raw[field]
                    group["source_json_files"].add(path.name)
                    for target, value in (
                        ("focal_methods", raw["focal_method"]), ("test_cases", raw["test_case"]),
                        ("test_classes", raw["test_class"]), ("test_paths", raw["test_path"]),
                        ("declared_java_hints", raw["declared_java_hint"]),
                        ("maven_version_hints", raw["maven_version_hint"]),
                        ("gradle_version_hints", raw["gradle_version_hint"]),
                    ):
                        if value not in (None, ""):
                            group[target].add(str(value))
                    public_count = 0
                    for method in focal.get("methods") or []:
                        modifiers = str(method.get("modifiers") or method.get("modifier") or "")
                        if re.search(r"\bpublic\b", modifiers) and not bool(method.get("constructor")):
                            public_count += 1
                    group["public_method_count_metadata"] = max(group["public_method_count_metadata"], public_count)
                except Exception as error:
                    parse_errors += 1
                    raw["error"] = f"{type(error).__name__}: {error}"[:1000]
                raw_rows.append(raw)

        unique_rows: list[dict[str, Any]] = []
        repo_counts: Counter[str] = Counter()
        set_fields = (
            "source_json_files", "focal_methods", "test_cases", "test_classes", "test_paths",
            "declared_java_hints", "maven_version_hints", "gradle_version_hints",
        )
        for key in sorted(groups, key=lambda item: (natural_key(groups[item]["repo_id"]), item)):
            group = dict(groups[key])
            group["mapping_count"] = len(group["source_json_files"])
            for field in set_fields:
                group[field] = ";".join(sorted(group[field], key=str.casefold))
            unique_rows.append(group)
            repo_counts[group["repo_id"]] += 1

        repo_metadata: dict[str, dict[str, str]] = {}
        for row in unique_rows:
            repo_metadata.setdefault(row["repo_id"], row)
        minimum = int(config["protocol"]["minimum_unique_classes_per_repo"])
        summary_rows = [
            {
                "repo_id": repo_id,
                "repo_url": repo_metadata[repo_id].get("repo_url", ""),
                "dataset_commit_sha": repo_metadata[repo_id].get("dataset_commit_sha", ""),
                "unique_mapped_focal_count": count,
                "metadata_prefilter_pass": count >= minimum,
                "minimum_required": minimum,
                "java_filter_applied": False,
            }
            for repo_id, count in sorted(repo_counts.items(), key=lambda item: natural_key(item[0]))
        ]
        raw_file = output / "raw_mapping_index.csv"
        frame_file = output / "unique_focal_class_frame.csv"
        summary_file = output / "repo_candidate_summary.csv"
        atomic_write_csv(raw_file, raw_rows, RAW_FIELDS)
        atomic_write_csv(frame_file, unique_rows, UNIQUE_FIELDS)
        atomic_write_csv(summary_file, summary_rows, [
            "repo_id", "repo_url", "dataset_commit_sha", "unique_mapped_focal_count",
            "metadata_prefilter_pass", "minimum_required", "java_filter_applied",
        ])
        details = {
            "repositories_scanned": len(repo_dirs), "mapping_json_files": len(raw_rows),
            "parse_errors": parse_errors, "unique_focal_classes": len(unique_rows),
            "candidate_repositories": sum(1 for row in summary_rows if row["metadata_prefilter_pass"]),
            "dataset_content_sha256": dataset_digest.hexdigest(),
            "bias_guard": "No Java, complexity, class-name, or outcome filter was applied in Step 001",
        }
        mark_done(config, "step001", [raw_file, frame_file, summary_file], details)
        logger.log(f"Step 001 PASS: {len(raw_rows)} mappings -> {len(unique_rows)} unique classes")
        return details


QUEUE_FIELDS = [
    "order_index", "repo_id", "repo_url", "dataset_commit_sha", "unique_mapped_focal_count",
    "repo_order_hash", "status", "failure_category", "failure_detail", "clone_status",
    "commit_sha", "declared_java_versions", "effective_java_runtime", "qualified_build_scopes",
    "unique_eligible_buildable_count", "selected_for_sample", "repository_storage_path",
    "promotion_status", "promotion_detail", "updated_at",
]


def create_repository_queue(config_path_value: Path | str) -> dict[str, Any]:
    config = load_config(config_path_value)
    verify_previous_step(config, "step001")
    output = output_directory(config)
    with pipeline_lock(config, "step002"):
        logger = StepLogger(output, "step002")
        summary = read_csv(output / "repo_candidate_summary.csv")
        seed = int(config["protocol"]["seed"])
        candidates = [row for row in summary if truthy(row["metadata_prefilter_pass"])]
        for row in candidates:
            row["repo_order_hash"] = stable_hash("v3-repo-order", seed, row["repo_id"])
        candidates.sort(key=lambda row: (row["repo_order_hash"], natural_key(row["repo_id"])))
        queue = []
        for index, row in enumerate(candidates):
            queue.append({
                "order_index": index, "repo_id": row["repo_id"], "repo_url": row["repo_url"],
                "dataset_commit_sha": row.get("dataset_commit_sha", ""),
                "unique_mapped_focal_count": row["unique_mapped_focal_count"],
                "repo_order_hash": row["repo_order_hash"], "status": "pending",
                "failure_category": "", "failure_detail": "", "clone_status": "pending",
                "commit_sha": "", "declared_java_versions": "", "effective_java_runtime": 8,
                "qualified_build_scopes": "", "unique_eligible_buildable_count": 0,
                "selected_for_sample": False, "repository_storage_path": "",
                "promotion_status": "", "promotion_detail": "", "updated_at": utc_now(),
            })
        queue_file = output / "repo_processing_order_seed42.csv"
        queue_snapshot = output / "state" / "repo_processing_order_seed42.initial.csv"
        atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
        atomic_write_csv(queue_snapshot, queue, QUEUE_FIELDS)
        details = {"queued_repositories": len(queue), "seed": seed, "algorithm": "sha256-v3-repo-order"}
        mark_done(config, "step002", [queue_file, queue_snapshot], details)
        logger.log(f"Step 002 PASS: queued {len(queue)} candidate repositories")
        return details


FAILURE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("obsolete_repository_unavailable", (r"repository not found", r"remote: not found", r"does not exist")),
    ("auth_required", (r"authentication failed", r"permission denied", r"status code 401", r"status code 403")),
    ("network_dns", (r"unknownhostexception", r"could not resolve host", r"name or service not known")),
    ("network_tls", (r"pkix path building failed", r"sslhandshakeexception", r"certificate.*failed")),
    ("insecure_http_repository_blocked", (r"maven-default-http-blocker", r"blocked mirror for repositories")),
    ("wrapper_download_failed", (r"could not download.*(?:maven|gradle)", r"gradle-wrapper.*failed", r"mavenwrapperdownloader")),
    ("missing_git_submodule", (r"no url found for submodule", r"not initialized.*submodule", r"child module.*does not exist")),
    ("requires_java_above_8", (r"invalid (?:target|source) release:\s*(?:9|1[0-9]|2[0-9])", r"requires java (?:9|1[0-9]|2[0-9])", r"release version (?:9|1[0-9]|2[0-9]) not supported")),
    ("jdk_version_range_mismatch", (r"requirejavaversion failed", r"detected jdk.*not in the allowed range", r"maven-enforcer-plugin.*java")),
    ("jvm_argument_incompatible", (r"unrecognized option: --add-(?:exports|opens)", r"unrecognized vm option", r"could not create the java virtual machine")),
    ("build_tool_version_incompatible", (r"minimum supported gradle version", r"could not determine java version from '1\.8", r"plugin with id 'maven' not found", r"could not generate a decorated class")),
    ("android_sdk_required", (r"android sdk", r"sdk location not found", r"com\.android\.(?:application|library)")),
    ("frontend_required", (r"frontend-maven-plugin", r"npm err!", r"yarn.*failed", r"node.*not found")),
    ("docker_required", (r"docker.*(?:not found|unavailable|failed)", r"could not connect to docker")),
    ("checkstyle_failed", (r"maven-checkstyle-plugin.*failure", r"checkstyle.*(?:failed|violation)")),
    ("license_failed", (r"license-maven-plugin.*failure", r"license.*(?:header|check).*(?:failed|missing)")),
    ("module_not_found", (r"could not find the selected project in the reactor", r"project .* not found in root project", r"task .* not found")),
    ("parent_pom_unavailable", (r"non-resolvable parent pom", r"parent\.relativepath.*wrong local pom")),
    ("plugin_resolution_failed", (r"plugin .* could not be resolved", r"pluginresolutionexception")),
    ("dependency_resolution_failed", (r"could not resolve dependencies", r"could not find artifact", r"could not resolve all files")),
    ("test_compile_failed", (r"failed to compile test", r"test compilation failure", r":compiletestjava failed")),
    ("source_compile_failed", (r"compilation failure", r"compilation error", r":compilejava failed", r"cannot find symbol")),
    ("out_of_memory", (r"outofmemoryerror", r"java heap space", r"gc overhead limit exceeded")),
    ("timeout", (r"timeout_after_\d+_seconds",)),
)


def classify_failure(text: str) -> str:
    normalized = text.casefold()
    for category, patterns in FAILURE_PATTERNS:
        if any(re.search(pattern, normalized, re.IGNORECASE | re.DOTALL) for pattern in patterns):
            return category
    return "unknown_build_failure"


TRANSIENT_FAILURES = {"network_dns", "network_tls", "wrapper_download_failed", "timeout", "out_of_memory"}


def parse_java_number(raw: Any) -> int | None:
    match = re.search(r"(?<!\d)(?:1\.)?(\d{1,2})(?!\d)", str(raw).strip())
    if not match:
        return None
    value = int(match.group(1))
    return value if 5 <= value <= 30 else None


def declared_java_allowed(version: int | None, config: dict[str, Any]) -> bool:
    """Metadata admission rule; an actual JDK 8 build remains authoritative."""
    java = config["java"]
    if version is None:
        return bool(java.get("try_unknown_version_on_jdk8", True))
    accepted = {int(value) for value in java.get("accepted_declared_versions", [5, 6, 7, 8])}
    return version in accepted and version <= int(java["maximum_declared_version"])


def read_text_lossy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_declared_java(build_files: Sequence[Path]) -> tuple[int | None, str, list[int]]:
    """Return the highest declared Java level; never decides buildability itself."""
    values: list[tuple[int, str]] = []
    for path in build_files:
        text = read_text_lossy(path)
        if path.name == "pom.xml":
            properties: dict[str, str] = {}
            try:
                root = ET.fromstring(text)
                for element in root.iter():
                    name = element.tag.rsplit("}", 1)[-1]
                    if element.text and name not in properties:
                        properties[name] = element.text.strip()
            except ET.ParseError:
                pass
            for tag in (
                "maven.compiler.release", "maven.compiler.source", "maven.compiler.target",
                "java.version", "jdk.version", "source", "target", "release",
            ):
                for raw in re.findall(rf"<{re.escape(tag)}>\s*([^<]+)\s*</{re.escape(tag)}>", text, re.IGNORECASE):
                    property_match = re.fullmatch(r"\$\{([^}]+)\}", raw.strip())
                    if property_match:
                        raw = properties.get(property_match.group(1), raw)
                    parsed = parse_java_number(raw)
                    if parsed:
                        values.append((parsed, path.as_posix()))
            for block in re.findall(r"<requireJavaVersion\b.*?</requireJavaVersion>", text, re.IGNORECASE | re.DOTALL):
                match = re.search(r"<version>\s*[\[(]?\s*((?:1\.)?\d{1,2})", block)
                if match and (parsed := parse_java_number(match.group(1))):
                    values.append((parsed, path.as_posix() + "#maven-enforcer"))
        else:
            patterns = (
                r"(?:sourceCompatibility|targetCompatibility)\s*=\s*(?:JavaVersion\.VERSION_)?['\"]?([0-9_.]+)",
                r"JavaLanguageVersion\.of\((\d+)\)", r"jvmToolchain\((\d+)\)",
                r"languageVersion\.set\(JavaLanguageVersion\.of\((\d+)\)\)",
            )
            for pattern in patterns:
                for raw in re.findall(pattern, text, re.IGNORECASE):
                    parsed = parse_java_number(str(raw).replace("VERSION_", "").replace("_", "."))
                    if parsed:
                        values.append((parsed, path.as_posix()))
    if not values:
        return None, "unknown", []
    highest = max(values, key=lambda item: item[0])
    return highest[0], highest[1], sorted({value for value, _ in values})


def strip_java_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def analyze_java_file(path: Path, frame_row: dict[str, str], config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "repo_id": frame_row["repo_id"], "repo_url": frame_row.get("repo_url", ""),
        "class_key": frame_row["class_key"], "focal_class": frame_row["focal_class"],
        "focal_path": frame_row["focal_path"], "mapping_count": int(frame_row.get("mapping_count") or 0),
        "source_json_files": frame_row.get("source_json_files", ""), "exact_path_exists": path.is_file(),
        "metric_status": "error", "eligible_for_sampling": False, "exclusion_reason": "",
        "build_scope_pass": False,
    }
    if not path.is_file():
        result["exclusion_reason"] = "exact_focal_path_not_found"
        return result
    try:
        import lizard  # type: ignore
    except ImportError as error:
        raise PipelineError("lizard is required for Step 003; install requirements-v3.txt") from error
    try:
        analysis = lizard.analyze_file(str(path))
        text = read_text_lossy(path)
        clean = strip_java_comments(text)
        name = str(frame_row["focal_class"]).split(".")[-1]
        functions = list(analysis.function_list)
        cc_values = [int(function.cyclomatic_complexity) for function in functions]
        public_regex = re.findall(
            r"\bpublic\s+(?:(?:static|final|synchronized|native|abstract|default)\s+)*"
            r"[\w<>,.?@\[\]\s]+\s+([A-Za-z_$][\w$]*)\s*\(", clean,
        )
        metadata_public = int(frame_row.get("public_method_count_metadata") or 0)
        eligibility = config["eligibility"]
        ordered_path_parts = [part.casefold() for part in PurePosixPath(frame_row["focal_path"]).parts]
        path_parts = set(ordered_path_parts)
        generated_segments = {str(value).casefold() for value in eligibility.get("generated_path_segments", [])}
        generated_markers = [str(value).casefold() for value in eligibility.get("generated_markers", [])]
        is_generated = bool(path_parts & generated_segments) or any(marker in text.casefold() for marker in generated_markers)
        is_test_source = any(
            ordered_path_parts[index] == "src" and ordered_path_parts[index + 1] == "test"
            for index in range(len(ordered_path_parts) - 1)
        )
        result.update({
            "metric_status": "success", "nloc": int(analysis.nloc), "token_count": int(analysis.token_count),
            "method_count": len(functions), "max_method_cc": max(cc_values) if cc_values else 0,
            "sum_method_cc": sum(cc_values),
            "avg_method_cc": (sum(cc_values) / len(cc_values)) if cc_values else 0.0,
            "public_method_count": max(metadata_public, len(public_regex)),
            "is_interface": bool(re.search(rf"\binterface\s+{re.escape(name)}\b", clean)),
            "is_enum": bool(re.search(rf"\benum\s+{re.escape(name)}\b", clean)),
            "is_generated": is_generated, "is_test_source": is_test_source,
        })
        reason = ""
        if result["nloc"] < int(eligibility["min_nloc"]) or result["nloc"] > int(eligibility["max_nloc"]):
            reason = "nloc_out_of_bounds"
        elif eligibility.get("require_public_non_constructor_method", True) and result["public_method_count"] < 1:
            reason = "no_public_non_constructor_method"
        elif eligibility.get("exclude_interfaces", True) and result["is_interface"]:
            reason = "is_interface"
        elif eligibility.get("exclude_enums", True) and result["is_enum"]:
            reason = "is_enum"
        elif eligibility.get("exclude_test_sources", True) and result["is_test_source"]:
            reason = "is_test_source"
        elif eligibility.get("exclude_generated_code", True) and result["is_generated"]:
            reason = "is_generated_code"
        result["exclusion_reason"] = reason
        result["eligible_for_sampling"] = not reason
    except PipelineError:
        raise
    except Exception as error:
        result["exclusion_reason"] = f"metric_error:{type(error).__name__}"
        result["metric_error"] = str(error)[:1000]
    return result


def ancestors_within(start: Path, root: Path) -> Iterator[Path]:
    current = start.resolve()
    root = root.resolve()
    while current == root or root in current.parents:
        yield current
        if current == root:
            break
        current = current.parent


def find_build_scope(repo: Path, focal_file: Path) -> dict[str, str] | None:
    ancestors = list(ancestors_within(focal_file.parent, repo))
    nearest_maven = next((path for path in ancestors if (path / "pom.xml").is_file()), None)
    nearest_gradle = next((path for path in ancestors if (path / "build.gradle").is_file() or (path / "build.gradle.kts").is_file()), None)
    use_maven = bool(nearest_maven) and (
        nearest_gradle is None or ancestors.index(nearest_maven) <= ancestors.index(nearest_gradle)
    )
    if use_maven and nearest_maven:
        root = nearest_maven
        for path in reversed(ancestors):
            if (path / "pom.xml").is_file():
                root = path
                break
        relative = nearest_maven.relative_to(root).as_posix()
        return {
            "build_tool": "maven", "module_dir": nearest_maven.relative_to(repo).as_posix() or ".",
            "build_root": root.relative_to(repo).as_posix() or ".", "module_selector": relative or ".",
            "scope_key": f"maven:{nearest_maven.relative_to(repo).as_posix() or '.'}",
        }
    if nearest_gradle:
        root = nearest_gradle
        for path in reversed(ancestors):
            if (path / "settings.gradle").is_file() or (path / "settings.gradle.kts").is_file():
                root = path
                break
        relative = nearest_gradle.relative_to(root)
        selector = ":".join(relative.parts)
        return {
            "build_tool": "gradle", "module_dir": nearest_gradle.relative_to(repo).as_posix() or ".",
            "build_root": root.relative_to(repo).as_posix() or ".", "module_selector": selector or ".",
            "scope_key": f"gradle:{nearest_gradle.relative_to(repo).as_posix() or '.'}",
        }
    return None


def find_wrapper(repo: Path, build_root: Path, tool: str) -> Path | None:
    names = ("mvnw.cmd", "mvnw") if tool == "maven" else ("gradlew.bat", "gradlew")
    for directory in ancestors_within(build_root, repo):
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate.resolve()
    return None


def build_recipes(repo: Path, scope: dict[str, str], config: dict[str, Any]) -> list[dict[str, Any]]:
    build = config["build"]
    root = repo / scope["build_root"]
    module = repo / scope["module_dir"]
    tool = scope["build_tool"]
    wrapper = find_wrapper(repo, root, tool) if build.get("prefer_repository_wrapper", True) else None
    executables: list[tuple[str, str]] = []
    if wrapper:
        executables.append((str(wrapper), "repository_wrapper"))
    if build.get("allow_global_tool_fallback", True):
        global_name = "mvn" if tool == "maven" else "gradle"
        executables.append((global_name, "global_fallback" if wrapper else "global_environment"))
    if not executables:
        raise PipelineError(f"No executable strategy configured for {tool}")
    recipes: list[dict[str, Any]] = []
    external_fallbacks: list[dict[str, Any]] = []
    for executable, source in executables:
        if tool == "maven":
            common = [executable, "-B", "-ntp", "-DskipTests", "-DskipITs"]
            module_args = [*common, "-f", str(module / "pom.xml"), "clean", "test-compile"]
            recipes.append({"name": f"{source}_maven_module", "args": module_args, "cwd": root, "source": source})
            recipes.append({
                "name": f"{source}_maven_module_skip_ancillary",
                "args": [*module_args[:-2], *[str(value) for value in build.get("maven_skip_flags", [])], "clean", "test-compile"],
                "cwd": root, "source": source,
            })
            if module.resolve() != root.resolve():
                reactor = [*common, "-f", str(root / "pom.xml"), "-pl", scope["module_selector"], "-am", "clean", "test-compile"]
                recipes.append({"name": f"{source}_maven_reactor", "args": reactor, "cwd": root, "source": source})
                recipes.append({
                    "name": f"{source}_maven_reactor_skip_ancillary",
                    "args": [*reactor[:-2], *[str(value) for value in build.get("maven_skip_flags", [])], "clean", "test-compile"],
                    "cwd": root, "source": source,
                })
            settings_file = build.get("maven_settings_file")
            if settings_file:
                settings = str(Path(str(settings_file)).resolve())
                fallback_common = [*common, "-s", settings]
                fallback_module = [
                    *fallback_common, "-f", str(module / "pom.xml"),
                    *[str(value) for value in build.get("maven_skip_flags", [])], "clean", "test-compile",
                ]
                external_fallbacks.append({
                    "name": f"{source}_maven_module_external_repository_fallback",
                    "args": fallback_module, "cwd": root,
                    "source": source + "+pre_registered_external_repository_fallback",
                })
                if module.resolve() != root.resolve():
                    external_fallbacks.append({
                        "name": f"{source}_maven_reactor_external_repository_fallback",
                        "args": [
                            *fallback_common, "-f", str(root / "pom.xml"), "-pl", scope["module_selector"], "-am",
                            *[str(value) for value in build.get("maven_skip_flags", [])], "clean", "test-compile",
                        ],
                        "cwd": root, "source": source + "+pre_registered_external_repository_fallback",
                    })
        else:
            selector = scope["module_selector"]
            task = "testClasses" if selector == "." else f":{selector}:testClasses"
            clean_task = "clean" if selector == "." else f":{selector}:clean"
            base = [executable, "--no-daemon", "--console=plain", "--stacktrace", clean_task, task, "-x", "test"]
            recipes.append({"name": f"{source}_gradle_module", "args": base, "cwd": root, "source": source})
            flags = [str(value) for value in build.get("gradle_project_flags", [])]
            if flags:
                recipes.append({"name": f"{source}_gradle_configured", "args": [*base, *flags], "cwd": root, "source": source})
            init_script = build.get("gradle_init_script")
            if init_script:
                external_fallbacks.append({
                    "name": f"{source}_gradle_external_repository_fallback",
                    "args": [
                        executable, "--no-daemon", "--console=plain", "--stacktrace",
                        "--init-script", str(Path(str(init_script)).resolve()), clean_task, task, "-x", "test", *flags,
                    ],
                    "cwd": root, "source": source + "+pre_registered_external_repository_fallback",
                })
    recipes.extend(external_fallbacks)
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for recipe in recipes:
        key = tuple(recipe["args"])
        if key not in seen:
            unique.append(recipe)
            seen.add(key)
    return unique


def tracked_status(repo: Path, env: dict[str, str]) -> tuple[int, str]:
    code, stdout, stderr, _ = run_process(["git", "status", "--porcelain", "--untracked-files=no"], repo, env, 60)
    return code, (stdout + "\n" + stderr).strip()


ATTEMPT_FIELDS = [
    "repo_id", "scope_key", "attempt_no", "recipe", "command_source", "command", "cwd",
    "declared_java_version", "effective_java_runtime", "tool_runtime", "exit_code", "status",
    "failure_category", "duration_seconds", "log_path", "started_at", "finished_at",
]


def append_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.is_file() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def execute_build_scope(
    repo_id: str, repo: Path, scope: dict[str, str], declared_java: int | None,
    config: dict[str, Any], logger: StepLogger,
) -> tuple[bool, str, str, list[dict[str, Any]]]:
    if not declared_java_allowed(declared_java, config):
        return False, "requires_java_above_8", f"scope declares unsupported Java {declared_java}", []
    env = jdk8_environment(config)
    java_code, java_out, java_err, _ = run_process(["java", "-version"], repo, env, 60)
    effective = java_major(java_out + "\n" + java_err)
    if java_code != 0 or effective != 8:
        return False, "wrong_jdk_runtime", f"effective Java is {effective or 'unknown'}, expected 8", []
    recipes = build_recipes(repo, scope, config)
    output = output_directory(config)
    attempts: list[dict[str, Any]] = []
    final_category = "unknown_build_failure"
    final_detail = ""
    attempt_no = 0
    maximum = int(config["build"].get("maximum_attempts_per_scope", 12))
    transient_limit = int(config["build"].get("transient_retries", 2))
    for recipe in recipes:
        if attempt_no >= maximum:
            break
        transient_count = 0
        while attempt_no < maximum:
            attempt_no += 1
            started = utc_now()
            executable = recipe["args"][0]
            version_args = [executable, "-version"] if scope["build_tool"] == "maven" else [executable, "--version"]
            tool_code, tool_out, tool_err, _ = run_process(version_args, recipe["cwd"], env, 120)
            tool_runtime = (tool_out + "\n" + tool_err).strip()[-2000:]
            if tool_code != 0:
                code, stdout, stderr, duration = tool_code, tool_out, tool_err, 0.0
            else:
                clean_code, clean_text = tracked_status(repo, env)
                if clean_code != 0 or clean_text:
                    return False, "tracked_files_dirty_before_build", clean_text[-4000:], attempts
                code, stdout, stderr, duration = run_process(
                    recipe["args"], recipe["cwd"], env, int(config["build"]["build_timeout_seconds"])
                )
            dirty_code, dirty_text = tracked_status(repo, env)
            if code == 0 and (dirty_code != 0 or dirty_text):
                code = 65
                stderr += "\nBUILD_MODIFIED_TRACKED_FILES\n" + dirty_text
            combined = stdout + "\n" + stderr
            category = "" if code == 0 else ("build_modified_tracked_files" if "BUILD_MODIFIED_TRACKED_FILES" in combined else classify_failure(combined))
            safe_scope = re.sub(r"[^A-Za-z0-9_.-]+", "_", scope["scope_key"])
            log_relative = f"logs/build/{repo_id}_{safe_scope}_{attempt_no}.log"
            atomic_write_text(
                output / log_relative,
                f"RECIPE: {recipe['name']}\nCOMMAND: {subprocess.list2cmdline(recipe['args'])}\n"
                f"CWD: {recipe['cwd']}\nDECLARED_JAVA: {declared_java or 'unknown'}\nEFFECTIVE_JAVA: 8\n"
                f"TOOL_RUNTIME:\n{tool_runtime}\nEXIT_CODE: {code}\nDURATION: {duration:.3f}\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}\n",
            )
            row = {
                "repo_id": repo_id, "scope_key": scope["scope_key"], "attempt_no": attempt_no,
                "recipe": recipe["name"], "command_source": recipe["source"],
                "command": subprocess.list2cmdline(recipe["args"]), "cwd": str(recipe["cwd"]),
                "declared_java_version": declared_java or "unknown", "effective_java_runtime": 8,
                "tool_runtime": tool_runtime.replace("\n", " | "), "exit_code": code,
                "status": "success" if code == 0 else "failed", "failure_category": category,
                "duration_seconds": f"{duration:.3f}", "log_path": log_relative,
                "started_at": started, "finished_at": utc_now(),
            }
            attempts.append(row)
            append_csv(output / "build_attempts.csv", [row], ATTEMPT_FIELDS)
            if code == 0:
                logger.log(f"Repo {repo_id} {scope['scope_key']} PASS via {recipe['name']} on JDK 8")
                return True, "", "", attempts
            final_category = category
            final_detail = combined[-4000:]
            if category in TRANSIENT_FAILURES and transient_count < transient_limit:
                transient_count += 1
                logger.log(f"Repo {repo_id} transient {category}; retry {transient_count}/{transient_limit}")
                continue
            break
    return False, final_category, final_detail, attempts


def _rmtree_clear_readonly(function: Any, path: str, exc_info: tuple[Any, BaseException, Any]) -> None:
    """Retry a failed Windows removal after clearing Git's read-only attribute."""
    error = exc_info[1]
    if not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    function(path)


def safe_remove_generated_tree(path: Path, owned_root: Path) -> None:
    resolved = path.resolve()
    root = owned_root.resolve()
    if resolved == root or root not in resolved.parents:
        raise PipelineError(f"Refusing to remove path outside generated root: {resolved}")
    if resolved.exists():
        last_error: OSError | None = None
        for attempt in range(3):
            try:
                shutil.rmtree(resolved, onerror=_rmtree_clear_readonly)
                return
            except OSError as error:
                last_error = error
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
        raise CleanupError(f"Cannot remove generated repository tree {resolved}: {last_error}") from last_error


def safe_promote_generated_tree(
    source: Path, destination: Path, working_root: Path, successful_root: Path,
) -> None:
    """Atomically promote a qualified clone, tolerating short-lived Windows readers."""
    resolved_source = source.resolve()
    resolved_destination = destination.resolve()
    resolved_working_root = working_root.resolve()
    resolved_successful_root = successful_root.resolve()
    if resolved_source == resolved_working_root or resolved_working_root not in resolved_source.parents:
        raise PipelineError(f"Refusing to promote source outside generated working root: {resolved_source}")
    if (
        resolved_destination == resolved_successful_root
        or resolved_successful_root not in resolved_destination.parents
    ):
        raise PipelineError(f"Refusing to promote destination outside generated successful root: {resolved_destination}")
    if not resolved_source.is_dir():
        raise PromotionError(f"Qualified working repository is missing: {resolved_source}")
    if resolved_destination.exists():
        raise PromotionError(f"Qualified destination already exists: {resolved_destination}")

    last_error: OSError | None = None
    for attempt in range(20):
        try:
            os.replace(resolved_source, resolved_destination)
            return
        except OSError as error:
            if not isinstance(error, PermissionError) and getattr(error, "winerror", None) not in {5, 32, 33}:
                raise PromotionError(
                    f"Cannot promote qualified repository {resolved_source} -> {resolved_destination}: {error}"
                ) from error
            last_error = error
            if attempt < 19:
                time.sleep(min(2.0, 0.25 * (attempt + 1)))
    raise PromotionError(
        f"Cannot promote qualified repository after 20 Windows retries: "
        f"{resolved_source} -> {resolved_destination}: {last_error}"
    ) from last_error


def promote_or_retain_qualified_repository(
    source: Path, destination: Path, working_root: Path, successful_root: Path,
) -> tuple[Path, str, str]:
    """Keep storage bookkeeping independent from the scientific qualification decision."""
    try:
        safe_promote_generated_tree(source, destination, working_root, successful_root)
        return destination, "promoted", ""
    except PromotionError as error:
        return source, "retained_in_working", str(error)[:4000]


def reset_queue_row_for_screening(row: dict[str, Any]) -> None:
    row.update({
        "status": "pending", "failure_category": "", "failure_detail": "",
        "clone_status": "pending", "commit_sha": "", "declared_java_versions": "",
        "effective_java_runtime": 8, "qualified_build_scopes": "",
        "unique_eligible_buildable_count": 0, "selected_for_sample": False,
        "repository_storage_path": "", "promotion_status": "", "promotion_detail": "",
        "updated_at": utc_now(),
    })


def recover_windows_filesystem_rows(queue: Sequence[dict[str, Any]]) -> list[str]:
    """Requeue only rows misclassified by the two known pre-fix Windows filesystem defects."""
    recovered: list[str] = []
    for row in queue:
        detail = re.sub(r"/+", "/", str(row.get("failure_detail", "")).replace("\\", "/")).casefold()
        repo_id = str(row.get("repo_id", ""))
        cleanup_fragment = f"/repos/working/{repo_id.casefold()}/.git/objects/pack/"
        working_fragment = f"/repos/working/{repo_id.casefold()}"
        successful_fragment = f"/repos/successful/{repo_id.casefold()}"
        known_cleanup = cleanup_fragment in detail
        known_promotion = working_fragment in detail and successful_fragment in detail and " -> " in detail
        if (
            row.get("status") == "rejected"
            and row.get("failure_category") == "pipeline_exception"
            and "permissionerror: [winerror 5] access is denied:" in detail
            and (known_cleanup or known_promotion)
        ):
            reset_queue_row_for_screening(row)
            recovered.append(repo_id)
    return recovered


def archive_step003_progress(output: Path, queue_file: Path) -> Path:
    """Move Step 003 artifacts to a recoverable archive before an explicit restart."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = output / "state" / "step003_restart_archives" / f"{stamp}_{os.getpid()}"
    archive.mkdir(parents=True, exist_ok=False)
    relative_paths = (
        "repo_processing_order_seed42.csv", "build_attempts.csv", "successful_repos_manifest.csv",
        "class_metrics_all.csv", "build_recipes.jsonl", "excluded_classes_log.csv",
        "state/step003.done.json", "state/repo_metrics", "repos/working", "repos/successful",
        "repos/failed", "logs/build", "logs/clone", "logs/submodules",
    )
    for relative in relative_paths:
        source = output / relative
        if not source.exists():
            continue
        destination = archive / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
    create_layout(output)
    if queue_file.exists():
        raise PipelineError(f"Restart archive did not move the queue: {queue_file}")
    return archive


def clone_repository(
    repo_id: str, url: str, dataset_commit: str, destination: Path,
    config: dict[str, Any], logger: StepLogger,
) -> tuple[bool, str, str]:
    env = jdk8_environment(config)
    args = ["git", "-c", "credential.helper=", "clone", "--recurse-submodules", "--jobs", "4", "--", url, str(destination)]
    code, stdout, stderr, duration = run_process(args, None, env, int(config["build"]["clone_timeout_seconds"]))
    log = output_directory(config) / "logs" / "clone" / f"{repo_id}.log"
    atomic_write_text(log, f"COMMAND: {subprocess.list2cmdline(args)}\nEXIT CODE: {code}\nDURATION: {duration:.3f}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}\n")
    if code != 0:
        return False, classify_failure(stdout + "\n" + stderr), (stdout + "\n" + stderr)[-4000:]
    if dataset_commit:
        checkout_code, checkout_out, checkout_err, _ = run_process(
            ["git", "checkout", "--detach", dataset_commit], destination, env, 300
        )
        if checkout_code != 0:
            return False, "dataset_commit_unavailable", (checkout_out + "\n" + checkout_err)[-4000:]
    sub_code, sub_out, sub_err, _ = run_process(
        ["git", "submodule", "update", "--init", "--recursive", "--jobs", "4"], destination, env, 600
    )
    atomic_write_text(output_directory(config) / "logs" / "submodules" / f"{repo_id}.log", sub_out + "\n" + sub_err)
    if sub_code != 0:
        logger.log(f"Repo {repo_id} submodule update failed")
        return False, "missing_git_submodule", (sub_out + "\n" + sub_err)[-4000:]
    return True, "", ""


def git_head(repo: Path, config: dict[str, Any]) -> str:
    code, stdout, _, _ = run_process(["git", "rev-parse", "HEAD"], repo, jdk8_environment(config), 60)
    return stdout.strip() if code == 0 else ""


def reusable_working_repository(
    repo: Path, expected_commit: str, config: dict[str, Any],
) -> tuple[bool, str]:
    """Accept an interrupted working clone only when identity and tracked content are intact."""
    if not (repo / ".git").exists():
        return False, "missing .git"
    observed_commit = git_head(repo, config)
    if not observed_commit:
        return False, "cannot resolve HEAD"
    if expected_commit and observed_commit.casefold() != expected_commit.strip().casefold():
        return False, f"HEAD {observed_commit} != dataset commit {expected_commit}"
    status_code, status_text = tracked_status(repo, jdk8_environment(config))
    if status_code != 0:
        return False, f"git status failed: {status_text[-1000:]}"
    if status_text:
        return False, f"tracked files are dirty: {status_text[-1000:]}"
    return True, observed_commit


def group_frame_by_repo(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        grouped[row["repo_id"]].append(row)
    return grouped


METRIC_FIELDS = [
    "repo_id", "repo_url", "commit_sha", "class_key", "focal_class", "focal_path", "mapping_count",
    "source_json_files", "exact_path_exists", "metric_status", "metric_error", "nloc", "token_count",
    "method_count", "public_method_count", "max_method_cc", "sum_method_cc", "avg_method_cc",
    "is_interface", "is_enum", "is_generated", "is_test_source", "eligible_for_sampling",
    "exclusion_reason", "build_tool", "build_root", "module_dir", "module_selector", "scope_key",
    "declared_java_version", "java_version_source", "effective_java_runtime", "build_scope_pass",
    "build_recipe", "repository_storage_path", "promotion_status",
]


def screen_and_build_repositories(
    config_path_value: Path | str, retry_recoverable: bool = False,
    mode: str = "resume", restart_confirmation: str = "",
) -> dict[str, Any]:
    if mode not in {"resume", "restart"}:
        raise PipelineError(f"Unknown Step 003 execution mode: {mode}")
    if mode == "restart" and restart_confirmation != STEP003_RESTART_CONFIRMATION:
        raise PipelineError(
            f"Restart requires --confirm-restart {STEP003_RESTART_CONFIRMATION}; resume is the safe default"
        )
    config = load_config(config_path_value)
    previous = verify_previous_step(
        config, "step002", {"repo_processing_order_seed42.csv"},
        source_amendment_reason=STEP003_CLEANUP_AMENDMENT_ID,
        source_amendment_from_hash=STEP003_CLEANUP_AMENDMENT_FROM_HASH,
    )
    output = output_directory(config)
    with pipeline_lock(config, "step003"):
        logger = StepLogger(output, "step003")
        amendment_file: Path | None = None
        amendment = previous.get("_source_amendment")
        if amendment:
            amendment_file = (
                output / "state" / "source_amendments" /
                f"step002_to_step003_{amendment['amended_source_inventory_sha256'][:12]}.json"
            )
            if not amendment_file.exists():
                atomic_write_json(amendment_file, {**amendment, "recorded_at": utc_now()})
            logger.log(
                f"Applied recorded source amendment {STEP003_CLEANUP_AMENDMENT_ID}: "
                f"{amendment['prior_source_inventory_sha256'][:12]} -> "
                f"{amendment['amended_source_inventory_sha256'][:12]}"
            )
        queue_file = output / "repo_processing_order_seed42.csv"
        queue = read_csv(queue_file)
        initial_queue = read_csv(output / "state" / "repo_processing_order_seed42.initial.csv")
        immutable_columns = (
            "order_index", "repo_id", "repo_url", "dataset_commit_sha",
            "unique_mapped_focal_count", "repo_order_hash",
        )
        observed_order = [tuple(row[column] for column in immutable_columns) for row in queue]
        expected_order = [tuple(row[column] for column in immutable_columns) for row in initial_queue]
        if observed_order != expected_order:
            raise PipelineError("Repository queue order/identity drifted from the immutable Step 002 snapshot")
        restart_archive: Path | None = None
        if mode == "restart":
            restart_archive = archive_step003_progress(output, queue_file)
            queue = [dict(row) for row in initial_queue]
            atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
            logger.log(f"Restart mode: prior Step 003 progress archived at {restart_archive}")
        else:
            recovered_cleanup_ids = recover_windows_filesystem_rows(queue)
            if recovered_cleanup_ids:
                atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
                logger.log(
                    f"Resume mode: requeued {len(recovered_cleanup_ids)} repositories affected by "
                    f"{STEP003_CLEANUP_AMENDMENT_ID}: {','.join(recovered_cleanup_ids)}"
                )
            logger.log("Execution mode: resume; qualified repositories and definitive rejections are preserved")
        storage_backfilled = False
        for row in queue:
            if row.get("status") != "qualified" or row.get("repository_storage_path"):
                continue
            repo_id = row["repo_id"]
            successful_path = output / "repos" / "successful" / repo_id
            working_path = output / "repos" / "working" / repo_id
            if successful_path.is_dir():
                row.update({
                    "repository_storage_path": successful_path.relative_to(output).as_posix(),
                    "promotion_status": "promoted_before_storage_audit",
                })
            elif working_path.is_dir():
                row.update({
                    "repository_storage_path": working_path.relative_to(output).as_posix(),
                    "promotion_status": "retained_in_working_before_storage_audit",
                })
            else:
                raise PipelineError(f"Qualified repository storage is missing for {repo_id}")
            storage_backfilled = True
        if storage_backfilled:
            atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
        frame = group_frame_by_repo(output / "unique_focal_class_frame.csv")
        if retry_recoverable:
            allowed = set(config["build"].get("automatically_retry_categories", []))
            for row in queue:
                if row["status"] == "rejected" and row["failure_category"] in allowed:
                    row.update({"status": "pending", "failure_category": "", "failure_detail": "", "updated_at": utc_now()})
            atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
        target = int(config["protocol"]["target_repositories"])
        minimum = int(config["protocol"]["minimum_unique_classes_per_repo"])
        selected = [row for row in queue if row["status"] == "qualified"]
        logger.log(f"Resume with {len(selected)}/{target} qualified repositories")
        for queue_row in queue:
            if len(selected) >= target:
                break
            if queue_row["status"] != "pending":
                continue
            repo_id = queue_row["repo_id"]
            working = output / "repos" / "working" / repo_id
            successful = output / "repos" / "successful" / repo_id
            logger.log(f"Screening repo {repo_id} ({len(selected)}/{target})")
            try:
                if successful.is_dir():
                    repo = successful
                    clone_ok, clone_category, clone_detail = True, "", ""
                else:
                    if working.exists():
                        reusable, reuse_detail = reusable_working_repository(
                            working, queue_row.get("dataset_commit_sha", ""), config
                        )
                    else:
                        reusable, reuse_detail = False, "working repository does not exist"
                    if reusable:
                        clone_ok, clone_category, clone_detail = True, "", ""
                        logger.log(f"Repo {repo_id} resuming verified clean working clone at {reuse_detail}")
                    else:
                        if working.exists():
                            logger.log(f"Repo {repo_id} discarding non-reusable working clone: {reuse_detail}")
                            safe_remove_generated_tree(working, output / "repos" / "working")
                        clone_ok, clone_category, clone_detail = clone_repository(
                            repo_id, queue_row["repo_url"], queue_row.get("dataset_commit_sha", ""), working, config, logger
                        )
                    repo = working
                if not clone_ok:
                    queue_row.update({
                        "status": "rejected", "failure_category": clone_category, "failure_detail": clone_detail,
                        "clone_status": "failed", "updated_at": utc_now(),
                    })
                    if working.exists() and not config["build"].get("keep_failed_repositories", False):
                        safe_remove_generated_tree(working, output / "repos" / "working")
                    atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
                    continue
                queue_row["clone_status"] = "success"
                commit = git_head(repo, config)
                if not commit:
                    raise PipelineError("cannot resolve exact commit SHA")
                queue_row["commit_sha"] = commit

                metrics: list[dict[str, Any]] = []
                scopes: dict[str, dict[str, Any]] = {}
                for frame_row in frame.get(repo_id, []):
                    focal = repo / normalize_relative_path(frame_row["focal_path"])
                    metric = analyze_java_file(focal, frame_row, config)
                    metric["commit_sha"] = commit
                    scope = find_build_scope(repo, focal) if focal.is_file() else None
                    if scope:
                        metric.update(scope)
                        entry = scopes.setdefault(scope["scope_key"], {"scope": scope, "metrics": []})
                        if metric["eligible_for_sampling"]:
                            entry["metrics"].append(metric)
                    else:
                        metric["eligible_for_sampling"] = False
                        metric["exclusion_reason"] = metric.get("exclusion_reason") or "build_scope_not_found"
                    metrics.append(metric)

                passed_scopes: list[str] = []
                declared_versions: set[int] = set()
                recipes_for_repo: list[dict[str, Any]] = []
                buildable_count = 0
                last_category, last_detail = "insufficient_unique_eligible_classes", ""
                scope_entries = sorted(scopes.values(), key=lambda value: (-len(value["metrics"]), value["scope"]["scope_key"]))
                for entry in scope_entries:
                    if buildable_count >= minimum:
                        break
                    scope = entry["scope"]
                    build_files: list[Path] = []
                    for relative in {scope["module_dir"], scope["build_root"]}:
                        directory = repo / relative
                        build_files.extend(path for path in (
                            directory / "pom.xml", directory / "build.gradle", directory / "build.gradle.kts"
                        ) if path.is_file())
                    declared, source, observed = detect_declared_java(build_files)
                    declared_versions.update(observed)
                    for metric in entry["metrics"]:
                        metric.update({
                            "declared_java_version": declared or "unknown", "java_version_source": source,
                            "effective_java_runtime": 8,
                        })
                    if not declared_java_allowed(declared, config):
                        last_category, last_detail = "requires_java_above_8", f"{scope['scope_key']} declares Java {declared}"
                        continue
                    passed, category, detail, attempts = execute_build_scope(repo_id, repo, scope, declared, config, logger)
                    if passed:
                        passed_scopes.append(scope["scope_key"])
                        winner = attempts[-1]
                        for metric in entry["metrics"]:
                            metric["build_scope_pass"] = True
                            metric["build_recipe"] = winner["recipe"]
                        recipes_for_repo.append({
                            "recipe_id": f"v3:{repo_id}:{scope['scope_key']}", "repo_id": repo_id,
                            "repo_url": queue_row["repo_url"], "commit_sha": commit, "scope": scope,
                            "declared_java_version": declared or "unknown", "java_version_source": source,
                            "effective_java_runtime": 8, "recipe": winner["recipe"],
                            "command_source": winner["command_source"], "command": winner["command"],
                            "working_directory": winner["cwd"], "validation_log": winner["log_path"],
                            "validated_at": winner["finished_at"], "source_or_dependency_files_modified": False,
                        })
                        buildable_count += len(entry["metrics"])
                    else:
                        last_category, last_detail = category, detail

                eligible_buildable = [row for row in metrics if row.get("eligible_for_sampling") and row.get("build_scope_pass")]
                metric_state = output / "state" / "repo_metrics" / f"{repo_id}.json"
                recipe_state = output / "state" / "repo_metrics" / f"{repo_id}.build_recipes.json"
                atomic_write_json(metric_state, metrics)
                atomic_write_json(recipe_state, recipes_for_repo)
                if len(eligible_buildable) < minimum:
                    queue_row.update({
                        "status": "rejected", "failure_category": last_category,
                        "failure_detail": f"eligible buildable {len(eligible_buildable)} < {minimum}; {last_detail}"[-4000:],
                        "declared_java_versions": ";".join(map(str, sorted(declared_versions))) or "unknown",
                        "effective_java_runtime": 8, "qualified_build_scopes": ";".join(passed_scopes),
                        "unique_eligible_buildable_count": len(eligible_buildable), "selected_for_sample": False,
                        "updated_at": utc_now(),
                    })
                    if repo == working and working.exists():
                        if config["build"].get("keep_failed_repositories", False):
                            failed = output / "repos" / "failed" / repo_id
                            if failed.exists():
                                safe_remove_generated_tree(failed, output / "repos" / "failed")
                            os.replace(working, failed)
                        else:
                            safe_remove_generated_tree(working, output / "repos" / "working")
                else:
                    promotion_status = "already_in_successful"
                    promotion_detail = ""
                    storage_path = successful
                    if repo == working:
                        if successful.exists():
                            safe_remove_generated_tree(successful, output / "repos" / "successful")
                        storage_path, promotion_status, promotion_detail = promote_or_retain_qualified_repository(
                            working, successful,
                            output / "repos" / "working", output / "repos" / "successful",
                        )
                        if promotion_status == "retained_in_working":
                            logger.log(
                                f"Repo {repo_id} QUALIFIED but retained in working because Windows blocked "
                                f"the storage promotion; eligibility is unchanged"
                            )
                    atomic_write_json(output / "state" / "repo_metrics" / f"{repo_id}.promotion.json", {
                        "repo_id": repo_id, "status": promotion_status,
                        "storage_path": storage_path.relative_to(output).as_posix(),
                        "detail": promotion_detail, "recorded_at": utc_now(),
                        "eligibility_affected": False,
                    })
                    queue_row.update({
                        "status": "qualified", "failure_category": "", "failure_detail": "",
                        "declared_java_versions": ";".join(map(str, sorted(declared_versions))) or "unknown",
                        "effective_java_runtime": 8, "qualified_build_scopes": ";".join(passed_scopes),
                        "unique_eligible_buildable_count": len(eligible_buildable), "selected_for_sample": True,
                        "repository_storage_path": storage_path.relative_to(output).as_posix(),
                        "promotion_status": promotion_status, "promotion_detail": promotion_detail,
                        "updated_at": utc_now(),
                    })
                    selected.append(queue_row)
                    logger.log(f"Repo {repo_id} QUALIFIED with {len(eligible_buildable)} classes")
                atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
            except KeyboardInterrupt:
                atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
                raise
            except (CleanupError, PromotionError) as error:
                atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
                logger.log(f"STOP: {error}; repository classification was preserved")
                raise
            except Exception as error:
                queue_row.update({
                    "status": "rejected", "failure_category": "pipeline_exception",
                    "failure_detail": f"{type(error).__name__}: {error}"[:4000], "updated_at": utc_now(),
                })
                atomic_write_text(output / "logs" / "build" / f"{repo_id}_pipeline_exception.log", traceback.format_exc())
                atomic_write_csv(queue_file, queue, QUEUE_FIELDS)
                logger.log(f"Repo {repo_id} rejected by pipeline exception: {error}")

        if len(selected) < target:
            raise PipelineError(
                f"INSUFFICIENT_QUALIFIED_REPOSITORIES: {len(selected)}/{target}. Criteria were not relaxed. "
                "Inspect logs, correct environment-only failures, then rerun with --retry-recoverable if appropriate."
            )
        selected = sorted(selected, key=lambda row: int(row["order_index"]))[:target]
        selected_ids = {row["repo_id"] for row in selected}
        for row in queue:
            row["selected_for_sample"] = row["repo_id"] in selected_ids
        atomic_write_csv(queue_file, queue, QUEUE_FIELDS)

        manifest_file = output / "successful_repos_manifest.csv"
        atomic_write_csv(manifest_file, selected, [
            "repo_id", "repo_url", "commit_sha", "declared_java_versions", "effective_java_runtime",
            "qualified_build_scopes", "unique_eligible_buildable_count", "order_index", "repo_order_hash",
            "repository_storage_path", "promotion_status", "promotion_detail",
        ])
        all_metrics: list[dict[str, Any]] = []
        all_recipes: list[dict[str, Any]] = []
        for row in selected:
            repo_id = row["repo_id"]
            storage = qualified_repository_storage_path(output, row)
            repo_metrics = json.loads(
                (output / "state" / "repo_metrics" / f"{repo_id}.json").read_text(encoding="utf-8")
            )
            for metric in repo_metrics:
                metric["repository_storage_path"] = storage.relative_to(output.resolve()).as_posix()
                metric["promotion_status"] = row.get("promotion_status", "")
            all_metrics.extend(repo_metrics)
            all_recipes.extend(json.loads((output / "state" / "repo_metrics" / f"{repo_id}.build_recipes.json").read_text(encoding="utf-8")))
        metrics_file = output / "class_metrics_all.csv"
        recipes_file = output / "build_recipes.jsonl"
        excluded_file = output / "excluded_classes_log.csv"
        atomic_write_csv(metrics_file, all_metrics, METRIC_FIELDS)
        atomic_write_csv(excluded_file, [row for row in all_metrics if not row.get("eligible_for_sampling") or not row.get("build_scope_pass")], METRIC_FIELDS)
        atomic_write_jsonl(recipes_file, all_recipes)
        details = {
            "qualified_repositories": len(selected), "effective_java_runtime": 8,
            "classes_in_qualified_frame": sum(1 for row in all_metrics if row.get("eligible_for_sampling") and row.get("build_scope_pass")),
            "source_or_dependency_modification_allowed": False,
            "execution_mode": mode,
            "restart_archive": str(restart_archive or ""),
            "source_amendment": str(amendment_file or ""),
            "qualified_repositories_retained_in_working": sum(
                row.get("promotion_status") == "retained_in_working" for row in selected
            ),
        }
        mark_done(config, "step003", [queue_file, manifest_file, metrics_file, recipes_file, excluded_file], details)
        logger.log("Step 003 PASS")
        return details


SAMPLE_FIELDS = [
    "repo_id", "repo_url", "commit_sha", "class_key", "focal_class", "focal_path", "mapping_count",
    "nloc", "token_count", "method_count", "public_method_count", "max_method_cc", "sum_method_cc",
    "avg_method_cc", "build_tool", "build_root", "module_dir", "module_selector", "scope_key",
    "declared_java_version", "effective_java_runtime", "selected_type", "selection_rank_in_repo",
    "selection_hash", "selection_seed", "selection_algorithm", "complexity_half", "replacement_of",
    "replacement_reason", "repository_storage_path", "promotion_status",
]


def select_repo_balanced_classes(
    eligible_rows: Sequence[dict[str, Any]], seed: int, main_per_repo: int = 10, backup_per_repo: int = 2
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in eligible_rows:
        row = dict(source)
        row["selection_hash"] = stable_hash("v3-class-selection", seed, row["class_key"])
        grouped[str(row["repo_id"])].append(row)
    mains: list[dict[str, Any]] = []
    backups: list[dict[str, Any]] = []
    for repo_id in sorted(grouped, key=natural_key):
        ordered = sorted(grouped[repo_id], key=lambda row: (row["selection_hash"], row["class_key"]))
        if len(ordered) < main_per_repo + backup_per_repo:
            raise PipelineError(f"Repo {repo_id} has only {len(ordered)} eligible buildable classes")
        for rank, row in enumerate(ordered[: main_per_repo + backup_per_repo], 1):
            row.update({
                "selected_type": "main" if rank <= main_per_repo else "backup",
                "selection_rank_in_repo": rank, "selection_seed": seed,
                "selection_algorithm": SELECTION_ALGORITHM, "complexity_half": "",
                "replacement_of": "", "replacement_reason": "",
            })
            (mains if rank <= main_per_repo else backups).append(row)
    return mains, backups


def sample_classes(config_path_value: Path | str) -> dict[str, Any]:
    config = load_config(config_path_value)
    verify_previous_step(config, "step003")
    output = output_directory(config)
    with pipeline_lock(config, "step004"):
        logger = StepLogger(output, "step004")
        metrics = read_csv(output / "class_metrics_all.csv")
        eligible = [row for row in metrics if truthy(row["eligible_for_sampling"]) and truthy(row["build_scope_pass"])]
        seed = int(config["protocol"]["seed"])
        mains, backups = select_repo_balanced_classes(
            eligible, seed, int(config["protocol"]["main_classes_per_repo"]),
            int(config["protocol"]["backup_classes_per_repo"]),
        )
        expected_repos = int(config["protocol"]["target_repositories"])
        if len({row["repo_id"] for row in mains}) != expected_repos:
            raise PipelineError("Sampling frame does not contain exactly 30 qualified repositories")
        main_file = output / "class_sampling_manifest_seed42.csv"
        backup_file = output / "class_backup_manifest_seed42.csv"
        summary_file = output / "repo_sampling_summary.csv"
        atomic_write_csv(main_file, mains, SAMPLE_FIELDS)
        atomic_write_csv(backup_file, backups, SAMPLE_FIELDS)
        summary_rows = []
        for repo_id in sorted({row["repo_id"] for row in mains}, key=natural_key):
            summary_rows.append({
                "repo_id": repo_id, "eligible_unique_classes": sum(1 for row in eligible if row["repo_id"] == repo_id),
                "main_classes": sum(1 for row in mains if row["repo_id"] == repo_id),
                "backup_classes": sum(1 for row in backups if row["repo_id"] == repo_id),
            })
        atomic_write_csv(summary_file, summary_rows, ["repo_id", "eligible_unique_classes", "main_classes", "backup_classes"])
        details = {
            "main_classes": len(mains), "backup_classes": len(backups), "repositories": expected_repos,
            "complexity_used_for_selection": False, "selection_algorithm": SELECTION_ALGORITHM,
        }
        mark_done(config, "step004", [main_file, backup_file, summary_file], details)
        logger.log("Step 004 PASS: selected 300 main + 60 backup without using complexity")
        return details


def assign_relative_complexity_halves(main_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in main_rows]
    rows.sort(key=lambda row: (
        float(row.get("max_method_cc") or 0), float(row.get("sum_method_cc") or 0),
        row.get("selection_hash", ""), row["class_key"],
    ))
    if len(rows) % 2:
        raise PipelineError("Relative complexity halves require an even number of main classes")
    boundary = len(rows) // 2
    for index, row in enumerate(rows):
        row["complexity_half"] = "lower_complexity_half" if index < boundary else "higher_complexity_half"
        row["complexity_rank"] = index + 1
    return rows


def numeric_summary(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(ordered), "min": min(ordered), "max": max(ordered),
        "mean": statistics.fmean(ordered), "median": statistics.median(ordered),
        "q1": ordered[(len(ordered) - 1) // 4], "q3": ordered[(3 * (len(ordered) - 1)) // 4],
    }


def validate_and_report(config_path_value: Path | str) -> dict[str, Any]:
    config = load_config(config_path_value)
    verify_previous_step(config, "step004")
    output = output_directory(config)
    with pipeline_lock(config, "step005"):
        logger = StepLogger(output, "step005")
        main_file = output / "class_sampling_manifest_seed42.csv"
        backup_file = output / "class_backup_manifest_seed42.csv"
        manifest_file = output / "successful_repos_manifest.csv"
        metrics_file = output / "class_metrics_all.csv"
        recipes_file = output / "build_recipes.jsonl"
        mains = read_csv(main_file)
        backups = read_csv(backup_file)
        repos = read_csv(manifest_file)
        metrics = read_csv(metrics_file)
        recipes = [json.loads(line) for line in recipes_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        errors: list[str] = []
        checks: list[dict[str, Any]] = []

        def check(name: str, expected: Any, observed: Any, passed: bool) -> None:
            checks.append({"check": name, "expected": expected, "observed": observed, "status": "PASS" if passed else "FAIL"})
            if not passed:
                errors.append(f"{name}: expected {expected}, observed {observed}")

        protocol = config["protocol"]
        repo_ids = [row["repo_id"] for row in repos]
        main_keys = [row["class_key"] for row in mains]
        backup_keys = [row["class_key"] for row in backups]
        check("qualified repositories", 30, len(set(repo_ids)), len(repos) == 30 and len(set(repo_ids)) == 30)
        check("main rows", 300, len(mains), len(mains) == 300)
        check("unique main keys", 300, len(set(main_keys)), len(set(main_keys)) == 300)
        check("backup rows", 60, len(backups), len(backups) == 60)
        check("unique backup keys", 60, len(set(backup_keys)), len(set(backup_keys)) == 60)
        overlap = len(set(main_keys) & set(backup_keys))
        check("main/backup overlap", 0, overlap, overlap == 0)
        for repo_id in sorted(set(repo_ids), key=natural_key):
            check(f"{repo_id} main", 10, sum(1 for row in mains if row["repo_id"] == repo_id), sum(1 for row in mains if row["repo_id"] == repo_id) == 10)
            check(f"{repo_id} backup", 2, sum(1 for row in backups if row["repo_id"] == repo_id), sum(1 for row in backups if row["repo_id"] == repo_id) == 2)
        check(
            "minimum eligible buildable classes per repo", ">=12",
            min(int(row["unique_eligible_buildable_count"]) for row in repos) if repos else 0,
            bool(repos) and all(int(row["unique_eligible_buildable_count"]) >= 12 for row in repos),
        )
        check("effective JDK runtime", 8, sorted({row["effective_java_runtime"] for row in repos}), all(str(row["effective_java_runtime"]) == "8" for row in repos))
        storage_by_repo: dict[str, Path] = {}
        storage_errors: list[str] = []
        for row in repos:
            try:
                storage_by_repo[row["repo_id"]] = qualified_repository_storage_path(output, row)
            except PipelineError as error:
                storage_errors.append(str(error))
        check(
            "qualified repository storage records", 30,
            sum(bool(row.get("repository_storage_path")) for row in repos),
            len(repos) == 30 and all(bool(row.get("repository_storage_path")) for row in repos),
        )
        check("invalid or missing qualified repository storage", 0, len(storage_errors), not storage_errors)
        recipe_repos = {str(row["repo_id"]) for row in recipes}
        check("repos with validated recipes", 30, len(recipe_repos & set(repo_ids)), set(repo_ids) <= recipe_repos)
        check("recipes modified source/dependencies", 0, sum(bool(row.get("source_or_dependency_files_modified")) for row in recipes), not any(bool(row.get("source_or_dependency_files_modified")) for row in recipes))

        metric_by_key = {row["class_key"]: row for row in metrics if truthy(row["eligible_for_sampling"]) and truthy(row["build_scope_pass"])}
        unknown_keys = (set(main_keys) | set(backup_keys)) - set(metric_by_key)
        check("sample keys outside eligible buildable frame", 0, len(unknown_keys), not unknown_keys)
        missing_paths = []
        sample_storage_mismatches = []
        for row in mains + backups:
            storage = storage_by_repo.get(row["repo_id"])
            if storage is None:
                missing_paths.append(row["class_key"])
                continue
            recorded_storage = normalize_relative_path(row.get("repository_storage_path", ""))
            expected_storage = storage.relative_to(output.resolve()).as_posix()
            if recorded_storage.casefold() != expected_storage.casefold():
                sample_storage_mismatches.append(row["class_key"])
            focal_relative = normalize_relative_path(row["focal_path"])
            focal = (storage / focal_relative).resolve() if focal_relative else storage
            if storage not in focal.parents:
                missing_paths.append(row["class_key"])
                continue
            if not focal.is_file():
                missing_paths.append(row["class_key"])
        check("sample/manifest storage mismatches", 0, len(sample_storage_mismatches), not sample_storage_mismatches)
        check("missing focal paths at frozen commits", 0, len(missing_paths), not missing_paths)

        seed = int(protocol["seed"])
        reconstructed_mains, reconstructed_backups = select_repo_balanced_classes(
            list(metric_by_key.values()), seed, int(protocol["main_classes_per_repo"]), int(protocol["backup_classes_per_repo"])
        )
        selection_mismatch = set(main_keys) ^ {row["class_key"] for row in reconstructed_mains}
        backup_mismatch = set(backup_keys) ^ {row["class_key"] for row in reconstructed_backups}
        check("deterministic main reconstruction mismatches", 0, len(selection_mismatch), not selection_mismatch)
        check("deterministic backup reconstruction mismatches", 0, len(backup_mismatch), not backup_mismatch)

        final_rows = assign_relative_complexity_halves(mains)
        lower = [row for row in final_rows if row["complexity_half"] == "lower_complexity_half"]
        higher = [row for row in final_rows if row["complexity_half"] == "higher_complexity_half"]
        check("lower relative complexity half", 150, len(lower), len(lower) == 150)
        check("higher relative complexity half", 150, len(higher), len(higher) == 150)
        boundary_tie = bool(lower and higher and float(lower[-1]["max_method_cc"]) == float(higher[0]["max_method_cc"]))

        final_fields = [*SAMPLE_FIELDS, "complexity_rank"]
        final_file = output / "class_sampling_manifest_final_seed42.csv"
        atomic_write_csv(final_file, final_rows, final_fields)
        checksum_rows = script_inventory()
        for path in (main_file, backup_file, manifest_file, metrics_file, recipes_file, final_file):
            checksum_rows.append({
                "path": path.relative_to(output).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)
            })
        checksum_file = output / "results" / "SHA256SUMS.csv"
        atomic_write_csv(checksum_file, checksum_rows, ["path", "size", "sha256"])

        report_lines = [
            "# Data V3 validation report", "", f"Generated: {utc_now()}", "",
            f"**Overall status: {'PASS' if not errors else 'FAIL'}**", "",
            "| Check | Expected | Observed | Status |", "|---|---:|---:|---|",
        ]
        report_lines.extend(f"| {row['check']} | {row['expected']} | {row['observed']} | {row['status']} |" for row in checks)
        if errors:
            report_lines.extend(["", "## Errors", "", *[f"- {error}" for error in errors]])
        validation_file = output / "results" / "validation_report.md"
        atomic_write_text(validation_file, "\n".join(report_lines) + "\n")

        complexity_file = output / "results" / "complexity_halves_summary.json"
        atomic_write_json(complexity_file, {
            "algorithm": COMPLEXITY_ALGORITHM, "boundary_tie_on_max_cc": boundary_tie,
            "lower": numeric_summary([float(row["max_method_cc"]) for row in lower]),
            "higher": numeric_summary([float(row["max_method_cc"]) for row in higher]),
            "labels_are_relative_not_absolute": True,
        })
        methodology_file = output / "results" / "sampling_methodology.md"
        atomic_write_text(methodology_file, "\n".join([
            "# Data V3 sampling methodology", "",
            "- Unit: one physical focal Java source file, identified by repository ID plus normalized focal path.",
            "- Repository frame: first 30 final-qualified repositories in the deterministic seed-42 SHA-256 queue.",
            "- Qualification: at least 12 unique structurally eligible classes in scopes compiled on the effective JDK 8 runtime.",
            "- Declared Java 5/6/7/8 and unknown are all tested on JDK 8; only evidence of a >8 requirement is excluded.",
            "- Selection: SHA-256 rank within repository; exactly 10 main and 2 backup classes per repository.",
            "- Complexity is not an eligibility or selection variable. It is used only after selection for relative 150/150 halves.",
            "- No source/build/dependency file may be edited to obtain a successful baseline build.",
            "- Backups are for documented pre-experiment technical failures only, never for unfavorable GPT/EvoSuite outcomes.",
            "- The operational physical-file unit is an explicit amendment to the proposal tuple-based reconstruction and must be disclosed.",
        ]) + "\n")
        integrity_file = output / "results" / "data_integrity_report.md"
        atomic_write_text(integrity_file, "\n".join([
            "# Data V3 scientific-integrity report", "",
            f"Status: {'PASS' if not errors else 'FAIL'}", "",
            "## Verified safeguards", "",
            "- Stable class identity and zero main/backup overlap are machine-checked.",
            "- Repository and class order use pre-declared seed 42 and SHA-256.",
            "- Complexity does not influence inclusion or class selection.",
            "- Build evidence records declared Java separately from the effective JDK 8 runtime.",
            "- Exact repository commits, commands, working directories, tool versions and logs are retained.",
            "- Script, config and principal output checksums are recorded.",
            "- No downstream GPT, EvoSuite, coverage or mutation outcome is available to this data-construction pipeline.",
        ]) + "\n")

        ready_file = output / "results" / "RUN_READY"
        if errors:
            with contextlib.suppress(FileNotFoundError):
                ready_file.unlink()
        else:
            atomic_write_json(ready_file, {
                "status": "READY", "validated_at": utc_now(), "config_sha256": current_config_hash(config),
                "main_manifest_sha256": sha256_file(final_file), "pipeline_version": PIPELINE_VERSION,
            })
        outputs = [final_file, checksum_file, validation_file, complexity_file, methodology_file, integrity_file]
        if not errors:
            outputs.append(ready_file)
        details = {
            "status": "PASS" if not errors else "FAIL", "errors": errors,
            "main": len(mains), "backup": len(backups), "lower": len(lower), "higher": len(higher),
        }
        if errors:
            logger.log(f"Step 005 FAIL with {len(errors)} validation errors")
            raise PipelineError("Step 005 validation failed; inspect results/validation_report.md")
        mark_done(config, "step005", outputs, details)
        logger.log("Step 005 PASS; RUN_READY created")
        return details
