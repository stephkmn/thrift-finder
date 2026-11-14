"""Unit tests for evaluation scoring (S3-2): no model, just labels and rankings."""

from __future__ import annotations

import pytest

from backend.app.ml import evaluation as ev
from backend.app.schemas import Attributes

PREDICTED = Attributes(
    category="jacket", color="black", fabric="denim", fit="regular fit", others=["hood", "zipper"]
)


def _query(edit_attribute="color", edit_from="black", edit_to="brown", category="jacket", **labels):
    return ev.EvalQuery(
        query_id="ds-01",
        source="dataset",
        image_path=ev.EVAL_DIR / "x.jpg",
        labels={
            "category": category,
            "color": labels.get("color", "black"),
            "fabric": labels.get("fabric"),
            "fit": labels.get("fit", "regular fit"),
            "others": labels.get("others", {"hood"}),
        },
        edit_attribute=edit_attribute,
        edit_from=edit_from,
        edit_to=edit_to,
    )


def _listing(garment="Jacket", colors=("Brown",), material=None, cut=None):
    return {
        "id": "x",
        "title": "t",
        "attributes": {"type": garment, "colors": list(colors), "material": material, "cut": cut},
    }


def test_apply_edit_changes_a_scalar():
    assert ev.apply_edit(PREDICTED, _query()).color == "brown"


@pytest.mark.parametrize(
    ("edit_from", "edit_to", "expected"),
    [("hood", "none", ["zipper"]), ("none", "striped", ["hood", "zipper", "striped"])],
)
def test_apply_edit_adds_or_removes_a_feature(edit_from, edit_to, expected):
    query = _query("others", edit_from, edit_to)
    assert ev.apply_edit(PREDICTED, query).others == expected


def test_removing_the_last_feature_gives_null():
    single = PREDICTED.model_copy(update={"others": ["hood"]})
    assert ev.apply_edit(single, _query("others", "hood", "none")).others is None


def test_type_matches_uses_the_dataset_type_families():
    assert ev.type_matches(_listing("Blazer"), "blazer")
    assert ev.type_matches(_listing("Jacket"), "blazer")  # the dataset files blazers as Jacket too
    assert not ev.type_matches(_listing("Vest"), "blazer")
    assert ev.type_matches(_listing("Winter Jacket"), "coat")
    assert not ev.type_matches(_listing("Blazer"), "puffer jacket")


def test_edit_satisfied_reads_mapped_listing_labels():
    assert ev.edit_satisfied(_listing(colors=["Grey"]), "color", "gray") is True
    assert ev.edit_satisfied(_listing(colors=[]), "color", "gray") is None
    # The dataset has no navy label: a Blue listing counts for a navy edit, not the reverse.
    assert ev.edit_satisfied(_listing(colors=["Blue"]), "color", "navy") is True
    assert ev.edit_satisfied(_listing(colors=["Navy"]), "color", "blue") is False
    assert ev.edit_satisfied(_listing(material="100% bomull"), "fabric", "cotton") is True
    assert ev.edit_satisfied(_listing(cut="['Cropped']"), "fit", "cropped") is True
    assert ev.edit_satisfied(_listing(), "others", "hood") is None


def test_score_ranking_counts_missing_slots_as_misses():
    results = [_listing(colors=["Brown"]), _listing(colors=["Black"]), _listing("Vest")]
    score = ev.score_ranking(results, _query(), k=10)
    assert score.type_match == pytest.approx(0.2)
    assert score.edit_satisfaction == pytest.approx(2 / 3)  # the vest is brown too
    assert score.precision == pytest.approx(0.1)  # only the brown jacket is both


def test_feature_edits_are_not_scored():
    score = ev.score_ranking([_listing()], _query("others", "hood", "none"), k=10)
    assert score.edit_satisfaction is None and score.precision is None
    assert score.type_match == pytest.approx(0.1)


def test_score_extraction_skips_unlabeled_attributes():
    score = ev.score_extraction(PREDICTED, _query(fabric=None, others={"hood", "belt"}))
    assert score.correct == {"category": True, "color": True, "fit": True}
    assert (score.true_pos, score.false_pos, score.false_neg) == (1, 1, 1)
    assert ev.precision_recall_f1([score]) == (0.5, 0.5, 0.5)


def test_unknown_others_label_is_not_counted():
    score = ev.score_extraction(PREDICTED, _query(others=None))
    assert (score.true_pos, score.false_pos, score.false_neg) == (0, 0, 0)
    assert ev.precision_recall_f1([score]) == (None, None, None)


def test_load_eval_set_joins_queries_and_labels(tmp_path):
    (tmp_path / "queries.csv").write_text(
        "query_id,source,split,row_index,file,edit_attribute,edit_from,edit_to,seed\n"
        "ds-01,dataset,test,275,images/a.jpg,others,hood,none,451\n",
        encoding="utf-8",
    )
    (tmp_path / "labels.csv").write_text(
        "image,category,color,fabric,fit,others\n../data/a.jpg,parka,olive,,regular fit,hood\n",
        encoding="utf-8",
    )
    [query] = ev.load_eval_set(tmp_path / "queries.csv", tmp_path / "labels.csv")
    assert query.labels == {
        "category": "parka",
        "color": "olive",
        "fabric": None,
        "fit": "regular fit",
        "others": {"hood"},
    }
    assert query.image_path == (tmp_path.parent / "data" / "a.jpg").resolve()
    assert (query.edit_attribute, query.edit_to) == ("others", "none")
