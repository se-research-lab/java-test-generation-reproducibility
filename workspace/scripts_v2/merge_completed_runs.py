from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import rbl4_v2_runner as runner


ROOT = Path(__file__).resolve().parent
DEFAULT_RUNS = ["pilot60_resume_20260724_083102", "20260724_022225_resume240"]
DEFAULT_RESULTS_DIR = ROOT / "results" / "runs"
DEFAULT_FULL_MANIFEST = ROOT / "data_new" / "class_sampling_manifest_final_seed42.csv"
DEFAULT_RECIPES = ROOT / "data_new" / "build_recipes_portable.csv"

CLASS_KEY_COLUMNS = {"class_key", "Class_Key"}
CSV_MERGE_FILES = [
    "preflight_classes.csv",
    "staged_classes.csv",
    "baseline_sandbox_readiness.csv",
    "baseline_classes.csv",
    "metrics_long.csv",
    "phase_log.csv",
    "api_log.csv",
    "failure_diagnostics.csv",
]
NUMERIC_COLUMNS = [
    "sample_index",
    "original_manifest_index",
    "nloc",
    "token_count",
    "method_count",
    "public_method_count",
    "max_method_cc",
    "sum_method_cc",
    "avg_method_cc",
    "selection_rank_in_repo",
    "compilation",
    "branch_coverage",
    "line_coverage",
    "method_coverage",
    "mutation_coverage",
    "strict_branch_coverage",
    "strict_line_coverage",
    "strict_method_coverage",
    "strict_mutation_coverage",
    "duration_sec",
    "prompt_chars",
    "completion_chars",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "attempts",
    "size_bytes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_source_run(df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    out = df.copy()
    out["source_run_id"] = run_id
    return out


def full_sample_index_map(baseline_df: pd.DataFrame) -> dict[str, int]:
    if "class_key" not in baseline_df.columns:
        raise ValueError("baseline_classes.csv must contain class_key")
    if "original_manifest_index" in baseline_df.columns:
        index_values = pd.to_numeric(baseline_df["original_manifest_index"], errors="coerce")
        if index_values.notna().all() and int(index_values.nunique()) == int(baseline_df["class_key"].nunique()):
            return {
                str(row["class_key"]): int(float(row["original_manifest_index"]))
                for _, row in baseline_df.iterrows()
            }
    return {str(row["class_key"]): i for i, (_, row) in enumerate(baseline_df.drop_duplicates("class_key").iterrows())}


def apply_full_sample_index(df: pd.DataFrame, class_to_index: dict[str, int]) -> pd.DataFrame:
    if df.empty or "class_key" not in df.columns:
        return df
    out = df.copy()
    if "sample_index" in out.columns:
        out["source_run_sample_index"] = out["sample_index"]
    original = out["sample_index"].astype(str) if "sample_index" in out.columns else pd.Series([""] * len(out), index=out.index)
    out["sample_index"] = [
        str(int(class_to_index[key])) if key in class_to_index else original_value
        for key, original_value in zip(out["class_key"].astype(str), original)
    ]
    return out


def numericize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in NUMERIC_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def sort_by_full_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "sample_index" in out.columns:
        out["_sample_sort"] = pd.to_numeric(out["sample_index"], errors="coerce")
    else:
        out["_sample_sort"] = 0
    if "arm" in out.columns:
        out["_arm_sort"] = out["arm"].map({"gpt": 0, "evosuite": 1}).fillna(9)
    else:
        out["_arm_sort"] = 0
    sort_cols = [column for column in ["_sample_sort", "class_key", "_arm_sort", "source_run_id"] if column in out.columns]
    return out.sort_values(sort_cols).drop(columns=["_sample_sort", "_arm_sort"], errors="ignore").reset_index(drop=True)


def union_concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False).fillna("")


