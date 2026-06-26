#!/usr/bin/env python
"""Generate a HAST framework concept figure using a GPT image endpoint.

The script reads API credentials only from environment variables:
HAST_IMAGE_API_KEY and HAST_IMAGE_BASE_URL.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "artifacts" / "figures"
REFERENCE = FIG_DIR / "Gemini-Framework.png"
OUT = FIG_DIR / "HAST-Framework-gpt-image2.png"
PROMPT_OUT = FIG_DIR / "HAST-Framework-gpt-image2.prompt.txt"


PROMPT = """
Create a wide, publication-quality technical framework diagram inspired by the
provided reference image style: soft muted green flow ribbons, clean academic
vector illustration, off-white background, circular graph motifs, light gray
failed branches, and clear left-to-right process flow.

IMPORTANT TEXT FIDELITY:
Use exactly these English labels where labels are needed. Keep labels short,
large, and readable. Do not invent extra titles or misspell HAST.

Overall title:
HAST: Three-Stage Heuristic Discovery for Network Dismantling

Left section title:
Stage I: Free Tree Search

Left section content:
- Root heuristic
- Candidate program h_t
- failure
- low credit
- high cost
- unstable
- credit-aware expansion

Middle section title:
Stage II: Evidence-Induced Candidate Boundaries

Inside the main green banner, title:
Log-Induced Bounded Candidate Language

Replace the generic icons in this banner with six simple experiment-grounded
summary icons. Keep them as generic small icons, similar in complexity to the
reference image, not detailed plots:
1. two-hop-boundary family
   A tiny graph with a center node and two local rings. Add text: two-hop boundary.
2. residual and neighbor degree
   A tiny graph with one larger node and degree-like spokes. Add text: residual degree.
3. frontier and weak tie
   Two communities connected by one bridge edge. Add text: frontier / weak tie.
4. bounded locality caps
   A small ruler/stop-cap icon with the exact text: caps 64/128.
5. lazy local heap updates
   A simple priority-queue stack with a local arrow. Add text: lazy heap.
6. forbidden slow patterns
   A crossed-out network scan icon. Add text: no global rescan.

Under the Stage II banner, add a compact policy card:
10/10 valid policy summaries
preferred family: two-hop-boundary
valid rate: 299/300
mean runtime: 0.026s
allowed radius <= 2

Right section title:
Stage III: Bounded Tree Search and Selection

Right section content:
- bounded candidate language
- local compression
- cost-aware credit
- prune low-potential family
- HAST-Final-Q (quality)
- HAST-Final-S (speed)

Use the same general feeling as the reference:
Stage I on the left with root heuristic branching into many candidate programs;
Stage II in the middle/top as a large green bounded-language funnel with the
six mini-figures; Stage III on the right with bounded search branches leading
to two final candidates.

Visual constraints:
- Do not include unrelated cross-task optimization terms.
- Do not use "Free-visualization" or "micro-visuitation".
- Use HAST-Final-Q for quality and HAST-Final-S for speed.
- Use a star icon for HAST-Final-Q and a clock icon for HAST-Final-S.
- Keep text readable and avoid overlapping labels.
- The diagram should be a single cohesive wide figure, not a collage.
"""


def _write_image_from_response(data: dict, out_path: Path) -> None:
    image_data = None
    if isinstance(data.get("data"), list) and data["data"]:
        first = data["data"][0]
        if first.get("b64_json"):
            image_data = base64.b64decode(first["b64_json"])
        elif first.get("url"):
            image_data = requests.get(first["url"], timeout=120).content
    if image_data is None:
        raise RuntimeError("No image data returned: " + json.dumps(data)[:1000])
    out_path.write_bytes(image_data)


def main() -> None:
    api_key = os.environ.get("HAST_IMAGE_API_KEY")
    base_url = os.environ.get("HAST_IMAGE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key:
        raise SystemExit("Set HAST_IMAGE_API_KEY first.")

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_OUT.write_text(PROMPT.strip() + "\n", encoding="utf-8")

    headers = {"Authorization": f"Bearer {api_key}"}

    # Prefer image edit with the existing framework figure as a style/layout
    # reference. If the provider does not expose edits for this model, fall back
    # to text-only generation.
    edit_url = f"{base_url}/images/edits"
    with REFERENCE.open("rb") as image_file:
        files = {"image": (REFERENCE.name, image_file, "image/png")}
        data = {
            "model": "gpt-image-2",
            "prompt": PROMPT,
            "size": "1536x1024",
            "response_format": "b64_json",
        }
        response = requests.post(edit_url, headers=headers, data=data, files=files, timeout=300)

    if response.status_code >= 400:
        gen_url = f"{base_url}/images/generations"
        payload = {
            "model": "gpt-image-2",
            "prompt": PROMPT,
            "size": "1536x1024",
            "response_format": "b64_json",
        }
        response = requests.post(gen_url, headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=300)

    if response.status_code >= 400:
        raise RuntimeError(f"Image API failed {response.status_code}: {response.text[:2000]}")

    _write_image_from_response(response.json(), OUT)
    print(OUT)
    print(PROMPT_OUT)


if __name__ == "__main__":
    main()
