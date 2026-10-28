from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


DEFAULT_MODEL = "gpt-4o-mini-2024-07-18"
DEFAULT_PROMPT = "rbl4-zero-shot"

RunMode = Literal["dry_run", "baseline_only", "report_only", "full_run"]
SampleKey = Literal["full_300", "pilot_60", "remaining_240", "custom"]
RunStatus = Literal["queued", "running", "completed", "failed", "cancelled", "unknown"]


class RunCreateRequest(BaseModel):
    sample_key: SampleKey = "full_300"
    custom_sample_csv: str | None = None
    run_mode: RunMode = "dry_run"
    model: str = DEFAULT_MODEL
    prompt: str = DEFAULT_PROMPT
    workers: int = Field(default=1, ge=1, le=32)
    resume: bool = False
    clear_agone_output: bool = True


class ArtifactInfo(BaseModel):
    name: str
    path: str
    size_bytes: int = 0
    modified_at: str | None = None


class GeneratedTestInfo(BaseModel):
    project: str = ""
    arm: str = ""
    file_name: str = ""
    source_path: str = ""
    stored_path: str = ""
    size_bytes: int = 0
    modified_at: str | None = None


class ApiCallInfo(BaseModel):
    timestamp_utc: str = ""
    model_requested: str = ""
    model_returned: str = ""
    duration_sec: str | float = ""
    prompt_tokens: str | int = ""
    completion_tokens: str | int = ""
    total_tokens: str | int = ""
    status: str = ""
    error_type: str = ""
    error_message: str = ""


class RunInfo(BaseModel):
    run_id: str
    status: RunStatus
    run_mode: RunMode | str
    sample_csv: str
    model: str
    prompt: str
    workers: int | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    pid: int | None = None
    return_code: int | None = None
    source_sample_n: int | None = None
    buildable_run_n: int | None = None
    precheck_skipped_n: int | None = None
    baseline_pass_n: int | None = None
    baseline_failed_n: int | None = None
    generation_run_n: int | None = None
    error: str | None = None
    artifacts: list[ArtifactInfo] = Field(default_factory=list)


class RunEvent(BaseModel):
    event_id: int
    timestamp_utc: str
    phase: str
    project: str = ""
    module: str = ""
    arm: str = ""
    focal_class: str = ""
    test_class: str = ""
    status: str = ""
    duration_sec: str | float = ""
    detail: str = ""


class SummaryPayload(BaseModel):
    run: RunInfo
    summary: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    generated_tests: list[GeneratedTestInfo] = Field(default_factory=list)
    api_calls: list[ApiCallInfo] = Field(default_factory=list)
    metrics_preview: list[dict[str, Any]] = Field(default_factory=list)
    recent_events: list[RunEvent] = Field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