def merge_baseline_scope(frames: list[pd.DataFrame], baseline_classes: pd.DataFrame) -> pd.DataFrame:
    scopes = union_concat(frames)
    if scopes.empty:
        return scopes
    scopes = scopes.sort_values(["project", "scope_key", "module", "source_run_id"], kind="stable")
    scopes = scopes.drop_duplicates(["project", "scope_key", "module"], keep="last").reset_index(drop=True)
    if {"project", "scope_key"} <= set(scopes.columns) and {"repo_id", "scope_key", "focal_class"} <= set(baseline_classes.columns):
        class_counts = (
            baseline_classes.groupby(["repo_id", "scope_key"], dropna=False)
            .agg(
                class_rows=("class_key", "count"),
                focal_classes=("focal_class", lambda values: ";".join(str(v) for v in values)),
            )
            .reset_index()
            .rename(columns={"repo_id": "project"})
        )
        scopes = scopes.drop(columns=[column for column in ["class_rows", "focal_classes"] if column in scopes.columns])
        scopes = scopes.merge(class_counts, on=["project", "scope_key"], how="left")
    return scopes


def combined_preflight_report(
    run_dirs: list[Path],
    baseline_classes: pd.DataFrame,
    baseline_scope_build: pd.DataFrame,
    manifest: Path,
    recipes: Path,
) -> dict[str, Any]:
    reports = [read_json(run_dir / "preflight_report.json") for run_dir in run_dirs]
    repo_counts = baseline_classes["repo_id"].astype(str).value_counts().sort_index().to_dict()
    split_counts = baseline_classes["split_name"].astype(str).value_counts().to_dict() if "split_name" in baseline_classes.columns else {}
    complexity_counts = baseline_classes["complexity_half"].astype(str).value_counts().to_dict() if "complexity_half" in baseline_classes.columns else {}
    build_tool_counts = baseline_classes["build_tool"].astype(str).str.lower().value_counts().to_dict() if "build_tool" in baseline_classes.columns else {}
    selected_type_counts = baseline_classes["selected_type"].astype(str).value_counts().to_dict() if "selected_type" in baseline_classes.columns else {"main": int(len(baseline_classes))}
    return {
        "timestamp_utc": utc_now(),
        "manifest_csv": str(manifest),
        "manifest_sha256": sha256_file(manifest),
        "recipes_csv": str(recipes),
        "recipes_sha256": sha256_file(recipes),
        "merged_from_runs": [run_dir.name for run_dir in run_dirs],
        "source_preflight_reports": reports,
        "manifest_rows": int(len(baseline_classes)),
        "manifest_repos": int(baseline_classes["repo_id"].nunique()) if "repo_id" in baseline_classes.columns else None,
        "recipe_rows": int(max((report.get("recipe_rows", 0) for report in reports), default=0)),
        "recipe_scopes": int(len(baseline_scope_build)) if not baseline_scope_build.empty else int(max((report.get("recipe_scopes", 0) for report in reports), default=0)),
        "classes_per_repo_min": int(min(repo_counts.values())) if repo_counts else None,
        "classes_per_repo_max": int(max(repo_counts.values())) if repo_counts else None,
        "classes_per_repo": repo_counts,
        "selected_type_counts": selected_type_counts,
        "complexity_half_counts": complexity_counts,
        "build_tool_counts": build_tool_counts,
        "split_name_counts": split_counts,
        "compiledrepos_root": next((report.get("compiledrepos_root") for report in reports if report.get("compiledrepos_root")), ""),
        "repo_missing_n": int(sum(int(report.get("repo_missing_n", 0) or 0) for report in reports)),
        "focal_missing_n": int(sum(int(report.get("focal_missing_n", 0) or 0) for report in reports)),
        "recipe_missing_n": int(sum(int(report.get("recipe_missing_n", 0) or 0) for report in reports)),
        "preflight_failed_class_n": int(sum(int(report.get("preflight_failed_class_n", 0) or 0) for report in reports)),
        "duplicate_class_key_rows": int(len(baseline_classes) - baseline_classes["class_key"].nunique()) if "class_key" in baseline_classes.columns else None,
        "duplicate_focal_path_rows": int(len(baseline_classes) - baseline_classes["focal_path"].nunique()) if "focal_path" in baseline_classes.columns else None,
        "missing_scope_recipes": [],
        "prompt_hash_sha256": runner.prompt_hash(),
        "prompt_protocol": "AgoneTest base zero-shot prompt from proposal; no java_language_rules; no project_structure/dependencies.",
    }


