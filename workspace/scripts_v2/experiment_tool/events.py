from __future__ import annotations

import asyncio
import csv
import json
import time
from pathlib import Path
from typing import AsyncIterator

from .schemas import RunEvent, utc_now


PHASE_LOG_FIELDS = [
    "timestamp_utc",
    "phase",
    "project",
    "module",
    "arm",
    "focal_class",
    "test_class",
    "status",
    "duration_sec",
    "detail",
]


def append_event(path: Path, phase: str, status: str, detail: str = "", **extra: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    row = {field: "" for field in PHASE_LOG_FIELDS}
    row.update(
        {
            "timestamp_utc": utc_now(),
            "phase": phase,
            "status": status,
            "detail": str(detail)[:1000],
        }
    )
    for key, value in extra.items():
        if key in row:
            row[key] = value
    def write_row(target_path: Path) -> None:
        target_exists = target_path.exists()
        with target_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=PHASE_LOG_FIELDS)
            if not target_exists:
                writer.writeheader()
            writer.writerow(row)

    for attempt in range(10):
        try:
            write_row(path)
            return
        except PermissionError:
            time.sleep(0.1 * (attempt + 1))
    try:
        write_row(path.with_name(path.name + ".fallback.csv"))
    except Exception as exc:
        print(f"[RBL4] Could not write phase event: {exc}")


def read_events(path: Path, limit: int | None = None) -> list[RunEvent]:
    if not path.exists():
        return []
    rows: list[RunEvent] = []
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader):
            rows.append(
                RunEvent(
                    event_id=index,
                    timestamp_utc=row.get("timestamp_utc") or "",
                    phase=row.get("phase") or "",
                    project=row.get("project") or "",
                    module=row.get("module") or "",
                    arm=row.get("arm") or "",
                    focal_class=row.get("focal_class") or "",
                    test_class=row.get("test_class") or "",
                    status=row.get("status") or "",
                    duration_sec=row.get("duration_sec") or "",
                    detail=row.get("detail") or "",
                )
            )
    if limit is not None:
        return rows[-limit:]
    return rows


async def event_stream(path: Path, stop_when_done: callable | None = None) -> AsyncIterator[str]:
    cursor = 0
    heartbeat = 0
    while True:
        events = read_events(path)
        for event in events[cursor:]:
            payload_dict = event.model_dump() if hasattr(event, "model_dump") else event.dict()
            payload = json.dumps(payload_dict, ensure_ascii=False)
            yield f"id: {event.event_id}\nevent: phase\ndata: {payload}\n\n"
        cursor = len(events)

        if stop_when_done is not None and stop_when_done():
            yield "event: done\ndata: {}\n\n"
            return

        heartbeat += 1
        if heartbeat % 10 == 0:
            yield "event: heartbeat\ndata: {}\n\n"
        await asyncio.sleep(1)
