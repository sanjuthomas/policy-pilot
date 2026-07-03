from __future__ import annotations

from etl.search_text.transforms import apply_transform, display_name, get_path


def test_get_path_nested_and_missing() -> None:
    doc = {"a": {"b": "value"}}
    assert get_path(doc, "a.b") == "value"
    assert get_path(doc, "a.c") is None
    assert get_path(doc, "x.y") is None


def test_display_name_variants() -> None:
    assert display_name(None) is None
    assert display_name({"user_id": "solo"}) == "solo"
    assert display_name({"user_id": "u1", "given_name": "A", "family_name": "B"}) == "B, A (u1)"


def test_apply_transform_join_list_and_default() -> None:
    assert apply_transform(["a", "", "b"], "join_list") == "a b"
    assert apply_transform([], "join_list") is None
    assert apply_transform("x", "join_list") == "x"
    assert apply_transform(["one", "two"], "default") == "one two"
    assert apply_transform("", "default") is None
    assert apply_transform({"user_id": "u1"}, "display_name") == "u1"
