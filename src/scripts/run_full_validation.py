# -*- coding: utf-8 -*-
"""完整验证命令入口。

该入口只评估阶段3固定的 HAST-Final-Q/S，不重新选择候选算法。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from experiments.full_validation import main


if __name__ == "__main__":
    main()
