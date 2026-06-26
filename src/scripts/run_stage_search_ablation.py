# -*- coding: utf-8 -*-
"""CLI wrapper for Section 5.3 HAST ablation analysis."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from experiments.stage_search_ablation import main


if __name__ == "__main__":
    main()

