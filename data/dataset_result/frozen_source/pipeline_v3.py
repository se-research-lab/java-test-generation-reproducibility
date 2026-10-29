#!/usr/bin/env python3
"""CLASSES2TEST research pipeline V3.

One entry point for backup, metadata reconstruction, deterministic repository
screening, module-aware build validation, class sampling, validation, and
reporting.  The program never edits V2 or repository source/build files.

The default full command is intentionally explicit:

    python pipeline_v3.py all

Use ``self-test`` and ``smoke`` before the full run.  Every durable step writes
state below data_v3/state and can be resumed by running ``all`` again.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence


PROGRAM_VERSION = "3.0.0"
SELECTION_ALGORITHM = "sha256_repo_balanced_v3"
COMPLEXITY_ALGORITHM = "relative_halves_maxcc_sumcc_v1"
CSV_ENCODING = "utf-8-sig"  # Excel-friendly while remaining valid UTF-8.


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    dataset_root: Path
    output_root: Path
    env_file: Path | None = None
    seed: int = 42
    target_repositories: int = 30
    minimum_unique_classes: int = 12
    main_per_repository: int = 10
    backup_per_repository: int = 2
    min_nloc: int = 5
    max_nloc: int = 500
    maximum_java_version: int = 8
    clone_timeout_seconds: int = 600
    build_timeout_seconds: int = 900
    transient_retries: int = 2
    metadata_workers: int = 16
    keep_failed_repositories: bool = False
    allow_android: bool = False
    maven_settings: Path | None = None
    repository_limit: int | None = None
    skip_backup: bool = False

    @property
    def dataset_dir(self) -> Path:
        nested = self.dataset_root / "dataset"
        return nested if nested.is_dir() else self.dataset_root

    def public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key, value in list(result.items()):
            if isinstance(value, Path):
                result[key] = value.as_posix()
        result["program_version"] = PROGRAM_VERSION
        result["selection_algorithm"] = SELECTION_ALGORITHM
        result["complexity_algorithm"] = COMPLEXITY_ALGORITHM
        return result


class PipelineError(RuntimeError):
    """A controlled pipeline failure that should be shown without traceback."""


class RunLogger:
    def __init__(self, output_root: Path, command: str) -> None:
        log_dir = output_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = log_dir / f"pipeline_{command}_{stamp}.log"

    def log(self, message: str) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_relative_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    parts: list[str] = []
    for part in PurePosixPath(text).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def class_key(repo_id: Any, focal_path: Any) -> str:
    return f"{str(repo_id).strip()}:{normalize_relative_path(focal_path).casefold()}"


def stable_hash(namespace: str, seed: int, value: str) -> str:
    material = f"{namespace}|{seed}|{value}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def atomic_write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    atomic_write_text(path, content)


def atomic_write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding=CSV_ENCODING, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})
    os.replace(temporary, path)


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ";".join(str(item) for item in value)
    if value is None:
        return ""
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding=CSV_ENCODING, newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise PipelineError(f"Invalid JSONL at {path}:{line_number}: {error}") from error
    return rows


def append_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding=CSV_ENCODING, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_remove_tree(path: Path, owned_root: Path) -> None:
    resolved = path.resolve()
    root = owned_root.resolve()
    if resolved == root or not is_relative_to(resolved, root):
        raise PipelineError(f"Refusing unsafe recursive delete: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def natural_repo_key(value: str) -> tuple[int, str]:
    return (0, f"{int(value):020d}") if value.isdigit() else (1, value.casefold())


def config_fingerprint(settings: Settings) -> str:
    encoded = json.dumps(settings.public_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def mark_done(settings: Settings, step: str, details: dict[str, Any] | None = None) -> None:
    payload = {
        "step": step,
        "completed_at": utc_now(),
        "program_version": PROGRAM_VERSION,
        "config_fingerprint": config_fingerprint(settings),
        "details": details or {},
    }
    atomic_write_json(settings.output_root / "state" / f"{step}.done.json", payload)


def done(settings: Settings, step: str) -> bool:
    marker = settings.output_root / "state" / f"{step}.done.json"
    if not marker.exists():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        return payload.get("config_fingerprint") == config_fingerprint(settings)
    except (OSError, json.JSONDecodeError):
        return False


def create_layout(settings: Settings) -> None:
    for relative in (
        "logs/build",
        "logs/clone",
        "logs/submodules",
        "state/repo_metrics",
        "repos/working",
        "repos/successful",
        "repos/failed",
        "results",
    ):
        (settings.output_root / relative).mkdir(parents=True, exist_ok=True)


def command_available(command: str, env: dict[str, str] | None = None) -> str:
    resolved = shutil.which(command, path=(env or {}).get("PATH"))
    return resolved or ""


def load_java_environment_file(path: Path | None) -> dict[str, str]:
    """Load only non-secret JDK location keys from an env file."""
    allowed = {"JAVA_HOME", "JAVA6_HOME", "JAVA7_HOME", "JAVA8_HOME"}
    values: dict[str, str] = {}
    if not path or not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in allowed:
            values[key] = value.strip().strip('"').strip("'")
    return values


def configured_environment(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    env.update(load_java_environment_file(settings.env_file))
    return env


def process_environment(settings: Settings, requested_java: int | None = None) -> dict[str, str]:
    env = configured_environment(settings)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["CI"] = "true"
    for uncontrolled in ("_JAVA_OPTIONS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS"):
        env.pop(uncontrolled, None)
    env["MAVEN_OPTS"] = "-Xmx2048m -Dfile.encoding=UTF-8"
    env["GRADLE_OPTS"] = "-Xmx2048m -Dfile.encoding=UTF-8"
    desired = requested_java if requested_java in (6, 7, 8) else 8
    candidates = [f"JAVA{desired}_HOME", "JAVA8_HOME", "JAVA_HOME"]
    for name in candidates:
        home = env.get(name)
        if home and Path(home).is_dir():
            env["JAVA_HOME"] = home
            env["PATH"] = str(Path(home) / "bin") + os.pathsep + env.get("PATH", "")
            break
    return env


def run_process(
    args: Sequence[str],
    cwd: Path | None,
    env: dict[str, str],
    timeout: int,
) -> tuple[int, str, str, float]:
    command = [str(item) for item in args]
    if command and not Path(command[0]).is_absolute():
        resolved_executable = shutil.which(command[0], path=env.get("PATH"))
        if resolved_executable:
            command[0] = resolved_executable
    if os.name == "nt" and command and command[0].lower().endswith((".cmd", ".bat")):
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "call", *command]
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
        return completed.returncode, completed.stdout, completed.stderr, time.time() - started
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode("utf-8", "replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode("utf-8", "replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        return 124, stdout, stderr + f"\nPROCESS_TIMEOUT_AFTER_{timeout}_SECONDS", time.time() - started
    except OSError as error:
        return 127, "", f"PROCESS_START_ERROR: {error}", time.time() - started


FAILURE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("timeout", (r"PROCESS_TIMEOUT_AFTER_", r"timed?\s*out", r"timeout has been exceeded")),
    ("disk_full", (r"no space left on device", r"not enough space on the disk", r"disk quota exceeded")),
    ("out_of_memory", (r"outofmemoryerror", r"java heap space", r"gc overhead limit exceeded", r"unable to create native thread")),
    ("path_too_long", (r"filename or extension is too long", r"path too long", r"cannot create a file when that file already exists")),
    ("file_permission", (r"access is denied", r"permission denied", r"read-only file system")),
    ("windows_symlink_privilege", (r"a required privilege is not held by the client", r"symbolic link.*privilege")),
    ("file_locked", (r"the process cannot access the file because it is being used", r"unable to delete file.*locked")),
    ("corrupted_download_or_cache", (r"zip end header not found", r"error in opening zip file", r"invalid loc header", r"checksum verification failed")),
    ("network_dns", (r"could not resolve host", r"unknownhostexception", r"temporary failure in name resolution")),
    ("network_proxy", (r"proxy authentication required", r"407 proxy", r"unable to tunnel through proxy")),
    ("network_rate_limited", (r"status code:\s*429", r"http.*429", r"too many requests")),
    ("network_transient", (r"connection reset", r"connection refused", r"network is unreachable", r"status code:\s*(?:500|502|503|504)")),
    ("ssl_error", (r"pkix path building failed", r"sslhandshakeexception", r"unable to find valid certification path", r"certificate.*expired")),
    ("insecure_http_repository_blocked", (r"maven-default-http-blocker", r"blocked mirror for repositories")),
    ("obsolete_repository_unavailable", (r"jcenter\.bintray\.com", r"dl\.bintray\.com", r"bintray.*(?:not found|gone|403)")),
    ("auth_or_private_dependency", (r"authentication failed", r"unauthorized", r"forbidden", r"status code:\s*(?:401|403)", r"not authorized")),
    ("missing_git_submodule", (r"child module .* does not exist", r"no url found for submodule path", r"not initialized.*submodule")),
    ("git_lfs_missing", (r"git-lfs", r"pointer file", r"smudge filter lfs failed")),
    ("vcs_metadata_required", (r"not a git repository", r"git describe.*failed", r"cannot determine git revision")),
    ("android_sdk_required", (r"sdk location not found", r"android_home", r"compilesdkversion is not specified", r"failed to find target with hash string 'android", r"failed to apply plugin 'com\.android", r"com\.android\.tools\.build:gradle")),
    ("docker_required", (r"cannot connect to (?:the )?docker", r"docker daemon", r"docker.*not found", r"testcontainers.*could not find")),
    ("frontend_required", (r"frontend-maven-plugin", r"npm(?:\.cmd)?.*(?:failed|not found|not recognized)", r"yarn.*(?:failed|not found|not recognized)", r"node(?:\.exe)?.*not recognized")),
    ("external_service_required", (r"connection refused.*(?:localhost|127\.0\.0\.1)", r"kafka.*(?:unavailable|connection)", r"redis.*connection", r"database.*connection")),
    ("native_tool_missing", (r"protoc.*(?:not found|not recognized)", r"cmake.*(?:not found|not recognized)", r"gcc.*(?:not found|not recognized)", r"make.*(?:not found|not recognized)")),
    ("unsupported_operating_system", (r"unsupported operating system", r"not supported on windows", r"requires linux", r"os\.name.*not supported")),
    ("missing_local_build_configuration", (r"local\.properties.*(?:cannot find|not found|does not exist)", r"credentials\.gradle.*(?:cannot find|not found)")),
    ("missing_environment_variable", (r"environment variable .* (?:is )?not set", r"could not resolve placeholder", r"missing required property")),
    ("wrapper_download_failed", (r"could not download.*(?:gradle|maven)", r"distributionurl", r"mavenwrapperdownloader", r"gradle-wrapper\.jar")),
    ("jdk_version_range_mismatch", (r"requirejavaversion failed", r"detected jdk .* is .*not in the allowed range", r"maven-enforcer-plugin.*enforce.*java")),
    ("jvm_argument_incompatible", (r"could not create the java virtual machine", r"unrecognized option: --add-(?:exports|opens)", r"unrecognized vm option")),
    ("wrong_jdk_runtime", (r"unsupported class file major version", r"source option (?:1\.)?[5-7] is no longer supported", r"java_home is not defined correctly", r"could not determine java version")),
    ("requires_java_above_8", (r"invalid (?:target|source) release:\s*(?:9|1[0-9]|2[0-9])", r"release version (?:9|1[0-9]|2[0-9]) not supported", r"requires java (?:9|1[0-9]|2[0-9])")),
    ("build_tool_version_incompatible", (r"minimum supported gradle version", r"needs gradle version .* or higher", r"maximum supported gradle jvm version", r"could not generate a decorated class", r"no such property:.*for class: org\.gradle", r"unable to resolve class org\.apache\.ivy", r"plugin with id 'maven' not found", r"shadowjavaplugin\$shadowjavalibrary", r"unresolved reference: (?:compileroptions|jvmtarget)", r"cannot add task 'wrapper'.*already exists", r"'buildsrc' cannot be used as a project name")),
    ("gradle_daemon_crashed", (r"gradle build daemon disappeared unexpectedly", r"daemon.*disappeared", r"daemon.*stopped unexpectedly")),
    ("compiler_plugin_incompatible", (r"illegalaccesserror.*(?:lombok|mapstruct|kapt)", r"annotation processor.*(?:failed|exception)", r"inaccessibleobjectexception", r"does not export.*to unnamed module")),
    ("toolchain_missing", (r"no matching toolchains found", r"cannot find matching toolchain", r"jdk toolchain.*not found")),
    ("plugin_resolution_failed", (r"could not resolve plugin", r"plugin .* was not found", r"no plugin found for prefix", r"unknown plugin")),
    ("parent_pom_unavailable", (r"non-resolvable parent pom", r"parent\.relativepath.*points at wrong local pom")),
    ("missing_dependency", (r"could not find artifact", r"could not resolve artifact", r"could not find .* in", r"unresolved dependency")),
    ("dependency_resolution_failed", (r"could not resolve (?:all )?dependencies", r"could not resolve all files for configuration", r"failed to collect dependencies", r"dependency resolution failed", r"could not transfer artifact")),
    ("module_not_found", (r"could not find the selected project in the reactor", r"project .* not found in root project", r"task .* not found", r"cannot locate tasks that match")),
    ("malformed_build_configuration", (r"non-parseable pom", r"malformed pom", r"could not compile build file", r"startup failed:", r"unknown lifecycle phase")),
    ("generated_sources_missing", (r"generated sources.*(?:missing|not found)", r"cannot find symbol.*generated", r"package .*generated.* does not exist")),
    ("checkstyle_failed", (r"maven-checkstyle-plugin", r"checkstyle.*(?:failed|violation|error)")),
    ("spotless_failed", (r"spotlesscheck", r"spotless.*(?:failed|violations)")),
    ("license_failed", (r"license.*(?:header|check).*(?:failed|missing)", r"license-maven-plugin.*failure")),
    ("signing_failed", (r"gpg.*(?:failed|signing)", r"failed to sign")),
    ("test_execution_unexpected", (r"tests run:.*failures:\s*[1-9]", r"there were failing tests")),
    ("test_compile_failed", (r"failed to compile test", r":compiletestjava failed", r"testcompile.*failure", r"test compilation failure")),
    ("source_compile_failed", (r"\bcompilation failure\b", r"\bcompilation error\b", r"javac.*failed", r"failed to execute goal.*compiler-plugin", r":compilejava failed")),
    ("build_tool_missing", (r"PROCESS_START_ERROR", r"is not recognized as an internal or external command", r"command not found")),
]


TRANSIENT_FAILURES = {
    "timeout",
    "network_dns",
    "network_proxy",
    "network_rate_limited",
    "network_transient",
    "ssl_error",
    "wrapper_download_failed",
}


def classify_failure(text: str) -> str:
    lowered = text.casefold()
    for category, patterns in FAILURE_PATTERNS:
        if any(re.search(pattern, lowered, re.IGNORECASE | re.DOTALL) for pattern in patterns):
            return category
    return "unknown_build_failure"


def redact(text: str) -> str:
    text = re.sub(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@", r"\1***:***@", text)
    text = re.sub(r"(?i)(authorization:\s*(?:basic|bearer)\s+)\S+", r"\1***", text)
    return text


def preflight(settings: Settings, logger: RunLogger) -> dict[str, Any]:
    create_layout(settings)
    if not settings.dataset_dir.is_dir():
        raise PipelineError(f"Dataset directory not found: {settings.dataset_dir}")
    if settings.output_root.resolve() in (settings.dataset_root.resolve(), (settings.workspace_root / "data_v2").resolve()):
        raise PipelineError("output_root must be separate from dataset_root and data_v2")
    version_env = process_environment(settings)
    tools = {name: command_available(name, version_env) for name in ("git", "java", "mvn", "gradle")}
    tool_versions: dict[str, str] = {}
    version_commands = {
        "git": ["git", "--version"],
        "java": ["java", "-version"],
        "mvn": ["mvn", "-version"],
        "gradle": ["gradle", "-version"],
    }
    for name, command in version_commands.items():
        if not tools[name]:
            tool_versions[name] = "unavailable"
            continue
        code, stdout, stderr, _ = run_process(command, None, version_env, 30)
        combined = redact((stdout + "\n" + stderr).strip())
        tool_versions[name] = combined if code == 0 else f"version-check-exit-{code}: {combined[-1000:]}"
    try:
        import lizard  # type: ignore

        lizard_status = getattr(lizard, "__version__", "installed-version-not-exposed")
    except ImportError as error:
        raise PipelineError("Python package 'lizard' is required") from error
    usage = shutil.disk_usage(settings.workspace_root)
    report = {
        "timestamp": utc_now(),
        "python": sys.version,
        "platform": sys.platform,
        "tools": tools,
        "tool_versions": tool_versions,
        "lizard": lizard_status,
        "disk_free_bytes": usage.free,
        "settings": settings.public_dict(),
    }
    atomic_write_json(settings.output_root / "state" / "preflight.json", report)
    if not tools["git"]:
        raise PipelineError("git is required for repository screening")
    if not tools["java"]:
        raise PipelineError("Java is required for repository screening")
    java_output = tool_versions.get("java", "")
    java_match = re.search(r'version\s+"(?:1\.)?(\d+)', java_output, re.IGNORECASE)
    effective_java = int(java_match.group(1)) if java_match else None
    if effective_java is None or effective_java > settings.maximum_java_version:
        raise PipelineError(
            f"Preflight selected unsupported Java runtime ({effective_java or 'unknown'}). "
            f"Configure Java <= {settings.maximum_java_version} in {settings.env_file or 'JAVA_HOME'}."
        )
    logger.log(f"Preflight PASS; free disk {usage.free / (1024**3):.1f} GiB")
    mark_done(settings, "preflight", {"disk_free_bytes": usage.free})
    return report


def directory_inventory(root: Path) -> tuple[int, int]:
    count = 0
    size = 0
    if not root.exists():
        return count, size
    for path in root.rglob("*"):
        if path.is_file():
            count += 1
            try:
                size += path.stat().st_size
            except OSError:
                pass
    return count, size


def backup_v2(settings: Settings, logger: RunLogger) -> Path | None:
    if settings.skip_backup:
        logger.log("Backup explicitly skipped by --skip-backup; this must be disclosed")
        mark_done(settings, "backup", {"skipped": True})
        return None
    state_file = settings.output_root / "state" / "backup.json"
    if done(settings, "backup") and state_file.exists():
        payload = json.loads(state_file.read_text(encoding="utf-8"))
        logger.log(f"Backup already verified: {payload['destination']}")
        return Path(payload["destination"])

    source_v2 = settings.workspace_root / "data_v2"
    source_pipeline = settings.workspace_root / "research_pipeline"
    if not source_v2.is_dir() or not source_pipeline.is_dir():
        raise PipelineError("data_v2 or research_pipeline is missing; refusing incomplete backup")

    source_files, source_bytes = directory_inventory(source_v2)
    free = shutil.disk_usage(settings.workspace_root).free
    required = source_bytes + 1024**3
    if free < required:
        raise PipelineError(
            f"Insufficient disk for backup: need approximately {required / (1024**3):.1f} GiB, "
            f"free {free / (1024**3):.1f} GiB"
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = settings.workspace_root / f"data_v2_backup_pre_v3_{stamp}"
    destination.mkdir(parents=False, exist_ok=False)
    logger.log(f"Backing up V2 to {destination}")

    shutil.copytree(source_v2, destination / "data_v2", copy_function=shutil.copy2)
    shutil.copytree(source_pipeline, destination / "research_pipeline", copy_function=shutil.copy2)
    if Path(__file__).resolve().parent.exists():
        shutil.copytree(Path(__file__).resolve().parent, destination / "research_pipeline_v3_snapshot", copy_function=shutil.copy2)
    for name in ("context.md", "HDSD.md"):
        source = settings.workspace_root / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    proposal = settings.workspace_root / "classes2test" / "proposal (2).md"
    if proposal.is_file():
        (destination / "classes2test").mkdir(exist_ok=True)
        shutil.copy2(proposal, destination / "classes2test" / proposal.name)

    manifest_rows: list[dict[str, Any]] = []
    for path in sorted(destination.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_file():
            stat = path.stat()
            manifest_rows.append({
                "relative_path": path.relative_to(destination).as_posix(),
                "size_bytes": stat.st_size,
                "modified_ns": stat.st_mtime_ns,
            })
    atomic_write_csv(destination / "backup_manifest.csv", manifest_rows, ["relative_path", "size_bytes", "modified_ns"])

    critical = [
        destination / "context.md",
        destination / "HDSD.md",
        destination / "classes2test" / "proposal (2).md",
        destination / "research_pipeline" / "config.yaml",
        destination / "data_v2" / "class_sampling_manifest_seed42.csv",
        destination / "data_v2" / "class_metrics.csv",
        destination / "data_v2" / "successful_repos_manifest.csv",
    ]
    checksum_lines = [f"{sha256_file(path)}  {path.relative_to(destination).as_posix()}" for path in critical if path.is_file()]
    atomic_write_text(destination / "SHA256SUMS.txt", "\n".join(checksum_lines) + "\n")

    copied_files, copied_bytes = directory_inventory(destination / "data_v2")
    if copied_files != source_files or copied_bytes != source_bytes:
        raise PipelineError(
            f"Backup verification failed: source {source_files}/{source_bytes}, copy {copied_files}/{copied_bytes}"
        )
    log = (
        "# V2 backup log\n\n"
        f"- Completed: {utc_now()}\n"
        f"- Source: `{source_v2}`\n"
        f"- Destination: `{destination}`\n"
        f"- V2 files: {source_files}\n"
        f"- V2 bytes: {source_bytes}\n"
        "- Verification: PASS (file count and total byte count)\n"
        "- Critical artifact checksums: `SHA256SUMS.txt`\n"
    )
    atomic_write_text(destination / "backup_log.md", log)
    payload = {"destination": str(destination), "files": source_files, "bytes": source_bytes, "completed_at": utc_now()}
    atomic_write_json(state_file, payload)
    mark_done(settings, "backup", payload)
    logger.log(f"Backup PASS: {source_files} V2 files, {source_bytes} bytes")
    return destination


RAW_MAPPING_FIELDS = [
    "repo_id", "repo_url", "json_file", "parse_status", "error", "class_key",
    "focal_class", "focal_path", "test_class", "test_path", "focal_method", "test_case",
]
UNIQUE_CLASS_FIELDS = [
    "repo_id", "repo_url", "class_key", "focal_class", "focal_path", "mapping_count",
    "source_json_files", "focal_methods", "test_cases", "test_classes", "test_paths",
    "public_method_count_metadata",
]


def reconstruct_frame(settings: Settings, logger: RunLogger, output_root: Path | None = None) -> dict[str, Any]:
    target = output_root or settings.output_root
    target.mkdir(parents=True, exist_ok=True)
    if output_root is None and done(settings, "step001"):
        logger.log("Step 001 already complete; using stored unique frame")
        return json.loads((settings.output_root / "state" / "step001_summary.json").read_text(encoding="utf-8"))

    repo_dirs = sorted((path for path in settings.dataset_dir.iterdir() if path.is_dir() and path.name != ".git"), key=lambda p: natural_repo_key(p.name))
    if settings.repository_limit:
        repo_dirs = repo_dirs[: settings.repository_limit]
    def list_json_paths(repo_dir: Path) -> list[Path]:
        try:
            with os.scandir(repo_dir) as entries:
                paths = [Path(entry.path) for entry in entries if entry.is_file() and entry.name.casefold().endswith(".json")]
            return sorted(paths, key=lambda path: path.name.casefold())
        except OSError:
            return []

    logger.log(f"Step 001 enumerating {len(repo_dirs)} repository directories with {settings.metadata_workers} workers")
    with ThreadPoolExecutor(max_workers=settings.metadata_workers) as list_executor:
        repo_json_lists = list(list_executor.map(list_json_paths, repo_dirs))
    json_file_count = sum(len(paths) for paths in repo_json_lists)

    def read_payload(path: Path) -> tuple[bytes | None, str]:
        try:
            return path.read_bytes(), ""
        except OSError as error:
            return None, f"{type(error).__name__}: {error}"

    logger.log(f"Step 001 reading {json_file_count} JSON files with {settings.metadata_workers} workers")
    read_executor = ThreadPoolExecutor(max_workers=settings.metadata_workers)
    groups: dict[str, dict[str, Any]] = {}
    repo_urls: dict[str, str] = {}
    raw_path = target / "raw_mapping_index.csv"
    raw_tmp = raw_path.with_name(raw_path.name + ".tmp")
    total_json = 0
    parse_errors = 0
    dataset_digest = hashlib.sha256()

    with raw_tmp.open("w", encoding=CSV_ENCODING, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_MAPPING_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for repo_index, repo_dir in enumerate(repo_dirs):
            json_paths = repo_json_lists[repo_index]
            payloads = read_executor.map(read_payload, json_paths)
            for json_path, (content, read_error) in zip(json_paths, payloads):
                total_json += 1
                raw: dict[str, Any] = {
                    "repo_id": repo_dir.name,
                    "json_file": json_path.name,
                    "parse_status": "error",
                    "error": "",
                }
                try:
                    if content is None:
                        raise OSError(read_error)
                    dataset_digest.update(repo_dir.name.encode("utf-8") + b"\0" + json_path.name.encode("utf-8") + b"\0" + content)
                    data = json.loads(content.decode("utf-8-sig"))
                    repository = data.get("repository") or {}
                    repo_id = str(repository.get("repo_id") or repo_dir.name)
                    repo_url = str(repository.get("url") or "").strip()
                    focal = data.get("focal_class") or {}
                    test = data.get("test_class") or {}
                    focal_method = data.get("focal_method") or {}
                    test_case = data.get("test_case") or {}
                    focal_path = normalize_relative_path(focal.get("file"))
                    if not focal_path or not focal.get("identifier"):
                        raise ValueError("missing focal_class.identifier or focal_class.file")
                    key = class_key(repo_id, focal_path)
                    if repo_url and not repo_urls.get(repo_id):
                        repo_urls[repo_id] = repo_url
                    raw.update({
                        "repo_id": repo_id,
                        "repo_url": repo_url,
                        "parse_status": "ok",
                        "class_key": key,
                        "focal_class": focal.get("identifier", ""),
                        "focal_path": focal_path,
                        "test_class": test.get("identifier", ""),
                        "test_path": normalize_relative_path(test.get("file")),
                        "focal_method": focal_method.get("class_method_signature") or focal_method.get("full_signature") or focal_method.get("signature") or "",
                        "test_case": test_case.get("class_method_signature") or test_case.get("full_signature") or test_case.get("signature") or "",
                    })
                    group = groups.setdefault(key, {
                        "repo_id": repo_id,
                        "repo_url": repo_url,
                        "class_key": key,
                        "focal_class": str(focal.get("identifier")),
                        "focal_path": focal_path,
                        "source_json_files": set(),
                        "focal_methods": set(),
                        "test_cases": set(),
                        "test_classes": set(),
                        "test_paths": set(),
                        "public_method_count_metadata": 0,
                    })
                    if repo_url and not group.get("repo_url"):
                        group["repo_url"] = repo_url
                    group["source_json_files"].add(json_path.name)
                    for field, value in (
                        ("focal_methods", raw["focal_method"]),
                        ("test_cases", raw["test_case"]),
                        ("test_classes", raw["test_class"]),
                        ("test_paths", raw["test_path"]),
                    ):
                        if value:
                            group[field].add(str(value))
                    public_methods = 0
                    for method in focal.get("methods") or []:
                        modifiers = str(method.get("modifiers") or "")
                        if re.search(r"\bpublic\b", modifiers) and not bool(method.get("constructor")):
                            public_methods += 1
                    group["public_method_count_metadata"] = max(group["public_method_count_metadata"], public_methods)
                except Exception as error:  # Per-file errors must never abort the scan.
                    parse_errors += 1
                    raw["error"] = f"{type(error).__name__}: {error}"[:1000]
                writer.writerow({key: csv_value(raw.get(key, "")) for key in RAW_MAPPING_FIELDS})
    read_executor.shutdown(wait=True)
    os.replace(raw_tmp, raw_path)

    unique_rows: list[dict[str, Any]] = []
    repo_counts: Counter[str] = Counter()
    for key in sorted(groups, key=lambda item: (natural_repo_key(str(groups[item]["repo_id"])), item)):
        group = groups[key]
        row = dict(group)
        for field in ("source_json_files", "focal_methods", "test_cases", "test_classes", "test_paths"):
            values = sorted(group[field], key=str.casefold)
            row[field] = ";".join(values)
        row["mapping_count"] = len(group["source_json_files"])
        unique_rows.append(row)
        repo_counts[str(group["repo_id"])] += 1
    atomic_write_csv(target / "unique_focal_class_frame.csv", unique_rows, UNIQUE_CLASS_FIELDS)

    summary_rows = []
    for repo_id in sorted(repo_counts, key=natural_repo_key):
        count = repo_counts[repo_id]
        summary_rows.append({
            "repo_id": repo_id,
            "repo_url": repo_urls.get(repo_id, ""),
            "unique_mapped_focal_count": count,
            "metadata_prefilter_pass": count >= settings.minimum_unique_classes,
            "minimum_required": settings.minimum_unique_classes,
        })
    atomic_write_csv(
        target / "repo_candidate_summary.csv",
        summary_rows,
        ["repo_id", "repo_url", "unique_mapped_focal_count", "metadata_prefilter_pass", "minimum_required"],
    )
    summary = {
        "repositories_scanned": len(repo_dirs),
        "mapping_json_files": total_json,
        "parse_errors": parse_errors,
        "unique_focal_classes": len(unique_rows),
        "prefilter_repositories": sum(1 for row in summary_rows if row["metadata_prefilter_pass"]),
        "dataset_content_sha256": dataset_digest.hexdigest(),
    }
    atomic_write_json(target / "state" / "step001_summary.json", summary)
    if output_root is None:
        mark_done(settings, "step001", summary)
    logger.log(
        f"Step 001: {total_json} mappings -> {len(unique_rows)} unique focal classes; "
        f"{parse_errors} parse errors; {summary['prefilter_repositories']} candidate repos"
    )
    return summary


QUEUE_FIELDS = [
    "order_index", "repo_id", "repo_url", "unique_mapped_focal_count", "repo_order_hash",
    "status", "failure_category", "failure_detail", "clone_status", "commit_sha", "java_version",
    "qualified_build_scopes", "unique_eligible_buildable_count", "selected_for_sample", "updated_at",
]


def create_queue(settings: Settings, logger: RunLogger) -> None:
    if done(settings, "step002"):
        logger.log("Step 002 already complete; using stored repository queue")
        return
    summary_path = settings.output_root / "repo_candidate_summary.csv"
    if not summary_path.exists():
        raise PipelineError("Step 001 output missing")
    candidates = []
    for row in read_csv(summary_path):
        if row["metadata_prefilter_pass"].casefold() != "true" or not row.get("repo_url"):
            continue
        row["repo_order_hash"] = stable_hash("repo-order-v3", settings.seed, row["repo_id"])
        candidates.append(row)
    candidates.sort(key=lambda row: (row["repo_order_hash"], natural_repo_key(row["repo_id"])))
    queue = []
    for index, row in enumerate(candidates):
        queue.append({
            "order_index": index,
            "repo_id": row["repo_id"],
            "repo_url": row["repo_url"],
            "unique_mapped_focal_count": row["unique_mapped_focal_count"],
            "repo_order_hash": row["repo_order_hash"],
            "status": "pending",
            "failure_category": "",
            "failure_detail": "",
            "clone_status": "pending",
            "commit_sha": "",
            "java_version": "",
            "qualified_build_scopes": "",
            "unique_eligible_buildable_count": 0,
            "selected_for_sample": False,
            "updated_at": utc_now(),
        })
    atomic_write_csv(settings.output_root / "repo_processing_order_seed42.csv", queue, QUEUE_FIELDS)
    mark_done(settings, "step002", {"queued_repositories": len(queue)})
    logger.log(f"Step 002: queued {len(queue)} deterministic candidate repositories")


def read_text_lossy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_java_version(build_files: Sequence[Path]) -> tuple[int | None, str]:
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
                properties = {}
            raw_values = []
            for tag in ("maven.compiler.release", "maven.compiler.source", "maven.compiler.target", "java.version", "source", "target", "release"):
                raw_values.extend(re.findall(rf"<{re.escape(tag)}>\s*([^<]+)\s*</{re.escape(tag)}>", text, re.IGNORECASE))
            for raw in raw_values:
                raw = raw.strip()
                match_property = re.fullmatch(r"\$\{([^}]+)\}", raw)
                if match_property:
                    raw = properties.get(match_property.group(1), raw)
                parsed = parse_java_number(raw)
                if parsed:
                    values.append((parsed, path.as_posix()))
            for block in re.findall(r"<requireJavaVersion\b.*?</requireJavaVersion>", text, re.IGNORECASE | re.DOTALL):
                match = re.search(r"<version>\s*([\[(]?\s*(?:1\.)?\d{1,2})", block, re.IGNORECASE)
                if match:
                    parsed = parse_java_number(match.group(1))
                    if parsed:
                        values.append((parsed, path.as_posix() + "#maven-enforcer"))
        else:
            patterns = (
                r"(?:sourceCompatibility|targetCompatibility)\s*=\s*(?:JavaVersion\.VERSION_)?['\"]?([0-9_.]+)",
                r"JavaLanguageVersion\.of\((\d+)\)",
                r"jvmToolchain\((\d+)\)",
                r"languageVersion\.set\(JavaLanguageVersion\.of\((\d+)\)\)",
            )
            for pattern in patterns:
                for raw in re.findall(pattern, text, re.IGNORECASE):
                    parsed = parse_java_number(str(raw).replace("VERSION_", "").replace("_", "."))
                    if parsed:
                        values.append((parsed, path.as_posix()))
    if not values:
        return None, "unknown"
    highest = max(values, key=lambda item: item[0])
    return highest


def parse_java_number(raw: str) -> int | None:
    match = re.search(r"(?<!\d)(?:1\.)?(\d{1,2})(?!\d)", raw.strip())
    if not match:
        return None
    value = int(match.group(1))
    return value if 5 <= value <= 30 else None


def strip_java_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def analyze_java_file(path: Path, frame_row: dict[str, str], settings: Settings) -> dict[str, Any]:
    import lizard  # type: ignore

    result: dict[str, Any] = {
        "repo_id": frame_row["repo_id"],
        "repo_url": frame_row.get("repo_url", ""),
        "class_key": frame_row["class_key"],
        "focal_class": frame_row["focal_class"],
        "focal_path": frame_row["focal_path"],
        "mapping_count": int(frame_row.get("mapping_count") or 0),
        "source_json_files": frame_row.get("source_json_files", ""),
        "exact_path_exists": path.is_file(),
        "metric_status": "error",
        "eligible_for_sampling": False,
        "exclusion_reason": "",
    }
    if not path.is_file():
        result["exclusion_reason"] = "exact_focal_path_not_found"
        return result
    try:
        analysis = lizard.analyze_file(str(path))
        text = read_text_lossy(path)
        clean = strip_java_comments(text)
        simple_name = str(frame_row["focal_class"]).split(".")[-1]
        functions = list(analysis.function_list)
        cc_values = [int(function.cyclomatic_complexity) for function in functions]
        metadata_public = int(frame_row.get("public_method_count_metadata") or 0)
        public_regex = len(re.findall(r"\bpublic\s+(?!class\b|interface\b|enum\b)[\w<>,.?\[\]\s]+\s+\w+\s*\(", clean))
        result.update({
            "metric_status": "success",
            "nloc": int(analysis.nloc),
            "token_count": int(analysis.token_count),
            "method_count": len(functions),
            "max_method_cc": max(cc_values) if cc_values else 0,
            "sum_method_cc": sum(cc_values),
            "avg_method_cc": (sum(cc_values) / len(cc_values)) if cc_values else 0.0,
            "public_method_count": max(metadata_public, public_regex),
            "is_interface": bool(re.search(rf"\binterface\s+{re.escape(simple_name)}\b", clean)),
            "is_enum": bool(re.search(rf"\benum\s+{re.escape(simple_name)}\b", clean)),
            "is_generated": "@Generated" in text or "generated code" in text.casefold() or "/generated/" in path.as_posix().casefold(),
        })
        reason = ""
        if result["nloc"] < settings.min_nloc or result["nloc"] > settings.max_nloc:
            reason = "nloc_out_of_bounds"
        elif result["public_method_count"] < 1:
            reason = "no_public_method"
        elif result["is_interface"]:
            reason = "is_interface"
        elif result["is_enum"]:
            reason = "is_enum"
        elif result["is_generated"]:
            reason = "is_generated_code"
        result["exclusion_reason"] = reason
        result["eligible_for_sampling"] = not reason
    except Exception as error:
        result["exclusion_reason"] = f"metric_error:{type(error).__name__}"
        result["metric_error"] = str(error)[:1000]
    return result


def ancestors_within(start: Path, root: Path) -> Iterator[Path]:
    current = start.resolve()
    root_resolved = root.resolve()
    while True:
        if not is_relative_to(current, root_resolved):
            return
        yield current
        if current == root_resolved:
            return
        current = current.parent


def find_build_scope(repo_dir: Path, focal_file: Path) -> dict[str, str] | None:
    nearest_maven: Path | None = None
    nearest_gradle: Path | None = None
    ancestors = list(ancestors_within(focal_file.parent, repo_dir))
    for directory in ancestors:
        if nearest_maven is None and (directory / "pom.xml").is_file():
            nearest_maven = directory
        if nearest_gradle is None and ((directory / "build.gradle").is_file() or (directory / "build.gradle.kts").is_file()):
            nearest_gradle = directory
    if nearest_maven is None and nearest_gradle is None:
        return None
    if nearest_maven is not None:
        module_dir = nearest_maven
        reactor_root = module_dir
        for directory in reversed(ancestors):
            if (directory / "pom.xml").is_file():
                reactor_root = directory
                break
        relative = module_dir.relative_to(reactor_root).as_posix()
        return {
            "build_tool": "maven",
            "module_dir": module_dir.relative_to(repo_dir).as_posix() or ".",
            "build_root": reactor_root.relative_to(repo_dir).as_posix() or ".",
            "module_selector": relative or ".",
            "scope_key": f"maven:{module_dir.relative_to(repo_dir).as_posix() or '.'}",
        }
    module_dir = nearest_gradle  # type: ignore[assignment]
    gradle_root = module_dir
    for directory in reversed(ancestors):
        if (directory / "settings.gradle").is_file() or (directory / "settings.gradle.kts").is_file():
            gradle_root = directory
            break
    relative = module_dir.relative_to(gradle_root)
    selector = ":".join(relative.parts)
    return {
        "build_tool": "gradle",
        "module_dir": module_dir.relative_to(repo_dir).as_posix() or ".",
        "build_root": gradle_root.relative_to(repo_dir).as_posix() or ".",
        "module_selector": selector or ".",
        "scope_key": f"gradle:{module_dir.relative_to(repo_dir).as_posix() or '.'}",
    }


def find_wrapper(repo_dir: Path, build_root: Path, build_tool: str) -> Path | None:
    names = ("mvnw.cmd", "mvnw") if build_tool == "maven" else ("gradlew.bat", "gradlew")
    for directory in ancestors_within(build_root, repo_dir):
        for name in names:
            path = directory / name
            if path.is_file():
                return path
    return None


MAVEN_BASE_FLAGS = ["-B", "-ntp", "-DskipTests", "-DskipITs"]
MAVEN_SERVICE_FLAGS = [
    "-Dcheckstyle.skip=true", "-Dspotless.check.skip=true", "-Dlicense.skip=true", "-Drat.skip=true",
    "-Dgpg.skip=true", "-DskipNexusStagingDeployMojo=true", "-Ddocker.skip=true", "-DskipDocker",
    "-Dfrontend.skip=true", "-DskipNpm", "-Dskip.npm=true", "-Dskip.yarn=true",
    "-Djacoco.skip=true", "-Dpmd.skip=true", "-Dfindbugs.skip=true", "-Dspotbugs.skip=true",
]
GRADLE_BASE_FLAGS = ["--no-daemon", "--console=plain", "--stacktrace"]
GRADLE_SKIPS = [
    "test", "integrationTest", "check", "checkstyleMain", "checkstyleTest", "spotlessCheck",
    "spotlessJavaCheck", "spotlessKotlinCheck", "licenseHeadersCheck", "pmdMain", "pmdTest",
    "spotbugsMain", "spotbugsTest", "docker", "dockerBuild", "jib", "npmInstall", "yarnInstall",
]


def build_recipes(repo_dir: Path, scope: dict[str, str], settings: Settings) -> list[dict[str, Any]]:
    build_root = repo_dir / scope["build_root"]
    module_dir = repo_dir / scope["module_dir"]
    tool = scope["build_tool"]
    wrapper = find_wrapper(repo_dir, build_root, tool)
    executable = str(wrapper) if wrapper else ("mvn" if tool == "maven" else "gradle")
    source = "wrapper" if wrapper else "recorded_global_environment"
    recipes: list[dict[str, Any]] = []
    if tool == "maven":
        module_pom = module_dir / "pom.xml"
        root_pom = build_root / "pom.xml"
        settings_flags = ["-s", str(settings.maven_settings.resolve())] if settings.maven_settings else []
        local_base = [executable, *MAVEN_BASE_FLAGS, *settings_flags, "-f", str(module_pom), "clean", "test-compile"]
        recipes.append({"name": "maven_module_baseline", "args": local_base, "cwd": build_root, "source": source})
        recipes.append({"name": "maven_module_skip_ancillary", "args": [*local_base[:-2], *MAVEN_SERVICE_FLAGS, "clean", "test-compile"], "cwd": build_root, "source": source})
        if module_dir.resolve() != build_root.resolve():
            selector = scope["module_selector"]
            reactor = [executable, *MAVEN_BASE_FLAGS, *settings_flags, "-f", str(root_pom), "-pl", selector, "-am", "clean", "test-compile"]
            recipes.append({"name": "maven_reactor_module", "args": reactor, "cwd": build_root, "source": source})
            recipes.append({"name": "maven_reactor_skip_ancillary", "args": [*reactor[:-2], *MAVEN_SERVICE_FLAGS, "clean", "test-compile"], "cwd": build_root, "source": source})
    else:
        selector = scope["module_selector"]
        task = "testClasses" if selector == "." else f":{selector}:testClasses"
        clean_task = "clean" if selector == "." else f":{selector}:clean"
        baseline = [executable, *GRADLE_BASE_FLAGS, clean_task, task, "-x", "test"]
        aggressive = [executable, *GRADLE_BASE_FLAGS, clean_task, task]
        for skipped in GRADLE_SKIPS:
            aggressive.extend(["-x", skipped])
        recipes.append({"name": "gradle_module_baseline", "args": baseline, "cwd": build_root, "source": source})
        recipes.append({"name": "gradle_module_skip_ancillary", "args": aggressive, "cwd": build_root, "source": source})
    return recipes


def contains_android_build(scope: dict[str, str], repo_dir: Path) -> bool:
    for directory_name in {scope["module_dir"], scope["build_root"]}:
        directory = repo_dir / directory_name
        for name in ("build.gradle", "build.gradle.kts", "pom.xml"):
            text = read_text_lossy(directory / name).casefold()
            if "com.android.application" in text or "com.android.library" in text or "android-maven-plugin" in text:
                return True
    return False


ATTEMPT_FIELDS = [
    "repo_id", "scope_key", "attempt_no", "recipe", "command_source", "command", "cwd", "exit_code",
    "status", "failure_category", "duration_seconds", "log_path", "started_at", "finished_at",
]


def execute_build_scope(
    repo_id: str,
    repo_dir: Path,
    scope: dict[str, str],
    requested_java: int | None,
    settings: Settings,
    logger: RunLogger,
) -> tuple[bool, str, str, list[dict[str, Any]]]:
    if contains_android_build(scope, repo_dir) and not settings.allow_android:
        return False, "unsupported_android_environment", "Android build excluded by pre-registered protocol", []
    if requested_java in (6, 7):
        profile_home = configured_environment(settings).get(f"JAVA{requested_java}_HOME", "")
        if not profile_home or not Path(profile_home).is_dir():
            return (
                False,
                "required_jdk_profile_unavailable",
                f"Scope requires Java {requested_java}, but JAVA{requested_java}_HOME is not configured",
                [],
            )
    recipes = build_recipes(repo_dir, scope, settings)
    if recipes and recipes[0]["source"] == "recorded_global_environment":
        command = "mvn" if scope["build_tool"] == "maven" else "gradle"
        if not command_available(command):
            return False, "build_tool_missing", f"No wrapper and global {command} is unavailable", []
    env = process_environment(settings, requested_java)
    attempts: list[dict[str, Any]] = []
    final_category = "unknown_build_failure"
    final_detail = ""
    attempt_no = 0
    for recipe in recipes:
        transient_count = 0
        while True:
            attempt_no += 1
            started = utc_now()
            code, stdout, stderr, duration = run_process(recipe["args"], recipe["cwd"], env, settings.build_timeout_seconds)
            finished = utc_now()
            if code == 0:
                dirty_code, dirty_out, dirty_err, _ = run_process(
                    ["git", "status", "--porcelain", "--untracked-files=no"], repo_dir, env, 60
                )
                if dirty_code != 0 or dirty_out.strip():
                    code = 65
                    stderr += (
                        "\nBUILD_MODIFIED_TRACKED_FILES_OR_STATUS_FAILED\n"
                        + dirty_out
                        + "\n"
                        + dirty_err
                    )
            combined = redact(stdout + "\n" + stderr)
            category = "" if code == 0 else (
                "build_modified_tracked_files"
                if "BUILD_MODIFIED_TRACKED_FILES_OR_STATUS_FAILED" in combined
                else classify_failure(combined)
            )
            log_rel = f"logs/build/{repo_id}_{scope['scope_key'].replace(':', '_').replace('/', '_')}_{attempt_no}.log"
            log_path = settings.output_root / log_rel
            atomic_write_text(
                log_path,
                f"RECIPE: {recipe['name']}\nCOMMAND: {subprocess.list2cmdline(recipe['args'])}\n"
                f"CWD: {recipe['cwd']}\nEXIT CODE: {code}\nDURATION: {duration:.3f}\n"
                f"STDOUT:\n{redact(stdout)}\nSTDERR:\n{redact(stderr)}\n",
            )
            row = {
                "repo_id": repo_id,
                "scope_key": scope["scope_key"],
                "attempt_no": attempt_no,
                "recipe": recipe["name"],
                "command_source": recipe["source"],
                "command": subprocess.list2cmdline(recipe["args"]),
                "cwd": str(recipe["cwd"]),
                "exit_code": code,
                "status": "success" if code == 0 else "failed",
                "failure_category": category,
                "duration_seconds": f"{duration:.3f}",
                "log_path": log_rel,
                "started_at": started,
                "finished_at": finished,
            }
            attempts.append(row)
            append_csv(settings.output_root / "build_attempts.csv", [row], ATTEMPT_FIELDS)
            if code == 0:
                logger.log(f"Repo {repo_id} scope {scope['scope_key']} PASS via {recipe['name']}")
                return True, "", recipe["name"], attempts
            final_category = category
            final_detail = combined[-4000:]
            if category in TRANSIENT_FAILURES and transient_count < settings.transient_retries:
                transient_count += 1
                logger.log(f"Repo {repo_id} transient {category}; retry {transient_count}/{settings.transient_retries}")
                continue
            break
    return False, final_category, final_detail, attempts


def clone_repository(repo_id: str, url: str, destination: Path, settings: Settings) -> tuple[bool, str, str]:
    env = process_environment(settings)
    args = ["git", "-c", "credential.helper=", "clone", "--recurse-submodules", "--jobs", "4", "--", url, str(destination)]
    code, stdout, stderr, duration = run_process(args, None, env, settings.clone_timeout_seconds)
    log_path = settings.output_root / "logs" / "clone" / f"{repo_id}.log"
    atomic_write_text(log_path, f"COMMAND: {subprocess.list2cmdline(args)}\nEXIT CODE: {code}\nDURATION: {duration:.3f}\nSTDOUT:\n{redact(stdout)}\nSTDERR:\n{redact(stderr)}\n")
    if code != 0:
        return False, classify_failure(stdout + "\n" + stderr), (stdout + "\n" + stderr)[-4000:]
    sub_args = ["git", "submodule", "update", "--init", "--recursive", "--jobs", "4"]
    sub_code, sub_out, sub_err, sub_duration = run_process(sub_args, destination, env, settings.clone_timeout_seconds)
    atomic_write_text(
        settings.output_root / "logs" / "submodules" / f"{repo_id}.log",
        f"COMMAND: {subprocess.list2cmdline(sub_args)}\nEXIT CODE: {sub_code}\nDURATION: {sub_duration:.3f}\nSTDOUT:\n{redact(sub_out)}\nSTDERR:\n{redact(sub_err)}\n",
    )
    if sub_code != 0:
        return False, "missing_git_submodule", (sub_out + "\n" + sub_err)[-4000:]
    return True, "", ""


def git_head(repo_dir: Path, settings: Settings) -> str:
    code, stdout, _, _ = run_process(["git", "rev-parse", "HEAD"], repo_dir, process_environment(settings), 60)
    return stdout.strip() if code == 0 else ""


def load_frame_by_repo(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        grouped[row["repo_id"]].append(row)
    return grouped


def screen_repositories(settings: Settings, logger: RunLogger) -> None:
    if done(settings, "step003"):
        logger.log("Step 003 already complete; using stored qualified repositories")
        return
    queue_path = settings.output_root / "repo_processing_order_seed42.csv"
    frame_path = settings.output_root / "unique_focal_class_frame.csv"
    if not queue_path.exists() or not frame_path.exists():
        raise PipelineError("Step 001/002 outputs missing")
    queue = read_csv(queue_path)
    frame = load_frame_by_repo(frame_path)
    selected = [row for row in queue if row["status"] == "qualified"]
    logger.log(f"Step 003 resume: {len(selected)}/{settings.target_repositories} qualified")

    for queue_row in queue:
        if len(selected) >= settings.target_repositories:
            break
        if queue_row["status"] != "pending":
            continue
        repo_id = queue_row["repo_id"]
        repo_url = queue_row["repo_url"]
        working = settings.output_root / "repos" / "working" / repo_id
        successful = settings.output_root / "repos" / "successful" / repo_id
        logger.log(f"Screening repo {repo_id} ({len(selected)}/{settings.target_repositories} qualified)")
        try:
            if successful.is_dir():
                repo_dir = successful
                clone_ok = True
                clone_category = ""
                clone_detail = ""
            else:
                if working.exists():
                    safe_remove_tree(working, settings.output_root / "repos" / "working")
                clone_ok, clone_category, clone_detail = clone_repository(repo_id, repo_url, working, settings)
                repo_dir = working
            if not clone_ok:
                queue_row.update({
                    "status": "rejected", "failure_category": clone_category, "failure_detail": clone_detail,
                    "clone_status": "failed", "updated_at": utc_now(),
                })
                if working.exists() and not settings.keep_failed_repositories:
                    safe_remove_tree(working, settings.output_root / "repos" / "working")
                atomic_write_csv(queue_path, queue, QUEUE_FIELDS)
                continue
            queue_row["clone_status"] = "success"
            commit_sha = git_head(repo_dir, settings)
            queue_row["commit_sha"] = commit_sha
            if not commit_sha:
                raise PipelineError("cannot resolve git commit SHA")

            metrics: list[dict[str, Any]] = []
            scopes: dict[str, dict[str, Any]] = {}
            recipes_for_repo: list[dict[str, Any]] = []
            for frame_row in frame.get(repo_id, []):
                focal_file = repo_dir / normalize_relative_path(frame_row["focal_path"])
                metric = analyze_java_file(focal_file, frame_row, settings)
                scope = find_build_scope(repo_dir, focal_file) if focal_file.is_file() else None
                if scope:
                    metric.update(scope)
                    scope_entry = scopes.setdefault(scope["scope_key"], {"scope": scope, "metrics": []})
                    if metric["eligible_for_sampling"]:
                        scope_entry["metrics"].append(metric)
                else:
                    metric["eligible_for_sampling"] = False
                    metric["exclusion_reason"] = metric.get("exclusion_reason") or "build_scope_not_found"
                metric["build_scope_pass"] = False
                metric["commit_sha"] = commit_sha
                metrics.append(metric)

            buildable_count = 0
            passed_scopes: list[str] = []
            java_versions: list[int] = []
            last_category = "insufficient_unique_eligible_classes"
            last_detail = ""
            scope_entries = sorted(scopes.values(), key=lambda item: (-len(item["metrics"]), item["scope"]["scope_key"]))
            for entry in scope_entries:
                if buildable_count >= settings.minimum_unique_classes:
                    break
                scope = entry["scope"]
                build_files = []
                for directory_name in {scope["module_dir"], scope["build_root"]}:
                    directory = repo_dir / directory_name
                    build_files.extend(path for path in (directory / "pom.xml", directory / "build.gradle", directory / "build.gradle.kts") if path.is_file())
                java_version, java_source = detect_java_version(build_files)
                if java_version:
                    java_versions.append(java_version)
                for metric in entry["metrics"]:
                    metric["detected_java_version"] = java_version or "unknown"
                    metric["java_version_source"] = java_source
                if java_version and java_version > settings.maximum_java_version:
                    last_category = "requires_java_above_8"
                    last_detail = f"scope {scope['scope_key']} declares Java {java_version}"
                    continue
                passed, category, detail, attempts = execute_build_scope(repo_id, repo_dir, scope, java_version, settings, logger)
                if passed:
                    passed_scopes.append(scope["scope_key"])
                    for metric in entry["metrics"]:
                        metric["build_scope_pass"] = True
                        metric["build_recipe"] = attempts[-1]["recipe"] if attempts else ""
                    winning = attempts[-1] if attempts else {}
                    recipes_for_repo.append({
                        "recipe_id": f"v3:{repo_id}:{scope['scope_key']}",
                        "repo_id": repo_id,
                        "repo_url": repo_url,
                        "commit_sha": commit_sha,
                        "scope": scope,
                        "detected_java_version": java_version or "unknown",
                        "java_version_source": java_source,
                        "recipe": winning.get("recipe", ""),
                        "command_source": winning.get("command_source", ""),
                        "command": winning.get("command", ""),
                        "working_directory": winning.get("cwd", ""),
                        "validation_log": winning.get("log_path", ""),
                        "validated_at": winning.get("finished_at", utc_now()),
                        "source_or_dependency_files_modified": False,
                    })
                    buildable_count += len(entry["metrics"])
                else:
                    last_category = category
                    last_detail = detail

            eligible_buildable = [row for row in metrics if row.get("eligible_for_sampling") and row.get("build_scope_pass")]
            metrics_state = settings.output_root / "state" / "repo_metrics" / f"{repo_id}.json"
            atomic_write_json(metrics_state, metrics)
            recipe_state = settings.output_root / "state" / "repo_metrics" / f"{repo_id}.build_recipes.json"
            atomic_write_json(recipe_state, recipes_for_repo)
            if len(eligible_buildable) < settings.minimum_unique_classes:
                queue_row.update({
                    "status": "rejected",
                    "failure_category": last_category if scopes else "build_scope_not_found",
                    "failure_detail": f"eligible buildable {len(eligible_buildable)} < {settings.minimum_unique_classes}; {last_detail}"[-4000:],
                    "java_version": max(java_versions) if java_versions else "unknown",
                    "qualified_build_scopes": ";".join(passed_scopes),
                    "unique_eligible_buildable_count": len(eligible_buildable),
                    "selected_for_sample": False,
                    "updated_at": utc_now(),
                })
                if repo_dir == working and working.exists() and not settings.keep_failed_repositories:
                    safe_remove_tree(working, settings.output_root / "repos" / "working")
            else:
                if repo_dir == working:
                    if successful.exists():
                        safe_remove_tree(successful, settings.output_root / "repos" / "successful")
                    working.replace(successful)
                queue_row.update({
                    "status": "qualified", "failure_category": "", "failure_detail": "",
                    "java_version": max(java_versions) if java_versions else "unknown",
                    "qualified_build_scopes": ";".join(passed_scopes),
                    "unique_eligible_buildable_count": len(eligible_buildable),
                    "selected_for_sample": True, "updated_at": utc_now(),
                })
                selected.append(queue_row)
                logger.log(f"Repo {repo_id} QUALIFIED with {len(eligible_buildable)} unique eligible buildable classes")
            atomic_write_csv(queue_path, queue, QUEUE_FIELDS)
        except KeyboardInterrupt:
            atomic_write_csv(queue_path, queue, QUEUE_FIELDS)
            raise
        except Exception as error:
            queue_row.update({
                "status": "rejected", "failure_category": "pipeline_exception",
                "failure_detail": f"{type(error).__name__}: {error}"[:4000], "updated_at": utc_now(),
            })
            atomic_write_text(settings.output_root / "logs" / "build" / f"{repo_id}_pipeline_exception.log", traceback.format_exc())
            atomic_write_csv(queue_path, queue, QUEUE_FIELDS)
            logger.log(f"Repo {repo_id} rejected by controlled pipeline exception: {error}")

    if len(selected) < settings.target_repositories:
        raise PipelineError(
            f"INSUFFICIENT_QUALIFIED_REPOSITORIES: {len(selected)}/{settings.target_repositories}. "
            "Criteria were not relaxed. Inspect queue and logs, then resume after environment correction."
        )
    selected = sorted(selected, key=lambda row: int(row["order_index"]))[: settings.target_repositories]
    selected_ids = {row["repo_id"] for row in selected}
    for row in queue:
        row["selected_for_sample"] = row["repo_id"] in selected_ids
    atomic_write_csv(queue_path, queue, QUEUE_FIELDS)
    manifest_fields = [
        "repo_id", "repo_url", "commit_sha", "java_version", "qualified_build_scopes",
        "unique_eligible_buildable_count", "order_index", "repo_order_hash",
    ]
    atomic_write_csv(settings.output_root / "successful_repos_manifest.csv", selected, manifest_fields)

    all_metrics: list[dict[str, Any]] = []
    all_recipes: list[dict[str, Any]] = []
    for row in selected:
        path = settings.output_root / "state" / "repo_metrics" / f"{row['repo_id']}.json"
        all_metrics.extend(json.loads(path.read_text(encoding="utf-8")))
        recipe_path = settings.output_root / "state" / "repo_metrics" / f"{row['repo_id']}.build_recipes.json"
        if recipe_path.exists():
            all_recipes.extend(json.loads(recipe_path.read_text(encoding="utf-8")))
    metric_fields = sorted({key for row in all_metrics for key in row})
    atomic_write_csv(settings.output_root / "class_metrics_all.csv", all_metrics, metric_fields)
    atomic_write_jsonl(settings.output_root / "build_recipes.jsonl", all_recipes)
    mark_done(settings, "step003", {
        "qualified_repositories": len(selected),
        "metrics_rows": len(all_metrics),
        "validated_build_recipes": len(all_recipes),
    })
    logger.log(f"Step 003 PASS: {len(selected)} final-qualified repositories")


SAMPLE_FIELDS = [
    "repo_id", "repo_url", "commit_sha", "class_key", "focal_class", "focal_path", "mapping_count",
    "build_tool", "build_root", "module_dir", "module_selector", "scope_key", "build_recipe",
    "nloc", "method_count", "max_method_cc", "sum_method_cc", "avg_method_cc", "public_method_count",
    "selection_seed", "selection_hash", "repo_rank", "sample_role", "complexity_rank",
    "complexity_group", "replacement_of", "replacement_reason", "algorithm_version",
]


def sample_classes(settings: Settings, logger: RunLogger) -> None:
    if done(settings, "step004"):
        logger.log("Step 004 already complete; using stored sampling manifests")
        return
    repos = read_csv(settings.output_root / "successful_repos_manifest.csv")
    if len(repos) != settings.target_repositories:
        raise PipelineError(f"Expected {settings.target_repositories} successful repos, found {len(repos)}")
    main_rows: list[dict[str, Any]] = []
    backup_rows: list[dict[str, Any]] = []
    pool_rows: list[dict[str, Any]] = []
    for repo in sorted(repos, key=lambda row: int(row["order_index"])):
        metrics_path = settings.output_root / "state" / "repo_metrics" / f"{repo['repo_id']}.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        eligible = [row for row in metrics if row.get("eligible_for_sampling") and row.get("build_scope_pass")]
        unique: dict[str, dict[str, Any]] = {}
        for row in eligible:
            key = row["class_key"]
            if key in unique:
                raise PipelineError(f"Duplicate eligible class key in repo {repo['repo_id']}: {key}")
            enriched = dict(row)
            enriched["selection_seed"] = settings.seed
            enriched["selection_hash"] = stable_hash("class-selection-v3", settings.seed, key)
            enriched["commit_sha"] = repo["commit_sha"]
            enriched["algorithm_version"] = SELECTION_ALGORITHM
            enriched["replacement_of"] = ""
            enriched["replacement_reason"] = ""
            enriched["complexity_rank"] = ""
            enriched["complexity_group"] = ""
            unique[key] = enriched
        ordered = sorted(unique.values(), key=lambda row: (row["selection_hash"], row["class_key"]))
        needed = settings.main_per_repository + settings.backup_per_repository
        if len(ordered) < needed:
            raise PipelineError(f"Repo {repo['repo_id']} has {len(ordered)} eligible classes; needs {needed}")
        for index, row in enumerate(ordered, start=1):
            row["repo_rank"] = index
            row["sample_role"] = "reserve"
            pool_rows.append(row)
        selected_main = ordered[: settings.main_per_repository]
        selected_backup = ordered[settings.main_per_repository:needed]
        for row in selected_main:
            row["sample_role"] = "main"
        for row in selected_backup:
            row["sample_role"] = "backup"
        main_rows.extend(selected_main)
        backup_rows.extend(selected_backup)
    atomic_write_csv(settings.output_root / "class_sampling_manifest_seed42.csv", main_rows, SAMPLE_FIELDS)
    atomic_write_csv(settings.output_root / "class_backup_manifest_seed42.csv", backup_rows, SAMPLE_FIELDS)
    atomic_write_csv(settings.output_root / "eligible_class_pool_seed42.csv", pool_rows, SAMPLE_FIELDS)
    mark_done(settings, "step004", {"main": len(main_rows), "backup": len(backup_rows), "pool": len(pool_rows)})
    logger.log(f"Step 004 PASS: {len(main_rows)} main + {len(backup_rows)} backup")


def truthy(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes"}


def validate_and_classify(settings: Settings, logger: RunLogger) -> dict[str, Any]:
    main_path = settings.output_root / "class_sampling_manifest_seed42.csv"
    backup_path = settings.output_root / "class_backup_manifest_seed42.csv"
    pool_path = settings.output_root / "eligible_class_pool_seed42.csv"
    main_rows = read_csv(main_path)
    backup_rows = read_csv(backup_path)
    pool_rows = read_csv(pool_path)
    recipes = read_jsonl(settings.output_root / "build_recipes.jsonl")
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, observed: Any, expected: Any) -> None:
        checks.append({"check": name, "status": "PASS" if condition else "FAIL", "observed": observed, "expected": expected})

    expected_main = settings.target_repositories * settings.main_per_repository
    expected_backup = settings.target_repositories * settings.backup_per_repository
    main_keys = [row["class_key"] for row in main_rows]
    backup_keys = [row["class_key"] for row in backup_rows]
    repo_main = Counter(row["repo_id"] for row in main_rows)
    repo_backup = Counter(row["repo_id"] for row in backup_rows)
    check("main row count", len(main_rows) == expected_main, len(main_rows), expected_main)
    check("backup row count", len(backup_rows) == expected_backup, len(backup_rows), expected_backup)
    check("unique main", len(set(main_keys)) == expected_main, len(set(main_keys)), expected_main)
    check("unique backup", len(set(backup_keys)) == expected_backup, len(set(backup_keys)), expected_backup)
    check("main backup overlap", not (set(main_keys) & set(backup_keys)), len(set(main_keys) & set(backup_keys)), 0)
    check("represented repositories", len(repo_main) == settings.target_repositories, len(repo_main), settings.target_repositories)
    check("ten main per repo", all(value == settings.main_per_repository for value in repo_main.values()), sorted(repo_main.values()), settings.main_per_repository)
    check("two backup per repo", all(value == settings.backup_per_repository for value in repo_backup.values()), sorted(repo_backup.values()), settings.backup_per_repository)
    recipe_scopes = {(str(row["repo_id"]), str((row.get("scope") or {}).get("scope_key", ""))) for row in recipes}
    main_scopes = {(row["repo_id"], row["scope_key"]) for row in main_rows}
    missing_recipe_scopes = sorted(main_scopes - recipe_scopes)
    check("validated recipe for every main scope", not missing_recipe_scopes, len(missing_recipe_scopes), 0)
    missing_commits = sum(not row.get("commit_sha") for row in main_rows)
    check("commit SHA for every main class", missing_commits == 0, missing_commits, 0)

    pool_by_repo: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pool_rows:
        pool_by_repo[row["repo_id"]].append(row)
    reconstruction_mismatches = 0
    for repo_id, rows in pool_by_repo.items():
        ordered = sorted(rows, key=lambda row: (row["selection_hash"], row["class_key"]))
        expected_main_keys = {row["class_key"] for row in ordered[: settings.main_per_repository]}
        expected_backup_keys = {row["class_key"] for row in ordered[settings.main_per_repository: settings.main_per_repository + settings.backup_per_repository]}
        observed_main_keys = {row["class_key"] for row in main_rows if row["repo_id"] == repo_id}
        observed_backup_keys = {row["class_key"] for row in backup_rows if row["repo_id"] == repo_id}
        if expected_main_keys != observed_main_keys or expected_backup_keys != observed_backup_keys:
            reconstruction_mismatches += 1
    check("deterministic selection reconstruction", reconstruction_mismatches == 0, reconstruction_mismatches, 0)

    hash_mismatches = sum(
        row["selection_hash"] != stable_hash("class-selection-v3", settings.seed, row["class_key"])
        for row in [*main_rows, *backup_rows]
    )
    check("selection hash reconstruction", hash_mismatches == 0, hash_mismatches, 0)
    missing_paths = 0
    for row in main_rows:
        path = settings.output_root / "repos" / "successful" / row["repo_id"] / normalize_relative_path(row["focal_path"])
        if not path.is_file():
            missing_paths += 1
    check("main focal paths exist", missing_paths == 0, missing_paths, 0)

    ordered_complexity = sorted(
        main_rows,
        key=lambda row: (
            int(float(row["max_method_cc"] or 0)),
            int(float(row["sum_method_cc"] or 0)),
            row["selection_hash"],
            row["class_key"],
        ),
    )
    midpoint = len(ordered_complexity) // 2
    for rank, row in enumerate(ordered_complexity, start=1):
        row["complexity_rank"] = rank
        row["complexity_group"] = "lower_complexity_half" if rank <= midpoint else "higher_complexity_half"
    lower = [row for row in ordered_complexity if row["complexity_group"] == "lower_complexity_half"]
    higher = [row for row in ordered_complexity if row["complexity_group"] == "higher_complexity_half"]
    check("relative complexity halves", len(lower) == 150 and len(higher) == 150, f"{len(lower)}/{len(higher)}", "150/150")
    check("all validations", all(item["status"] == "PASS" for item in checks), "computed below", "PASS")

    atomic_write_csv(main_path, sorted(ordered_complexity, key=lambda row: (int(row["repo_rank"]), row["repo_id"])), SAMPLE_FIELDS)
    atomic_write_csv(settings.output_root / "final_main_manifest_seed42.csv", ordered_complexity, SAMPLE_FIELDS)
    overall = all(item["status"] == "PASS" for item in checks[:-1])
    checks[-1]["status"] = "PASS" if overall else "FAIL"
    summary = {
        "status": "PASS" if overall else "FAIL",
        "checks": checks,
        "lower_count": len(lower),
        "higher_count": len(higher),
        "median_boundary": {
            "lower_max_cc": int(float(lower[-1]["max_method_cc"])) if lower else None,
            "higher_min_cc": int(float(higher[0]["max_method_cc"])) if higher else None,
            "boundary_tied_on_max_cc": bool(lower and higher and lower[-1]["max_method_cc"] == higher[0]["max_method_cc"]),
        },
    }
    atomic_write_json(settings.output_root / "state" / "validation.json", summary)
    if not overall:
        raise PipelineError("Step 005 validation FAILED; RUN_READY will not be created")
    mark_done(settings, "step005", summary)
    logger.log("Step 005 PASS: deterministic 300 main, 60 backup, relative 150/150 complexity halves")
    return summary


def metric_summary(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    quartiles = statistics.quantiles(ordered, n=4, method="inclusive") if len(ordered) > 1 else [ordered[0]] * 3
    return {
        "count": len(ordered),
        "min": min(ordered),
        "max": max(ordered),
        "mean": round(statistics.fmean(ordered), 4),
        "median": statistics.median(ordered),
        "q1": quartiles[0],
        "q3": quartiles[2],
    }


def generate_reports(settings: Settings, logger: RunLogger) -> None:
    validation = json.loads((settings.output_root / "state" / "validation.json").read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        raise PipelineError("Cannot report a dataset that did not pass validation")
    main_rows = read_csv(settings.output_root / "final_main_manifest_seed42.csv")
    backup_rows = read_csv(settings.output_root / "class_backup_manifest_seed42.csv")
    repos = read_csv(settings.output_root / "successful_repos_manifest.csv")
    queue = read_csv(settings.output_root / "repo_processing_order_seed42.csv")
    lower = [row for row in main_rows if row["complexity_group"] == "lower_complexity_half"]
    higher = [row for row in main_rows if row["complexity_group"] == "higher_complexity_half"]
    lower_stats = metric_summary([float(row["max_method_cc"]) for row in lower])
    higher_stats = metric_summary([float(row["max_method_cc"]) for row in higher])
    failure_counts = Counter(row["failure_category"] for row in queue if row["status"] == "rejected")

    summary = f"""# V3 final sampling summary

