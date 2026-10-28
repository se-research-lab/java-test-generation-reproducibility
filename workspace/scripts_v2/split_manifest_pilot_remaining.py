from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data_new" / "class_sampling_manifest_final_seed42.csv"
DEFAULT_PILOT = ROOT / "data_new" / "class_sampling_manifest_pilot60_seed42.csv"
DEFAULT_REMAINING = ROOT / "data_new" / "class_sampling_manifest_remaining240_seed42.csv"
DEFAULT_REPORT_JSON = ROOT / "data_new" / "manifest_split_report.json"
DEFAULT_REPORT_MD = ROOT / "data_new" / "manifest_split_report.md"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([float("nan")] * len(df), index=df.index)
    return pd.to_numeric(df[column], errors="coerce")


def sort_for_split(group: pd.DataFrame) -> pd.DataFrame:
    ranked = group.copy()
    ranked["_rank_num"] = numeric_series(ranked, "selection_rank_in_repo")
    ranked["_cc_num"] = numeric_series(ranked, "max_method_cc")
    ranked["_sum_cc_num"] = numeric_series(ranked, "sum_method_cc")
    if "_original_manifest_index" not in ranked.columns:
        ranked["_original_manifest_index"] = ranked.index
    return ranked.sort_values(
        by=["_rank_num", "selection_hash", "_cc_num", "_sum_cc_num", "_original_manifest_index"],
        na_position="last",
        kind="mergesort",
    )


def choose_pilot_rows(group: pd.DataFrame, pilot_per_repo: int) -> list[int]:
    ordered = sort_for_split(group)
    chosen: list[int] = []
    if pilot_per_repo == 2 and "complexity_half" in ordered.columns:
        for bucket in ["lower_complexity_half", "higher_complexity_half"]:
            bucket_rows = ordered[ordered["complexity_half"].astype(str) == bucket]
            if not bucket_rows.empty:
                chosen.append(int(bucket_rows.index[0]))
    for idx in ordered.index:
        if len(chosen) >= pilot_per_repo:
            break
        if int(idx) not in chosen:
            chosen.append(int(idx))
    return chosen


