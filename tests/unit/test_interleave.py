import pytest

from caching_service.services.interleave import interleave


def test_alternates_items_starting_with_first_list() -> None:
    assert interleave(["a1", "a2", "a3"], ["b1", "b2", "b3"]) == [
        "a1",
        "b1",
        "a2",
        "b2",
        "a3",
        "b3",
    ]


def test_empty_lists_give_empty_result() -> None:
    assert interleave([], []) == []


def test_different_lengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="same length"):
        interleave(["a"], ["b", "c"])