def write_combined_status(run_dir: Path, manifest: Path, model: str, prompt: str) -> None:
    write_json(
        run_dir / "status.json",
        {
            "run_id": run_dir.name,
            "status": "completed",
            "run_mode": "combined_report",
            "sample_csv": str(manifest),
            "model": model,
            "prompt": prompt,
            "workers": None,
            "created_at": utc_now(),
            "started_at": utc_now(),
            "completed_at": utc_now(),
            "pid": os.getpid(),
            "return_code": 0,
            "updated_at": utc_now(),
            "error": None,
        },
    )


def write_combined_manifest(
    run_dir: Path,
    run_dirs: list[Path],
    preflight_report: dict[str, Any],
    baseline_classes: pd.DataFrame,
    baseline_scope_build: pd.DataFrame,
    metrics: pd.DataFrame,
    manifest: Path,
    recipes: Path,
    compiledrepos: Path,
    model: str,
    prompt: str,
) -> None:
    baseline_pass = int((baseline_classes["baseline_build_status"].astype(str) == "PASS").sum()) if "baseline_build_status" in baseline_classes.columns else None
    baseline_failed = int(len(baseline_classes) - baseline_pass) if baseline_pass is not None else None
    write_json(
        run_dir / "manifest.json",
        {
            "timestamp_utc": utc_now(),
            "run_id": run_dir.name,
            "status": "completed",
            "error": None,
            "run_mode": "combined_report",
            "combined_from_runs": [run_dir_item.name for run_dir_item in run_dirs],
            "merge_policy": {
                "sample_index": "reset to original_manifest_index/full manifest index when available",
                "baseline_scope_build": "deduplicated by project/scope_key/module and class_rows recomputed on combined N=300",
                "metrics": "row-level concat of completed run metrics, then RQ/statistical artifacts recomputed on combined N",
                "api_logs": "row-level concat from root api_log.csv files; missing API rows remain absent when generation was blocked before GPT",
                "generated_tests": "copied into this combined run and manifest paths rewritten",
            },
            "manifest_csv": str(manifest),
            "manifest_sha256": sha256_file(manifest),
            "recipes_csv": str(recipes),
            "recipes_sha256": sha256_file(recipes),
            "compiledrepos_root": str(compiledrepos),
            "model": model,
            "prompt": prompt,
            "workers": None,
            "prompt_hash_sha256": runner.prompt_hash(),
            "prompt_protocol": "AgoneTest base zero-shot from proposal; no java_language_rules.",
            "source_sample_n": int(len(baseline_classes)),
            "buildable_run_n": int(len(baseline_classes) - int(preflight_report.get("preflight_failed_class_n", 0))),
            "precheck_skipped_n": int(preflight_report.get("preflight_failed_class_n", 0)),
            "baseline_pass_n": baseline_pass,
            "baseline_failed_n": baseline_failed,
            "repo_n": int(baseline_classes["repo_id"].nunique()) if "repo_id" in baseline_classes.columns else None,
            "build_scope_n": int(len(baseline_scope_build)),
            "classes_per_repo_min": preflight_report.get("classes_per_repo_min"),
            "classes_per_repo_max": preflight_report.get("classes_per_repo_max"),
            "split_name_counts": preflight_report.get("split_name_counts", {}),
            "complexity_half_counts": preflight_report.get("complexity_half_counts", {}),
            "build_tool_counts": preflight_report.get("build_tool_counts", {}),
            "gpt_rows": int((metrics["arm"] == "gpt").sum()) if "arm" in metrics.columns else 0,
            "evosuite_rows": int((metrics["arm"] == "evosuite").sum()) if "arm" in metrics.columns else 0,
            "fairness_policy": {
                "replacement_after_dataset_lock": False,
                "generated_test_repair": False,
                "prompt": "original AgoneTest zero-shot prompt from proposal",
                "sandbox_policy": "one focal class per sandbox; only that generated test is installed and measured",
                "baseline_gate": "all classes/scopes must pass clean baseline build and per-class sandbox prewarm readiness before generation starts",
                "failure_scoring": "failed generated tests are compilation=0 and strict metrics=0",
            },
        },
    )


