#!/usr/bin/env python3
"""Step 001: reconstruct the unique physical focal-class metadata frame."""

import argparse
from pathlib import Path

from v3_core import PipelineError, reconstruct_unique_frame


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 001 — deduplicate CLASSES2TEST mappings without Java/CC/outcome filtering"
    )
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config_v3.yaml"))
    args = parser.parse_args()
    try:
        reconstruct_unique_frame(args.config)
        return 0
    except PipelineError as error:
        parser.exit(2, f"STOP: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())

