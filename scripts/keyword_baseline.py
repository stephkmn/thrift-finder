"""Run the S3-3 keyword-only baseline against the local listing dataset.

Usage from the repository root (no FashionCLIP model required):
    python -m scripts.keyword_baseline --query "brown leather jacket"
    python -m scripts.keyword_baseline --category jacket --color brown --fabric leather
    python -m scripts.keyword_baseline --query "brown jacket" --out data/keyword_baseline.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.data.keyword_baseline import rank_edited_attributes, rank_keywords
from backend.app.data.local_dataset import DEFAULT_LISTINGS, load_listings
from backend.app.data.query_keywords import build_keywords
from backend.app.schemas import Attributes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listings", type=Path, default=DEFAULT_LISTINGS)
    parser.add_argument("--query", help="Keyword query, e.g. 'brown leather jacket'")
    parser.add_argument("--category", default="unknown")
    parser.add_argument("--color", default="unknown")
    parser.add_argument("--fabric", default="unknown")
    parser.add_argument("--fit", default="unknown")
    parser.add_argument(
    "--other",
    action="append",
    default=[],
    help="Additional feature; repeatable",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--out", type=Path, help="Optional JSON output (ignored data/ recommended)")
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be a positive integer")
    if args.query and any(
        v != "unknown" for v in (args.category, args.color, args.fabric, args.fit)
    ):
        parser.error("Use either --query or individual attribute flags, not both")
    if args.query and args.other:
        parser.error("Use either --query or individual attribute flags, not both")

    listings = load_listings(args.listings, require_image=False)
    if args.query is not None:
        keywords = args.query
        matches = rank_keywords(keywords, listings, top_k=args.top_k)
    else:
        edited = Attributes(
            category=args.category,
            color=args.color,
            fabric=args.fabric,
            fit=args.fit,
            others=args.other or None,
        )
        keywords = build_keywords(edited)
        matches = rank_edited_attributes(edited, listings, top_k=args.top_k)

    report = {
        "method": "keyword_overlap_v1",
        "query": keywords,
        "listings_scanned": len(listings),
        "score_definition": (
            "percentage of unique query tokens found in "
            "normalized listing metadata"),
        "results": [
            {
                "rank": rank,
                "id": match.listing["id"],
                "title": match.listing["title"],
                "coverage": match.coverage,
                "matched_terms": list(match.matched_terms),
            }
            for rank, match in enumerate(matches, start=1)
        ],
    }
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out is None:
        print(output)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
        print(f"Saved {len(matches)} matches to {args.out}")


if __name__ == "__main__":
    main()
