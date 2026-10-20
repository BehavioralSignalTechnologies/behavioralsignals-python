import importlib

import pytest

from behavioralsignals import focus
from behavioralsignals.focus import OUTPUTS, CONTEXTS
from behavioralsignals.models import ResultResponse


FOCUS_MODULE = importlib.import_module("behavioralsignals.focus")


def _utterance(uid, start, end, speaker="SPEAKER_00", angry=0.1, hesitation=0.1, text="hello"):
    """The rows the API returns for one utterance, as dicts."""
    neutral = round(1 - angry - 0.05, 3)
    emotion = max(
        {"neutral": neutral, "angry": angry}, key=lambda k: {"neutral": neutral, "angry": angry}[k]
    )
    common = {"id": uid, "startTime": str(start), "endTime": str(end), "level": "utterance"}
    return [
        {
            **common,
            "task": "diarization",
            "prediction": [{"label": speaker}],
            "finalLabel": speaker,
        },
        {**common, "task": "asr", "prediction": [{"label": text}], "finalLabel": f" {text}"},
        {
            **common,
            "task": "emotion",
            "prediction": [
                {"label": "neutral", "posterior": str(neutral)},
                {"label": "angry", "posterior": str(angry)},
                {"label": "happy", "posterior": "0.03"},
                {"label": "sad", "posterior": "0.02"},
            ],
            "finalLabel": emotion,
        },
        {
            **common,
            "task": "hesitation",
            "prediction": [
                {"label": "no", "posterior": str(round(1 - hesitation, 3))},
                {"label": "yes", "posterior": str(hesitation)},
            ],
            "finalLabel": "yes" if hesitation > 0.5 else "no",
        },
    ]


def _results(*utterances):
    return [row for u in utterances for row in u]


def test_close_call_hidden_by_neutral_is_detected():
    results = _results(_utterance("0", 0, 4, angry=0.4), _utterance("1", 5, 9, angry=0.05))

    out = focus(results, ["angry"])

    first, second = out.utterances
    assert first.scores["angry"] == pytest.approx(0.4)
    assert first.labels["emotion"] == "neutral"
    assert first.detected == ["angry"]
    assert first.hidden_by_neutral == ["angry"]
    assert second.detected == []
    assert first.text == "hello"
    assert first.speaker == "SPEAKER_00"


def test_label_already_angry_is_detected_but_not_hidden():
    out = focus(_results(_utterance("0", 0, 4, angry=0.8)), ["angry"])

    assert out.utterances[0].detected == ["angry"]
    assert out.utterances[0].hidden_by_neutral == []


def test_context_and_overrides_set_thresholds():
    results = _results(_utterance("0", 0, 4, angry=0.27))

    assert focus(results, ["angry"]).utterances[0].detected == []
    assert focus(results, ["angry"], context="car").utterances[0].detected == ["angry"]
    strict = focus(results, ["angry"], context="car", thresholds={"anger": 0.5})
    assert strict.thresholds == {"angry": 0.5}
    assert strict.utterances[0].detected == []


def test_above_the_speakers_own_average():
    results = _results(
        _utterance("0", 0, 4, angry=0.05),
        _utterance("1", 5, 9, angry=0.05),
        _utterance("2", 10, 14, angry=0.29),
        _utterance("3", 15, 19, speaker="SPEAKER_01", angry=0.29),
    )

    out = focus(results, ["angry"])

    raised = {u.id: u.above_baseline for u in out.utterances}
    assert raised == {"0": [], "1": [], "2": ["angry"], "3": []}  # SPEAKER_01 has no baseline


def test_episodes_merge_close_utterances_per_speaker():
    results = _results(
        _utterance("0", 0, 4, angry=0.4),
        _utterance("1", 5, 9, angry=0.6),
        _utterance("2", 20, 24, angry=0.5),
        _utterance("3", 5, 8, speaker="SPEAKER_01", angry=0.45),
    )

    events = focus(results, ["angry"]).events

    spans = [(e.speaker, e.start, e.end, e.peak, e.utterance_ids) for e in events]
    assert spans == [
        ("SPEAKER_00", 0.0, 9.0, 0.6, ["0", "1"]),
        ("SPEAKER_01", 5.0, 8.0, 0.45, ["3"]),
        ("SPEAKER_00", 20.0, 24.0, 0.5, ["2"]),
    ]


