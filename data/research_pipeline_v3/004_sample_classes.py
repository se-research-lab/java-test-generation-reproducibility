#!/usr/bin/env python3
"""Step 004: select 10 main and 2 backup classes per qualified repository."""

import argparse
from pathlib import Path

from v3_core import PipelineError, sample_classes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 004 — SHA-256 class sampling independent of cyclomatic complexity"
    )
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config_v3.yaml"))
    args = parser.parse_args()
    try:
        sample_classes(args.config)
        return 0
    except PipelineError as error:
        parser.exit(2, f"STOP: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())

