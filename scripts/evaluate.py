"""Evaluate extraction and search on the S1-11 set (S3-2), with baselines (S3-3) and tuning (S3-1).

For each query photo: extract attributes, apply the query's intended edit, then search with
  - keyword:      Member B's keyword-only baseline on the edited attributes (no model)
  - image only:   the upload's embedding with no edit applied
  - image + edit: the full system (edit arithmetic + re-ranker)
Scores come from backend/app/ml/evaluation.py. Dataset and own photos are reported separately.

Usage:
    python scripts/evaluate.py
    python scripts/evaluate.py --sweep --out docs/eval_results.md --details data/eval/details.csv
    python scripts/evaluate.py --judging-sheet data/eval/judging.csv   # for team-judged P@10
    python scripts/evaluate.py --judged data/eval/judging.csv          # report team-judged P@10
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image

from backend.app.config import get_settings
from backend.app.data.keyword_baseline import rank_edited_attributes
from backend.app.ml import evaluation as ev
from backend.app.ml.attributes import SCALAR_NAMES, AttributeExtractor
from backend.app.ml.encoder import get_encoder
from backend.app.ml.index import DEFAULT_INDEX, load_index
from backend.app.ml.query import EDIT_STRENGTH, build_query
from backend.app.ml.rerank import WEIGHTS, rank

SYSTEMS = ("keyword", "image only", "image + edit")
SWEEP_STRENGTHS = (0.0, 0.5, 1.0, 1.5, 2.0)
SWEEP_WEIGHTS = ((0.5, 0.3, 0.2), (0.7, 0.2, 0.1), (0.3, 0.4, 0.3), (1.0, 0.0, 0.0))
GROUPS = ("dataset", "own", "all")


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _in_group(row: dict, group: str) -> bool:
    return group == "all" or row["query"].source == group


def _search(encoder, index, extraction, target, top_k, strength=EDIT_STRENGTH, weights=WEIGHTS):
    """Top-k listings for the upload searched with `target` attributes (no edit if unchanged)."""
    built = build_query(
        encoder, extraction.embedding, "image", extraction.attributes, target, strength=strength
    )
    return [match.listing for match in rank(built, index, top_k, weights)]


def run(args: argparse.Namespace) -> tuple[list[dict], dict]:
    settings = get_settings()
    encoder = get_encoder(args.model, settings.model_dtype)
    extractor = AttributeExtractor(encoder)
    index = load_index(args.model, args.index)
    queries = ev.load_eval_set(args.queries, args.labels)
    missing = [q.query_id for q in queries if not q.image_path.is_file()]
    if missing:
        print(f"Skipping {len(missing)} queries whose photo isn't on this machine: {missing}")

    rows, sweep = [], defaultdict(list)
    for query in (q for q in queries if q.image_path.is_file()):
        with Image.open(query.image_path) as image:
            started = time.perf_counter()
            extraction = extractor.extract(image=image)
            extract_ms = (time.perf_counter() - started) * 1000
        original = extraction.attributes
        edited = ev.apply_edit(original, query)

        started = time.perf_counter()
        results = {"image + edit": _search(encoder, index, extraction, edited, args.top_k)}
        search_ms = (time.perf_counter() - started) * 1000
        results["image only"] = _search(encoder, index, extraction, original, args.top_k)
        results["keyword"] = [
            m.listing for m in rank_edited_attributes(edited, index.listings, top_k=args.top_k)
        ]
        rows.append(
            {
                "query": query,
                "predicted": original,
                "extraction": ev.score_extraction(original, query),
                "results": results,
                "scores": {s: ev.score_ranking(results[s], query, args.top_k) for s in SYSTEMS},
                "extract_ms": extract_ms,
                "search_ms": search_ms,
            }
        )
        if args.sweep:
            for strength in SWEEP_STRENGTHS:
                for weights in SWEEP_WEIGHTS:
                    listings = _search(
                        encoder, index, extraction, edited, args.top_k, strength, weights
                    )
                    sweep[(strength, weights)].append(
                        (query, ev.score_ranking(listings, query, args.top_k))
                    )
        print(f"  {query.query_id}: done")
    return rows, sweep


def judged_precision(path: Path, k: int) -> dict[tuple[str, str], float]:
    """Team-judged P@k per (query_id, system) from a filled-in judging sheet."""
    hits: dict[tuple[str, str], int] = defaultdict(int)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["relevant"].strip().lower() in {"1", "y", "yes", "true"}:
                hits[(row["query_id"], row["system"])] += 1
    return {key: count / k for key, count in hits.items()}


def report(rows: list[dict], sweep: dict, args: argparse.Namespace) -> str:
    judged = judged_precision(args.judged, args.top_k) if args.judged else None
    lines = [f"Model: `{args.model}` · top {args.top_k} · {len(rows)} queries\n"]
    for group in GROUPS:
        group_rows = [r for r in rows if _in_group(r, group)]
        if not group_rows:
            continue
        lines += [f"### {group.capitalize()} photos ({len(group_rows)} queries)\n"]
        lines += ["| Attribute | n | Accuracy |", "|---|---|---|"]
        for name in SCALAR_NAMES:
            marks = [
                r["extraction"].correct[name] for r in group_rows if name in r["extraction"].correct
            ]
            if marks:
                lines.append(f"| {name} | {len(marks)} | {_pct(sum(marks) / len(marks))} |")
        precision, recall, f1 = ev.precision_recall_f1(r["extraction"] for r in group_rows)
        lines.append(
            f"| others P / R / F1 | {len(group_rows)} | "
            f"{_pct(precision)} / {_pct(recall)} / {_pct(f1)} |\n"
        )
        scored = [r for r in group_rows if r["query"].edit_attribute in ev.SCOREABLE_EDITS]
        header = "| System | Edit-satisfaction | Type match@10 | Auto P@10 |"
        divider = "|---|---|---|---|"
        if judged is not None:
            header, divider = header + " Team P@10 |", divider + "---|"
        lines += [
            f"Edit metrics over the {len(scored)} color/fabric/fit edits; "
            f"type match over all {len(group_rows)}.\n",
            header,
            divider,
        ]
        for system in SYSTEMS:
            cells = [
                _pct(ev.mean(r["scores"][system].edit_satisfaction for r in scored)),
                _pct(ev.mean(r["scores"][system].type_match for r in group_rows)),
                _pct(ev.mean(r["scores"][system].precision for r in scored)),
            ]
            if judged is not None:
                cells.append(
                    _pct(
                        ev.mean(judged.get((r["query"].query_id, system), 0.0) for r in group_rows)
                    )
                )
            lines.append(f"| {system} | " + " | ".join(cells) + " |")
        lines.append("")

    extract = statistics.median(r["extract_ms"] for r in rows)
    search = statistics.median(r["search_ms"] for r in rows)
    lines.append(
        f"Median latency ({get_settings().model_dtype}, CPU): extract {extract:.0f} ms, "
        f"search {search:.0f} ms.\n"
    )
    if sweep:
        lines += [
            "### Tuning sweep (image + edit, all photos)\n",
            "| λ | Weights (w1, w2, w3) | Edit-satisfaction | Type match@10 | Auto P@10 |",
            "|---|---|---|---|---|",
        ]
        for (strength, weights), results in sweep.items():
            scored = [s for q, s in results if q.edit_attribute in ev.SCOREABLE_EDITS]
            satisfaction = _pct(ev.mean(s.edit_satisfaction for s in scored))
            type_match = _pct(ev.mean(s.type_match for _, s in results))
            precision = _pct(ev.mean(s.precision for s in scored))
            lines.append(
                f"| {strength} | {weights} | {satisfaction} | {type_match} | {precision} |"
            )
    return "\n".join(lines) + "\n"


def write_details(rows: list[dict], path: Path) -> None:
    """One line per query and system, for the failure log."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "query_id",
                "source",
                "edit",
                "predicted",
                "system",
                "edit_satisfaction",
                "type_match",
                "auto_p_at_10",
                "top_titles",
            ]
        )
        for r in rows:
            q, p = r["query"], r["predicted"]
            predicted = f"{p.color} {p.fabric} {p.fit} {p.category} {p.others or []}"
            for system in SYSTEMS:
                s = r["scores"][system]
                titles = "; ".join(item["title"] for item in r["results"][system])
                writer.writerow(
                    [
                        q.query_id,
                        q.source,
                        f"{q.edit_attribute}: {q.edit_from} -> {q.edit_to}",
                        predicted,
                        system,
                        s.edit_satisfaction,
                        s.type_match,
                        s.precision,
                        titles,
                    ]
                )