- Generated: {utc_now()}
- Program: `{PROGRAM_VERSION}`
- Validation: **PASS**
- Repositories: **{len(repos)}**
- Main classes: **{len(main_rows)}** unique classes
- Backup classes: **{len(backup_rows)}** unique classes
- Repository contribution: **{settings.main_per_repository} main + {settings.backup_per_repository} backup per repo**
- Selection seed: **{settings.seed}**
- Selection algorithm: `{SELECTION_ALGORITHM}`
- Complexity grouping: `{COMPLEXITY_ALGORITHM}`
- Lower-complexity half: **{len(lower)}**; MaxCC summary `{json.dumps(lower_stats)}`
- Higher-complexity half: **{len(higher)}**; MaxCC summary `{json.dumps(higher_stats)}`

Complexity did not influence class selection. The two complexity labels are relative to the frozen 300-class main sample and are not universal Low/High thresholds.
"""
    atomic_write_text(settings.output_root / "results" / "final_sampling_summary.md", summary)

    validation_lines = [
        "# V3 validation report",
        "",
        f"Overall status: **{validation['status']}**",
        "",
        "| Check | Expected | Observed | Status |",
        "|---|---:|---:|---|",
    ]
    for item in validation["checks"]:
        validation_lines.append(f"| {item['check']} | {item['expected']} | {item['observed']} | {item['status']} |")
    atomic_write_text(settings.output_root / "results" / "validation_report.md", "\n".join(validation_lines) + "\n")

    failure_lines = ["# Repository screening outcomes", "", "| Failure category | Repositories |", "|---|---:|"]
    for category, count in failure_counts.most_common():
        failure_lines.append(f"| {category or '(none)'} | {count} |")
    atomic_write_text(settings.output_root / "results" / "build_failure_summary.md", "\n".join(failure_lines) + "\n")

    methodology = f"""# V3 sampling methodology

