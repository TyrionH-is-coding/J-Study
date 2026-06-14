from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OutputPaths:
    chunks: Path
    trace: Path
    evidence: Path
    evidence_links: Path
    markdown: Path
    quality: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "chunks": self.chunks,
            "trace": self.trace,
            "evidence": self.evidence,
            "evidence_links": self.evidence_links,
            "markdown": self.markdown,
            "quality": self.quality,
        }


def build_output_paths(output_dir: Path, output_prefix: str) -> OutputPaths:
    return OutputPaths(
        chunks=output_dir / f"{output_prefix}-chunks.json",
        trace=output_dir / f"{output_prefix}-retrieval_trace.json",
        evidence=output_dir / f"{output_prefix}-evidence.json",
        evidence_links=output_dir / f"{output_prefix}-evidence_links.json",
        markdown=output_dir / f"{output_prefix}-output.md",
        quality=output_dir / f"{output_prefix}-quality.json",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
