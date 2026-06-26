# -*- coding: utf-8 -*-
"""Candidate code extraction, validation, and execution."""

from __future__ import annotations

import ast
import hashlib
import math
import re
import textwrap
from dataclasses import dataclass
from typing import Any, Callable

import networkx as nx
import numpy as np

from baselines.ND_native_baseline.native_baseline.utils import complete_order

ALLOWED_IMPORT_ROOTS = {
    "math",
    "heapq",
    "random",
    "itertools",
    "collections",
    "networkx",
    "numpy",
}

FORBIDDEN_TOKENS = [
    "__import__",
    "open(",
    "exec(",
    "eval(",
    "compile(",
    "input(",
    "globals(",
    "locals(",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "shutil",
    "pathlib",
    "pickle",
    "marshal",
    "ctypes",
    "multiprocessing",
    "threading",
    "os.",
    "sys.",
    "write(",
    "rmdir(",
    "unlink(",
]


@dataclass
class CandidateProgram:
    candidate_id: str
    code: str
    family: str = "unknown"
    source_stage: str = "unknown"


def stable_hash(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def extract_code(response_text: str, function_name: str = "degree_order") -> str:
    pattern = rf"def\s+{re.escape(function_name)}\s*\("
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", response_text, flags=re.DOTALL | re.IGNORECASE)
    for block in blocks:
        if re.search(pattern, block):
            return block.strip()
    match = re.search(pattern, response_text)
    if match:
        return response_text[match.start() :].strip()
    return response_text.strip()


def validate_code(code: str, function_name: str = "degree_order") -> str:
    code = textwrap.dedent(code).strip()
    if f"def {function_name}" not in code:
        raise ValueError(f"missing {function_name} function")
    lowered = code.lower()
    for token in FORBIDDEN_TOKENS:
        if token.lower() in lowered:
            raise ValueError(f"forbidden token: {token}")
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    raise ValueError(f"import not allowed: {name}")
    return code


def compile_candidate(program: CandidateProgram, function_name: str = "degree_order") -> Callable[..., list[Any]]:
    code = validate_code(program.code, function_name=function_name)

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        del globals, locals, level
        root = name.split(".")[0]
        if root not in ALLOWED_IMPORT_ROOTS:
            raise ImportError(f"import not allowed: {name}")
        return __import__(name, fromlist=fromlist)

    namespace: dict[str, Any] = {
        "math": math,
        "np": np,
        "numpy": np,
        "nx": nx,
        "networkx": nx,
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "iter": iter,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "next": next,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "__import__": safe_import,
        },
    }
    exec(compile(code, f"<candidate:{program.candidate_id}>", "exec"), namespace, namespace)
    fn = namespace.get(function_name)
    if not callable(fn):
        raise ValueError(f"{function_name} is not callable")

    if function_name != "degree_order":
        return fn

    def runner(graph: nx.Graph) -> list[Any]:
        return complete_order(graph, fn(graph.copy()))

    return runner


def make_program(
    code: str,
    family: str = "unknown",
    source_stage: str = "unknown",
    function_name: str = "degree_order",
) -> CandidateProgram:
    clean = validate_code(code, function_name=function_name)
    return CandidateProgram(candidate_id=stable_hash(clean), code=clean, family=family, source_stage=source_stage)

