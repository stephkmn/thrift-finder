
from backend.app.data.query_keywords import build_keywords
from backend.app.schemas import Attributes


def test_edited_color_replaces_original_color():
    edited = Attributes(
        category="jacket",
        color="brown",
        fabric="denim",
        fit="regular",
    )

    assert build_keywords(edited) == "brown denim jacket regular"


def test_other_features_and_removed_features():
    edited = Attributes(
        category="coat",
        color="black",
        fabric="wool",
        fit="oversized",
        others=["zipper", "no hood"],
    )

    assert build_keywords(edited) == "black wool coat oversized zipper"


def test_duplicate_and_missing_attributes():
    edited = Attributes(
        category="jacket",
        color="unknown",
        fabric="denim",
        fit="N/A",
        others=["denim", "pockets", "POCKETS"],
    )

    assert build_keywords(edited) == "denim jacket pockets"
