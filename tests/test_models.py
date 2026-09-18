import pytest

from behavioralsignals.models import ResultItem, ProcessItem, ProcessListResponse


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


def test_process_list_can_be_used_like_a_list():
    response = ProcessListResponse(processes=[ProcessItem(pid=7), ProcessItem(pid=8)])
    assert [process.pid for process in response] == [7, 8]
    assert len(response) == 2
    assert response[0].pid == 7


def test_process_list_still_serializes_its_own_fields():
    response = ProcessListResponse(processes=[ProcessItem(pid=7)])
    dump = response.model_dump()
    assert dump["total_count"] == 1
    assert [process["pid"] for process in dump["processes"]] == [7]
