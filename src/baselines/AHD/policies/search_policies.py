# -*- coding: utf-8 -*-
"""Compatibility shim for older imports.

Implementations live in the nine method-specific modules and registry.py.
"""

from .registry import (
    AlphaEvolvePolicy,
    CladeAHDPolicy,
    EOHPolicy,
    ERAPolicy,
    FunSearchPolicy,
    HiFoPromptPolicy,
    HSEvoPolicy,
    MCTSAHDPolicy,
    ReEvoPolicy,
    all_policies,
)

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
