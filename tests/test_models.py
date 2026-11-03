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


def _signal_quality():
    return ResultItem(
        id="3",
        startTime="0.5",
        endTime="1.5",
        task="signal_quality",
        level="utterance",
        outputs={
            "snr": {"prediction": [{"score": "0.81"}]},
            "overall": {"prediction": [{"score": "0.77"}]},
        },
    )


def test_grouped_task_keeps_its_outputs():
    item = _signal_quality()
    assert item.prediction is None
    assert item.outputs["snr"].prediction[0].score == "0.81"
    assert item.model_dump()["outputs"] == {
        "snr": {"prediction": [{"score": "0.81"}]},
        "overall": {"prediction": [{"score": "0.77"}]},
    }


def test_flatten_outputs_gives_one_item_per_output():
    rows = _signal_quality().flatten_outputs()
    assert [(row.task, row.id, row.st, row.prediction[0].score) for row in rows] == [
        ("signal_quality.snr", "3", 0.5, "0.81"),
        ("signal_quality.overall", "3", 0.5, "0.77"),
    ]
    assert all(row.outputs is None for row in rows)


def test_flatten_outputs_keeps_other_items():
    item = ResultItem(task="emotion", finalLabel="sad")
    assert item.flatten_outputs() == [item]


def test_empty_outputs_are_dropped():
    assert ResultItem(task="emotion", outputs={}).outputs is None
