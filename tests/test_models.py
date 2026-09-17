import pytest

from behavioralsignals.models import ResultItem


def test_result_times_are_floats():
    item = ResultItem(task="emotion", startTime="0.209", endTime="7.681")
    assert (item.st, item.et) == pytest.approx((0.209, 7.681))
    assert item.model_dump()["st"] == pytest.approx(0.209)


def test_result_without_times_can_be_dumped():
    item = ResultItem(task="emotion")
    assert item.st is None and item.et is None
    assert item.model_dump() == {"task": "emotion"}


def test_result_with_empty_times_can_be_dumped():
    item = ResultItem(task="emotion", startTime="", endTime="")
    assert item.st is None and item.et is None
    assert item.model_dump() == {"task": "emotion", "startTime": "", "endTime": ""}
