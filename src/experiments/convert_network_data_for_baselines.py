# -*- coding: utf-8 -*-
"""Convert CHD2026/network/Data files to baseline-readable edge lists."""

from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IN_DIR = ROOT / "network" / "Data" / "Data"
OUT_DIR = ROOT / "network" / "Data" / "baseline_edgelists"
MANIFEST = ROOT / "network" / "Data" / "baseline_edgelists_manifest.csv"


def parse_edges(path: Path) -> tuple[list[tuple[int, int]], dict[str, int]]:
    edges: set[tuple[int, int]] = set()
    stats = {
        "raw_nonempty_lines": 0,
        "usable_edge_lines": 0,
        "bad_lines": 0,
        "selfloops": 0,
    }
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            text = line.strip()
            if not text or text.startswith("#") or text.startswith("%"):
                continue
            stats["raw_nonempty_lines"] += 1
            parts = text.replace(",", " ").split()
            if len(parts) < 2:
                stats["bad_lines"] += 1
                continue
            try:
                u = int(float(parts[0]))
                v = int(float(parts[1]))
            except ValueError:
                stats["bad_lines"] += 1
                continue
            if u == v:
                stats["selfloops"] += 1
                continue
            a, b = (u, v) if u <= v else (v, u)
            edges.add((a, b))
            stats["usable_edge_lines"] += 1
    return sorted(edges), stats


def edge_hash(edges: list[tuple[int, int]]) -> str:
    digest = hashlib.sha256()
    for u, v in edges:
        digest.update(f"{u} {v}\n".encode("utf-8"))
    return digest.hexdigest()


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    seen_hash: dict[str, str] = {}
    used_outputs: set[str] = set()
    for path in sorted(IN_DIR.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".txt", ".edgelist"}:
            rows.append(
                {
                    "source": str(path),
                    "status": "skipped",
                    "reason": "unsupported_extension",
                }
            )
            continue
        edges, stats = parse_edges(path)
        if not edges:
            rows.append(
                {
                    "source": str(path),
                    "status": "skipped",
                    "reason": "no_parseable_edges",
                    **stats,
                }
            )
            continue
        digest = edge_hash(edges)
        output_name = f"{path.stem}.edgelist"
        if output_name.lower() in used_outputs:
            output_name = f"{path.stem}__{path.suffix.lower().lstrip('.')}.edgelist"
        used_outputs.add(output_name.lower())
        output = OUT_DIR / output_name
        with output.open("w", encoding="utf-8", newline="\n") as fh:
            for u, v in edges:
                fh.write(f"{u} {v}\n")
        nodes = {node for edge in edges for node in edge}
        rows.append(
            {
                "source": str(path),
                "output": str(output),
                "status": "converted",
                "reason": "",
                "nodes": len(nodes),
                "unique_edges": len(edges),
                "sha256_normalized_edges": digest,
                "duplicate_of": seen_hash.get(digest, ""),
                **stats,
            }
        )
        seen_hash.setdefault(digest, str(output))

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[done] converted={sum(1 for row in rows if row.get('status') == 'converted')} manifest={MANIFEST}")


if __name__ == "__main__":
    main()
