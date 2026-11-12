"""Tests for the S1-11 evaluation-set builder (offline: fake test-split listing records)."""

from __future__ import annotations

import csv

import pytest

from backend.app.data.eval_set import (
    EXCLUDED_FIELDS,
    LABEL_FIELDS,
    QUERY_FIELDS,
    EvalSetPaths,
    apply_exclusions,
    build,
    check_pool,
    dataset_labels,
    draw,
    load_exclusions,
    merge_rows,
    replacement_order,
    stratified_quotas,
)
from backend.app.data.local_dataset import DEFAULT_LISTINGS

# The pool `scripts/ingest.py --split test` saved on Nov 12, 2026: 212 eligible photos minus
# one exact duplicate (a Blazer).
TEST_POOL = {
    "Jacket": 114,
    "Blazer": 40,
    "Vest": 37,
    "Winter Jacket": 15,
    "Rain Jacket": 3,
    "Denim Jacket": 2,
}

OWN_QUERY = {
    "query_id": "own-01", "source": "own", "split": "", "row_index": "",
    "file": "jacket1-flat.JPG", "edit_attribute": "others", "edit_from": "hood",
    "edit_to": "none", "seed": "",
}  # fmt: skip
OWN_LABEL = {
    "image": "../samples/jacket1-flat.JPG", "category": "windbreaker", "color": "pink",
    "fabric": "polyester", "fit": "regular fit", "others": "hood;zipper",
}  # fmt: skip


def _listing(row: int, garment_type: str) -> dict:
    """A record shaped like data/eval/dataset/listings.jsonl."""
    return {
        "id": f"secondhand-{row:06d}",
        "source_index": row,
        "image_path": f"data/eval/dataset/images/secondhand-{row:06d}.jpg",
        "attributes": {
            "type": garment_type,
            "colors": ["Black"],
            "material": "100% Wool",
            "cut": "['Regular']",
            "pattern": None,
        },
    }


def _fake_pool() -> list[dict]:
    types = [t for t, n in TEST_POOL.items() for _ in range(n)]
    types = types[::2] + types[1::2]  # don't group row indices by type
    return [_listing(59 + 15 * i, t) for i, t in enumerate(types)]


def _write(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def paths(tmp_path):
    return EvalSetPaths(eval_dir=tmp_path / "eval")


def test_quotas_match_the_documented_split():
    assert stratified_quotas(TEST_POOL, 30) == {
        "Jacket": 16,
        "Blazer": 6,
        "Vest": 5,
        "Winter Jacket": 2,
        "Rain Jacket": 1,
        "Denim Jacket": 0,
    }
    # The duplicate the importer dropped doesn't change the split: same with 41 blazers.
    assert stratified_quotas({**TEST_POOL, "Blazer": 41}, 30) == stratified_quotas(TEST_POOL, 30)


def test_quotas_reject_impossible_counts():
    with pytest.raises(ValueError):
        stratified_quotas({"Jacket": 3}, 4)
    with pytest.raises(ValueError):
        stratified_quotas({"Jacket": 3}, 0)


def test_draw_is_reproducible_and_follows_the_quotas():
    pool = {i: t for i, t in enumerate(t for t, n in TEST_POOL.items() for _ in range(n))}
    first = draw(pool, 30, 451)
    assert first == draw(pool, 30, 451)
    assert len(set(first)) == 30
    assert draw(pool, 30, 452) != first
    drawn_types = [pool[i] for i in first]
    assert {t: drawn_types.count(t) for t in set(drawn_types)} == {
        t: n for t, n in stratified_quotas(TEST_POOL, 30).items() if n
    }


def test_search_listings_are_refused_as_a_query_pool():
    with pytest.raises(ValueError, match="train"):
        check_pool(DEFAULT_LISTINGS)


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        (
            {"type": "Rain Jacket", "colors": ["Grey"], "material": "100% Polyester",
             "cut": "['Regular']"},
            {"category": "raincoat", "color": "gray", "fabric": "polyester", "fit": "regular fit"},
        ),
        (
            {"type": "Winter Jacket", "colors": ["Black", "White"],
             "material": "34%polyester 66%viscose", "cut": []},
            {"category": "", "color": "", "fabric": "", "fit": ""},
        ),
        (
            {"type": "Blazer", "colors": ["Beige"], "material": "wool", "cut": None},
            {"category": "blazer", "color": "tan", "fabric": "wool", "fit": ""},
        ),
    ],
)  # fmt: skip
def test_dataset_labels_map_to_vocabulary_or_stay_blank(attributes, expected):
    assert dataset_labels(attributes) == {**expected, "others": ""}


