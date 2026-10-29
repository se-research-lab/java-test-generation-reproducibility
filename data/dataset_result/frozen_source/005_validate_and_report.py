#!/usr/bin/env python3
"""Step 005: validate every invariant, assign relative CC halves, and report readiness."""

import argparse
from pathlib import Path

from v3_core import PipelineError, validate_and_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 005 — integrity validation and reproducibility reports")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config_v3.yaml"))
    args = parser.parse_args()
    try:
        validate_and_report(args.config)
        return 0
    except PipelineError as error:
        parser.exit(2, f"STOP: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