def resolve_generated_path(source_run_dir: Path, stored_path: str, source_path: str) -> Path | None:
    candidates: list[Path] = []
    if stored_path:
        stored = Path(stored_path)
        candidates.append(stored if stored.is_absolute() else ROOT / stored)
        candidates.append(source_run_dir / stored)
    if source_path:
        candidates.append(Path(source_path))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def copied_generated_name(full_index: int | None, original_name: str, source_run_id: str) -> str:
    if full_index is None:
        return f"{source_run_id}__{original_name}"
    return re.sub(r"^\d+_", f"{full_index:03d}_", original_name, count=1) if re.match(r"^\d+_", original_name) else f"{full_index:03d}_{source_run_id}_{original_name}"


def merge_generated_tests(run_dirs: list[Path], out_dir: Path, class_to_index: dict[str, int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    dest_root = out_dir / "generated_tests"
    for source_run_dir in run_dirs:
        manifest = read_csv(source_run_dir / "generated_tests_manifest.csv")
        if manifest.empty:
            continue
        manifest = add_source_run(manifest, source_run_dir.name)
        manifest = apply_full_sample_index(manifest, class_to_index)
        for _, rec in manifest.iterrows():
            arm = str(rec.get("arm", "unknown")) or "unknown"
            src = resolve_generated_path(source_run_dir, str(rec.get("stored_path", "")), str(rec.get("source_path", "")))
            original_name = src.name if src is not None else Path(str(rec.get("stored_path", ""))).name
            full_index = class_to_index.get(str(rec.get("class_key", "")))
            dest_name = copied_generated_name(full_index, original_name, source_run_dir.name)
            dest = dest_root / arm / dest_name
            copied = False
            if src is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                copied = True
            row = rec.to_dict()
            row["source_run_id"] = source_run_dir.name
            row["original_source_path"] = row.get("source_path", "")
            row["original_stored_path"] = row.get("stored_path", "")
            row["stored_path"] = str(dest)
            row["source_path"] = str(src) if src is not None else ""
            row["copied_to_combined_run"] = int(copied)
            row["size_bytes"] = dest.stat().st_size if copied else row.get("size_bytes", "")
            rows.append(row)
    return sort_by_full_index(pd.DataFrame(rows).fillna("")) if rows else pd.DataFrame()


def merge_prompt_logs(run_dirs: list[Path], out_path: Path, class_to_index: dict[str, int]) -> int:
    records: list[dict[str, Any]] = []
    for source_run_dir in run_dirs:
        prompt_path = source_run_dir / "api_prompts.jsonl"
        if not prompt_path.exists():
            continue
        with prompt_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record["source_run_id"] = source_run_dir.name
                key = str(record.get("class_key", ""))
                if key in class_to_index:
                    record["source_run_sample_index"] = record.get("sample_index", "")
                    record["sample_index"] = class_to_index[key]
                records.append(record)
    records.sort(key=lambda rec: (int(rec.get("sample_index", 10**9) or 10**9), str(rec.get("source_run_id", ""))))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records)


def copy_class_logs(run_dirs: list[Path], out_dir: Path) -> None:
    dest_root = out_dir / "class_logs"
    for source_run_dir in run_dirs:
        src = source_run_dir / "class_logs"
        if not src.exists():
            continue
        dest = dest_root / source_run_dir.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)


def zip_generated_tests(run_dir: Path) -> Path:
    zip_path = run_dir / "generated_tests.zip"
    source_dir = run_dir / "generated_tests"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if source_dir.exists():
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(run_dir))
    return zip_path