def write_judging_sheet(rows: list[dict], path: Path) -> None:
    """Every (query, system, rank) result with an empty `relevant` column for the team to fill."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "query_id",
                "query_image",
                "edit",
                "system",
                "rank",
                "listing_id",
                "listing_image",
                "title",
                "relevant",
            ]
        )
        for r in rows:
            q = r["query"]
            for system in SYSTEMS:
                for position, item in enumerate(r["results"][system], start=1):
                    writer.writerow(
                        [
                            q.query_id,
                            q.image_path.name,
                            f"{q.edit_attribute}: {q.edit_to}",
                            system,
                            position,
                            item["id"],
                            item["image_path"],
                            item["title"],
                            "",
                        ]
                    )


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--queries", type=Path, default=ev.EVAL_DIR / "queries.csv")
    parser.add_argument("--labels", type=Path, default=ev.EVAL_DIR / "labels.csv")
    parser.add_argument("--model", default=settings.model_name)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--sweep", action="store_true", help="also try λ and weight settings")
    parser.add_argument("--out", type=Path, help="write the Markdown report here")
    parser.add_argument("--details", type=Path, help="write per-query results (CSV) here")
    parser.add_argument("--judging-sheet", type=Path, help="write a sheet for team P@10 here")
    parser.add_argument("--judged", type=Path, help="filled-in judging sheet to report")
    args = parser.parse_args()

    rows, sweep = run(args)
    text = report(rows, sweep, args)
    print("\n" + text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    if args.details:
        write_details(rows, args.details)
    if args.judging_sheet:
        write_judging_sheet(rows, args.judging_sheet)


if __name__ == "__main__":
    main()
