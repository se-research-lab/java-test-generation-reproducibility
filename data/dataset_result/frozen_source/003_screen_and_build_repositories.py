#!/usr/bin/env python3
"""Step 003: module-aware qualification on the user's effective JDK 8 runtime."""

import argparse
from pathlib import Path

from v3_core import PipelineError, STEP003_RESTART_CONFIRMATION, screen_and_build_repositories


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 003 — clone, freeze, module-build on JDK 8, and qualify 30 repositories"
    )
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config_v3.yaml"))
    parser.add_argument(
        "--retry-recoverable", action="store_true",
        help="Reset only pre-registered transient failure categories to pending before resuming",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--resume", dest="mode", action="store_const", const="resume",
        help="Preserve qualified/definitive results and continue the immutable queue (default)",
    )
    mode.add_argument(
        "--restart-from-beginning", dest="mode", action="store_const", const="restart",
        help="Archive all current Step 003 progress and restart screening from queue position 1",
    )
    parser.set_defaults(mode="resume")
    parser.add_argument(
        "--confirm-restart", default="", metavar="TOKEN",
        help=f"Required safety token for restart mode: {STEP003_RESTART_CONFIRMATION}",
    )
    args = parser.parse_args()
    try:
        screen_and_build_repositories(
            args.config, retry_recoverable=args.retry_recoverable,
            mode=args.mode, restart_confirmation=args.confirm_restart,
        )
        return 0
    except PipelineError as error:
        parser.exit(2, f"STOP: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
