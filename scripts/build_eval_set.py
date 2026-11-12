"""Draw the dataset half of the S1-11 evaluation set (docs/EVALUATION.md -> S1-11 evaluation set).

Reads the test-split pool that `scripts/ingest.py --split test` saved to data/eval/dataset/
(never the train listings the search index uses), draws 30 outerwear photos with seed 451
stratified by garment type, and adds rows to eval/queries.csv, eval/labels.csv, and
eval/dataset_source.csv. Rows already in those files, including Member D's own photos and
anything already labeled, are left alone. Nothing is downloaded.

Run from the repository root:
    python scripts/ingest.py --split test --limit 300   # once, to fetch the pool
    python scripts/build_eval_set.py
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.data.eval_set import (  # noqa: E402
    COUNT,
    EVAL_LISTINGS,
    SEED,
    EvalSetPaths,
    build,
    check_pool,
)
from backend.app.data.local_dataset import load_listings  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listings", type=Path, default=EVAL_LISTINGS, help="Test-split pool")
    parser.add_argument("--count", type=int, default=COUNT)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    check_pool(args.listings)
    if not args.listings.is_file():
        raise SystemExit(
            f"{args.listings} not found; run: python scripts/ingest.py --split test --limit 300"
        )
    listings = load_listings(args.listings)  # also checks every listed photo exists
    result = build(
        listings, EvalSetPaths(eval_dir=PROJECT_ROOT / "eval"), count=args.count, seed=args.seed
    )

    print(f"Pool in {args.listings}: {sum(result.pool_sizes.values())} photos")
    for name, size in result.pool_sizes.items():
        print(f"  {name}: {size}")
    print(f"Drew {len(result.chosen)} with seed {args.seed}: test rows {result.chosen}")
    for name, added in result.added.items():
        print(f"Rows added to eval/{'dataset_source' if name == 'source' else name}.csv: {added}")

    # The importer drops duplicates within the test split; also warn if a drawn photo is
    # byte-identical to a search listing (both are saved with the same preprocessing).
    search_images = PROJECT_ROOT / "data" / "images"
    if search_images.is_dir():
        indexed = {_sha256(p) for p in search_images.glob("*.jpg")}
        drawn = {int(r["source_index"]): r for r in listings}
        clashes = [
            drawn[row]["image_path"]
            for row in result.chosen
            if _sha256(PROJECT_ROOT / drawn[row]["image_path"]) in indexed
        ]
        if clashes:
            print(f"WARNING: identical to a search listing photo: {clashes}")


if __name__ == "__main__":
    main()