def test_summary_in_plain_words():
    results = _results(_utterance("0", 61, 65, angry=0.4, hesitation=0.05), _utterance("1", 70, 74))

    text = focus(results, ["angry", "hesitation"]).summary()

    assert text.splitlines() == [
        (
            "angry (emotion, probability >= 0.30): 1 of 2 utterances, 1 of them labeled neutral "
            "by the API. 1 well above the speaker's own average. Strongest: SPEAKER_00 1:01-1:05 "
            "(peak 0.40)."
        ),
        "hesitation (hesitation, probability >= 0.35): 0 of 2 utterances.",
    ]


def test_accepts_a_result_response_and_skips_short_utterances():
    short = {"id": "9", "startTime": "30", "endTime": "30.8", "task": "asr", "finalLabel": "ok"}
    response = ResultResponse.model_validate(
        {"pid": 1, "results": _results(_utterance("0", 0, 4, angry=0.4)) + [short]}
    )

    out = focus(response, ["Angry"])

    assert [u.id for u in out.utterances] == ["0"]


def test_unknown_names_are_rejected():
    results = _results(_utterance("0", 0, 4))
    with pytest.raises(ValueError, match="Unknown output"):
        focus(results, ["deception"])
    with pytest.raises(ValueError, match="Unknown context"):
        focus(results, ["angry"], context="hospital")
    with pytest.raises(ValueError, match="at least one output"):
        focus(results, [])


def test_output_missing_from_an_utterance_is_not_scored():
    results = _results(_utterance("0", 0, 4, angry=0.4))

    out = focus(results, ["angry", "negative"])

    assert out.utterances[0].scores == {"angry": 0.4}
    assert "negative (positivity" in out.summary()


def test_hesitation_has_its_own_threshold():
    results = _results(_utterance("0", 0, 4, hesitation=0.32))

    out = focus(results, ["hesitation"])

    assert out.thresholds == {"hesitation": 0.35}
    assert out.utterances[0].detected == []
    assert focus(results, ["hesitation"], context="car").utterances[0].detected == ["hesitation"]


def test_negative_tone_uses_angry_and_sad_and_names_the_tone():
    positivity = [
        {
            "id": uid,
            "startTime": st,
            "endTime": et,
            "task": "positivity",
            "finalLabel": "neutral",
            "prediction": [
                {"label": "neutral", "posterior": "0.9"},
                {"label": "negative", "posterior": "0.1"},
            ],
        }
        for uid, st, et in (("0", "0", "4"), ("1", "5", "9"))
    ]
    results = _results(_utterance("0", 0, 4, angry=0.25), _utterance("1", 5, 9, angry=0.05))

    out = focus(results + positivity, ["negative_tone"])

    first, second = out.utterances
    assert first.scores["negative_tone"] == pytest.approx(0.27)  # angry 0.25 + sad 0.02
    assert first.detected == ["negative_tone"]
    assert first.hidden_by_neutral == ["negative_tone"]
    assert first.tone == "heated"  # no strength rows: strong and weak tie at 0
    assert second.scores["negative_tone"] == pytest.approx(0.1)  # positivity wins: 0.1 > 0.07
    assert second.detected == []
    assert second.tone is None


def test_result_rows_add_negative_tone_in_the_api_format():
    results = _results(_utterance("0", 0, 4, angry=0.3), _utterance("1", 5, 9, angry=0.05))

    rows = focus(results, ["negative_tone", "angry"]).result_rows()

    assert [(r["id"], r["task"], r["finalLabel"], r.get("tone"), r["source"]) for r in rows] == [
        ("0", "negative_tone", "negative", "heated", "focus"),
        ("1", "negative_tone", "neutral", None, "focus"),
    ]
    assert rows[0]["prediction"] == [{"label": "negative", "posterior": "0.3200"}]
    assert rows[0]["startTime"] == "0.000"
    assert rows[0]["threshold"] == pytest.approx(0.2)
    assert focus(results, ["angry"]).result_rows() == []


def _fake_words_model(monkeypatch, negative_by_text):
    """Stands in for the text model: negative probability by text, the rest neutral."""

    def model(texts):
        return [
            [
                {"label": "negative", "score": negative_by_text.get(t, 0.1)},
                {"label": "neutral", "score": 1 - negative_by_text.get(t, 0.1)},
            ]
            for t in texts
        ]

    monkeypatch.setattr(FOCUS_MODULE, "_words_model", lambda: model)


