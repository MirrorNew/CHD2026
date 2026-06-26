# -*- coding: utf-8 -*-
"""CHD 阶段搜索命令入口。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from experiments.chd_main_search import main


if __name__ == "__main__":
    main()