def count_dict(df: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in df.columns:
        return {}
    return {str(key): int(value) for key, value in df[column].fillna("").astype(str).value_counts().sort_index().items()}


def describe_split(df: pd.DataFrame, name: str) -> dict[str, Any]:
    per_repo = df.groupby("repo_id").size()
    return {
        "name": name,
        "rows": int(len(df)),
        "repos": int(df["repo_id"].astype(str).nunique()),
        "classes_per_repo_min": int(per_repo.min()) if len(per_repo) else 0,
        "classes_per_repo_max": int(per_repo.max()) if len(per_repo) else 0,
        "classes_per_repo": {str(k): int(v) for k, v in per_repo.sort_index().items()},
        "complexity_half_counts": count_dict(df, "complexity_half"),
        "build_tool_counts": count_dict(df, "build_tool"),
        "scope_count": int(df[["repo_id", "scope_key"]].drop_duplicates().shape[0]) if {"repo_id", "scope_key"} <= set(df.columns) else 0,
        "duplicate_class_key_rows": int(df.duplicated("class_key", keep=False).sum()) if "class_key" in df.columns else 0,
        "duplicate_focal_path_rows": int(df.duplicated(["repo_id", "focal_path"], keep=False).sum())
        if {"repo_id", "focal_path"} <= set(df.columns)
        else 0,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Manifest Split Report",
        "",
        f"- Created UTC: `{report['created_utc']}`",
        f"- Source manifest: `{report['source_manifest']}`",
        f"- Source SHA-256: `{report['source_sha256']}`",
        f"- Algorithm: `{report['algorithm']}`",
        f"- Pilot policy: `{report['pilot_policy']}`",
        "",
        "## Summary",
        "",
        "| Split | Rows | Repos | Min class/repo | Max class/repo | Scopes | Duplicate class_key rows | Duplicate focal rows |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["splits"]:
        lines.append(
            "| {name} | {rows} | {repos} | {classes_per_repo_min} | {classes_per_repo_max} | {scope_count} | "
            "{duplicate_class_key_rows} | {duplicate_focal_path_rows} |".format(**item)
        )
    lines.extend(["", "## Complexity Half Counts", ""])
    for item in report["splits"]:
        lines.append(f"### {item['name']}")
        for key, value in item["complexity_half_counts"].items():
            lines.append(f"- `{key}`: {value}")
        lines.append("")
    lines.extend(
        [
            "## Notes",
            "",
            "- Pilot lấy đúng `2` class mỗi repo.",
            "- Khi repo có cả `lower_complexity_half` và `higher_complexity_half`, pilot lấy một class ở mỗi nửa theo `selection_rank_in_repo` rồi `selection_hash`.",
            "- Nếu repo thiếu một nửa complexity, pilot lấy thêm class kế tiếp theo thứ tự deterministic đã khóa.",
            "- Remaining chứa toàn bộ class còn lại và không trùng `class_key` với pilot.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_manifest(source: Path, pilot_out: Path, remaining_out: Path, report_json: Path, report_md: Path, pilot_per_repo: int) -> dict[str, Any]:
    df = pd.read_csv(source, dtype=str).fillna("")
    required = {"repo_id", "class_key", "focal_path", "scope_key", "selection_rank_in_repo"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{source} missing required columns: {missing}")

    df = df.copy()
    df["_original_manifest_index"] = range(len(df))
    per_repo = df.groupby("repo_id").size()
    if int(per_repo.min()) < pilot_per_repo:
        raise ValueError(f"At least one repo has fewer than {pilot_per_repo} classes; cannot build pilot split.")

    pilot_indices: list[int] = []
    for _, group in df.groupby("repo_id", sort=True):
        pilot_indices.extend(choose_pilot_rows(group, pilot_per_repo))

    pilot_set = set(pilot_indices)
    pilot = df[df.index.isin(pilot_set)].copy()
    remaining = df[~df.index.isin(pilot_set)].copy()

    pilot = pilot.sort_values(["repo_id", "_original_manifest_index"], kind="mergesort").reset_index(drop=True)
    remaining = remaining.sort_values(["repo_id", "_original_manifest_index"], kind="mergesort").reset_index(drop=True)

    for name, split_df in [("pilot60", pilot), ("remaining240", remaining)]:
        split_df["split_name"] = name
        split_df["split_source_manifest"] = source.name
        split_df["split_created_utc"] = utc_now()
        split_df["split_algorithm"] = "per_repo_2class_pilot_complexity_half_then_selection_rank_seed42"

    pilot = pilot.rename(columns={"_original_manifest_index": "original_manifest_index"})
    remaining = remaining.rename(columns={"_original_manifest_index": "original_manifest_index"})
    helper_cols = [column for column in pilot.columns if column.startswith("_")]
    pilot = pilot.drop(columns=helper_cols, errors="ignore")
    remaining = remaining.drop(columns=helper_cols, errors="ignore")

    pilot_out.parent.mkdir(parents=True, exist_ok=True)
    pilot.to_csv(pilot_out, index=False)
    remaining.to_csv(remaining_out, index=False)

    overlap = sorted(set(pilot["class_key"].astype(str)) & set(remaining["class_key"].astype(str)))
    report = {
        "created_utc": utc_now(),
        "source_manifest": str(source),
        "source_sha256": sha256_file(source),
        "pilot_manifest": str(pilot_out),
        "pilot_sha256": sha256_file(pilot_out),
        "remaining_manifest": str(remaining_out),
        "remaining_sha256": sha256_file(remaining_out),
        "algorithm": "deterministic split from already sampled seed42 manifest",
        "pilot_policy": f"{pilot_per_repo} classes per repo; prefer one lower_complexity_half and one higher_complexity_half",
        "overlap_class_key_n": len(overlap),
        "overlap_class_key_examples": overlap[:10],
        "source": describe_split(df, "source300"),
        "splits": [describe_split(pilot, "pilot60"), describe_split(remaining, "remaining240")],
    }
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report_md, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split RBL-4 data_new manifest into pilot60 and remaining240 files.")
    parser.add_argument("--source", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--pilot-out", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--remaining-out", type=Path, default=DEFAULT_REMAINING)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--pilot-per-repo", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = split_manifest(
        args.source.resolve(),
        args.pilot_out.resolve(),
        args.remaining_out.resolve(),
        args.report_json.resolve(),
        args.report_md.resolve(),
        args.pilot_per_repo,
    )
    print(json.dumps({key: report[key] for key in ["pilot_manifest", "remaining_manifest", "overlap_class_key_n"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