def test_negative_words_reads_the_transcript_including_short_replies(monkeypatch):
    _fake_words_model(monkeypatch, {"I want to quit": 0.92, "Terrible.": 0.87})
    positivity = {
        "id": "0",
        "startTime": "0",
        "endTime": "4",
        "task": "positivity",
        "finalLabel": "neutral",
        "prediction": [
            {"label": "neutral", "posterior": "0.95"},
            {"label": "negative", "posterior": "0.05"},
        ],
    }
    short = [
        {"id": "9", "startTime": "5", "endTime": "5.8", "task": "asr", "finalLabel": " Terrible."},
        {
            "id": "9",
            "startTime": "5",
            "endTime": "5.8",
            "task": "diarization",
            "finalLabel": "SPEAKER_00",
        },
    ]
    results = _results(_utterance("0", 0, 4, text="I want to quit")) + [positivity] + short

    out = focus(results, ["negative_words"])

    first, reply = out.utterances
    assert first.scores == {"negative_words": pytest.approx(0.92)}
    assert first.hidden_by_neutral == ["negative_words"]
    assert reply.id == "9" and reply.detected == ["negative_words"]
    assert reply.hidden_by_neutral == []  # the API gave the short reply no label at all
    assert out.thresholds == {"negative_words": 0.45}
    assert [(r["id"], r["task"], r["finalLabel"]) for r in out.result_rows()] == [
        ("0", "negative_words", "negative"),
        ("9", "negative_words", "negative"),
    ]
    assert out.summary().startswith("negative_words (words, probability >= 0.45): 2 of 2")


def test_positive_words_scores_the_same_transcript_alongside_negative_words(monkeypatch):
    def model(texts):
        return [
            [
                {"label": "positive", "score": 0.9},
                {"label": "neutral", "score": 0.08},
                {"label": "negative", "score": 0.02},
            ]
            for _ in texts
        ]

    monkeypatch.setattr(FOCUS_MODULE, "_words_model", lambda: model)
    results = _results(_utterance("0", 0, 4, text="This is so much better!"))

    out = focus(results, ["positive_words", "negative_words"])

    (u,) = out.utterances
    assert u.scores == {"positive_words": pytest.approx(0.9), "negative_words": pytest.approx(0.02)}
    assert u.detected == ["positive_words"]
    assert out.thresholds == {"positive_words": 0.45, "negative_words": 0.45}
    assert [
        (r["task"], r["finalLabel"], r["prediction"][0]["label"]) for r in out.result_rows()
    ] == [
        ("negative_words", "neutral", "negative"),
        ("positive_words", "positive", "positive"),
    ]
    assert out.summary().startswith("positive_words (words, probability >= 0.45): 1 of 1")


def test_negative_words_without_the_extra_says_how_to_install(monkeypatch):
    def missing(name):
        raise ImportError(name)

    FOCUS_MODULE._words_model.cache_clear()
    monkeypatch.setattr(FOCUS_MODULE.importlib, "import_module", missing)
    with pytest.raises(ImportError, match="behavioralsignals\\[words\\]"):
        focus(_results(_utterance("0", 0, 4)), ["negative_words"])
    FOCUS_MODULE._words_model.cache_clear()
    assert FOCUS_MODULE._words_scores([]) == []


def test_every_context_has_sane_values():
    for preset in CONTEXTS.values():
        assert 0 < preset.threshold < 1
        assert all(o in OUTPUTS and 0 < t < 1 for o, t in preset.per_output.items())
        assert 0 < preset.baseline_margin < 1
        assert preset.max_gap >= 0


def _as_segment(rows):
    return [{**r, "level": "segment"} for r in rows]


def test_streaming_segments_with_the_same_id_do_not_mix_with_utterances():
    segment = _as_segment(_utterance("1", 0.0, 2.0, angry=0.9))
    utterance = _utterance("1", 0.0, 8.0, angry=0.05)

    view = focus(segment + utterance, ["angry"])

    assert [(u.id, u.level, u.start, u.end) for u in view.utterances] == [
        ("1", "utterance", 0.0, 8.0)
    ]
    assert view.utterances[0].scores["angry"] == pytest.approx(0.05)


def test_segment_only_results_are_scored_and_keep_their_level():
    rows = _as_segment(_utterance("3", 0.0, 2.0, angry=0.9)) + _as_segment(
        _utterance("4", 2.0, 4.0, angry=0.1)
    )

    view = focus(rows, ["angry", "negative_tone"])

    assert [(u.id, u.level, "angry" in u.detected) for u in view.utterances] == [
        ("3", "segment", True),
        ("4", "segment", False),
    ]
    assert {r["level"] for r in view.result_rows()} == {"segment"}