def test_merge_rows_keeps_existing_rows_and_is_idempotent(tmp_path):
    path = tmp_path / "queries.csv"
    _write(path, QUERY_FIELDS, [OWN_QUERY])
    new = {**OWN_QUERY, "query_id": "ds-01", "source": "dataset"}
    assert merge_rows(path, QUERY_FIELDS, [new], "query_id") == 1
    assert merge_rows(path, QUERY_FIELDS, [new], "query_id") == 0
    assert _read(path) == [OWN_QUERY, new]


def test_merge_rows_leaves_existing_bytes_untouched(tmp_path):
    # Hand-edited like Member D's file: LF endings, a short row, no newline at the end.
    original = (
        "query_id,source,split,row_index,file,edit_attribute,edit_from,edit_to,seed\n"
        "own-01,own,,,jacket1-flat.JPG,others,hood,none"
    )
    path = tmp_path / "queries.csv"
    path.write_text(original, encoding="utf-8", newline="")
    new = {**OWN_QUERY, "query_id": "ds-01", "source": "dataset", "seed": "451"}
    assert merge_rows(path, QUERY_FIELDS, [new], "query_id") == 1
    text = path.read_bytes().decode("utf-8")
    assert text.startswith(original + "\n")
    assert "\r" not in text
    assert text.endswith("ds-01,dataset,,,jacket1-flat.JPG,others,hood,none,451\n")


def test_merge_rows_refuses_a_different_header(tmp_path):
    path = tmp_path / "labels.csv"
    _write(path, ["image", "category"], [{"image": "a", "category": "coat"}])
    with pytest.raises(ValueError, match="columns"):
        merge_rows(path, LABEL_FIELDS, [], "image")


def test_build_end_to_end_keeps_own_rows_and_member_d_edits(paths):
    _write(paths.queries, QUERY_FIELDS, [OWN_QUERY])
    _write(paths.labels, LABEL_FIELDS, [OWN_LABEL])

    result = build(_fake_pool(), paths)
    assert result.pool_sizes == dict(sorted(TEST_POOL.items()))
    assert len(result.chosen) == 30
    assert result.added == {"queries": 30, "labels": 30, "source": 30}

    queries, labels, sources = _read(paths.queries), _read(paths.labels), _read(paths.source)
    assert queries[0] == OWN_QUERY and labels[0] == OWN_LABEL
    first = queries[1]
    row = int(first["row_index"])
    assert first["query_id"] == "ds-01" and first["split"] == "test" and first["seed"] == "451"
    assert row == result.chosen[0]
    assert first["file"] == f"images/secondhand-{row:06d}.jpg"
    assert labels[1]["image"] == f"../data/eval/dataset/images/secondhand-{row:06d}.jpg"
    assert labels[1]["color"] == "black" and labels[1]["fabric"] == "wool"
    assert labels[1]["fit"] == "regular fit" and labels[1]["others"] == ""
    assert sources[0]["colors"] == "Black" and sources[0]["row_index"] == str(row)

    # Member D fills in an edit, then the script is run again: nothing is overwritten.
    queries[1].update(edit_attribute="color", edit_from="black", edit_to="brown")
    _write(paths.queries, QUERY_FIELDS, queries)
    again = build(_fake_pool(), paths)
    assert again.chosen == result.chosen
    assert again.added == {"queries": 0, "labels": 0, "source": 0}
    assert _read(paths.queries)[1]["edit_to"] == "brown"


def test_build_refuses_a_different_draw_over_existing_rows(paths):
    build(_fake_pool(), paths)
    with pytest.raises(ValueError, match="original seed"):
        build(_fake_pool(), paths, seed=7)


def test_build_ignores_non_outerwear_records(paths):
    pool = _fake_pool() + [_listing(9000 + i, "T-shirt") for i in range(40)]
    result = build(pool, paths)
    assert "T-shirt" not in result.pool_sizes
    assert all(row < 9000 for row in result.chosen)


def _pool():
    return {int(r["source_index"]): r["attributes"]["type"] for r in _fake_pool()}


