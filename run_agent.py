#!/usr/bin/env python3
"""Autonomous Canvas SpeedGrader Grading Agent Runner.

Top-level CLI execution script for autonomous grading across allocated cohorts.
Defaults to headed browser mode (headless=False) per user directive.
"""

from __future__ import annotations

import sys
from src.cli import main

if __name__ == "__main__":
    sys.exit(main())
