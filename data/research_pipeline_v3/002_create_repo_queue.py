#!/usr/bin/env python3
"""Step 002: create the deterministic seed-42 candidate repository queue."""

import argparse
from pathlib import Path

from v3_core import PipelineError, create_repository_queue


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 002 — deterministic repository queue")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config_v3.yaml"))
    args = parser.parse_args()
    try:
        create_repository_queue(args.config)
        return 0
    except PipelineError as error:
        parser.exit(2, f"STOP: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())

