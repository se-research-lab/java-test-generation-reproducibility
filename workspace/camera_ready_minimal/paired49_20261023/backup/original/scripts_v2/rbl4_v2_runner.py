from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "data_new" / "class_sampling_manifest_final_seed42.csv"
DEFAULT_RECIPES = ROOT / "data_new" / "build_recipes_portable.csv"
DEFAULT_COMPILED_REPOS = Path(os.getenv("RBL4_COMPILED_REPOS", ROOT.parent / "compiledrepos")).absolute()
DEFAULT_RESULTS_DIR = ROOT / "results" / "runs"
DEFAULT_MODEL = "gpt-4o-mini-2024-07-18"
DEFAULT_PROMPT = "rbl4-zero-shot"
AGONE_TEST_TYPES = ["evosuite", DEFAULT_MODEL]

REFERENCE = {
    "mutation_compiled_only_gpt4o_mini": 44.5,
    "branch_compiled_only_gpt4o_mini": 41.9,
    "build_success_gpt4o_mini": 0.286,
    "rq4_noninferiority_margin_pp": 5.0,
}
ALPHA = 0.05
PREWARMED_REACTOR_SCOPES: set[tuple[str, str, str]] = set()
PREWARMED_REACTOR_SCOPES_LOCK = threading.Lock()
MAVEN_PREWARM_SCOPE_LOCKS: dict[tuple[str, str], threading.Lock] = {}
MAVEN_PREWARM_SCOPE_LOCKS_LOCK = threading.Lock()
CSV_APPEND_LOCKS: dict[str, threading.Lock] = {}
CSV_APPEND_LOCKS_LOCK = threading.Lock()