def annotate_rq_decisions(run_dir: Path, metrics: pd.DataFrame) -> None:
    path = run_dir / "rq_decisions.csv"
    if not path.exists() or path.stat().st_size == 0 or metrics.empty:
        return
    rq = pd.read_csv(path, dtype=str).fillna("")
    gpt = metrics[metrics["arm"] == "gpt"].copy()
    compiled_gpt = gpt[gpt["compilation"] == 1].copy()
    wide = runner.build_metrics_wide(metrics)
    observation_counts = {
        "RQ1": int(pd.to_numeric(compiled_gpt.get("mutation_coverage", pd.Series(dtype=float)), errors="coerce").notna().sum()),
        "RQ2": int(pd.to_numeric(compiled_gpt.get("branch_coverage", pd.Series(dtype=float)), errors="coerce").notna().sum()),
        "RQ3": int(len(gpt)),
        "RQ4": int(len(wide)),
    }
    rq["metric_observation_n"] = rq["rq"].map(observation_counts).fillna("")
    runner.write_csv_artifact(rq, path)


def build_validation(
    run_dir: Path,
    baseline_classes: pd.DataFrame,
    metrics: pd.DataFrame,
    api_log: pd.DataFrame,
    prompt_line_count: int,
    generated_manifest: pd.DataFrame,
) -> dict[str, Any]:
    baseline_keys = set(baseline_classes["class_key"].astype(str)) if "class_key" in baseline_classes.columns else set()
    api_keys = set(api_log["class_key"].astype(str)) if "class_key" in api_log.columns else set()
    generated_keys = set(generated_manifest["class_key"].astype(str)) if "class_key" in generated_manifest.columns else set()
    validations = {
        "baseline_rows": int(len(baseline_classes)),
        "baseline_unique_classes": int(len(baseline_keys)),
        "baseline_pass_n": int((baseline_classes["baseline_build_status"].astype(str) == "PASS").sum()) if "baseline_build_status" in baseline_classes.columns else None,
        "metrics_rows": int(len(metrics)),
        "metrics_unique_classes": int(metrics["class_key"].nunique()) if "class_key" in metrics.columns else None,
        "gpt_rows": int((metrics["arm"] == "gpt").sum()) if "arm" in metrics.columns else None,
        "evosuite_rows": int((metrics["arm"] == "evosuite").sum()) if "arm" in metrics.columns else None,
        "api_log_rows": int(len(api_log)),
        "api_unique_classes": int(len(api_keys)),
        "api_prompt_lines": int(prompt_line_count),
        "generated_tests_manifest_rows": int(len(generated_manifest)),
        "generated_tests_unique_classes": int(len(generated_keys)),
        "classes_missing_api_log": sorted(baseline_keys - api_keys),
        "classes_missing_generated_test_file": sorted(baseline_keys - generated_keys),
    }
    validations["ready_for_full300_paper_tables"] = bool(
        validations["baseline_rows"] == 300
        and validations["baseline_unique_classes"] == 300
        and validations["baseline_pass_n"] == 300
        and validations["metrics_rows"] == 600
        and validations["metrics_unique_classes"] == 300
        and validations["gpt_rows"] == 300
        and validations["evosuite_rows"] == 300
    )
    write_json(run_dir / "merge_validation.json", validations)
    rows = [{"check": key, "value": json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value} for key, value in validations.items()]
    runner.write_csv_artifact(pd.DataFrame(rows), run_dir / "merge_validation.csv")
    return validations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge completed RBL-4 runs into one paper-ready combined run.")
    parser.add_argument("--runs", nargs="+", default=DEFAULT_RUNS, help="Run ids or absolute run directories to merge.")
    parser.add_argument("--run-id", default=f"full300_merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_FULL_MANIFEST)
    parser.add_argument("--recipes", type=Path, default=DEFAULT_RECIPES)
    parser.add_argument("--compiledrepos", type=Path, default=runner.DEFAULT_COMPILED_REPOS)
    parser.add_argument("--model", default=runner.DEFAULT_MODEL)
    parser.add_argument("--prompt", default=runner.DEFAULT_PROMPT)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def resolve_run_dirs(results_dir: Path, run_ids: list[str]) -> list[Path]:
    run_dirs: list[Path] = []
    for run_id in run_ids:
        candidate = Path(run_id)
        if not candidate.exists():
            candidate = results_dir / run_id
        if not candidate.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")
        run_dirs.append(candidate.resolve())
    return run_dirs


def main() -> int:
    os.chdir(ROOT)
    args = parse_args()
    args.results_dir = args.results_dir.resolve()
    args.manifest = args.manifest.resolve()
    args.recipes = args.recipes.resolve()
    args.compiledrepos = args.compiledrepos.resolve()
    run_dirs = resolve_run_dirs(args.results_dir, args.runs)
    out_dir = args.results_dir / args.run_id
    if out_dir.exists():
        if not args.overwrite:
            raise FileExistsError(f"Output run already exists: {out_dir}. Use --overwrite to replace it.")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_frames: dict[str, list[pd.DataFrame]] = {name: [] for name in CSV_MERGE_FILES}
    scope_frames: list[pd.DataFrame] = []
    for source_run_dir in run_dirs:
        status = read_json(source_run_dir / "status.json")
        if status.get("status") != "completed":
            raise RuntimeError(f"Source run is not completed: {source_run_dir.name} status={status.get('status')}")
        for name in CSV_MERGE_FILES:
            frame = read_csv(source_run_dir / name)
            if not frame.empty:
                csv_frames[name].append(add_source_run(frame, source_run_dir.name))
        scope = read_csv(source_run_dir / "baseline_scope_build.csv")
        if not scope.empty:
            scope_frames.append(add_source_run(scope, source_run_dir.name))

    baseline_classes = union_concat(csv_frames["baseline_classes.csv"])
    if baseline_classes.empty:
        raise RuntimeError("No baseline_classes.csv rows found.")
    class_to_index = full_sample_index_map(baseline_classes)

    merged_csvs: dict[str, pd.DataFrame] = {}
    for name, frames in csv_frames.items():
        merged = union_concat(frames)
        merged = apply_full_sample_index(merged, class_to_index)
        merged = sort_by_full_index(merged)
        merged_csvs[name] = numericize(merged)

    baseline_classes = merged_csvs["baseline_classes.csv"]
    baseline_scope_build = merge_baseline_scope(scope_frames, baseline_classes)
    baseline_scope_build = numericize(sort_by_full_index(baseline_scope_build))
    preflight_report = combined_preflight_report(run_dirs, baseline_classes, baseline_scope_build, args.manifest, args.recipes)

    for name, frame in merged_csvs.items():
        runner.write_csv_artifact(frame, out_dir / name)
    runner.write_csv_artifact(baseline_scope_build, out_dir / "baseline_scope_build.csv")
    runner.write_csv_artifact(baseline_classes, out_dir / "generation_classes.csv")
    write_json(out_dir / "preflight_report.json", preflight_report)

    metrics = numericize(merged_csvs["metrics_long.csv"])
    runner.write_analysis_artifacts(out_dir, metrics, source_n=len(baseline_classes))
    annotate_rq_decisions(out_dir, metrics)
    runner.write_csv_artifact(runner.generated_failures(metrics), out_dir / "generated_failures.csv")

    generated_manifest = merge_generated_tests(run_dirs, out_dir, class_to_index)
    runner.write_csv_artifact(numericize(generated_manifest), out_dir / "generated_tests_manifest.csv")
    zip_generated_tests(out_dir)

    api_log = numericize(merged_csvs["api_log.csv"])
    prompt_line_count = merge_prompt_logs(run_dirs, out_dir / "api_prompts.jsonl", class_to_index)
    copy_class_logs(run_dirs, out_dir)

    write_combined_status(out_dir, args.manifest, args.model, args.prompt)
    write_combined_manifest(
        out_dir,
        run_dirs,
        preflight_report,
        baseline_classes,
        baseline_scope_build,
        metrics,
        args.manifest,
        args.recipes,
        args.compiledrepos,
        args.model,
        args.prompt,
    )
    validations = build_validation(out_dir, baseline_classes, metrics, api_log, prompt_line_count, generated_manifest)
    runner.write_final_report_files(out_dir)
    print(f"MERGED_RUN={out_dir}")
    print(json.dumps(validations, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