CLASSES2TEST mapping JSON files were reconstructed into unique physical focal source classes using repository ID plus normalized focal path. Repositories were ordered deterministically with seed {settings.seed}. A repository was retained only when a frozen commit could be validated under the declared Java/build protocol and provided at least {settings.minimum_unique_classes} unique eligible focal classes in buildable modules.

Within each of {settings.target_repositories} repositories, classes were ordered using SHA-256 of `class-selection-v3|{settings.seed}|class_key`. The first {settings.main_per_repository} classes were main observations and the next {settings.backup_per_repository} were backups. Complexity did not influence sampling. After the final {len(main_rows)} main classes were frozen, they were ranked by MaxCC, SumCC, selection hash, and class key, then split into two relative halves.

Buildability means that production and test sources for the focal module compile using a pre-registered Maven/Gradle recipe, with no source or dependency-file edits and no required external service. `-DskipTests` may suppress test execution but `-Dmaven.test.skip=true` is never accepted because it can skip test compilation.

Backups are only for pre-experiment technical failures. GPT/EvoSuite generation or compilation failures are experimental outcomes and do not trigger replacement.
"""
    atomic_write_text(settings.output_root / "results" / "sampling_methodology.md", methodology)

    integrity = """# V3 data integrity report

- [VERIFIED] Class identity is repository ID plus normalized focal path.
- [VERIFIED] Main and backup manifests contain no duplicate or overlapping class keys.
- [VERIFIED] Each repository contributes equally.
- [VERIFIED] Sampling hashes reconstruct from seed and class key.
- [VERIFIED] Complexity values do not participate in selection hashes or per-repository ranks.
- [VERIFIED] Build attempts, exact commands, logs, commit SHAs, scopes, and outcomes are retained.
- [TEAM DECLARATION REQUIRED] Confirm that no GPT/EvoSuite/coverage/mutation outcome was inspected before sampling was frozen.
- [DISCLOSURE REQUIRED] The physical-focal-file unit is an operational amendment from any proposal wording that treats focal/test tuples as distinct instances.
- [DISCLOSURE REQUIRED] Upstream metadata does not provide an original repository commit for every mapping; V3 freezes and reports the commit available at screening time.
"""
    atomic_write_text(settings.output_root / "results" / "data_integrity_report.md", integrity)

    preflight_report = settings.output_root / "state" / "preflight.json"
    if preflight_report.exists():
        shutil.copy2(preflight_report, settings.output_root / "results" / "environment_versions.json")
    checksum_targets = [
        settings.output_root / "final_main_manifest_seed42.csv",
        settings.output_root / "class_backup_manifest_seed42.csv",
        settings.output_root / "successful_repos_manifest.csv",
        settings.output_root / "class_metrics_all.csv",
        settings.output_root / "repo_processing_order_seed42.csv",
        settings.output_root / "results" / "validation_report.md",
        settings.output_root / "results" / "sampling_methodology.md",
        Path(__file__).resolve(),
    ]
    checksum_lines = [f"{sha256_file(path)}  {path.as_posix()}" for path in checksum_targets if path.is_file()]
    atomic_write_text(settings.output_root / "results" / "SHA256SUMS.txt", "\n".join(checksum_lines) + "\n")
    atomic_write_text(settings.output_root / "results" / "RUN_READY", f"PASS {utc_now()} pipeline_v3={PROGRAM_VERSION}\n")
    mark_done(settings, "step006", {"run_ready": True})
    logger.log("Step 006 PASS: reports and RUN_READY generated")


def audit_v2_build_logs(settings: Settings, logger: RunLogger) -> None:
    """Reclassify historical V2 logs with the V3 taxonomy, without changing V2."""
    log_dir = settings.workspace_root / "data_v2" / "logs" / "build"
    if not log_dir.is_dir():
        raise PipelineError(f"V2 build log directory not found: {log_dir}")
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for path in sorted(log_dir.glob("*.log"), key=lambda item: item.name.casefold()):
        text = path.read_text(encoding="utf-8", errors="replace")
        exit_match = re.search(r"(?im)^EXIT CODE:\s*(-?\d+)", text)
        exit_code = int(exit_match.group(1)) if exit_match else None
        category = "success" if exit_code == 0 else classify_failure(text)
        counts[category] += 1
        interesting = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and re.search(
                r"(?i)(error|failed|failure|exception|what went wrong|could not|not found|not supported|timed out)",
                line,
            )
        ]
        excerpt = " | ".join(interesting[-8:]) if interesting else " ".join(text.split())[-1500:]
        rows.append({
            "log_file": path.name,
            "repo_id": path.name.split("_", 1)[0],
            "exit_code": "" if exit_code is None else exit_code,
            "v3_failure_category": category,
            "evidence_excerpt": redact(excerpt)[:2000],
        })
    output = settings.output_root / "results" / "v2_build_log_reclassification.csv"
    atomic_write_csv(
        output,
        rows,
        ["log_file", "repo_id", "exit_code", "v3_failure_category", "evidence_excerpt"],
    )
    lines = [
        "# V2 build-log reclassification with V3 taxonomy",
        "",
        f"- Generated: {utc_now()}",
        f"- Logs audited: {len(rows)}",
        "- This is a read-only diagnostic; it does not change any V2 status.",
        "",
        "| Category | Log files |",
        "|---|---:|",
    ]
    for category, count in counts.most_common():
        lines.append(f"| {category} | {count} |")
    unknown = counts.get("unknown_build_failure", 0)
    lines.extend(["", f"Unknown logs remaining: **{unknown}**. These require taxonomy review, not per-repo source repair."])
    atomic_write_text(settings.output_root / "results" / "v2_build_log_reclassification.md", "\n".join(lines) + "\n")
    logger.log(f"V2 log audit complete: {len(rows)} logs; {unknown} remain unknown")


def self_test(logger: RunLogger) -> None:
    assertions = 0

    def expect(condition: bool, message: str) -> None:
        nonlocal assertions
        assertions += 1
        if not condition:
            raise AssertionError(message)

    expect(normalize_relative_path(r".\src\main\A.java") == "src/main/A.java", "path normalization")
    expect(class_key("7", "SRC/A.java") == class_key(7, "src/a.java"), "casefold identity")
    expect(stable_hash("x", 42, "a") == stable_hash("x", 42, "a"), "stable hash")
    expect(classify_failure("Could not resolve host example.org") == "network_dns", "DNS classification")
    expect(classify_failure("Child module abc does not exist") == "missing_git_submodule", "submodule classification")
    expect(classify_failure("SDK location not found. Define ANDROID_HOME") == "android_sdk_required", "Android classification")
    expect(classify_failure("Blocked mirror for repositories by maven-default-http-blocker") == "insecure_http_repository_blocked", "HTTP blocker classification")
    expect(classify_failure("Gradle build daemon disappeared unexpectedly") == "gradle_daemon_crashed", "Gradle daemon classification")
    expect(classify_failure("No space left on device") == "disk_full", "disk classification")
    expect(classify_failure("Could not find artifact x:y:jar:1") == "missing_dependency", "dependency classification")
    expect(classify_failure("[ERROR] COMPILATION ERROR") == "source_compile_failed", "compile classification")
    expect(parse_java_number("1.8") == 8 and parse_java_number("17") == 17, "Java version parser")

    with tempfile.TemporaryDirectory(prefix="pipeline_v3_test_") as temporary:
        root = Path(temporary)
        dataset = root / "classes2test" / "dataset"
        repo = dataset / "100"
        repo.mkdir(parents=True)
        base = {
            "repository": {"repo_id": 100, "url": "https://example.invalid/r.git"},
            "focal_class": {
                "identifier": "A",
                "file": "src/main/java/A.java",
                "methods": [{"identifier": "m", "modifiers": "public", "constructor": False}],
            },
            "test_class": {"identifier": "ATest", "file": "src/test/java/ATest.java"},
            "focal_method": {"class_method_signature": "A.m()"},
            "test_case": {"class_method_signature": "ATest.t()"},
        }
        for index in range(3):
            payload = json.loads(json.dumps(base))
            payload["test_case"]["class_method_signature"] = f"ATest.t{index}()"
            (repo / f"{index}.json").write_text(json.dumps(payload), encoding="utf-8")
        second = json.loads(json.dumps(base))
        second["focal_class"]["identifier"] = "B"
        second["focal_class"]["file"] = ".\\src\\main\\java\\B.java"
        (repo / "3.json").write_text(json.dumps(second), encoding="utf-8")
        output = root / "out"
        settings = Settings(
            workspace_root=root,
            dataset_root=root / "classes2test",
            output_root=output,
            minimum_unique_classes=2,
            target_repositories=1,
            main_per_repository=1,
            backup_per_repository=1,
            skip_backup=True,
        )
        summary = reconstruct_frame(settings, logger, output_root=output)
        expect(summary["mapping_json_files"] == 4, "fixture mapping count")
        expect(summary["unique_focal_classes"] == 2, "fixture dedupe count")
        rows = read_csv(output / "unique_focal_class_frame.csv")
        counts = sorted(int(row["mapping_count"]) for row in rows)
        expect(counts == [1, 3], "fixture mapping aggregation")
        keys = [row["class_key"] for row in rows]
        expect(len(keys) == len(set(keys)), "fixture uniqueness")

        fake_repo = root / "fake_repo"
        module = fake_repo / "module"
        source = module / "src" / "main" / "java" / "A.java"
        source.parent.mkdir(parents=True)
        source.write_text("public class A { public void m() {} }", encoding="utf-8")
        (fake_repo / "pom.xml").write_text("<project><modules><module>module</module></modules></project>", encoding="utf-8")
        (module / "pom.xml").write_text("<project><properties><maven.compiler.source>1.8</maven.compiler.source></properties></project>", encoding="utf-8")
        scope = find_build_scope(fake_repo, source)
        expect(scope is not None and scope["build_tool"] == "maven", "module detection")
        expect(scope is not None and scope["module_selector"] == "module", "module selector")
        version, _ = detect_java_version([module / "pom.xml"])
        expect(version == 8, "module Java detection")
        recipes = build_recipes(fake_repo, scope or {}, settings)
        expect(any("-pl" in recipe["args"] and "-am" in recipe["args"] for recipe in recipes), "Maven reactor recipe")
        expect(all("-Dmaven.test.skip=true" not in recipe["args"] for recipe in recipes), "test compilation is never skipped")
        expect(all("clean" in recipe["args"] for recipe in recipes), "every recipe starts from clean build outputs")

    logger.log(f"SELF-TEST PASS: {assertions} assertions")


def smoke_test(settings: Settings, logger: RunLogger) -> None:
    self_test(logger)
    with tempfile.TemporaryDirectory(prefix="pipeline_v3_smoke_") as temporary:
        smoke_settings = Settings(**{
            **asdict(settings),
            "output_root": Path(temporary) / "out",
            "repository_limit": min(settings.repository_limit or 3, 3),
            "skip_backup": True,
        })
        summary = reconstruct_frame(smoke_settings, logger, output_root=smoke_settings.output_root)
        if summary["repositories_scanned"] < 1 or summary["mapping_json_files"] < 1:
            raise PipelineError("Smoke scan found no real metadata")
        logger.log(
            f"SMOKE PASS: scanned {summary['repositories_scanned']} real repos, "
            f"{summary['mapping_json_files']} mappings, {summary['unique_focal_classes']} unique classes"
        )


def build_smoke_test(settings: Settings, logger: RunLogger, repo_id: str) -> None:
    """Build one preserved V2 success in a temporary copy to test the V3 runner."""
    source_repo = settings.workspace_root / "data_v2" / "repos" / "successful" / repo_id
    metrics_path = settings.workspace_root / "data_v2" / "class_metrics.csv"
    if not source_repo.is_dir() or not metrics_path.is_file():
        raise PipelineError(f"Build-smoke source is unavailable for repo {repo_id}")
    focal_rows = [
        row for row in read_csv(metrics_path)
        if row.get("repo_id") == repo_id and truthy(row.get("eligible_for_sampling"))
    ]
    if not focal_rows:
        raise PipelineError(f"No eligible V2 focal path available for build-smoke repo {repo_id}")
    focal_rows.sort(key=lambda row: normalize_relative_path(row.get("focal_path")))
    with tempfile.TemporaryDirectory(prefix=f"pipeline_v3_build_smoke_{repo_id}_") as temporary:
        temporary_root = Path(temporary)
        copied_repo = temporary_root / repo_id
        shutil.copytree(source_repo, copied_repo, copy_function=shutil.copy2)
        focal_path = copied_repo / normalize_relative_path(focal_rows[0]["focal_path"])
        if not focal_path.is_file():
            raise PipelineError(f"Build-smoke focal path is missing: {focal_path}")
        scope = find_build_scope(copied_repo, focal_path)
        if not scope:
            raise PipelineError("Build-smoke could not determine focal build scope")
        build_files: list[Path] = []
        for directory_name in {scope["module_dir"], scope["build_root"]}:
            directory = copied_repo / directory_name
            build_files.extend(
                path for path in (directory / "pom.xml", directory / "build.gradle", directory / "build.gradle.kts")
                if path.is_file()
            )
        java_version, _ = detect_java_version(build_files)
        smoke_settings = Settings(**{
            **asdict(settings),
            "output_root": temporary_root / "out",
            "skip_backup": True,
        })
        create_layout(smoke_settings)
        passed, category, detail, attempts = execute_build_scope(
            repo_id, copied_repo, scope, java_version, smoke_settings, logger
        )
        evidence_dir = settings.output_root / "results" / "build_smoke"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        for attempt in attempts:
            source_log = smoke_settings.output_root / attempt["log_path"]
            if source_log.is_file():
                shutil.copy2(source_log, evidence_dir / Path(attempt["log_path"]).name)
        result = {
            "timestamp": utc_now(),
            "repo_id": repo_id,
            "source": "temporary copy of preserved V2 successful repository",
            "focal_path": focal_rows[0]["focal_path"],
            "scope": scope,
            "detected_java_version": java_version or "unknown",
            "passed": passed,
            "failure_category": category,
            "failure_detail": detail[-2000:],
            "attempts": attempts,
        }
        atomic_write_json(evidence_dir / f"{repo_id}_result.json", result)
        if not passed:
            raise PipelineError(f"BUILD SMOKE FAILED for {repo_id}: {category}: {detail[-500:]}")
        logger.log(f"BUILD SMOKE PASS: repo {repo_id}, scope {scope['scope_key']}, {len(attempts)} attempt(s)")


def run_all(settings: Settings, logger: RunLogger) -> None:
    preflight(settings, logger)
    backup_v2(settings, logger)
    reconstruct_frame(settings, logger)
    create_queue(settings, logger)
    screen_repositories(settings, logger)
    sample_classes(settings, logger)
    validate_and_classify(settings, logger)
    generate_reports(settings, logger)


def acquire_lock(settings: Settings, command: str) -> Path | None:
    if command in {"self-test", "smoke"}:
        return None
    lock = settings.output_root / "state" / "pipeline.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "command": command, "created_at": utc_now()}))
        return lock
    except FileExistsError as error:
        raise PipelineError(f"Another run may be active. Remove stale lock only after checking: {lock}") from error


def build_parser() -> argparse.ArgumentParser:
    script_root = Path(__file__).resolve().parent
    workspace = script_root.parent
    parser = argparse.ArgumentParser(description="CLASSES2TEST V3 one-file reproducible pipeline")
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=("preflight", "backup", "step001", "step002", "step003", "step004", "step005", "step006", "audit-v2-logs", "self-test", "smoke", "build-smoke", "all"),
    )
    parser.add_argument("--workspace-root", type=Path, default=workspace)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--env-file", type=Path, help="Only JAVA*_HOME keys are loaded; secrets are ignored")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-repositories", type=int, default=30)
    parser.add_argument("--minimum-unique-classes", type=int, default=12)
    parser.add_argument("--main-per-repository", type=int, default=10)
    parser.add_argument("--backup-per-repository", type=int, default=2)
    parser.add_argument("--min-nloc", type=int, default=5)
    parser.add_argument("--max-nloc", type=int, default=500)
    parser.add_argument("--maximum-java-version", type=int, default=8)
    parser.add_argument("--clone-timeout-seconds", type=int, default=600)
    parser.add_argument("--build-timeout-seconds", type=int, default=900)
    parser.add_argument("--transient-retries", type=int, default=2)
    parser.add_argument("--metadata-workers", type=int, default=16)
    parser.add_argument("--keep-failed-repositories", action="store_true")
    parser.add_argument("--allow-android", action="store_true")
    parser.add_argument("--maven-settings", type=Path)
    parser.add_argument("--repository-limit", type=int)
    parser.add_argument("--smoke-repo-id", default="73087334")
    parser.add_argument("--skip-backup", action="store_true", help="Explicit integrity amendment; never the default")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    workspace = args.workspace_root.resolve()
    dataset = (args.dataset_root or workspace / "classes2test").resolve()
    output = (args.output_root or workspace / "data_v3").resolve()
    default_env = workspace / "research_pipeline" / "env" / "local.env"
    env_file = (args.env_file or default_env).resolve() if (args.env_file or default_env.exists()) else None
    if args.target_repositories < 1 or args.minimum_unique_classes < 1:
        raise PipelineError("Repository counts must be positive")
    if args.main_per_repository + args.backup_per_repository > args.minimum_unique_classes:
        raise PipelineError("minimum_unique_classes must cover main + backup per repository")
    if args.min_nloc < 1 or args.max_nloc < args.min_nloc:
        raise PipelineError("Invalid NLOC bounds")
    if args.metadata_workers < 1 or args.metadata_workers > 64:
        raise PipelineError("metadata_workers must be between 1 and 64")
    return Settings(
        workspace_root=workspace,
        dataset_root=dataset,
        output_root=output,
        env_file=env_file,
        seed=args.seed,
        target_repositories=args.target_repositories,
        minimum_unique_classes=args.minimum_unique_classes,
        main_per_repository=args.main_per_repository,
        backup_per_repository=args.backup_per_repository,
        min_nloc=args.min_nloc,
        max_nloc=args.max_nloc,
        maximum_java_version=args.maximum_java_version,
        clone_timeout_seconds=args.clone_timeout_seconds,
        build_timeout_seconds=args.build_timeout_seconds,
        transient_retries=args.transient_retries,
        metadata_workers=args.metadata_workers,
        keep_failed_repositories=args.keep_failed_repositories,
        allow_android=args.allow_android,
        maven_settings=args.maven_settings.resolve() if args.maven_settings else None,
        repository_limit=args.repository_limit,
        skip_backup=args.skip_backup,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        settings = settings_from_args(args)
        create_layout(settings)
        logger = RunLogger(settings.output_root, args.command)
        logger.log(f"pipeline_v3 {PROGRAM_VERSION} command={args.command}")
        atomic_write_json(settings.output_root / "state" / "effective_config.json", settings.public_dict())
        lock = acquire_lock(settings, args.command)
        try:
            actions = {
                "preflight": lambda: preflight(settings, logger),
                "backup": lambda: backup_v2(settings, logger),
                "step001": lambda: reconstruct_frame(settings, logger),
                "step002": lambda: create_queue(settings, logger),
                "step003": lambda: screen_repositories(settings, logger),
                "step004": lambda: sample_classes(settings, logger),
                "step005": lambda: validate_and_classify(settings, logger),
                "step006": lambda: generate_reports(settings, logger),
                "audit-v2-logs": lambda: audit_v2_build_logs(settings, logger),
                "self-test": lambda: self_test(logger),
                "smoke": lambda: smoke_test(settings, logger),
                "build-smoke": lambda: build_smoke_test(settings, logger, str(args.smoke_repo_id)),
                "all": lambda: run_all(settings, logger),
            }
            actions[args.command]()
            logger.log(f"Command {args.command} completed successfully")
            return 0
        finally:
            if lock and lock.exists():
                lock.unlink()
    except KeyboardInterrupt:
        print("Interrupted; durable state was preserved. Run the same command to resume.", file=sys.stderr)
        return 130
    except PipelineError as error:
        print(f"PIPELINE ERROR: {error}", file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
