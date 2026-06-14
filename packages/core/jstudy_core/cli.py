from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packages.core.jstudy_core.pipeline import PROJECT_ROOT, run_mvp
from packages.core.jstudy_core.settings import RuntimeSettings
from packages.retrieval.hybrid import load_rag_config


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = PROJECT_ROOT
    settings = RuntimeSettings.from_env(root)
    parser = argparse.ArgumentParser(description="Run the single-courseware DeepTutor MVP.")
    parser.add_argument("--pdf", type=Path, default=root / "courseware.pdf")
    parser.add_argument("--soul", type=Path, default=settings.soul_path)
    parser.add_argument("--mnemonics", type=Path, default=settings.mnemonics_path)
    parser.add_argument("--api-key", type=Path, default=settings.api_key_path)
    parser.add_argument("--outline", type=Path)
    parser.add_argument("--output-dir", type=Path, default=root)
    parser.add_argument("--output-prefix", default="mvp")
    parser.add_argument("--chat-model", default=settings.chat_model)
    parser.add_argument("--embed-model", default=settings.embed_model)
    parser.add_argument("--rag-config", type=Path)
    parser.add_argument("--embedding-cache", type=Path, default=root / ".mvp_cache" / "embeddings.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    outputs = run_mvp(
        pdf_path=args.pdf,
        soul_path=args.soul,
        mnemonics_path=args.mnemonics,
        api_key_path=args.api_key,
        output_dir=args.output_dir,
        chat_model=args.chat_model,
        embed_model=args.embed_model,
        output_prefix=args.output_prefix,
        rag_config=load_rag_config(args.rag_config),
        embedding_cache_path=args.embedding_cache,
        outline_path=args.outline,
    )
    print("MVP outputs:")
    for name, path in outputs.items():
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
