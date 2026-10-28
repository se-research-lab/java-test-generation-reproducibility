from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import rbl4_v2_runner as runner


ROOT = Path(__file__).resolve().parent


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ns_for_runner(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        mode="full_run",
        manifest=args.manifest,
        recipes=args.recipes,
        compiledrepos=args.compiledrepos,
        model=args.model,
        prompt=args.prompt,
        workers=args.workers,
    )


def merge_readiness_result(
    baseline_df: pd.DataFrame,
    readiness_df: pd.DataFrame,
    repair_record: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample_index = str(repair_record.get("sample_index", ""))
    class_key = str(repair_record.get("class_key", ""))
    mask = (baseline_df["sample_index"].astype(str) == sample_index) & (
        baseline_df["class_key"].astype(str) == class_key
    )
    read_mask = (readiness_df["sample_index"].astype(str) == sample_index) & (
        readiness_df["class_key"].astype(str) == class_key
    )
    if read_mask.any():
        for key, value in repair_record.items():
            readiness_df.loc[read_mask, key] = value
    else:
        readiness_df = pd.concat([readiness_df, pd.DataFrame([repair_record])], ignore_index=True)

    prefix_map = {
        "status": "sandbox_readiness_status",
        "fail_stage": "sandbox_readiness_fail_stage",
        "detail": "sandbox_readiness_detail",
        "sandbox_path": "sandbox_readiness_path",
        "duration_sec": "sandbox_readiness_duration_sec",
    }
    for src_key, dst_key in prefix_map.items():
        if dst_key in baseline_df.columns:
            baseline_df.loc[mask, dst_key] = repair_record.get(src_key, "")
    if "baseline_scope_status" in baseline_df.columns:
        scope_pass = baseline_df.loc[mask, "baseline_scope_status"].astype(str).eq("PASS")
    else:
        scope_pass = pd.Series([True] * int(mask.sum()))
        baseline_df["baseline_scope_status"] = baseline_df["baseline_build_status"]
    baseline_df.loc[mask, "baseline_build_status"] = (
        "PASS" if str(repair_record.get("status", "")) == "PASS" and bool(scope_pass.all()) else "FAIL"
    )
    return baseline_df, readiness_df


def ensure_runner_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    fallback_columns = {
        "Project": ["repo_id"],
        "Focal_Class": ["Focal_Class_agone", "focal_class"],
        "Focal_Path": ["Focal_Path_agone", "focal_path"],
        "Build_Tool": ["Build_Tool_agone", "build_tool"],
    }
    for required, fallbacks in fallback_columns.items():
        if required not in out.columns:
            for fallback in fallbacks:
                if fallback in out.columns:
                    out[required] = out[fallback]
                    break
    if "Build_Tool" in out.columns:
        out["Build_Tool"] = out["Build_Tool"].map(
            lambda value: "Gradle" if str(value).strip().lower() == "gradle" else "Maven"
        )
    if "Module" not in out.columns and "module_dir" in out.columns:
        out["Module"] = out["module_dir"]
    if "Java_Version" not in out.columns and "declared_java_version" in out.columns:
        out["Java_Version"] = out["declared_java_version"].map(runner.normalize_java_version)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resume RBL-4 generation from a completed baseline/readiness run.")
    parser.add_argument("--source-run", required=True, help="Run id or absolute path to reuse baseline artifacts from.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--manifest", type=Path, default=runner.DEFAULT_MANIFEST)
    parser.add_argument("--recipes", type=Path, default=runner.DEFAULT_RECIPES)
    parser.add_argument("--compiledrepos", type=Path, default=runner.DEFAULT_COMPILED_REPOS)
    parser.add_argument("--results-dir", type=Path, default=runner.DEFAULT_RESULTS_DIR)
    parser.add_argument("--model", default=runner.DEFAULT_MODEL)
    parser.add_argument("--prompt", default=runner.DEFAULT_PROMPT)
    parser.add_argument("--workers", type=int, default=int(os.getenv("RBL4_WORKERS", "1")))
    parser.add_argument("--limit", type=int, default=0, help="Debug only: first N classes after baseline reuse.")
    return parser.parse_args()


def main() -> int:
    os.chdir(ROOT)
    runner.load_local_env()
    args = parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")
    args.manifest = args.manifest.resolve()
    args.recipes = args.recipes.resolve()
    args.compiledrepos = args.compiledrepos.absolute()
    args.results_dir.mkdir(parents=True, exist_ok=True)

    source_run = Path(args.source_run)
    if not source_run.exists():
        source_run = args.results_dir / args.source_run
    if not source_run.exists():
        raise FileNotFoundError(f"source run not found: {args.source_run}")
    run_id = args.run_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_resume"
    run_dir = args.results_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    ns = ns_for_runner(args)

    preflight_report = read_json(source_run / "preflight_report.json")
    metrics_df: pd.DataFrame | None = None
    runner.write_status(run_dir, "running", ns)
    try:
        runner.write_run_settings(args.model, args.prompt)
        for name in [
            "preflight_classes.csv",
            "preflight_report.json",
            "staged_classes.csv",
            "baseline_scope_build.csv",
        ]:
            copy_if_exists(source_run / name, run_dir / name)

        baseline_path = source_run / "baseline_classes.csv"
        readiness_path = source_run / "baseline_sandbox_readiness.csv"
        if not baseline_path.exists() or not readiness_path.exists():
            raise FileNotFoundError("source run must contain baseline_classes.csv and baseline_sandbox_readiness.csv")
        baseline_df = ensure_runner_columns(pd.read_csv(baseline_path, dtype=str).fillna(""))
        readiness_df = pd.read_csv(readiness_path, dtype=str).fillna("")
        runner.append_phase(
            run_dir,
            "baseline_reuse",
            status="PASS",
            detail=f"source_run={source_run.name}; reused baseline artifacts; rows={len(baseline_df)}",
        )

        failed = baseline_df[baseline_df["baseline_build_status"].astype(str) != "PASS"].copy()
        if not failed.empty:
            runner.append_phase(
                run_dir,
                "baseline_reuse_repair",
                status="START",
                detail=f"rerun sandbox readiness for {len(failed)} previously failed classes with current runner",
            )
            readiness_workspace_key = run_dir.parent / f"{run_dir.name}__baseline_repair"
            repair_records = []
            for _, row in failed.iterrows():
                repair_row = row.copy()
                if str(repair_row.get("baseline_scope_status", "")) == "PASS":
                    repair_row["baseline_build_status"] = "PASS"
                repair_record = runner.run_baseline_readiness_one(
                    repair_row,
                    readiness_workspace_key,
                    run_dir,
                    args.compiledrepos,
                )
                repair_records.append(repair_record)
                baseline_df, readiness_df = merge_readiness_result(baseline_df, readiness_df, repair_record)
            repaired_pass = sum(1 for rec in repair_records if rec.get("status") == "PASS")
            runner.append_phase(
                run_dir,
                "baseline_reuse_repair",
                status="PASS" if repaired_pass == len(repair_records) else "FAIL",
                detail=f"repaired_pass={repaired_pass}/{len(repair_records)}",
            )

        runner.write_csv_artifact(readiness_df, run_dir / "baseline_sandbox_readiness.csv")
        runner.write_csv_artifact(baseline_df, run_dir / "baseline_classes.csv")
        still_failed = baseline_df[baseline_df["baseline_build_status"].astype(str) != "PASS"]
        if not still_failed.empty:
            raise RuntimeError(f"Reused baseline still has {len(still_failed)} failed classes; generation not started.")

        generation_sample = ensure_runner_columns(baseline_df)
        if args.limit > 0:
            generation_sample = generation_sample.head(args.limit).copy()
        all_metrics = runner.run_generation_sample(
            generation_sample,
            run_dir,
            args.compiledrepos,
            args.model,
            args.prompt,
            source_n=len(baseline_df),
            workers=args.workers,
        )
        metrics_df = runner.metrics_records_dataframe(all_metrics)
        failures = runner.generated_failures(metrics_df)
        runner.write_csv_artifact(failures, run_dir / "generated_failures.csv")
        runner.write_analysis_artifacts(run_dir, metrics_df, source_n=len(baseline_df))
        runner.write_manifest(run_dir, ns, "completed", None, preflight_report, metrics_df)
        runner.write_final_report_files(run_dir)
        runner.write_status(run_dir, "completed", ns)
        return 0
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        runner.append_phase(run_dir, "runner", status="ERROR", detail=error)
        runner.write_manifest(run_dir, ns, "failed", error, preflight_report, metrics_df)
        runner.write_final_report_files(run_dir)
        runner.write_status(run_dir, "failed", ns, error)
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
