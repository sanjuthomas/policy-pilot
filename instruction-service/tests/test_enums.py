import pytest

from ilm.models.enums import is_valid_owning_lob


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("FICC", True),
        ("FX", True),
        ("DESK_RATES", True),
        ("DESK_CREDIT", True),
        ("DESK_A1", True),
        ("ficc", False),
        ("INVALID", False),
        ("DESK_", False),
        ("DESK_lowercase", False),
        ("", False),
    ],
)
def test_is_valid_owning_lob(value: str, expected: bool) -> None:
    assert is_valid_owning_lob(value) is expected
