#!/usr/bin/env python3
"""Step 000: validate the JDK 8 environment and create the immutable V2 backup."""

import argparse
from pathlib import Path

from v3_core import PipelineError, preflight_and_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 000 — JDK 8 preflight and complete V2 backup")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config_v3.yaml"))
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Run environment preflight without creating another V2 backup; the marker records backup_skipped=true",
    )
    args = parser.parse_args()
    try:
        preflight_and_backup(args.config, skip_backup=args.skip_backup)
        return 0
    except PipelineError as error:
        parser.exit(2, f"STOP: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