PROMPT_MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are provided with Java class. Create a test class that fully tests "
            "the proposed Java class using the project information for imports. "
            "Reply with code only, do not add other text that is not code."
        ),
    },
    {
        "role": "user",
        "content": (
            "The project uses {{testing_framework}} and Java {{java_version}} and "
            "Java class is:\n<code>\n{{focal_class}}\n</code>"
        ),
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_name(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_") or "item"


def prompt_hash() -> str:
    return hashlib.sha256(json.dumps(PROMPT_MESSAGES, sort_keys=True).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class CrossProcessFileLock:
    def __init__(self, target: Path, timeout_sec: float = 60.0) -> None:
        self.lock_path = target.with_name(target.name + ".lock")
        self.timeout_sec = timeout_sec
        self.handle: int | None = None

    def __enter__(self) -> "CrossProcessFileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout_sec
        while True:
            try:
                self.handle = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self.handle, str(os.getpid()).encode("ascii", errors="ignore"))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.lock_path.stat().st_mtime > max(self.timeout_sec, 300.0):
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.time() >= deadline:
                    raise TimeoutError(f"Timed out waiting for file lock: {self.lock_path}")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.handle is not None:
            os.close(self.handle)
            self.handle = None
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def thread_lock_for_path(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with CSV_APPEND_LOCKS_LOCK:
        lock = CSV_APPEND_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            CSV_APPEND_LOCKS[key] = lock
        return lock


def maven_prewarm_scope_lock(repo_id: str, scope_key: str) -> threading.Lock:
    # Maven -am install for different modules in the same repo still writes
    # overlapping SNAPSHOT parent/upstream artifacts into the shared ~/.m2.
    # Serialize by repo, not by module scope, to avoid local-repository races.
    key = (str(repo_id), "__repo__")
    with MAVEN_PREWARM_SCOPE_LOCKS_LOCK:
        lock = MAVEN_PREWARM_SCOPE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            MAVEN_PREWARM_SCOPE_LOCKS[key] = lock
        return lock


def append_csv(path: Path, row: dict[str, Any], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(row.keys())
    for attempt in range(10):
        try:
            with thread_lock_for_path(path):
                with CrossProcessFileLock(path):
                    exists = path.exists()
                    with path.open("a", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=names, extrasaction="ignore")
                        if not exists:
                            writer.writeheader()
                        writer.writerow(row)
            return
        except (PermissionError, TimeoutError):
            time.sleep(0.1 * (attempt + 1))
    fallback = path.with_name(path.name + ".fallback.csv")
    with thread_lock_for_path(fallback):
        with CrossProcessFileLock(fallback):
            exists = fallback.exists()
            with fallback.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=names, extrasaction="ignore")
                if not exists:
                    writer.writeheader()
                writer.writerow(row)


def csv_safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Avoid case-insensitive duplicate headers in artifacts consumed by Excel/PowerShell/R."""
    if df.empty:
        return df.copy()
    columns: list[str] = []
    seen: set[str] = set()
    for column in df.columns:
        name = str(column)
        candidate = name
        if candidate.lower() in seen:
            suffix = "agone" if any(char.isupper() for char in name) else "manifest"
            candidate = f"{name}_{suffix}"
            counter = 2
            while candidate.lower() in seen:
                candidate = f"{name}_{suffix}_{counter}"
                counter += 1
        seen.add(candidate.lower())
        columns.append(candidate)
    out = df.copy()
    out.columns = columns
    return out


def write_csv_artifact(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    csv_safe_dataframe(df).to_csv(path, index=False)


def append_phase(run_dir: Path, phase: str, **kwargs: Any) -> None:
    started = kwargs.pop("started_at", None)
    detail = str(kwargs.pop("detail", ""))
    detail_limit = int(os.getenv("RBL4_PHASE_DETAIL_LIMIT", "12000"))
    if len(detail) > detail_limit:
        detail = detail[-detail_limit:]
    row = {
        "timestamp_utc": utc_now(),
        "phase": phase,
        "project": kwargs.pop("project", ""),
        "module": kwargs.pop("module", ""),
        "arm": kwargs.pop("arm", ""),
        "sample_index": kwargs.pop("sample_index", ""),
        "class_key": kwargs.pop("class_key", ""),
        "focal_class": kwargs.pop("focal_class", ""),
        "test_class": kwargs.pop("test_class", ""),
        "status": kwargs.pop("status", ""),
        "duration_sec": round(time.time() - started, 3) if started is not None else "",
        "detail": detail,
    }
    append_csv(run_dir / "phase_log.csv", row)


def normalize_repo_rel_path(path: Any) -> str:
    value = str(path or "").strip().replace("\\", "/")
    value = value.removeprefix("./")
    while value.startswith("/"):
        value = value[1:]
    return value


def normalize_java_version(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"", "nan", "none", "unknown"}:
        return "1.8"
    if raw in {"5", "1.5"}:
        return "1.5"
    if raw in {"6", "1.6"}:
        return "1.6"
    if raw in {"7", "1.7"}:
        return "1.7"
    if raw in {"8", "1.8"}:
        return "1.8"
    return raw


def java_major(value: Any) -> int:
    version = normalize_java_version(value)
    if version.startswith("1."):
        version = version.split(".", 1)[1]
    match = re.search(r"\d+", version)
    return int(match.group(0)) if match else 8


def java_identifier(value: str) -> str:
    clean = re.sub(r"\W+", "_", str(value)).strip("_")
    if not clean:
        clean = "Generated"
    if not re.match(r"[A-Za-z_$]", clean[0]):
        clean = "_" + clean
    return clean


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def java_package(source: str) -> str:
    cleaned = re.sub(r"//.*", "", source)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    match = re.search(r"\bpackage\s+([\w.]+)\s*;", cleaned)
    return match.group(1) if match else ""


def derive_test_path(focal_path: str, package_name: str, test_class: str) -> str:
    focal = normalize_repo_rel_path(focal_path)
    package_path = package_name.replace(".", "/") if package_name else ""
    if "/src/main/java/" in focal:
        prefix = focal.split("/src/main/java/", 1)[0]
        return f"{prefix}/src/test/java/{package_path}/{test_class}.java".replace("//", "/")
    if "/src/main/" in focal:
        prefix = focal.split("/src/main/", 1)[0]
        return f"{prefix}/src/test/java/{package_path}/{test_class}.java".replace("//", "/")
    parent = str(Path(focal).parent).replace("\\", "/")
    return f"{parent}/src/test/java/{package_path}/{test_class}.java".replace("//", "/")


def placeholder_test_source(package_name: str, test_class: str) -> str:
    package_line = f"package {package_name};\n\n" if package_name else ""
    return f"{package_line}public class {test_class} {{\n}}\n"


def infer_test_framework(repo_dir: Path, module_dir: str) -> dict[str, str | None]:
    search_dir = repo_dir / module_dir if module_dir else repo_dir
    texts: list[str] = []
    for name in ["pom.xml", "build.gradle", "build.gradle.kts"]:
        path = search_dir / name
        if path.exists():
            texts.append(read_text(path).lower())
    text = "\n".join(texts)
    if "testng" in text:
        return {"junit_version": None, "testng_version": "7"}
    if "junit-jupiter" in text or "org.junit.jupiter" in text:
        return {"junit_version": "5", "testng_version": None}
    return {"junit_version": "4", "testng_version": None}


def infer_gradle_version(repo_dir: Path, module_dir: str, build_root: str = "") -> str:
    module = normalize_repo_rel_path(module_dir)
    root = normalize_repo_rel_path(build_root)
    candidates: list[Path] = []
    if root and root != ".":
        candidates.append(repo_dir / root / "gradle" / "wrapper" / "gradle-wrapper.properties")
    else:
        candidates.append(repo_dir / "gradle" / "wrapper" / "gradle-wrapper.properties")
    if module and module != root:
        candidates.append(repo_dir / module / "gradle" / "wrapper" / "gradle-wrapper.properties")
    for path in candidates:
        if not path.exists():
            continue
        text = read_text(path)
        match = re.search(r"gradle-([0-9]+(?:\.[0-9]+)*)(?:-(?:bin|all))?\.zip", text)
        if match:
            return match.group(1)
    return "8.4"


@dataclass
class Dataset:
    manifest: pd.DataFrame
    recipes: pd.DataFrame
    sample: pd.DataFrame


def load_dataset(manifest_path: Path, recipes_path: Path, compiled_repos: Path) -> Dataset:
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    recipes = pd.read_csv(recipes_path, dtype=str).fillna("")
    manifest.attrs["source_path"] = str(manifest_path)
    manifest.attrs["source_sha256"] = file_sha256(manifest_path)
    recipes.attrs["source_path"] = str(recipes_path)
    recipes.attrs["source_sha256"] = file_sha256(recipes_path)
    required = {
        "repo_id",
        "class_key",
        "focal_class",
        "focal_path",
        "scope_key",
        "module_dir",
        "build_tool",
        "declared_java_version",
        "effective_java_runtime",
        "selection_hash",
    }
    missing = sorted(required - set(manifest.columns))
    if missing:
        raise ValueError(f"{manifest_path} missing columns: {missing}")
    recipe_required = {"repo_id", "scope_key", "portable_command_windows", "portable_command_posix"}
    recipe_missing = sorted(recipe_required - set(recipes.columns))
    if recipe_missing:
        raise ValueError(f"{recipes_path} missing columns: {recipe_missing}")

    recipe_index = {
        (str(row.repo_id), str(row.scope_key)): row._asdict()
        for row in recipes.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for idx, row in manifest.iterrows():
        repo_id = str(row["repo_id"])
        focal_path = normalize_repo_rel_path(row["focal_path"])
        source_path = compiled_repos / repo_id / focal_path
        package_name = java_package(read_text(source_path)) if source_path.exists() else ""
        short_hash = hashlib.sha1(str(row["class_key"]).encode("utf-8")).hexdigest()[:8]
        test_class = f"{java_identifier(row['focal_class'])}_RBL4_{short_hash}Test"
        test_path = derive_test_path(focal_path, package_name, test_class)
        module = normalize_repo_rel_path(row["module_dir"])
        if module in {"", "."}:
            module = ""
        build_tool = str(row["build_tool"]).strip().lower()
        recipe = recipe_index.get((repo_id, str(row["scope_key"])), {})
        record = row.to_dict()
        record.update(
            {
                "sample_index": idx,
                "Project": repo_id,
                "Focal_Class": str(row["focal_class"]),
                "Test_Class": test_class,
                "Focal_Path": f"repos/{repo_id}/{focal_path}",
                "Test_Path": f"repos/{repo_id}/{test_path}",
                "Module": module,
                "Repo_Dir": str(compiled_repos / repo_id),
                "Compiled_Focal_Path": str(source_path),
                "Synthesized_Test_Rel_Path": test_path,
                "Package": package_name,
                "Java_Version": normalize_java_version(row["declared_java_version"]),
                "Build_Tool": "Gradle" if build_tool == "gradle" else "Maven",
                "Recipe_Command_Windows": recipe.get("portable_command_windows", ""),
                "Recipe_Command_Posix": recipe.get("portable_command_posix", ""),
                "Recipe_ID": recipe.get("recipe_id", ""),
            }
        )
        rows.append(record)
    sample = pd.DataFrame(rows)
    return Dataset(manifest=manifest, recipes=recipes, sample=sample)


def preflight(dataset: Dataset, compiled_repos: Path, run_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    sample = dataset.sample.copy()
    sample["repo_exists"] = sample["Project"].map(lambda repo: int((compiled_repos / str(repo)).is_dir()))
    sample["focal_exists"] = sample["Compiled_Focal_Path"].map(lambda p: int(Path(str(p)).exists()))
    sample["recipe_exists"] = sample.apply(lambda row: int(bool(row["Recipe_Command_Windows"] or row["Recipe_Command_Posix"])), axis=1)
    sample["duplicate_class_key"] = sample.duplicated("class_key", keep=False).astype(int)
    sample["duplicate_focal_path"] = sample.duplicated(["Project", "focal_path"], keep=False).astype(int)
    sample["preflight_status"] = sample.apply(
        lambda row: "PASS"
        if row["repo_exists"] and row["focal_exists"] and row["recipe_exists"] and not row["duplicate_class_key"] and not row["duplicate_focal_path"]
        else "FAIL",
        axis=1,
    )
    scope_pairs = dataset.manifest[["repo_id", "scope_key"]].drop_duplicates()
    recipe_pairs = dataset.recipes[["repo_id", "scope_key"]].drop_duplicates()
    missing_scopes = (
        scope_pairs.merge(recipe_pairs, on=["repo_id", "scope_key"], how="left", indicator=True)
        .query("_merge == 'left_only'")[["repo_id", "scope_key"]]
        .to_dict(orient="records")
    )
    report = {
        "timestamp_utc": utc_now(),
        "manifest_csv": str(dataset.manifest.attrs.get("source_path", "")),
        "manifest_sha256": str(dataset.manifest.attrs.get("source_sha256", "")),
        "recipes_csv": str(dataset.recipes.attrs.get("source_path", "")),
        "recipes_sha256": str(dataset.recipes.attrs.get("source_sha256", "")),
        "manifest_rows": int(len(dataset.manifest)),
        "manifest_repos": int(dataset.manifest["repo_id"].nunique()),
        "recipe_rows": int(len(dataset.recipes)),
        "recipe_scopes": int(recipe_pairs.shape[0]),
        "classes_per_repo_min": int(dataset.manifest.groupby("repo_id").size().min()),
        "classes_per_repo_max": int(dataset.manifest.groupby("repo_id").size().max()),
        "classes_per_repo": {
            str(key): int(value)
            for key, value in dataset.manifest.groupby("repo_id").size().sort_index().items()
        },
        "selected_type_counts": {
            str(key): int(value)
            for key, value in dataset.manifest["selected_type"].astype(str).value_counts().sort_index().items()
        }
        if "selected_type" in dataset.manifest.columns
        else {},
        "complexity_half_counts": {
            str(key): int(value)
            for key, value in dataset.manifest["complexity_half"].astype(str).value_counts().sort_index().items()
        }
        if "complexity_half" in dataset.manifest.columns
        else {},
        "build_tool_counts": {
            str(key): int(value)
            for key, value in dataset.manifest["build_tool"].astype(str).value_counts().sort_index().items()
        }
        if "build_tool" in dataset.manifest.columns
        else {},
        "split_name_counts": {
            str(key): int(value)
            for key, value in dataset.manifest["split_name"].astype(str).value_counts().sort_index().items()
        }
        if "split_name" in dataset.manifest.columns
        else {},
        "compiledrepos_root": str(compiled_repos),
        "repo_missing_n": int((sample["repo_exists"] == 0).sum()),
        "focal_missing_n": int((sample["focal_exists"] == 0).sum()),
        "recipe_missing_n": int((sample["recipe_exists"] == 0).sum()),
        "preflight_failed_class_n": int((sample["preflight_status"] != "PASS").sum()),
        "duplicate_class_key_rows": int(sample["duplicate_class_key"].sum()),
        "duplicate_focal_path_rows": int(sample["duplicate_focal_path"].sum()),
        "missing_scope_recipes": missing_scopes,
        "prompt_hash_sha256": prompt_hash(),
        "prompt_protocol": "AgoneTest base zero-shot prompt from proposal; no java_language_rules; no project_structure/dependencies.",
    }
    write_csv_artifact(sample, run_dir / "preflight_classes.csv")
    (run_dir / "preflight_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return sample, report


def command_for_recipe(row: pd.Series) -> str:
    if platform.system() == "Windows":
        return str(row.get("Recipe_Command_Windows", "")).strip()
    return str(row.get("Recipe_Command_Posix", "")).strip()


def _maven_file_arg(command: str, repo_dir: Path) -> Path | None:
    match = re.search(r"(?:^|\s)-f\s+(\"[^\"]+\"|\S+)", command)
    if not match:
        return None
    raw = match.group(1).strip().strip('"').replace("${REPO_DIR}", str(repo_dir))
    path = Path(raw)
    if not path.is_absolute():
        path = repo_dir / path
    return path


def _maven_pl_arg(command: str) -> str:
    match = re.search(r"(?:^|\s)-pl\s+(\"[^\"]+\"|'[^']+'|\S+)", command)
    if not match:
        return ""
    return match.group(1).strip().strip('"').strip("'").replace("\\", "/")


def _has_maven_also_make(command: str) -> bool:
    return bool(re.search(r"(?:^|\s)-am(?=\s|$)", command))


def _quote_cli_arg(value: Any) -> str:
    text = str(value)
    escaped = text.replace('"', '\\"')
    return f'"{escaped}"'


def _maven_settings_clause(repo_id: Any) -> str:
    repair_settings = ROOT / "repair_configs" / str(repo_id) / "settings_retry.xml"
    if repair_settings.exists():
        return f"-s {_quote_cli_arg(repair_settings)}"
    settings_path = ROOT / "settings.xml"
    if settings_path.exists():
        return f"-s {_quote_cli_arg(settings_path)}"
    return ""


def _replace_maven_file_arg(command: str, pom_path: Path) -> str:
    pom_text = str(pom_path)

    def repl(match: re.Match[str]) -> str:
        prefix = match.group(1)
        return f'{prefix}"{pom_text}"'

    return re.sub(r"((?:^|\s)-f\s+)(\"[^\"]+\"|\S+)", repl, command, count=1)


def _remove_maven_pl_am(command: str) -> str:
    command = re.sub(r"\s+-pl\s+(\"[^\"]+\"|\S+)", "", command)
    command = re.sub(r"\s+-am(?=\s|$)", "", command)
    return re.sub(r"\s+", " ", command).strip()


def _candidate_project_dirs(row: pd.Series, repo_dir: Path) -> list[Path]:
    dirs: list[Path] = []
    for value in [
        row.get("build_root") or row.get("Build_Root") or row.get("build_root_relative") or "",
        row.get("module_dir") or row.get("Module") or row.get("module_dir_relative") or "",
        row.get("working_directory_placeholder") or "",
    ]:
        rel = normalize_repo_rel_path(value)
        if not rel or rel in {".", "${REPO_DIR}", "repository_wrapper"}:
            continue
        path = repo_dir / rel
        if path not in dirs:
            dirs.append(path)
    if repo_dir not in dirs:
        dirs.append(repo_dir)
    return dirs


def _gradle_wrapper_name() -> str:
    return "gradlew.bat" if platform.system() == "Windows" else "gradlew"


def _gradle_token_regex() -> re.Pattern[str]:
    if platform.system() == "Windows":
        return re.compile(r'("[^"]*(?:gradlew\.bat|gradle\.bat)"|\S*(?:gradlew\.bat|gradle\.bat)|\bgradle\.bat\b)', re.IGNORECASE)
    return re.compile(r'("[^"]*gradlew"|\S*gradlew|\bgradle\b)', re.IGNORECASE)


def _strip_quotes(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _replace_first_token(command: str, token: str, replacement: str) -> str:
    return command.replace(token, replacement, 1)


def normalize_gradle_command(command: str, row: pd.Series, repo_dir: Path) -> tuple[str, str, Path]:
    project_dirs = _candidate_project_dirs(row, repo_dir)
    existing_project_dirs = [path for path in project_dirs if path.exists() and path.is_dir()]
    working_dir = existing_project_dirs[0] if existing_project_dirs else repo_dir
    wrapper_name = _gradle_wrapper_name()
    wrapper_candidates = [path / wrapper_name for path in project_dirs]
    selected_wrapper = next((path for path in wrapper_candidates if path.exists()), None)

    detail_parts: list[str] = []
    token_match = _gradle_token_regex().search(command)
    fixed = command
    current_wrapper: Path | None = None
    token = token_match.group(0) if token_match else ""
    if token:
        raw_token = _strip_quotes(token)
        if raw_token.lower() not in {"gradle", "gradle.bat"}:
            current_wrapper = Path(raw_token)
            if not current_wrapper.is_absolute():
                current_wrapper = repo_dir / current_wrapper

    if selected_wrapper:
        replacement = f'"{selected_wrapper}"'
        if token:
            if current_wrapper and current_wrapper.exists():
                working_dir = current_wrapper.parent
            elif current_wrapper and current_wrapper != selected_wrapper:
                fixed = _replace_first_token(fixed, token, replacement)
                working_dir = selected_wrapper.parent
                detail_parts.append(f"normalized Gradle wrapper {current_wrapper} -> {selected_wrapper}")
            else:
                fixed = _replace_first_token(fixed, token, replacement)
                working_dir = selected_wrapper.parent
        elif fixed.strip():
            fixed = f'{replacement} {fixed}'
            working_dir = selected_wrapper.parent
            detail_parts.append(f"added Gradle wrapper {selected_wrapper}")
    elif current_wrapper and not current_wrapper.exists():
        global_gradle = "gradle.bat" if platform.system() == "Windows" else "gradle"
        fixed = _replace_first_token(fixed, token, global_gradle)
        detail_parts.append(f"missing Gradle wrapper {current_wrapper}; falling back to {global_gradle}")

    if platform.system() == "Windows" and re.match(r'^\s*"[^"]*\.bat"', fixed, flags=re.IGNORECASE):
        fixed = "call " + fixed.lstrip()

    if working_dir != repo_dir:
        detail_parts.append(f"baseline cwd {repo_dir} -> {working_dir}")
    return fixed, "; ".join(detail_parts), working_dir


def normalize_baseline_command(command: str, row: pd.Series, repo_dir: Path) -> tuple[str, str, Path]:
    command = command.replace("${REPO_DIR}", str(repo_dir))
    build_tool = str(row.get("Build_Tool", "")).lower()
    if build_tool == "gradle":
        return normalize_gradle_command(command, row, repo_dir)
    if build_tool != "maven":
        return command, "", repo_dir

    current_pom = _maven_file_arg(command, repo_dir)
    if current_pom is None or current_pom.exists():
        return command, "", repo_dir

    build_root = normalize_repo_rel_path(row.get("build_root") or row.get("Build_Root") or "")
    module_dir = normalize_repo_rel_path(row.get("module_dir") or row.get("Module") or "")
    module_selector = str(row.get("module_selector", "") or "").strip()
    has_pl = bool(re.search(r"(?:^|\s)-pl\s+", command))

    build_root_pom = repo_dir / build_root / "pom.xml" if build_root and build_root != "." else repo_dir / "pom.xml"
    module_pom = repo_dir / module_dir / "pom.xml" if module_dir and module_dir != "." else build_root_pom

    selected_pom: Path | None = None
    remove_pl = False
    if has_pl and module_selector and module_selector != "." and build_root_pom.exists():
        selected_pom = build_root_pom
    elif module_pom.exists():
        selected_pom = module_pom
        remove_pl = has_pl
    elif build_root_pom.exists():
        selected_pom = build_root_pom

    if selected_pom is None:
        return command, f"missing -f POM: {current_pom}; no fallback POM found", repo_dir

    fixed = _replace_maven_file_arg(command, selected_pom)
    if remove_pl:
        fixed = _remove_maven_pl_am(fixed)
    return fixed, f"normalized missing POM {current_pom} -> {selected_pom}", repo_dir


def build_maven_reactor_prewarm_command(row: pd.Series, repo_dir: Path) -> tuple[str, str, Path] | None:
    if str(row.get("Build_Tool", "")).lower() != "maven":
        return None

    command = command_for_recipe(row)
    if not command:
        return None

    normalized_command, normalization_detail, command_cwd = normalize_baseline_command(command, row, repo_dir)
    if not _has_maven_also_make(normalized_command):
        return None

    module_selector = _maven_pl_arg(normalized_command)
    if not module_selector or module_selector == ".":
        return None

    pom_path = _maven_file_arg(normalized_command, repo_dir)
    if pom_path is None:
        build_root = normalize_repo_rel_path(row.get("build_root") or row.get("Build_Root") or "")
        pom_path = repo_dir / build_root / "pom.xml" if build_root and build_root != "." else repo_dir / "pom.xml"
    if not pom_path.exists():
        return None

    maven = "mvn"
    skip_args = [
        "-DskipTests",
        "-DskipITs",
        "-Dgpg.skip=true",
        "-Dcheckstyle.skip=true",
        "-Drat.skip=true",
        "-Dlicense.skip=true",
        "-Ddependency-check.skip=true",
        "-Dfrontend.skip=true",
        "-Dskip.npm=true",
        "-Dskip.bower=true",
        "-Dskip.yarn=true",
        "-Dskip.grunt=true",
        "-Dskip.gulp=true",
        "-Dskip.webpack=true",
        "-Denforcer.skip=true",
        "-Dspotbugs.skip=true",
        "-Dspotless.skip=true",
        "-Dspotless.apply.skip=true",
        "-Dspotless.check.skip=true",
        "-Dfindbugs.skip=true",
        "-Dpmd.skip=true",
        "-Dcpd.skip=true",
        "-Dformatter.skip=true",
        "-Dexec.skip=true",
        "-Dspring-boot.repackage.skip=true",
        "-Djacoco.skip=true",
        "-Dmaven.javadoc.skip=true",
        "-DfailIfNoTests=false",
        "-DfailIfNoSpecifiedTests=false",
    ]
    settings_clause = _maven_settings_clause(row.get("Project", row.get("repo_id", "")))
    prewarm_command = (
        f"{maven} -B -ntp -nsu {settings_clause} "
        f"{' '.join(skip_args)} "
        f"-f {_quote_cli_arg(pom_path)} "
        f"-pl {_quote_cli_arg(module_selector)} -am install"
    ).replace("  ", " ").strip()
    detail = f"prewarm reactor dependencies for -pl {module_selector}"
    if normalization_detail:
        detail = f"{normalization_detail}; {detail}"
    return prewarm_command, detail, command_cwd


def synthesized_test_file(row: pd.Series, sandbox_repo_dir: Path) -> Path | None:
    rel = normalize_repo_rel_path(row.get("Synthesized_Test_Rel_Path", ""))
    if not rel:
        return None
    return sandbox_repo_dir / rel


def hide_synthesized_test_for_prewarm(row: pd.Series, sandbox_repo_dir: Path) -> tuple[Path, Path] | None:
    test_path = synthesized_test_file(row, sandbox_repo_dir)
    if test_path is None or not test_path.exists():
        return None
    hidden_path = test_path.with_name(f".{test_path.name}.rbl4_prewarm_hidden_{os.getpid()}_{time.time_ns()}")
    test_path.replace(hidden_path)
    return test_path, hidden_path


def restore_synthesized_test_for_prewarm(hidden: tuple[Path, Path] | None) -> None:
    if hidden is None:
        return
    test_path, hidden_path = hidden
    if hidden_path.exists():
        hidden_path.replace(test_path)


def run_maven_reactor_prewarm(row: pd.Series, sandbox: Path, run_dir: Path) -> bool:
    repo_id = str(row.get("Project", row.get("repo_id", "")))
    scope_key = str(row.get("scope_key", ""))
    cache_key = (str(sandbox.resolve()), repo_id, scope_key)
    with PREWARMED_REACTOR_SCOPES_LOCK:
        already_prewarmed = cache_key in PREWARMED_REACTOR_SCOPES
    if already_prewarmed:
        return True

    sandbox_repo_dir = sandbox / "compiledrepos" / repo_id
    command_info = build_maven_reactor_prewarm_command(row, sandbox_repo_dir)
    if command_info is None:
        return True

    command, detail, command_cwd = command_info

    # Maven writes installed module artifacts into the shared local repository.
    # Parallel prewarm of the same repo/module can corrupt or race on SNAPSHOT installs.
    scope_lock = maven_prewarm_scope_lock(repo_id, scope_key)
    lock_wait_started = time.time()
    with scope_lock:
        wait_seconds = time.time() - lock_wait_started
        if wait_seconds >= 0.1:
            append_phase(
                run_dir,
                "maven_reactor_prewarm_wait",
                project=repo_id,
                module=row.get("Module", ""),
                sample_index=row.get("sample_index", ""),
                class_key=row.get("class_key", ""),
                focal_class=row.get("Focal_Class", ""),
                status="PASS",
                started_at=lock_wait_started,
                detail=f"waited {wait_seconds:.3f}s for same repo prewarm lock: {scope_key}",
            )
        with PREWARMED_REACTOR_SCOPES_LOCK:
            already_prewarmed = cache_key in PREWARMED_REACTOR_SCOPES
        if already_prewarmed:
            return True

        hidden_test = hide_synthesized_test_for_prewarm(row, sandbox_repo_dir)
        if hidden_test is not None:
            detail = f"{detail}; synthesized placeholder test hidden during prewarm: {hidden_test[0].name}"
        started = time.time()
        append_phase(
            run_dir,
            "maven_reactor_prewarm",
            project=repo_id,
            module=row.get("Module", ""),
            sample_index=row.get("sample_index", ""),
            class_key=row.get("class_key", ""),
            focal_class=row.get("Focal_Class", ""),
            status="START",
            detail=detail,
        )
        toolchains = load_toolchains()
        env = toolchains.build_java_env(row.get("Java_Version"), min_major=8)
        env["RBL4_MAVEN_REACTOR_PREWARM"] = "1"
        try:
            try:
                result = subprocess.run(
                    command,
                    cwd=command_cwd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=int(os.getenv("RBL4_REACTOR_PREWARM_TIMEOUT_SECONDS", "900")),
                    env=env,
                )
            finally:
                restore_synthesized_test_for_prewarm(hidden_test)
            output_tail = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()[-5000:]
            if result.returncode == 0:
                with PREWARMED_REACTOR_SCOPES_LOCK:
                    PREWARMED_REACTOR_SCOPES.add(cache_key)
                append_phase(
                    run_dir,
                    "maven_reactor_prewarm",
                    project=repo_id,
                    module=row.get("Module", ""),
                    sample_index=row.get("sample_index", ""),
                    class_key=row.get("class_key", ""),
                    focal_class=row.get("Focal_Class", ""),
                    status="PASS",
                    started_at=started,
                    detail=f"{detail}\n{output_tail}"[-5000:],
                )
                return True

            append_phase(
                run_dir,
                "maven_reactor_prewarm",
                project=repo_id,
                module=row.get("Module", ""),
                sample_index=row.get("sample_index", ""),
                class_key=row.get("class_key", ""),
                focal_class=row.get("Focal_Class", ""),
                status="FAIL",
                started_at=started,
                detail=f"{detail}\ncommand={command}\n{output_tail}"[-5000:],
            )
            return False
        except subprocess.TimeoutExpired as exc:
            restore_synthesized_test_for_prewarm(hidden_test)
            out = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            err = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            append_phase(
                run_dir,
                "maven_reactor_prewarm",
                project=repo_id,
                module=row.get("Module", ""),
                sample_index=row.get("sample_index", ""),
                class_key=row.get("class_key", ""),
                focal_class=row.get("Focal_Class", ""),
                status="ERROR",
                started_at=started,
                detail=f"timeout\n{detail}\n{out}\n{err}"[-5000:],
            )
            return False
        except Exception:
            restore_synthesized_test_for_prewarm(hidden_test)
            raise


def sandbox_focal_path(row: pd.Series, sandbox_repo_dir: Path) -> Path:
    repo_id = str(row.get("Project", row.get("repo_id", "")))
    raw = normalize_repo_rel_path(row.get("Focal_Path") or row.get("focal_path") or "")
    for prefix in [f"repos/{repo_id}/", f"compiledrepos/{repo_id}/", f"{repo_id}/"]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    marker = f"/{repo_id}/"
    if marker in raw:
        raw = raw.split(marker, 1)[1]
    return sandbox_repo_dir / raw


def find_gradle_main_classes_dir(row: pd.Series, sandbox_repo_dir: Path) -> Path | None:
    def main_classes_under(base: Path) -> Path | None:
        for rel in [
            Path("build") / "classes" / "java" / "main",
            Path("build") / "classes" / "main",
            Path("build") / "classes" / "kotlin" / "main",
        ]:
            classes_dir = base / rel
            if classes_dir.is_dir():
                return classes_dir
        return None

    focal = sandbox_focal_path(row, sandbox_repo_dir)
    start = focal.parent if focal.suffix else focal
    try:
        repo_root = sandbox_repo_dir.resolve()
    except OSError:
        repo_root = sandbox_repo_dir

    current = start
    while True:
        classes_dir = main_classes_under(current)
        if classes_dir is not None:
            return classes_dir
        if current == sandbox_repo_dir or current.parent == current:
            break
        try:
            current.relative_to(repo_root)
        except ValueError:
            break
        current = current.parent

    for value in [row.get("module_dir"), row.get("Module"), row.get("build_root"), row.get("Build_Root")]:
        rel = normalize_repo_rel_path(value)
        if not rel or rel in {".", "${REPO_DIR}", "repository_wrapper"}:
            continue
        classes_dir = main_classes_under(sandbox_repo_dir / rel)
        if classes_dir is not None:
            return classes_dir
        for layout in [
            sandbox_repo_dir / "build" / rel / "classes" / "java" / "main",
            sandbox_repo_dir / "build" / rel / "classes" / "main",
            sandbox_repo_dir / "build" / rel / "classes" / "kotlin" / "main",
        ]:
            if layout.is_dir():
                return layout
    return main_classes_under(sandbox_repo_dir)


def run_gradle_sandbox_prewarm(row: pd.Series, sandbox: Path, run_dir: Path) -> bool:
    if str(row.get("Build_Tool", "")).lower() != "gradle":
        return True

    repo_id = str(row.get("Project", row.get("repo_id", "")))
    sandbox_repo_dir = sandbox / "compiledrepos" / repo_id
    command = command_for_recipe(row)
    started = time.time()
    if not command:
        append_phase(
            run_dir,
            "gradle_sandbox_prewarm",
            project=repo_id,
            module=row.get("Module", ""),
            sample_index=row.get("sample_index", ""),
            class_key=row.get("class_key", ""),
            focal_class=row.get("Focal_Class", ""),
            status="FAIL",
            started_at=started,
            detail="missing portable Gradle build command",
        )
        return False

    command, normalization_detail, command_cwd = normalize_baseline_command(command, row, sandbox_repo_dir)
    detail = "compile Gradle sandbox before AgoneTest/EvoSuite"
    if normalization_detail:
        detail = f"{normalization_detail}; {detail}"
    hidden_test = hide_synthesized_test_for_prewarm(row, sandbox_repo_dir)
    if hidden_test is not None:
        detail = f"{detail}; synthesized placeholder test hidden during prewarm: {hidden_test[0].name}"
    append_phase(
        run_dir,
        "gradle_sandbox_prewarm",
        project=repo_id,
        module=row.get("Module", ""),
        sample_index=row.get("sample_index", ""),
        class_key=row.get("class_key", ""),
        focal_class=row.get("Focal_Class", ""),
        status="START",
        detail=detail,
    )

    toolchains = load_toolchains()
    env = toolchains.build_java_env(row.get("Java_Version"), min_major=8)
    env["RBL4_GRADLE_SANDBOX_PREWARM"] = "1"
    try:
        try:
            result = subprocess.run(
                command,
                cwd=command_cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=int(os.getenv("RBL4_GRADLE_PREWARM_TIMEOUT_SECONDS", "900")),
                env=env,
            )
        finally:
            restore_synthesized_test_for_prewarm(hidden_test)
        output_tail = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()[-5000:]
        classes_dir = find_gradle_main_classes_dir(row, sandbox_repo_dir)
        if result.returncode == 0 and classes_dir is not None:
            append_phase(
                run_dir,
                "gradle_sandbox_prewarm",
                project=repo_id,
                module=row.get("Module", ""),
                sample_index=row.get("sample_index", ""),
                class_key=row.get("class_key", ""),
                focal_class=row.get("Focal_Class", ""),
                status="PASS",
                started_at=started,
                detail=f"{detail}; classes_dir={classes_dir}\n{output_tail}"[-5000:],
            )
            return True

        reason = "Gradle command returned non-zero" if result.returncode != 0 else "Gradle command passed but build/classes/java/main was not found"
        append_phase(
            run_dir,
            "gradle_sandbox_prewarm",
            project=repo_id,
            module=row.get("Module", ""),
            sample_index=row.get("sample_index", ""),
            class_key=row.get("class_key", ""),
            focal_class=row.get("Focal_Class", ""),
            status="FAIL",
            started_at=started,
            detail=f"{reason}; command={command}\n{detail}\n{output_tail}"[-5000:],
        )
        return False
    except subprocess.TimeoutExpired as exc:
        restore_synthesized_test_for_prewarm(hidden_test)
        out = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        append_phase(
            run_dir,
            "gradle_sandbox_prewarm",
            project=repo_id,
            module=row.get("Module", ""),
            sample_index=row.get("sample_index", ""),
            class_key=row.get("class_key", ""),
            focal_class=row.get("Focal_Class", ""),
            status="ERROR",
            started_at=started,
            detail=f"timeout; command={command}\n{detail}\n{out}\n{err}"[-5000:],
        )
        return False
    except Exception as exc:
        restore_synthesized_test_for_prewarm(hidden_test)
        append_phase(
            run_dir,
            "gradle_sandbox_prewarm",
            project=repo_id,
            module=row.get("Module", ""),
            sample_index=row.get("sample_index", ""),
            class_key=row.get("class_key", ""),
            focal_class=row.get("Focal_Class", ""),
            status="ERROR",
            started_at=started,
            detail=f"{type(exc).__name__}: {exc}; command={command}\n{detail}"[-5000:],
        )
        return False


def load_toolchains():
    sys.path.insert(0, str((ROOT / "AgoneTest").resolve()))
    import toolchains  # type: ignore

    return toolchains


def run_baseline_scopes(sample: pd.DataFrame, run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    toolchains = load_toolchains()
    rows: list[dict[str, Any]] = []
    grouped = sample.groupby(["Project", "scope_key"], dropna=False)
    for (repo_id, scope_key), group in grouped:
        first = group.iloc[0]
        started = time.time()
        command = command_for_recipe(first)
        repo_dir = Path(str(first["Repo_Dir"]))
        module = str(first.get("Module", ""))
        status = "FAIL"
        detail = ""
        if not repo_dir.exists():
            detail = f"missing repo: {repo_dir}"
        elif not command:
            detail = "missing portable build command"
        else:
            command, normalization_detail, command_cwd = normalize_baseline_command(command, first, repo_dir)
            env = toolchains.build_java_env(first.get("Java_Version"), min_major=8)
            try:
                result = subprocess.run(
                    command,
                    cwd=command_cwd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=int(os.getenv("RBL4_BASELINE_TIMEOUT_SECONDS", "900")),
                    env=env,
                )
                status = "PASS" if result.returncode == 0 else "FAIL"
                detail = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()[-5000:]
                if normalization_detail:
                    detail = f"{normalization_detail}\n{detail}"[-5000:]
            except subprocess.TimeoutExpired as exc:
                status = "FAIL"
                out = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                err = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                detail = f"timeout\n{out}\n{err}"[-5000:]
                if normalization_detail:
                    detail = f"{normalization_detail}\n{detail}"[-5000:]
        row = {
            "project": repo_id,
            "scope_key": scope_key,
            "module": module,
            "class_rows": int(len(group)),
            "focal_classes": ";".join(group["Focal_Class"].astype(str).tolist()),
            "build_tool": first.get("Build_Tool", ""),
            "java_version": first.get("Java_Version", ""),
            "command": command,
            "status": status,
            "duration_sec": round(time.time() - started, 3),
            "detail": detail,
        }
        rows.append(row)
        append_phase(run_dir, "baseline_scope_build", project=repo_id, module=module, status=status, started_at=started, detail=detail or command)
    scope_df = pd.DataFrame(rows)
    status_by_scope = {
        (str(row.project), str(row.scope_key)): str(row.status)
        for row in scope_df.itertuples(index=False)
    }
    class_rows = []
    for _, row in sample.iterrows():
        status = status_by_scope.get((str(row["Project"]), str(row["scope_key"])), "FAIL")
        rec = row.to_dict()
        rec["baseline_build_status"] = status
        class_rows.append(rec)
    class_df = pd.DataFrame(class_rows)
    write_csv_artifact(scope_df, run_dir / "baseline_scope_build.csv")
    write_csv_artifact(class_df, run_dir / "baseline_classes.csv")
    return scope_df, class_df


def run_baseline_readiness_one(row: pd.Series, readiness_workspace_key: Path, run_dir: Path, compiled_repos: Path) -> dict[str, Any]:
    started = time.time()
    repo_id = str(row.get("Project", row.get("repo_id", "")))
    status = "FAIL"
    fail_stage = ""
    detail = ""
    sandbox_path = ""
    append_phase(
        run_dir,
        "baseline_sandbox_readiness",
        project=repo_id,
        module=row.get("Module", ""),
        sample_index=row.get("sample_index", ""),
        class_key=row.get("class_key", ""),
        focal_class=row.get("Focal_Class", row.get("focal_class", "")),
        test_class=row.get("Test_Class", ""),
        status="START",
        detail="prepare per-class sandbox and run generation prewarm without invoking GPT/EvoSuite",
    )
    if str(row.get("baseline_build_status", "")) != "PASS":
        fail_stage = "baseline_scope_build_failed"
        detail = "scope baseline failed; sandbox readiness skipped"
    else:
        try:
            sandbox = prepare_sandbox(row, readiness_workspace_key, compiled_repos)
            sandbox_path = str(sandbox)
            if not run_maven_reactor_prewarm(row, sandbox, run_dir):
                fail_stage = "maven_reactor_prewarm_failed"
                detail = "Maven reactor prewarm failed in baseline-equivalent sandbox"
            elif not run_gradle_sandbox_prewarm(row, sandbox, run_dir):
                fail_stage = "gradle_sandbox_prewarm_failed"
                detail = "Gradle sandbox prewarm failed in baseline-equivalent sandbox"
            else:
                status = "PASS"
                fail_stage = "ok"
                detail = "sandbox readiness passed"
        except Exception as exc:
            fail_stage = "sandbox_prepare_failed"
            detail = f"{type(exc).__name__}: {exc}"

    append_phase(
        run_dir,
        "baseline_sandbox_readiness",
        project=repo_id,
        module=row.get("Module", ""),
        sample_index=row.get("sample_index", ""),
        class_key=row.get("class_key", ""),
        focal_class=row.get("Focal_Class", row.get("focal_class", "")),
        test_class=row.get("Test_Class", ""),
        status=status,
        started_at=started,
        detail=f"{fail_stage}; {detail}",
    )
    return {
        "sample_index": row.get("sample_index", ""),
        "class_key": row.get("class_key", ""),
        "project": repo_id,
        "repo_id": repo_id,
        "module": row.get("Module", ""),
        "scope_key": row.get("scope_key", ""),
        "build_tool": row.get("Build_Tool", row.get("build_tool", "")),
        "focal_class": row.get("Focal_Class", row.get("focal_class", "")),
        "test_class": row.get("Test_Class", ""),
        "status": status,
        "fail_stage": fail_stage,
        "duration_sec": round(time.time() - started, 3),
        "sandbox_path": sandbox_path,
        "detail": detail,
    }


def run_baseline_sandbox_readiness(class_df: pd.DataFrame, run_dir: Path, compiled_repos: Path, workers: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    readiness_workspace_key = run_dir.parent / f"{run_dir.name}__baseline_readiness"
    updated = class_df.copy()
    row_items = [row.copy() for _, row in updated.iterrows()]
    worker_count = max(1, int(workers or 1))
    append_phase(
        run_dir,
        "baseline_sandbox_readiness_workers",
        status="PASS",
        detail=f"workers={worker_count}; classes={len(row_items)}",
    )
    if worker_count == 1 or len(row_items) <= 1:
        for row in row_items:
            rows.append(run_baseline_readiness_one(row, readiness_workspace_key, run_dir, compiled_repos))
    else:
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="rbl4-readiness") as executor:
            futures = {
                executor.submit(run_baseline_readiness_one, row, readiness_workspace_key, run_dir, compiled_repos): row
                for row in row_items
            }
            for future in as_completed(futures):
                row = futures[future]
                try:
                    rows.append(future.result())
                except Exception as exc:
                    repo_id = str(row.get("Project", row.get("repo_id", "")))
                    append_phase(
                        run_dir,
                        "baseline_sandbox_readiness",
                        project=repo_id,
                        module=row.get("Module", ""),
                        sample_index=row.get("sample_index", ""),
                        class_key=row.get("class_key", ""),
                        focal_class=row.get("Focal_Class", row.get("focal_class", "")),
                        test_class=row.get("Test_Class", ""),
                        status="ERROR",
                        detail=f"worker_exception: {type(exc).__name__}: {exc}",
                    )
                    rows.append(
                        {
                            "sample_index": row.get("sample_index", ""),
                            "class_key": row.get("class_key", ""),
                            "project": repo_id,
                            "repo_id": repo_id,
                            "module": row.get("Module", ""),
                            "scope_key": row.get("scope_key", ""),
                            "build_tool": row.get("Build_Tool", row.get("build_tool", "")),
                            "focal_class": row.get("Focal_Class", row.get("focal_class", "")),
                            "test_class": row.get("Test_Class", ""),
                            "status": "ERROR",
                            "fail_stage": "worker_exception",
                            "duration_sec": "",
                            "sandbox_path": "",
                            "detail": f"{type(exc).__name__}: {exc}",
                        }
                    )

    readiness_df = pd.DataFrame(rows)
    if not readiness_df.empty:
        readiness_df["_sample_sort"] = pd.to_numeric(readiness_df["sample_index"], errors="coerce")
        readiness_df = readiness_df.sort_values(["_sample_sort", "class_key"]).drop(columns=["_sample_sort"])
    write_csv_artifact(readiness_df, run_dir / "baseline_sandbox_readiness.csv")
    if not readiness_df.empty:
        key_cols = ["sample_index", "class_key"]
        readiness_small = readiness_df[
            key_cols + ["status", "fail_stage", "detail", "sandbox_path", "duration_sec"]
        ].rename(
            columns={
                "status": "sandbox_readiness_status",
                "fail_stage": "sandbox_readiness_fail_stage",
                "detail": "sandbox_readiness_detail",
                "sandbox_path": "sandbox_readiness_path",
                "duration_sec": "sandbox_readiness_duration_sec",
            }
        )
        updated = updated.merge(readiness_small, on=key_cols, how="left")
    else:
        updated["sandbox_readiness_status"] = ""
        updated["sandbox_readiness_fail_stage"] = ""
        updated["sandbox_readiness_detail"] = ""
        updated["sandbox_readiness_path"] = ""
        updated["sandbox_readiness_duration_sec"] = ""

    updated["baseline_scope_status"] = updated["baseline_build_status"]
    updated["baseline_build_status"] = updated.apply(
        lambda rec: "PASS"
        if str(rec.get("baseline_scope_status", "")) == "PASS"
        and str(rec.get("sandbox_readiness_status", "")) == "PASS"
        else "FAIL",
        axis=1,
    )
    write_csv_artifact(updated, run_dir / "baseline_classes.csv")
    return readiness_df, updated


def copy_repo_to_sandbox(source_repo: Path, target_repo: Path) -> None:
    ignore_names = {
        ".git",
        ".gradle",
        ".evosuite",
        "evosuite-tests",
        "evosuite-report",
        "target",
        "build",
    }

    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignore_names}

    shutil.copytree(source_repo, target_repo, ignore=ignore)


def write_run_settings(model: str, prompt_name: str) -> None:
    settings = {
        "agents": [
            {"model": "evosuite"},
            {
                "model": model,
                "temperature": 0,
                "top_p": 1,
                "max_tokens": 2048,
                "frequency_penalty": 0,
                "presence_penalty": 0,
            },
        ],
        "prompts": [{"name": prompt_name, "value": PROMPT_MESSAGES}],
    }
    with (ROOT / "AgoneTest" / "run_settings.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False, allow_unicode=False)
    (ROOT / "prompt_manifest.json").write_text(
        json.dumps(
            {
                "timestamp_utc": utc_now(),
                "prompt_name": prompt_name,
                "model": model,
                "prompt_hash_sha256": prompt_hash(),
                "messages": PROMPT_MESSAGES,
                "protocol_note": "AgoneTest base zero-shot prompt from proposal; source-level rule placeholder removed.",
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def project_info_for_row(row: pd.Series, sandbox_repo: Path) -> dict[str, Any]:
    framework = infer_test_framework(sandbox_repo, str(row.get("Module", "")))
    build_tool = str(row.get("Build_Tool", "Maven"))
    module = str(row.get("Module", ""))
    build_root = normalize_repo_rel_path(row.get("build_root", row.get("Build_Root", "")))
    module_selector = str(row.get("module_selector", row.get("Module_Selector", "")) or "").strip()
    build_version = infer_gradle_version(sandbox_repo, module, build_root) if build_tool == "Gradle" else "3.8.1"
    base_info = {
        "type": build_tool,
        "version": build_version,
        "java_version": row.get("Java_Version", "1.8"),
        "build_root": build_root,
        "module_dir": module,
        "module_selector": module_selector,
        **framework,
    }
    info = {str(row["Project"]): dict(base_info)}
    if module:
        info[str(row["Project"])]["modules"] = [module]
        info[f"{row['Project']}_{module}"] = dict(base_info)
    return info


def prepare_sandbox(row: pd.Series, run_dir: Path, compiled_repos: Path) -> Path:
    # Keep Windows -javaagent paths short enough for old JDK/Gradle/JaCoCo stacks.
    class_id = f"{int(row['sample_index']):03d}_{safe_name(row['Project'])}_{hashlib.sha1(str(row['class_key']).encode()).hexdigest()[:8]}"
    sandbox = ROOT / "workspaces" / run_dir.name / class_id
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "compiledrepos").mkdir(parents=True, exist_ok=True)
    source_repo = compiled_repos / str(row["Project"])
    target_repo = sandbox / "compiledrepos" / str(row["Project"])
    copy_repo_to_sandbox(source_repo, target_repo)
    test_rel = normalize_repo_rel_path(row["Synthesized_Test_Rel_Path"])
    test_file = target_repo / test_rel
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(placeholder_test_source(str(row["Package"]), str(row["Test_Class"])), encoding="utf-8")
    (sandbox / "output" / str(row["Project"])).mkdir(parents=True, exist_ok=True)
    class_row = pd.DataFrame(
        [
            {
                "Project": row["Project"],
                "Focal_Class": row["Focal_Class"],
                "Test_Class": row["Test_Class"],
                "Focal_Path": row["Focal_Path"],
                "Test_Path": row["Test_Path"],
                "Module": row["Module"],
                "Build_Root": row.get("build_root", row.get("Build_Root", "")),
                "Module_Selector": row.get("module_selector", row.get("Module_Selector", "")),
                "Scope_Key": row.get("scope_key", row.get("Scope_Key", "")),
            }
        ]
    )
    class_row.to_csv(sandbox / "output" / "classes.csv", index=False)
    info = project_info_for_row(row, target_repo)
    (sandbox / "output" / "project_info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    for file_name in ["settings.xml", "TestSmellDetector.jar"]:
        src = ROOT / file_name
        if src.exists():
            shutil.copy2(src, sandbox / file_name)
    return sandbox


def compact_log_text(value: Any, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def safe_read_text_tail(path: Path | None, limit: int = 5000) -> str:
    if path is None or not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-limit:]


def class_phase_rows(run_dir: Path, row: pd.Series) -> list[dict[str, str]]:
    path = run_dir / "phase_log.csv"
    if not path.exists() or not path.stat().st_size:
        return []
    for _ in range(3):
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
            break
        except Exception:
            time.sleep(0.1)
    else:
        return []
    sample = str(row.get("sample_index", ""))
    class_key = str(row.get("class_key", ""))
    mask = df["sample_index"].astype(str).eq(sample) if "sample_index" in df.columns else pd.Series(False, index=df.index)
    if class_key and "class_key" in df.columns:
        keyed = mask & df["class_key"].astype(str).eq(class_key)
        if keyed.any():
            mask = keyed
    return df[mask].to_dict(orient="records")


def generated_response_exists(sandbox: Path, row: pd.Series, arm: str) -> bool:
    out_dir = sandbox / "output" / str(row["Project"])
    if not out_dir.exists():
        return False
    if arm == "evosuite":
        return any(out_dir.glob("response_evosuite*.java"))
    return any(path.name.startswith("response_") and not path.name.startswith("response_evosuite") for path in out_dir.glob("response_*.java"))


def agone_artifacts_for_arm(sandbox: Path, row: pd.Series, arm: str, generator: str, prompt_name: str) -> list[Path]:
    out_dir = sandbox / "output" / str(row["Project"])
    if not out_dir.exists():
        return []
    generator_tag = safe_name(generator).lower()
    prompt_tag = safe_name(prompt_name).lower()
    artifacts: list[Path] = []
    for path in out_dir.rglob("TestClasses_*"):
        text = path.name.lower()
        if arm == "evosuite":
            if "evosuite" in text:
                artifacts.append(path)
        elif generator_tag in text and prompt_tag in text:
            artifacts.append(path)
    return artifacts


def classify_verify_failure(detail: str, build_tool: str) -> str:
    text = str(detail or "").lower()
    prefix = "gradle" if str(build_tool).lower().startswith("gradle") else "maven"
    if "timed out" in text or "timeout" in text:
        return f"{prefix}_verify_timeout"
    if (
        "compilation errors" in text
        or "cannot find symbol" in text
        or "package " in text and " does not exist" in text
        or "invalid method declaration" in text
        or "has private access" in text
        or "is abstract; cannot be instantiated" in text
        or "class file has wrong version" in text
    ):
        return "generated_test_compile_failed"
    if "pitest" in text or "pit_report_missing" in text or "mutationcoverage" in text or "coverage generation minion" in text:
        return "pit_failed"
    if "jacoco" in text:
        return "jacoco_failed"
    if "there are test failures" in text or "test failures" in text or "surefire" in text or "failing tests" in text:
        return "generated_test_runtime_failed"
    return f"{prefix}_verify_failed"


def failure_owner_for_stage(fail_stage: str, arm: str = "") -> tuple[str, str]:
    stage = str(fail_stage or "").lower()
    arm_name = str(arm or "").lower()
    if stage == "ok":
        return "ok", "Arm này compile và đo metric thành công."
    if stage in {
        "baseline_scope_build_failed",
        "repo_baseline_build_failed",
        "project_dependency_resolution_error",
        "java_runtime_too_old_for_maven",
    }:
        return "repository_or_environment", "Repo/dependency/JDK/recipe đầu vào chưa sẵn sàng cho protocol đo."
    if stage in {
        "generated_test_compile_failed",
        "generated_test_runtime_failed",
        "generated_test_assertion_failure",
        "java_source_level_incompatible",
    }:
        return "generator_output", "Generated test của arm này sai/không tương thích nên compilation=0 và strict metrics=0."
    if stage in {
        "gpt_generation_failed",
        "gpt_generated_test_missing",
    }:
        return "generator_output", "GPT/API không tạo được test Java hợp lệ cho arm này."
    if stage in {
        "evosuite_generate_failed",
        "evosuite_generate_timeout",
        "evosuite_generated_test_missing",
    } or arm_name == "evosuite" and "evosuite" in stage:
        return "evosuite_engine", "EvoSuite không sinh được test trước bước đo hoặc bị crash/timeout."
    if stage in {
        "maven_reactor_prewarm_failed",
        "gradle_sandbox_prewarm_failed",
        "sandbox_prepare_failed",
        "agone_runtime_failed",
        "agone_output_missing",
        "missing_or_failed_output",
        "agone_metric_extraction_failed",
        "agone_result_csv_write_failed",
        "gradle_testng_pitest_unsupported",
        "maven_verify_failed",
        "gradle_verify_failed",
        "gradle_test_jacoco_failed",
        "gradle_pitest_failed",
        "pit_failed",
        "jacoco_failed",
        "worker_exception",
    }:
        return "agonetest_harness", "AgoneTest/RBL4 runner chưa đo/trích xuất được metric rõ ràng; không quy trực tiếp cho năng lực sinh test."
    if "verify" in stage or "jacoco" in stage or "pit" in stage or "prewarm" in stage or "sandbox" in stage or "output" in stage:
        return "agonetest_harness", "Lỗi thuộc lớp đo/build harness và cần đọc log trước khi quy cho generator."
    return "unknown_needs_manual_review", "Chưa đủ dấu hiệu tự động để quy trách nhiệm; cần đọc phase_log/stdout/stderr."


def latest_phase_detail(rows: list[dict[str, str]], phases: set[str], statuses: set[str] | None = None) -> str:
    for rec in reversed(rows):
        if rec.get("phase") in phases and (statuses is None or rec.get("status") in statuses):
            return str(rec.get("detail", ""))
    return ""


def diagnose_arm_failure(
    *,
    sandbox: Path,
    run_dir: Path,
    row: pd.Series,
    arm: str,
    generator: str,
    prompt_name: str,
    compilation: int,
    agone_return_code: int,
    stdout_path: Path | None,
    stderr_path: Path | None,
) -> tuple[str, str, str]:
    if compilation == 1:
        return "ok", "", ""

    rows = class_phase_rows(run_dir, row)
    artifacts = agone_artifacts_for_arm(sandbox, row, arm, generator, prompt_name)
    artifact_names = [str(path.relative_to(sandbox)) for path in artifacts]
    failed_artifact = next((path for path in artifacts if path.suffix in {".mavenfailed", ".gradlefailed", ".failed"}), None)
    response_exists = generated_response_exists(sandbox, row, arm)
    stdout_tail = safe_read_text_tail(stdout_path)
    stderr_tail = safe_read_text_tail(stderr_path)
    combined_tail = f"{stdout_tail}\n{stderr_tail}"

    if failed_artifact is not None:
        if failed_artifact.suffix == ".failed":
            if arm == "gpt" and not response_exists:
                return "gpt_generation_failed", "; ".join(artifact_names), compact_log_text(combined_tail)
            return "agone_runtime_failed", "; ".join(artifact_names), compact_log_text(combined_tail)
        detail = latest_phase_detail(
            rows,
            {"maven_verify_jacoco_pit", "gradle_test_jacoco_pitest", "gradle_test_jacoco", "gradle_pitest", "coverage_metric_retrieval"},
            {"FAIL", "ERROR"},
        )
        stage = classify_verify_failure(detail or combined_tail, row.get("Build_Tool", ""))
        return stage, "; ".join(artifact_names), compact_log_text(detail or combined_tail)

    if arm == "evosuite":
        evosuite_fail = latest_phase_detail(rows, {"evosuite_generate"}, {"FAIL", "ERROR"})
        if evosuite_fail:
            stage = "evosuite_generate_timeout" if "timed out" in evosuite_fail.lower() else "evosuite_generate_failed"
            return stage, "; ".join(artifact_names), compact_log_text(evosuite_fail)

    if "trying to save the test type csv file" in combined_tail.lower() or latest_phase_detail(rows, {"agone_result_csv_write"}, {"FAIL"}):
        detail = latest_phase_detail(rows, {"agone_result_csv_write"}, {"FAIL"}) or combined_tail
        return "agone_result_csv_write_failed", "; ".join(artifact_names), compact_log_text(detail)

    if "pitest is not compatible with testng on gradle projects" in combined_tail.lower():
        return "gradle_testng_pitest_unsupported", "; ".join(artifact_names), compact_log_text(combined_tail)

    verify_pass = latest_phase_detail(rows, {"maven_verify_jacoco_pit", "gradle_test_jacoco_pitest", "gradle_test_jacoco"}, {"PASS"})
    if verify_pass and response_exists:
        return "agone_metric_extraction_failed", "; ".join(artifact_names), compact_log_text(verify_pass or combined_tail)

    verify_fail = latest_phase_detail(
        rows,
        {"maven_verify_jacoco_pit", "gradle_test_jacoco_pitest", "gradle_test_jacoco", "gradle_pitest", "coverage_metric_retrieval"},
        {"FAIL", "ERROR"},
    )
    if verify_fail:
        return classify_verify_failure(verify_fail, row.get("Build_Tool", "")), "; ".join(artifact_names), compact_log_text(verify_fail)

    if agone_return_code != 0:
        return "agone_runtime_failed", "; ".join(artifact_names), compact_log_text(combined_tail)
    if not response_exists:
        return ("evosuite_generated_test_missing" if arm == "evosuite" else "gpt_generated_test_missing"), "; ".join(artifact_names), compact_log_text(combined_tail)
    return "agone_output_missing", "; ".join(artifact_names), compact_log_text(combined_tail)


def append_failure_diagnostics(run_dir: Path, records: list[dict[str, Any]]) -> None:
    for rec in records:
        if rec.get("fail_stage") == "ok":
            continue
        row = {
            "sample_index": rec.get("sample_index", ""),
            "repo_id": rec.get("repo_id", ""),
            "class_key": rec.get("class_key", ""),
            "focal_class": rec.get("focal_class", ""),
            "arm": rec.get("arm", ""),
            "generator": rec.get("generator", ""),
            "fail_stage": rec.get("fail_stage", ""),
            "failure_owner": rec.get("failure_owner", ""),
            "failure_owner_note": rec.get("failure_owner_note", ""),
            "failure_artifact": rec.get("failure_artifact", ""),
            "failure_detail": rec.get("failure_detail", ""),
        }
        append_csv(run_dir / "failure_diagnostics.csv", row)
        append_phase(
            run_dir,
            "class_failure_diagnosis",
            project=rec.get("repo_id", ""),
            arm=rec.get("arm", ""),
            sample_index=rec.get("sample_index", ""),
            class_key=rec.get("class_key", ""),
            focal_class=rec.get("focal_class", ""),
            status="FAIL",
            detail=f"{rec.get('fail_stage', '')}; artifact={rec.get('failure_artifact', '')}; {rec.get('failure_detail', '')}",
        )


def parse_agone_metrics(
    output_csv: Path,
    row: pd.Series,
    model: str,
    prompt_name: str,
    sandbox: Path,
    run_dir: Path,
    agone_return_code: int = 0,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
) -> list[dict[str, Any]]:
    arms = [
        ("gpt", model, prompt_name),
        ("evosuite", "evosuite", "-"),
    ]
    out = pd.read_csv(output_csv) if output_csv.exists() and output_csv.stat().st_size else pd.DataFrame()
    result: list[dict[str, Any]] = []
    for arm, generator, prompt in arms:
        found = pd.Series(dtype=object)
        if not out.empty:
            mask = out["Generator(LLM/EVOSUITE)"].astype(str).eq(generator)
            if generator != "evosuite" and "Prompt_Technique" in out.columns:
                mask = mask & out["Prompt_Technique"].astype(str).eq(prompt_name)
            subset = out[mask]
            if not subset.empty:
                found = subset.iloc[-1]
        compilation = int(float(found.get("Compilation", 0))) if not found.empty and str(found.get("Compilation", "")).strip() else 0
        fail_stage, failure_artifact, failure_detail = diagnose_arm_failure(
            sandbox=sandbox,
            run_dir=run_dir,
            row=row,
            arm=arm,
            generator=generator,
            prompt_name=prompt_name,
            compilation=compilation,
            agone_return_code=agone_return_code,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        failure_owner, failure_owner_note = failure_owner_for_stage(fail_stage, arm)
        values = {
            "branch_coverage": found.get("Branch_Coverage", None) if not found.empty else None,
            "line_coverage": found.get("Line_Coverage", None) if not found.empty else None,
            "method_coverage": found.get("Method_Coverage", None) if not found.empty else None,
            "mutation_coverage": found.get("Mutation_Coverage", None) if not found.empty else None,
        }
        rec = {
            "sample_index": row["sample_index"],
            "class_key": row["class_key"],
            "project": row["Project"],
            "repo_id": row["Project"],
            "focal_class": row["Focal_Class"],
            "focal_path": row["focal_path"],
            "module": row["Module"],
            "scope_key": row.get("scope_key", ""),
            "build_tool": row.get("Build_Tool", ""),
            "java_version": row.get("Java_Version", ""),
            "complexity_half": row.get("complexity_half", ""),
            "nloc": row.get("nloc", ""),
            "token_count": row.get("token_count", ""),
            "method_count": row.get("method_count", ""),
            "public_method_count": row.get("public_method_count", ""),
            "max_method_cc": row.get("max_method_cc", ""),
            "sum_method_cc": row.get("sum_method_cc", ""),
            "avg_method_cc": row.get("avg_method_cc", ""),
            "selection_rank_in_repo": row.get("selection_rank_in_repo", ""),
            "original_manifest_index": row.get("original_manifest_index", ""),
            "split_name": row.get("split_name", ""),
            "arm": arm,
            "generator": generator,
            "prompt": prompt,
            "compilation": compilation,
            "fail_stage": fail_stage,
            "failure_owner": failure_owner,
            "failure_owner_note": failure_owner_note,
            "failure_artifact": failure_artifact,
            "failure_detail": failure_detail,
            **values,
        }
        for metric in ["branch_coverage", "line_coverage", "method_coverage", "mutation_coverage"]:
            numeric = pd.to_numeric(pd.Series([rec[metric]]), errors="coerce").iloc[0]
            rec[metric] = numeric if pd.notna(numeric) else None
            rec[f"strict_{metric}"] = float(numeric) if compilation == 1 and pd.notna(numeric) else 0.0
        result.append(rec)
    return result


def copy_generated_tests(sandbox: Path, run_dir: Path, row: pd.Series, model: str, prompt_name: str) -> None:
    out_dir = sandbox / "output" / str(row["Project"])
    dest_dir = run_dir / "generated_tests"
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for path in out_dir.glob("response_*.java"):
        arm = "evosuite" if path.name.startswith("response_evosuite") else "gpt"
        dest = dest_dir / arm / f"{int(row['sample_index']):03d}_{safe_name(row['Project'])}_{safe_name(row['Test_Class'])}.java"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        manifest_rows.append(
            {
                "sample_index": row["sample_index"],
                "repo_id": row["Project"],
                "class_key": row["class_key"],
                "arm": arm,
                "source_path": str(path),
                "stored_path": str(dest),
                "size_bytes": dest.stat().st_size,
            }
        )
    for rec in manifest_rows:
        append_csv(run_dir / "generated_tests_manifest.csv", rec)


def run_one_class(row: pd.Series, run_dir: Path, compiled_repos: Path, model: str, prompt_name: str) -> list[dict[str, Any]]:
    started = time.time()
    append_phase(
        run_dir,
        "class_sandbox_start",
        project=row["Project"],
        module=row["Module"],
        sample_index=row["sample_index"],
        class_key=row["class_key"],
        focal_class=row["Focal_Class"],
        test_class=row["Test_Class"],
        status="START",
    )
    try:
        sandbox = prepare_sandbox(row, run_dir, compiled_repos)
    except Exception as exc:
        append_phase(run_dir, "class_sandbox_start", project=row["Project"], status="FAIL", started_at=started, detail=f"{type(exc).__name__}: {exc}")
        metrics = fallback_metrics(row, model, prompt_name, "sandbox_prepare_failed")
        for rec in metrics:
            rec["failure_detail"] = f"{type(exc).__name__}: {exc}"
        append_failure_diagnostics(run_dir, metrics)
        return metrics

    if not run_maven_reactor_prewarm(row, sandbox, run_dir):
        append_phase(
            run_dir,
            "class_agone_run",
            project=row["Project"],
            module=row["Module"],
            sample_index=row["sample_index"],
            class_key=row["class_key"],
            focal_class=row["Focal_Class"],
            test_class=row["Test_Class"],
            status="FAIL",
            started_at=started,
            detail="maven_reactor_prewarm_failed; AgoneTest was not invoked for this class",
        )
        metrics = fallback_metrics(row, model, prompt_name, "maven_reactor_prewarm_failed")
        append_failure_diagnostics(run_dir, metrics)
        return metrics

    if not run_gradle_sandbox_prewarm(row, sandbox, run_dir):
        append_phase(
            run_dir,
            "class_agone_run",
            project=row["Project"],
            module=row["Module"],
            sample_index=row["sample_index"],
            class_key=row["class_key"],
            focal_class=row["Focal_Class"],
            test_class=row["Test_Class"],
            status="FAIL",
            started_at=started,
            detail="gradle_sandbox_prewarm_failed; AgoneTest was not invoked for this class",
        )
        metrics = fallback_metrics(row, model, prompt_name, "gradle_sandbox_prewarm_failed")
        append_failure_diagnostics(run_dir, metrics)
        return metrics

    stdout_path = run_dir / "class_logs" / f"{int(row['sample_index']):03d}_{safe_name(row['Project'])}_{safe_name(row['Focal_Class'])}.stdout.log"
    stderr_path = stdout_path.with_suffix(".stderr.log")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    toolchains = load_toolchains()
    env = toolchains.build_java_env(row.get("Java_Version"), min_major=8)
    append_phase(
        run_dir,
        "class_agone_env",
        project=row["Project"],
        module=row["Module"],
        sample_index=row["sample_index"],
        class_key=row["class_key"],
        focal_class=row["Focal_Class"],
        test_class=row["Test_Class"],
        status="PASS",
        detail=toolchains.describe(row.get("Java_Version"), min_major=8),
    )
    env["PYTHONPATH"] = str(ROOT / "AgoneTest")
    env["RBL4_API_LOG_CSV"] = str(run_dir / "api_log.csv")
    env["RBL4_API_PROMPTS_JSONL"] = str(run_dir / "api_prompts.jsonl")
    env["RBL4_PHASE_LOG_CSV"] = str(run_dir / "phase_log.csv")
    env["RBL4_CURRENT_PROJECT"] = str(row["Project"])
    env["RBL4_SAMPLE_INDEX"] = str(row["sample_index"])
    env["RBL4_CLASS_KEY"] = str(row["class_key"])
    command = [
        sys.executable,
        str(ROOT / "agone_one.py"),
        "--sandbox",
        str(sandbox),
        "--project",
        str(row["Project"]),
        "--model",
        model,
        "--prompt",
        prompt_name,
    ]
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        result = subprocess.run(
            command,
            cwd=sandbox,
            stdout=stdout,
            stderr=stderr,
            env=env,
            timeout=int(os.getenv("RBL4_CLASS_TIMEOUT_SECONDS", "1800")),
        )
    copy_generated_tests(sandbox, run_dir, row, model, prompt_name)
    agone_output = sandbox / "output" / "output_agone_classes.csv"
    metrics = parse_agone_metrics(
        agone_output,
        row,
        model,
        prompt_name,
        sandbox,
        run_dir,
        agone_return_code=result.returncode,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    if result.returncode != 0:
        for rec in metrics:
            if rec["compilation"] != 1 and rec.get("fail_stage") in {"agone_output_missing", "gpt_generated_test_missing", "evosuite_generated_test_missing"}:
                rec["fail_stage"] = "agone_runtime_failed"
                rec["failure_owner"], rec["failure_owner_note"] = failure_owner_for_stage(rec["fail_stage"], rec.get("arm", ""))
        detail = f"return_code={result.returncode}; stdout={stdout_path.name}; stderr={stderr_path.name}"
        append_phase(
            run_dir,
            "class_agone_run",
            project=row["Project"],
            module=row["Module"],
            sample_index=row["sample_index"],
            class_key=row["class_key"],
            focal_class=row["Focal_Class"],
            test_class=row["Test_Class"],
            status="FAIL",
            started_at=started,
            detail=detail,
        )
    else:
        append_phase(
            run_dir,
            "class_agone_run",
            project=row["Project"],
            module=row["Module"],
            sample_index=row["sample_index"],
            class_key=row["class_key"],
            focal_class=row["Focal_Class"],
            test_class=row["Test_Class"],
            status="PASS",
            started_at=started,
        )
    append_failure_diagnostics(run_dir, metrics)
    return metrics


def fallback_metrics(row: pd.Series, model: str, prompt_name: str, fail_stage: str) -> list[dict[str, Any]]:
    records = []
    for arm, generator, prompt in [("gpt", model, prompt_name), ("evosuite", "evosuite", "-")]:
        failure_owner, failure_owner_note = failure_owner_for_stage(fail_stage, arm)
        rec = {
            "sample_index": row.get("sample_index", ""),
            "class_key": row.get("class_key", ""),
            "project": row.get("Project", row.get("repo_id", "")),
            "repo_id": row.get("Project", row.get("repo_id", "")),
            "focal_class": row.get("Focal_Class", row.get("focal_class", "")),
            "focal_path": row.get("focal_path", ""),
            "module": row.get("Module", ""),
            "scope_key": row.get("scope_key", ""),
            "build_tool": row.get("Build_Tool", row.get("build_tool", "")),
            "java_version": row.get("Java_Version", row.get("declared_java_version", "")),
            "complexity_half": row.get("complexity_half", ""),
            "nloc": row.get("nloc", ""),
            "token_count": row.get("token_count", ""),
            "method_count": row.get("method_count", ""),
            "public_method_count": row.get("public_method_count", ""),
            "max_method_cc": row.get("max_method_cc", ""),
            "sum_method_cc": row.get("sum_method_cc", ""),
            "avg_method_cc": row.get("avg_method_cc", ""),
            "selection_rank_in_repo": row.get("selection_rank_in_repo", ""),
            "original_manifest_index": row.get("original_manifest_index", ""),
            "split_name": row.get("split_name", ""),
            "arm": arm,
            "generator": generator,
            "prompt": prompt,
            "compilation": 0,
            "fail_stage": fail_stage,
            "failure_owner": failure_owner,
            "failure_owner_note": failure_owner_note,
            "failure_artifact": "",
            "failure_detail": "",
            "branch_coverage": None,
            "line_coverage": None,
            "method_coverage": None,
            "mutation_coverage": None,
            "strict_branch_coverage": 0.0,
            "strict_line_coverage": 0.0,
            "strict_method_coverage": 0.0,
            "strict_mutation_coverage": 0.0,
        }
        records.append(rec)
    return records


def metrics_records_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    if "sample_index" in df.columns:
        df["_sample_sort"] = pd.to_numeric(df["sample_index"], errors="coerce")
    else:
        df["_sample_sort"] = 0
    if "arm" in df.columns:
        arm_order = {"gpt": 0, "evosuite": 1}
        df["_arm_sort"] = df["arm"].map(arm_order).fillna(9)
    else:
        df["_arm_sort"] = 0
    sort_cols = [column for column in ["_sample_sort", "class_key", "_arm_sort"] if column in df.columns]
    df = df.sort_values(sort_cols).drop(columns=[column for column in ["_sample_sort", "_arm_sort"] if column in df.columns])
    return df.reset_index(drop=True)


def generated_failures(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty or not {"compilation", "fail_stage"} <= set(metrics_df.columns):
        return pd.DataFrame()
    return metrics_df[(metrics_df["compilation"] != 1) | (metrics_df["fail_stage"] != "ok")].copy()


def run_generation_sample(
    generation_sample: pd.DataFrame,
    run_dir: Path,
    compiled_repos: Path,
    model: str,
    prompt_name: str,
    source_n: int,
    workers: int,
) -> list[dict[str, Any]]:
    row_items = [row.copy() for _, row in generation_sample.iterrows()]
    total = len(row_items)
    worker_count = max(1, int(workers or 1))
    all_metrics: list[dict[str, Any]] = []
    append_phase(
        run_dir,
        "generation_workers",
        status="PASS",
        detail=f"workers={worker_count}; classes={total}",
    )
    if worker_count == 1 or total <= 1:
        for done, row in enumerate(row_items, start=1):
            all_metrics.extend(run_one_class(row, run_dir, compiled_repos, model, prompt_name))
            metrics_df = metrics_records_dataframe(all_metrics)
            write_analysis_artifacts(run_dir, metrics_df, source_n=source_n)
            append_phase(run_dir, "generation_progress", status="PASS", detail=f"{done}/{total} classes completed")
        return all_metrics

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="rbl4-class") as executor:
        futures = {
            executor.submit(run_one_class, row, run_dir, compiled_repos, model, prompt_name): row
            for row in row_items
        }
        for done, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            try:
                class_metrics = future.result()
            except Exception as exc:
                append_phase(
                    run_dir,
                    "class_agone_run",
                    project=row.get("Project", row.get("repo_id", "")),
                    module=row.get("Module", ""),
                    sample_index=row.get("sample_index", ""),
                    class_key=row.get("class_key", ""),
                    focal_class=row.get("Focal_Class", row.get("focal_class", "")),
                    test_class=row.get("Test_Class", ""),
                    status="ERROR",
                    detail=f"worker_exception: {type(exc).__name__}: {exc}",
                )
                class_metrics = fallback_metrics(row, model, prompt_name, "worker_exception")
            all_metrics.extend(class_metrics)
            metrics_df = metrics_records_dataframe(all_metrics)
            write_analysis_artifacts(run_dir, metrics_df, source_n=source_n)
            append_phase(
                run_dir,
                "generation_progress",
                status="PASS",
                detail=f"{done}/{total} classes completed; workers={worker_count}",
            )
    return all_metrics


def build_summary(metrics: pd.DataFrame, source_n: int) -> pd.DataFrame:
    rows = []
    for arm, group in metrics.groupby("arm"):
        rec: dict[str, Any] = {
            "arm": arm,
            "n": int(len(group)),
            "source_n": int(source_n),
            "compilation_success_n": int((group["compilation"] == 1).sum()),
            "compilation_success_rate": round(float((group["compilation"] == 1).mean()), 6) if len(group) else 0.0,
        }
        compiled = group[group["compilation"] == 1]
        for metric in ["branch_coverage", "line_coverage", "method_coverage", "mutation_coverage"]:
            strict = f"strict_{metric}"
            rec[f"{metric}_compiled_mean"] = round(float(compiled[metric].mean()), 6) if not compiled.empty else None
            rec[f"{metric}_compiled_median"] = round(float(compiled[metric].median()), 6) if not compiled.empty else None
            rec[f"{metric}_strict_mean"] = round(float(group[strict].mean()), 6) if len(group) else 0.0
            rec[f"{metric}_strict_median"] = round(float(group[strict].median()), 6) if len(group) else 0.0
        rows.append(rec)
    return pd.DataFrame(rows)


def rank_biserial_from_shifted(values: pd.Series) -> float | None:
    diff = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    diff = diff[diff != 0]
    if diff.empty:
        return None
    ranks = diff.abs().rank(method="average")
    w_pos = float(ranks[diff > 0].sum())
    w_neg = float(ranks[diff < 0].sum())
    denominator = w_pos + w_neg
    return (w_pos - w_neg) / denominator if denominator else None


def wilson_ci(success_n: int, total_n: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if total_n <= 0:
        return None, None
    phat = success_n / total_n
    denominator = 1 + z * z / total_n
    center = (phat + z * z / (2 * total_n)) / denominator
    half_width = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total_n)) / total_n) / denominator
    return center - half_width, center + half_width


def vargha_delaney_a12(left: pd.Series, right: pd.Series) -> float | None:
    x = pd.to_numeric(left, errors="coerce").dropna().astype(float).tolist()
    y = pd.to_numeric(right, errors="coerce").dropna().astype(float).tolist()
    if not x or not y:
        return None
    wins = 0.0
    for x_value in x:
        for y_value in y:
            if x_value > y_value:
                wins += 1.0
            elif x_value == y_value:
                wins += 0.5
    return wins / (len(x) * len(y))


def build_metrics_wide(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty or "class_key" not in metrics.columns:
        return pd.DataFrame()
    metadata_cols = [
        "sample_index",
        "class_key",
        "project",
        "repo_id",
        "focal_class",
        "focal_path",
        "module",
        "scope_key",
        "build_tool",
        "java_version",
        "complexity_half",
        "nloc",
        "token_count",
        "method_count",
        "public_method_count",
        "max_method_cc",
        "sum_method_cc",
        "avg_method_cc",
        "selection_rank_in_repo",
        "original_manifest_index",
        "split_name",
    ]
    existing_metadata = [column for column in metadata_cols if column in metrics.columns]
    base = metrics[existing_metadata].drop_duplicates("class_key", keep="last") if existing_metadata else metrics[["class_key"]].drop_duplicates()
    value_cols = [
        "compilation",
        "branch_coverage",
        "line_coverage",
        "method_coverage",
        "mutation_coverage",
        "strict_branch_coverage",
        "strict_line_coverage",
        "strict_method_coverage",
        "strict_mutation_coverage",
    ]
    existing_values = [column for column in value_cols if column in metrics.columns]
    wide = metrics.pivot_table(index="class_key", columns="arm", values=existing_values, aggfunc="last")
    if wide.empty:
        return base
    wide.columns = [f"{arm}_{metric}" for metric, arm in wide.columns]
    wide = wide.reset_index()
    out = base.merge(wide, on="class_key", how="left")
    if {"gpt_strict_mutation_coverage", "evosuite_strict_mutation_coverage"} <= set(out.columns):
        out["strict_mutation_diff_gpt_minus_evosuite"] = (
            pd.to_numeric(out["gpt_strict_mutation_coverage"], errors="coerce").fillna(0.0)
            - pd.to_numeric(out["evosuite_strict_mutation_coverage"], errors="coerce").fillna(0.0)
        )
        out["rq4_wilcoxon_shifted_value"] = out["strict_mutation_diff_gpt_minus_evosuite"] + REFERENCE["rq4_noninferiority_margin_pp"]
    if {"gpt_strict_branch_coverage", "evosuite_strict_branch_coverage"} <= set(out.columns):
        out["strict_branch_diff_gpt_minus_evosuite"] = (
            pd.to_numeric(out["gpt_strict_branch_coverage"], errors="coerce").fillna(0.0)
            - pd.to_numeric(out["evosuite_strict_branch_coverage"], errors="coerce").fillna(0.0)
        )
    return out


def build_statistical_test_inputs(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if metrics.empty:
        return pd.DataFrame()
    common = [
        "sample_index",
        "class_key",
        "project",
        "repo_id",
        "focal_class",
        "module",
        "scope_key",
        "complexity_half",
        "max_method_cc",
        "sum_method_cc",
        "avg_method_cc",
        "split_name",
    ]
    gpt = metrics[metrics["arm"] == "gpt"].copy()
    for _, rec in gpt.iterrows():
        base = {column: rec.get(column, "") for column in common}
        compilation = int(float(rec.get("compilation", 0) or 0))
        rows.append(
            {
                **base,
                "rq": "RQ3",
                "arm": "gpt",
                "protocol_layer": "AgoneTest-compatible full-sample compilation",
                "metric": "compilation_success",
                "observed_value": compilation,
                "threshold": REFERENCE["build_success_gpt4o_mini"],
                "included_in_test": 1,
                "fail_stage": rec.get("fail_stage", ""),
            }
        )
        mutation = pd.to_numeric(pd.Series([rec.get("mutation_coverage")]), errors="coerce").iloc[0]
        rows.append(
            {
                **base,
                "rq": "RQ1",
                "arm": "gpt",
                "protocol_layer": "AgoneTest-compatible compiled-only",
                "metric": "mutation_coverage",
                "observed_value": mutation if compilation == 1 and pd.notna(mutation) else None,
                "threshold": REFERENCE["mutation_compiled_only_gpt4o_mini"],
                "included_in_test": int(compilation == 1 and pd.notna(mutation)),
                "fail_stage": rec.get("fail_stage", ""),
            }
        )
        branch = pd.to_numeric(pd.Series([rec.get("branch_coverage")]), errors="coerce").iloc[0]
        rows.append(
            {
                **base,
                "rq": "RQ2",
                "arm": "gpt",
                "protocol_layer": "AgoneTest-compatible compiled-only",
                "metric": "branch_coverage",
                "observed_value": branch if compilation == 1 and pd.notna(branch) else None,
                "threshold": REFERENCE["branch_compiled_only_gpt4o_mini"],
                "included_in_test": int(compilation == 1 and pd.notna(branch)),
                "fail_stage": rec.get("fail_stage", ""),
            }
        )

    wide = build_metrics_wide(metrics)
    required = {"gpt_strict_mutation_coverage", "evosuite_strict_mutation_coverage", "strict_mutation_diff_gpt_minus_evosuite"}
    if required <= set(wide.columns):
        for _, rec in wide.iterrows():
            base = {column: rec.get(column, "") for column in common}
            rows.append(
                {
                    **base,
                    "rq": "RQ4",
                    "arm": "paired_gpt_minus_evosuite",
                    "protocol_layer": "strict whole-sample zero-fill",
                    "metric": "strict_mutation_diff_gpt_minus_evosuite",
                    "observed_value": rec.get("strict_mutation_diff_gpt_minus_evosuite"),
                    "threshold": -REFERENCE["rq4_noninferiority_margin_pp"],
                    "wilcoxon_shifted_value": rec.get("rq4_wilcoxon_shifted_value"),
                    "gpt_strict_mutation_coverage": rec.get("gpt_strict_mutation_coverage"),
                    "evosuite_strict_mutation_coverage": rec.get("evosuite_strict_mutation_coverage"),
                    "included_in_test": int(pd.notna(rec.get("strict_mutation_diff_gpt_minus_evosuite"))),
                    "fail_stage": "",
                }
            )
    return pd.DataFrame(rows)


def rq_decisions(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if metrics.empty:
        return pd.DataFrame(rows)
    gpt = metrics[metrics["arm"] == "gpt"].copy()
    evosuite = metrics[metrics["arm"] == "evosuite"].copy()
    compiled = gpt[gpt["compilation"] == 1]
    try:
        from scipy.stats import binomtest, wilcoxon
    except Exception:
        binomtest = None
        wilcoxon = None

    def wilcoxon_greater(values: pd.Series, threshold: float, min_n: int = 60) -> tuple[Any, str, float | None]:
        values = values.dropna().astype(float)
        if len(values) < min_n:
            return None, f"descriptive_only_n_lt_{min_n}", rank_biserial_from_shifted(values - threshold)
        if wilcoxon is None:
            return None, "scipy_unavailable", rank_biserial_from_shifted(values - threshold)
        shifted = values - threshold
        try:
            return float(wilcoxon(shifted, alternative="greater").pvalue), "tested", rank_biserial_from_shifted(shifted)
        except Exception as exc:
            return None, f"test_error:{type(exc).__name__}", rank_biserial_from_shifted(shifted)

    p, note, effect = wilcoxon_greater(compiled["mutation_coverage"], REFERENCE["mutation_compiled_only_gpt4o_mini"])
    observed = float(compiled["mutation_coverage"].median()) if len(compiled) else None
    reject = bool(p is not None and p < ALPHA and observed is not None and observed > REFERENCE["mutation_compiled_only_gpt4o_mini"])
    rows.append(
        {
            "rq": "RQ1",
            "metric": "GPT compiled-only mutation median",
            "n": int(len(compiled)),
            "observed": observed,
            "threshold": REFERENCE["mutation_compiled_only_gpt4o_mini"],
            "p_value": p,
            "alpha": ALPHA,
            "effect_size_rank_biserial": effect,
            "median_minus_threshold": observed - REFERENCE["mutation_compiled_only_gpt4o_mini"] if observed is not None else None,
            "reject_h0": reject,
            "decision_note": note,
        }
    )
    p, note, effect = wilcoxon_greater(compiled["branch_coverage"], REFERENCE["branch_compiled_only_gpt4o_mini"])
    observed = float(compiled["branch_coverage"].median()) if len(compiled) else None
    reject = bool(p is not None and p < ALPHA and observed is not None and observed > REFERENCE["branch_compiled_only_gpt4o_mini"])
    rows.append(
        {
            "rq": "RQ2",
            "metric": "GPT compiled-only branch median",
            "n": int(len(compiled)),
            "observed": observed,
            "threshold": REFERENCE["branch_compiled_only_gpt4o_mini"],
            "p_value": p,
            "alpha": ALPHA,
            "effect_size_rank_biserial": effect,
            "median_minus_threshold": observed - REFERENCE["branch_compiled_only_gpt4o_mini"] if observed is not None else None,
            "reject_h0": reject,
            "decision_note": note,
        }
    )
    success_n = int((gpt["compilation"] == 1).sum())
    p3 = None
    note3 = "empty_gpt_rows" if len(gpt) == 0 else "scipy_unavailable"
    if binomtest is not None and len(gpt) > 0:
        p3 = float(binomtest(success_n, len(gpt), REFERENCE["build_success_gpt4o_mini"], alternative="greater").pvalue)
        note3 = "tested"
    observed3 = success_n / len(gpt) if len(gpt) else None
    ci_low, ci_high = wilson_ci(success_n, len(gpt))
    reject3 = bool(p3 is not None and p3 < ALPHA and observed3 is not None and observed3 >= REFERENCE["build_success_gpt4o_mini"])
    rows.append(
        {
            "rq": "RQ3",
            "metric": "GPT build success rate",
            "n": int(len(gpt)),
            "success_n": success_n,
            "observed": observed3,
            "threshold": REFERENCE["build_success_gpt4o_mini"],
            "p_value": p3,
            "alpha": ALPHA,
            "wilson_ci_low": ci_low,
            "wilson_ci_high": ci_high,
            "proportion_minus_threshold": observed3 - REFERENCE["build_success_gpt4o_mini"] if observed3 is not None else None,
            "reject_h0": reject3,
            "decision_note": note3,
        }
    )
    wide = metrics.pivot_table(index="class_key", columns="arm", values="strict_mutation_coverage", aggfunc="last")
    p4 = None
    note4 = "missing_arms"
    observed = None
    effect4 = None
    a12 = None
    if {"gpt", "evosuite"} <= set(wide.columns):
        diff = wide["gpt"] - wide["evosuite"]
        observed = float(diff.median())
        shifted = diff + REFERENCE["rq4_noninferiority_margin_pp"]
        effect4 = rank_biserial_from_shifted(shifted)
        a12 = vargha_delaney_a12(wide["gpt"], wide["evosuite"])
        if wilcoxon is not None:
            try:
                p4 = float(wilcoxon(shifted, alternative="greater").pvalue)
                note4 = "tested"
            except Exception as exc:
                note4 = f"test_error:{type(exc).__name__}"
        else:
            note4 = "scipy_unavailable"
    rows.append(
        {
            "rq": "RQ4",
            "metric": "strict mutation median GPT-EvoSuite",
            "n": int(len(wide)),
            "observed": observed,
            "threshold": -REFERENCE["rq4_noninferiority_margin_pp"],
            "p_value": p4,
            "alpha": ALPHA,
            "effect_size_rank_biserial": effect4,
            "effect_size_vargha_delaney_a12": a12,
            "median_minus_threshold": observed + REFERENCE["rq4_noninferiority_margin_pp"] if observed is not None else None,
            "reject_h0": bool(p4 is not None and p4 < ALPHA and observed is not None and observed >= -REFERENCE["rq4_noninferiority_margin_pp"]),
            "decision_note": note4,
        }
    )
    return pd.DataFrame(rows)


def write_analysis_artifacts(run_dir: Path, metrics: pd.DataFrame, source_n: int) -> None:
    write_csv_artifact(metrics, run_dir / "metrics_long.csv")
    write_csv_artifact(build_summary(metrics, source_n=source_n), run_dir / "summary.csv")
    write_csv_artifact(rq_decisions(metrics), run_dir / "rq_decisions.csv")
    metrics_wide = build_metrics_wide(metrics)
    write_csv_artifact(metrics_wide, run_dir / "metrics_wide.csv")
    write_csv_artifact(build_statistical_test_inputs(metrics), run_dir / "statistical_test_inputs.csv")
    rq4_columns = [
        "sample_index",
        "class_key",
        "project",
        "repo_id",
        "focal_class",
        "module",
        "complexity_half",
        "gpt_strict_mutation_coverage",
        "evosuite_strict_mutation_coverage",
        "strict_mutation_diff_gpt_minus_evosuite",
        "rq4_wilcoxon_shifted_value",
    ]
    existing = [column for column in rq4_columns if column in metrics_wide.columns]
    write_csv_artifact(pd.DataFrame(metrics_wide[existing] if existing else []), run_dir / "rq4_pairwise_strict_mutation.csv")


def write_manifest(run_dir: Path, args: argparse.Namespace, status: str, error: str | None, preflight_report: dict[str, Any], metrics: pd.DataFrame | None = None) -> None:
    baseline_pass_n = None
    baseline_failed_n = None
    baseline_classes = run_dir / "baseline_classes.csv"
    if baseline_classes.exists() and baseline_classes.stat().st_size:
        try:
            baseline_df = pd.read_csv(baseline_classes)
            baseline_pass_n = int((baseline_df["baseline_build_status"].astype(str) == "PASS").sum())
            baseline_failed_n = int((baseline_df["baseline_build_status"].astype(str) != "PASS").sum())
        except Exception:
            baseline_pass_n = None
            baseline_failed_n = None
    manifest = {
        "timestamp_utc": utc_now(),
        "run_id": run_dir.name,
        "status": status,
        "error": error,
        "run_mode": args.mode,
        "manifest_csv": str(args.manifest),
        "manifest_sha256": preflight_report.get("manifest_sha256", ""),
        "recipes_csv": str(args.recipes),
        "recipes_sha256": preflight_report.get("recipes_sha256", ""),
        "compiledrepos_root": str(args.compiledrepos),
        "model": args.model,
        "prompt": args.prompt,
        "workers": int(getattr(args, "workers", 1)),
        "prompt_hash_sha256": prompt_hash(),
        "prompt_protocol": "AgoneTest base zero-shot from proposal; no java_language_rules.",
        "source_sample_n": int(preflight_report.get("manifest_rows", 0)),
        "buildable_run_n": int(preflight_report.get("manifest_rows", 0)) - int(preflight_report.get("preflight_failed_class_n", 0)),
        "precheck_skipped_n": int(preflight_report.get("preflight_failed_class_n", 0)),
        "baseline_pass_n": baseline_pass_n,
        "baseline_failed_n": baseline_failed_n,
        "repo_n": int(preflight_report.get("manifest_repos", 0)),
        "build_scope_n": int(preflight_report.get("recipe_scopes", 0)),
        "classes_per_repo_min": preflight_report.get("classes_per_repo_min"),
        "classes_per_repo_max": preflight_report.get("classes_per_repo_max"),
        "split_name_counts": preflight_report.get("split_name_counts", {}),
        "complexity_half_counts": preflight_report.get("complexity_half_counts", {}),
        "build_tool_counts": preflight_report.get("build_tool_counts", {}),
        "gpt_rows": int((metrics["arm"] == "gpt").sum()) if metrics is not None and not metrics.empty else 0,
        "evosuite_rows": int((metrics["arm"] == "evosuite").sum()) if metrics is not None and not metrics.empty else 0,
        "fairness_policy": {
            "replacement_after_dataset_lock": False,
            "generated_test_repair": False,
            "prompt": "original AgoneTest zero-shot prompt from proposal",
            "sandbox_policy": "one focal class per sandbox; only that generated test is installed and measured",
            "baseline_gate": "all classes/scopes must pass clean baseline build and per-class sandbox prewarm readiness before generation starts",
            "failure_scoring": "failed generated tests are compilation=0 and strict metrics=0",
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def write_status(run_dir: Path, status: str, args: argparse.Namespace, error: str | None = None) -> None:
    existing = {}
    status_path = run_dir / "status.json"
    if status_path.exists():
        try:
            existing = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    doc = {
        "run_id": run_dir.name,
        "status": status,
        "run_mode": args.mode,
        "sample_csv": str(args.manifest),
        "model": args.model,
        "prompt": args.prompt,
        "workers": int(getattr(args, "workers", 1)),
        "created_at": existing.get("created_at", utc_now()),
        "started_at": existing.get("started_at", utc_now()),
        "pid": existing.get("pid", os.getpid()),
        "return_code": existing.get("return_code"),
        "updated_at": utc_now(),
        "error": error,
    }
    status_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def write_final_report_files(run_dir: Path) -> None:
    try:
        from experiment_tool.reports import build_error_summary, write_excel_report

        build_error_summary(run_dir)
        write_excel_report(run_dir)
    except Exception as exc:
        append_phase(run_dir, "final_report", status="WARN", detail=f"{type(exc).__name__}: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RBL-4 v2 official runner for data_new.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--recipes", type=Path, default=DEFAULT_RECIPES)
    parser.add_argument("--compiledrepos", type=Path, default=DEFAULT_COMPILED_REPOS)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--mode", choices=["dry_run", "baseline_only", "full_run"], default="dry_run")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--limit", type=int, default=0, help="Debug only: process first N classes after preflight/baseline.")
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("RBL4_WORKERS", "1")),
        help="Number of per-class workers for sandbox readiness and full generation. Use 1 for sequential reproducibility.",
    )
    parser.add_argument("--keep-workspaces", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    return args


def main() -> int:
    os.chdir(ROOT)
    load_local_env()
    args = parse_args()
    args.manifest = args.manifest.resolve()
    args.recipes = args.recipes.resolve()
    args.compiledrepos = args.compiledrepos.absolute()
    args.results_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    run_dir = args.results_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_status(run_dir, "running", args)
    preflight_report: dict[str, Any] = {}
    metrics_df: pd.DataFrame | None = None
    try:
        write_run_settings(args.model, args.prompt)
        dataset = load_dataset(args.manifest, args.recipes, args.compiledrepos)
        sample, preflight_report = preflight(dataset, args.compiledrepos, run_dir)
        write_csv_artifact(sample, run_dir / "staged_classes.csv")
        if preflight_report["manifest_rows"] <= 0 or preflight_report["manifest_repos"] <= 0:
            raise RuntimeError("Selected manifest is empty or has no repository.")
        hard_preflight_fail = sample[sample["preflight_status"] != "PASS"]
        if args.mode == "dry_run":
            status = "completed" if hard_preflight_fail.empty else "failed"
            error = None if hard_preflight_fail.empty else f"Preflight failed for {len(hard_preflight_fail)} classes."
            write_manifest(run_dir, args, status, error, preflight_report)
            write_final_report_files(run_dir)
            write_status(run_dir, status, args, error)
            return 0 if hard_preflight_fail.empty else 2
        if not hard_preflight_fail.empty:
            raise RuntimeError(f"Preflight failed for {len(hard_preflight_fail)} classes; see preflight_classes.csv.")

        baseline_scope_df, baseline_class_df = run_baseline_scopes(sample, run_dir)
        baseline_readiness_df, baseline_class_df = run_baseline_sandbox_readiness(
            baseline_class_df,
            run_dir,
            args.compiledrepos,
            workers=args.workers,
        )
        baseline_failed = baseline_class_df[baseline_class_df["baseline_build_status"] != "PASS"]
        if args.mode == "baseline_only":
            status = "completed" if baseline_failed.empty else "failed"
            error = None if baseline_failed.empty else f"Baseline/sandbox readiness failed for {len(baseline_failed)} classes."
            write_manifest(run_dir, args, status, error, preflight_report)
            write_final_report_files(run_dir)
            write_status(run_dir, status, args, error)
            return 0 if baseline_failed.empty else 3
        if not baseline_failed.empty:
            raise RuntimeError(f"Baseline/sandbox readiness gate failed for {len(baseline_failed)} classes; generation not started.")

        generation_sample = baseline_class_df.copy()
        if args.limit > 0:
            generation_sample = generation_sample.head(args.limit).copy()
        all_metrics = run_generation_sample(
            generation_sample,
            run_dir,
            args.compiledrepos,
            args.model,
            args.prompt,
            source_n=len(sample),
            workers=args.workers,
        )
        metrics_df = metrics_records_dataframe(all_metrics)
        failures = generated_failures(metrics_df)
        write_csv_artifact(failures, run_dir / "generated_failures.csv")
        write_analysis_artifacts(run_dir, metrics_df, source_n=len(sample))
        write_manifest(run_dir, args, "completed", None, preflight_report, metrics_df)
        write_final_report_files(run_dir)
        write_status(run_dir, "completed", args)
        if not args.keep_workspaces:
            # Keep workspaces by default during development only when requested; deletion is intentionally
            # not performed here to preserve reproducibility artifacts in this environment.
            pass
        return 0
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        append_phase(run_dir, "runner", status="ERROR", detail=error)
        write_manifest(run_dir, args, "failed", error, preflight_report, metrics_df)
        write_final_report_files(run_dir)
        write_status(run_dir, "failed", args, error)
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
