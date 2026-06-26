# -*- coding: utf-8 -*-
"""Rebuild paper figure artifacts from actual Markdown references."""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
DOC = PROJECT / "docs" / "15_chinese_paper_full_cn.md"
FIGURES = PROJECT / "artifacts" / "figures"
SNAPSHOT = PROJECT / "src" / "runs" / "figure_rebuild_snapshot"
FALLBACK_ROOTS = [
    SNAPSHOT,
    PROJECT / "src" / "runs" / "runs_paper_evidence_20260616",
    PROJECT.parent / "research" / "paper_problem_solution_reframe_20260522" / "figures",
    PROJECT.parent / "history-HAST-Gen-1st",
]
SECTIONS = [
    "03_motivation",
    "04_method",
    "05_2_benchmark",
    "05_3_ablation",
    "05_4_interpretability",
    "05_5_scaling",
    "05_5_collapse",
    "appendix",
]

MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HTML_IMAGE_RE = re.compile(r"<img\b([^>]*?)src=\"([^\"]+)\"([^>]*)>", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#+)\s+(.+?)\s*$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_src(src: str) -> Path:
    text = src.strip()
    if re.match(r"^[A-Za-z]:\\", text):
        return Path(text)
    return (DOC.parent / text).resolve()


def find_by_name(name: str) -> Path | None:
    for root in FALLBACK_ROOTS:
        if not root.exists():
            continue
        matches = sorted(root.rglob(name), key=lambda p: len(str(p)))
        if matches:
            return matches[0]
    return None


def rel_to_doc(path: Path) -> str:
    return Path("..", *path.resolve().relative_to(PROJECT).parts).as_posix()


def section_for(current_heading: str) -> str:
    if current_heading.startswith("3"):
        return "03_motivation"
    if current_heading.startswith("4"):
        return "04_method"
    if current_heading.startswith("5.2"):
        return "05_2_benchmark"
    if current_heading.startswith("5.3"):
        return "05_3_ablation"
    if current_heading.startswith("5.4"):
        return "05_4_interpretability"
    if current_heading.startswith("5.5.2"):
        return "05_5_collapse"
    if current_heading.startswith("5.5"):
        return "05_5_scaling"
    return "appendix"


def convert_png_to_pdf(src: Path, dest: Path) -> None:
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    img = mpimg.imread(src)
    height, width = img.shape[:2]
    fig_w = max(1.0, width / 160.0)
    fig_h = max(1.0, height / 160.0)
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=160)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(img)
    ax.axis("off")
    fig.savefig(dest, format="pdf", bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def clean_figures_dir() -> list[dict[str, str]]:
    resolved = FIGURES.resolve()
    expected = (PROJECT / "artifacts" / "figures").resolve()
    if resolved != expected:
        raise RuntimeError(f"refusing to clean unexpected path: {resolved}")
    rows: list[dict[str, str]] = []
    if SNAPSHOT.exists():
        shutil.rmtree(SNAPSHOT)
    if FIGURES.exists():
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(FIGURES, SNAPSHOT)
        rows.append({"path": str(SNAPSHOT), "action": "snapshotted_existing_figures"})
    if FIGURES.exists():
        shutil.rmtree(FIGURES)
        rows.append({"path": str(FIGURES), "action": "cleared_generated_figures_dir"})
    for section in SECTIONS:
        (FIGURES / section).mkdir(parents=True, exist_ok=True)
    return rows


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    clean_rows = clean_figures_dir()
    manifest: list[dict[str, object]] = []
    replacements: dict[str, str] = {}
    current_heading = ""

    for lineno, line in enumerate(lines, start=1):
        heading = HEADING_RE.match(line.strip())
        if heading:
            current_heading = heading.group(2)
        section = section_for(current_heading)

        matches: list[tuple[str, str, str]] = []
        for match in MD_IMAGE_RE.finditer(line):
            matches.append(("markdown", match.group(0), match.group(2)))
        for match in HTML_IMAGE_RE.finditer(line):
            matches.append(("html", match.group(0), match.group(2)))

        for kind, full_ref, src_text in matches:
            src = resolve_src(src_text)
            if not src.exists():
                fallback = find_by_name(Path(src_text).name)
                if fallback is not None:
                    src = fallback
            status = "ok" if src.exists() else "missing_source"
            dest_png = ""
            dest_pdf = ""
            data_path = ""
            raster_pdf = False
            if status == "ok":
                dest_dir = FIGURES / section
                ext = src.suffix.lower()
                dest = dest_dir / src.name
                if ext != ".png":
                    dest = dest.with_suffix(ext)
                shutil.copy2(src, dest)
                dest_png = str(dest)

                sibling_pdf = src.with_suffix(".pdf")
                pdf_dest = dest.with_suffix(".pdf")
                if sibling_pdf.exists():
                    shutil.copy2(sibling_pdf, pdf_dest)
                elif ext in {".png", ".jpg", ".jpeg"}:
                    convert_png_to_pdf(src, pdf_dest)
                    raster_pdf = True
                dest_pdf = str(pdf_dest) if pdf_dest.exists() else ""

                data_dest = dest.with_suffix(".data.csv")
                with data_dest.open("w", encoding="utf-8-sig", newline="") as fh:
                    writer = csv.DictWriter(
                        fh,
                        fieldnames=[
                            "figure",
                            "paper_line",
                            "source_path",
                            "source_sha256",
                            "copied_image",
                            "copied_pdf",
                        ],
                    )
                    writer.writeheader()
                    writer.writerow(
                        {
                            "figure": dest.name,
                            "paper_line": lineno,
                            "source_path": str(src),
                            "source_sha256": sha256(src),
                            "copied_image": str(dest),
                            "copied_pdf": dest_pdf,
                        }
                    )
                data_path = str(data_dest)

                new_src = rel_to_doc(dest)
                if kind == "markdown":
                    replacements[src_text] = new_src
                else:
                    replacements[src_text] = new_src

            manifest.append(
                {
                    "paper_line": lineno,
                    "section": section,
                    "kind": kind,
                    "original_src": src_text,
                    "resolved_src": str(src),
                    "status": status,
                    "copied_image": dest_png,
                    "copied_pdf": dest_pdf,
                    "data": data_path,
                    "raster_pdf": raster_pdf,
                }
            )

    new_text = text
    for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        new_text = new_text.replace(old, new)
    DOC.write_text(new_text, encoding="utf-8")

    manifest_path = FIGURES / "figure_manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        writer.writeheader()
        writer.writerows(manifest)
    with (FIGURES / "deletion_manifest.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "action"])
        writer.writeheader()
        writer.writerows(clean_rows)
    print(f"[done] rebuilt {len(manifest)} figures into {FIGURES}")


if __name__ == "__main__":
    main()
