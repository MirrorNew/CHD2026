# -*- coding: utf-8 -*-
"""Policy registry for AHD baselines."""

from __future__ import annotations

import random
from typing import Any

from ..task_adapters import BaseTaskAdapter, get_task_adapter
from .alphaevolve import Policy as AlphaEvolvePolicy
from .clade_ahd import Policy as CladeAHDPolicy
from .eoh import Policy as EOHPolicy
from .era import Policy as ERAPolicy
from .funsearch import Policy as FunSearchPolicy
from .hifo_prompt import Policy as HiFoPromptPolicy
from .hsevo import Policy as HSEvoPolicy
from .mcts_ahd import Policy as MCTSAHDPolicy
from .reevo import Policy as ReEvoPolicy


POLICY_CLASSES = [
    ERAPolicy,
    EOHPolicy,
    ReEvoPolicy,
    MCTSAHDPolicy,
    HiFoPromptPolicy,
    FunSearchPolicy,
    HSEvoPolicy,
    CladeAHDPolicy,
    AlphaEvolvePolicy,
]


def all_policies(task_adapter: BaseTaskAdapter | None = None) -> list[Any]:
    adapter = task_adapter or get_task_adapter("nd")
    rng = random.Random(20260603)
    return [policy_class(adapter, rng=random.Random(rng.randint(0, 10**9))) for policy_class in POLICY_CLASSES]


__all__ = [
    "AlphaEvolvePolicy",
    "CladeAHDPolicy",
    "EOHPolicy",
    "ERAPolicy",
    "FunSearchPolicy",
    "HiFoPromptPolicy",
    "HSEvoPolicy",
    "MCTSAHDPolicy",
    "ReEvoPolicy",
    "all_policies",
]
