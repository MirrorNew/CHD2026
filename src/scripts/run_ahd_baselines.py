# -*- coding: utf-8 -*-
"""CLI wrapper for task-adapted AHD baseline smoke/search runs."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from baselines.AHD.run_smoke import main


if __name__ == "__main__":
    main()
