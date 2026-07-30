from __future__ import annotations

from collections.abc import Iterable

from .models import InlineRun, MaterialPackageV2


def _render_runs(runs: Iterable[InlineRun]) -> str:
    rendered: list[str] = []
    for run in runs:
        if run.type == "text":
            rendered.append(run.text)
        elif run.type == "strong":
            rendered.append(f"**{run.text}**")
        elif run.type == "emphasis":
            rendered.append(f"*{run.text}*")
        elif run.type == "inline_code":
            rendered.append(f"`{run.text}`")
        elif run.type == "inline_formula":
            rendered.append(f"${run.latex}$")
        else:
            rendered.append(f"<!-- evidence: {run.evidence_id} -->")
    return "".join(rendered)


def _table_cell(runs: Iterable[InlineRun]) -> str:
    return _render_runs(runs).replace("|", r"\|").replace("\n", " ")


def _render_block(block: object) -> str:
    block_type = getattr(block, "type")
    if block_type == "heading":
        return f"{'#' * block.level} {_render_runs(block.runs)}"
    if block_type == "paragraph":
        return _render_runs(block.runs)
    if block_type == "list":
        marker = (
            lambda index: f"{index}."
            if block.ordered
            else "-"
        )
        return "\n".join(
            f"{marker(index)} {_render_runs(item)}"
            for index, item in enumerate(block.items, start=1)
        )
    if block_type == "table":
        header = "| " + " | ".join(_table_cell(cell) for cell in block.headers) + " |"
        separator = "| " + " | ".join("---" for _ in block.headers) + " |"
        rows = [
            "| " + " | ".join(_table_cell(cell) for cell in row) + " |"
            for row in block.rows
        ]
        return "\n".join([header, separator, *rows])
    if block_type == "callout":
        labels = {
            "key_point": "关键点",
            "note": "说明",
            "warning": "警告",
        }
        return f"> **{labels[block.variant]}：** {_render_runs(block.runs)}"
    return f"$$\n{block.latex}\n$$"


def render_compatibility_markdown(package: MaterialPackageV2) -> str:
    parts = [f"# {package.title}"]
    for section in sorted(package.sections, key=lambda item: item.order):
        parts.append(f"## {section.title}")
        parts.extend(_render_block(block) for block in section.blocks)
    return "\n\n".join(parts) + "\n"
