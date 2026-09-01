"""Downloadable-FTWS top-N watchlist via LEI probes. Thin wrapper around build_watchlist."""
from __future__ import annotations

import argparse
from pathlib import Path

from papertrails.build_watchlist import DEFAULT_GOGEL, main as build_main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Build downloadable-FTWS top-N watchlist "
            "(sec_docType FTWS + ISIN ≥12 + downloadFile, same builder)"
        )
    )
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--out", type=Path, default=Path("papertrails/watchlist_top50.yaml"))
    ap.add_argument(
        "--probes-per-parent",
        type=int,
        default=8,
        help="Max LEIs to probe per parent (parent first, then finance/operating subs)",
    )
    ap.add_argument("--gogel", type=Path, default=DEFAULT_GOGEL)
    ap.add_argument("--no-benchmarks", action="store_true")
    args = ap.parse_args(argv)

    forwarded = [
        "--top",
        str(args.top),
        "--out",
        str(args.out),
        "--verify-solr",
        "--leis-per-parent",
        str(args.probes_per_parent),
        "--gogel",
        str(args.gogel),
    ]
    if args.no_benchmarks:
        forwarded.append("--no-benchmarks")
    return build_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