def test_replacement_order_is_seeded_per_type_and_independent_of_the_draw():
    pool = _pool()
    blazers = replacement_order(pool, "Blazer", 451)
    assert blazers == replacement_order(pool, "Blazer", 451)
    assert sorted(blazers) == sorted(r for r, t in pool.items() if t == "Blazer")
    assert blazers != replacement_order(pool, "Blazer", 452)
    # Computing replacements never touches the main draw's random stream.
    before = draw(pool, 30, 451)
    replacement_order(pool, "Jacket", 451)
    assert draw(pool, 30, 451) == before


def test_apply_exclusions_swaps_same_type_rows_only():
    pool = _pool()
    chosen = draw(pool, 30, 451)
    blazer = next(r for r in chosen if pool[r] == "Blazer")
    jacket = next(r for r in chosen if pool[r] == "Jacket")
    replacements, unused = apply_exclusions(pool, chosen, {blazer, jacket}, 451)
    assert set(replacements) == {blazer, jacket}
    assert pool[replacements[blazer]] == "Blazer" and pool[replacements[jacket]] == "Jacket"
    assert not set(replacements.values()) & set(chosen)
    assert unused == []


def test_excluding_a_replacement_moves_on_to_the_next_row():
    pool = _pool()
    chosen = draw(pool, 30, 451)
    blazer = next(r for r in chosen if pool[r] == "Blazer")
    first, _ = apply_exclusions(pool, chosen, {blazer}, 451)
    second, unused = apply_exclusions(pool, chosen, {blazer, first[blazer]}, 451)
    assert second[blazer] != first[blazer] and pool[second[blazer]] == "Blazer"
    assert unused == [first[blazer]]  # excluded, but never drawn: only skipped


def test_apply_exclusions_fails_when_a_type_runs_out():
    pool = {1: "Rain Jacket", 2: "Rain Jacket", 3: "Jacket"}
    with pytest.raises(ValueError, match="No Rain Jacket left"):
        apply_exclusions(pool, [1, 2], {1}, 451)


def test_load_exclusions(tmp_path):
    path = tmp_path / "excluded.csv"
    assert load_exclusions(path) == {}
    _write(path, EXCLUDED_FIELDS, [{"query_id": "ds-02", "row_index": "346", "reason": "blouse"}])
    assert load_exclusions(path) == {346: "blouse"}
    _write(path, ["row_index"], [{"row_index": "346"}])
    with pytest.raises(ValueError, match="columns"):
        load_exclusions(path)


def test_build_swaps_excluded_rows_in_place_and_keeps_everything_else(paths):
    _write(paths.queries, QUERY_FIELDS, [OWN_QUERY])
    _write(paths.labels, LABEL_FIELDS, [OWN_LABEL])
    first = build(_fake_pool(), paths)
    # Member D labels and edits every row, then finds ds-03 unusable.
    queries = _read(paths.queries)
    for row in queries[1:]:
        row.update(edit_attribute="color", edit_from="black", edit_to="brown")
    _write(paths.queries, QUERY_FIELDS, queries)
    before = {
        p: p.read_text(encoding="utf-8").splitlines()
        for p in (paths.queries, paths.labels, paths.source)
    }
    excluded_row = first.chosen[2]
    _write(
        paths.excluded,
        EXCLUDED_FIELDS,
        [{"query_id": "ds-03", "row_index": str(excluded_row), "reason": "not outerwear"}],
    )

    result = build(_fake_pool(), paths)
    new_row = result.replaced["ds-03"][1]
    assert result.replaced == {"ds-03": (excluded_row, new_row)}
    assert result.chosen == first.chosen and result.final[2] == new_row
    assert result.swapped_rows == 3 and result.added == {"queries": 0, "labels": 0, "source": 0}

    for path, old_lines in before.items():
        new_lines = path.read_text(encoding="utf-8").splitlines()
        assert len(new_lines) == len(old_lines)
        changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines, strict=True)) if a != b]
        assert len(changed) == 1  # only the ds-03 line
    swapped = _read(paths.queries)[3]
    assert swapped["query_id"] == "ds-03" and swapped["row_index"] == str(new_row)
    assert swapped["edit_attribute"] == ""  # the old photo's edit is dropped
    assert _read(paths.queries)[4]["edit_to"] == "brown"  # other edits kept
    assert _read(paths.labels)[3]["image"].endswith(f"secondhand-{new_row:06d}.jpg")

    # Running again changes nothing.
    again = build(_fake_pool(), paths)
    assert again.swapped_rows == 0 and again.final == result.final
