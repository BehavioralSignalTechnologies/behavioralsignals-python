"""Focus behavioral results on the outputs you care about.

`finalLabel` keeps only the top label, so an utterance that is 55% neutral and 40% angry reads as
`neutral`. `focus()` scores every utterance on the outputs you pick (e.g. angry, hesitation) from
their probabilities, flags the ones above a threshold or above the speaker's own average, groups
them into episodes, and summarizes them in plain words. It works on results you already have and
never calls the API (negative_words and positive_words download a text model on first use). Scores are model
estimates: use them to find moments to review, not as decisions.
"""

import importlib
from functools import lru_cache
from collections import defaultdict
from collections.abc import Iterable

from pydantic import Field, BaseModel

from .models import ResultItem, ResultResponse


# Output name -> (task, label).
OUTPUTS: dict[str, tuple[str, str]] = {
    "angry": ("emotion", "angry"),
    "happy": ("emotion", "happy"),
    "sad": ("emotion", "sad"),
    "negative": ("positivity", "negative"),
    "positive": ("positivity", "positive"),
    "strong": ("strength", "strong"),
    "weak": ("strength", "weak"),
    "engaged": ("engagement", "engaged"),
    "withdrawn": ("engagement", "withdrawn"),
    "hesitation": ("hesitation", "yes"),
    "fast": ("speaking_rate", "fast"),
    "slow": ("speaking_rate", "slow"),
    # The higher of P(negative) and P(angry) + P(sad).
    "negative_tone": ("positivity", "negative"),
    # P(negative) of the utterance's transcript, from a text model. Needs the words extra.
    "negative_words": ("positivity", "negative"),
    # P(positive) of the utterance's transcript, from the same text model.
    "positive_words": ("positivity", "positive"),
}
# Outputs computed by this module rather than returned by the API.
DERIVED = ("negative_tone", "negative_words", "positive_words")
# Outputs read from the transcript -> the text model's label.
WORDS = {"negative_words": "negative", "positive_words": "positive"}

# Text model for negative_words and positive_words: twitter-roberta-base-sentiment-latest by Cardiff NLP,
# huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest, licensed CC BY 4.0, unmodified.
WORDS_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
_ALIASES = {"anger": "angry", "happiness": "happy", "sadness": "sad", "hesitant": "hesitation"}

# The label each task falls back to when nothing stands out.
_RESTING_LABELS = {
    "emotion": "neutral",
    "positivity": "neutral",
    "strength": "neutral",
    "engagement": "neutral",
    "hesitation": "no",
    "speaking_rate": "normal",
}


class Context(BaseModel):
    """How sensitive `focus()` is in one setting."""

    threshold: float = Field(
        description="Flag an utterance when an output's probability reaches this"
    )
    baseline_margin: float = Field(
        description="Also flag it when the probability is this much above the speaker's average"
    )
    max_gap: float = Field(
        description="Seconds between flagged utterances that still form one episode"
    )
    per_output: dict[str, float] = Field(
        default_factory=dict, description="Thresholds for single outputs, replacing `threshold`"
    )


# Starting points, to be tuned with labeled audio from each setting. Hesitation is a yes/no task
# whose label already flips at 0.5, so it gets a stricter bar than the multi-class outputs.
# The words outputs read text, which noise does not change, so they keep one value.
CONTEXTS: dict[str, Context] = {
    "general": Context(
        threshold=0.3,
        baseline_margin=0.15,
        max_gap=2.0,
        per_output={
            "hesitation": 0.35,
            "negative_tone": 0.2,
            "negative_words": 0.45,
            "positive_words": 0.45,
        },
    ),
    # Cabin noise makes the model less sure, so probabilities run lower.
    "car": Context(
        threshold=0.25,
        baseline_margin=0.15,
        max_gap=2.0,
        per_output={
            "hesitation": 0.3,
            "negative_tone": 0.15,
            "negative_words": 0.45,
            "positive_words": 0.45,
        },
    ),
    # Speakers tend to stay restrained, so smaller changes from their own average matter.
    "legal": Context(
        threshold=0.3,
        baseline_margin=0.1,
        max_gap=3.0,
        per_output={
            "hesitation": 0.35,
            "negative_tone": 0.2,
            "negative_words": 0.45,
            "positive_words": 0.45,
        },
    ),
}


class FocusedUtterance(BaseModel):
    id: str
    speaker: str | None = None
    start: float
    end: float
    text: str | None = None
    scores: dict[str, float] = Field(description="Probability of each chosen output")
    labels: dict[str, str] = Field(description="The API's finalLabel for each chosen output's task")
    detected: list[str] = Field(description="Outputs at or above their threshold")
    above_baseline: list[str] = Field(description="Outputs well above the speaker's own average")
    hidden_by_neutral: list[str] = Field(
        description="Detected outputs whose task's finalLabel is the resting label (e.g. neutral)"
    )
    tone: str | None = Field(
        None, description="'heated' or 'resigned' when negative_tone is detected"
    )


class FocusEvent(BaseModel):
    """Consecutive detected utterances of one speaker for one output."""

    output: str
    speaker: str | None = None
    start: float
    end: float
    peak: float
    utterance_ids: list[str]


class FocusResult(BaseModel):
    outputs: list[str]
    context: str
    thresholds: dict[str, float]
    utterances: list[FocusedUtterance]
    events: list[FocusEvent]

    def result_rows(self) -> list[dict]:
        """negative_tone, negative_words and positive_words as rows in the API's result format,
        marked with "source": "focus".

        finalLabel is the output's label ("negative" or "positive") when it reaches its threshold,
        otherwise "neutral".
        Negative negative_tone rows also carry "tone": "heated" or "resigned".
        """
        rows = []
        for u in self.utterances:
            for output in (o for o in DERIVED if o in self.outputs):
                score = u.scores.get(output)
                if score is None:
                    continue
                label = OUTPUTS[output][1]
                row = {
                    "id": u.id,
                    "startTime": f"{u.start:.3f}",
                    "endTime": f"{u.end:.3f}",
                    "task": output,
                    "prediction": [{"label": label, "posterior": f"{score:.4f}"}],
                    "finalLabel": label if output in u.detected else "neutral",
                    "level": "utterance",
                    "source": "focus",
                    "threshold": self.thresholds[output],
                }
                if output == "negative_tone" and u.tone:
                    row["tone"] = u.tone
                rows.append(row)
        return rows

    def summary(self) -> str:
        """One paragraph per output, in plain words."""
        lines = []
        for output in self.outputs:
            task = OUTPUTS[output][0]
            source = "voice" if output == "negative_tone" else "words" if output in WORDS else task
            scored = [u for u in self.utterances if output in u.scores]
            detected = [u for u in scored if output in u.detected]
            hidden = [u for u in detected if output in u.hidden_by_neutral]
            raised = [u for u in scored if output in u.above_baseline]
            line = (
                f"{output} ({source}, probability >= {self.thresholds[output]:.2f}): "
                f"{len(detected)} of {len(scored)} utterances"
            )
            if hidden:
                line += f", {len(hidden)} of them labeled {_RESTING_LABELS[task]} by the API"
            line += "."
            if raised:
                line += f" {len(raised)} well above the speaker's own average."
            events = [e for e in self.events if e.output == output]
            if events:
                top = sorted(events, key=lambda e: e.peak, reverse=True)[:3]
                line += " Strongest: " + "; ".join(
                    f"{e.speaker or 'unknown speaker'} {_clock(e.start)}-{_clock(e.end)} "
                    f"(peak {e.peak:.2f})"
                    for e in top
                )
                line += "."
            lines.append(line)
        return "\n".join(lines)


def focus(
    results: ResultResponse | Iterable[ResultItem | dict],
    outputs: Iterable[str],
    context: str = "general",
    thresholds: dict[str, float] | None = None,
) -> FocusResult:
    """Score behavioral results on the outputs you pick.

    Args:
        results: A `ResultResponse`, or its `results` list as `ResultItem`s or dicts.
        outputs: Output names from `OUTPUTS`, e.g. `["angry", "hesitation"]`.
        context: A key of `CONTEXTS`, e.g. `"car"`. Sets the thresholds and episode gap.
        thresholds: Per-output thresholds that override the context's, e.g. `{"angry": 0.4}`.

    Returns:
        FocusResult: Scored utterances, episodes, and `summary()`.
    """
    chosen = [_resolve(o) for o in outputs]
    if not chosen:
        raise ValueError("Pick at least one output, e.g. ['angry', 'hesitation']")
    if context not in CONTEXTS:
        raise ValueError(f"Unknown context {context!r}. Choose one of: {', '.join(CONTEXTS)}")
    preset = CONTEXTS[context]
    limits = {o: preset.per_output.get(o, preset.threshold) for o in chosen}
    for name, value in (thresholds or {}).items():
        limits[_resolve(name)] = value

    utterances = _score(_items(results), chosen)
    _flag(utterances, chosen, limits, preset.baseline_margin)
    return FocusResult(
        outputs=chosen,
        context=context,
        thresholds=limits,
        utterances=utterances,
        events=_episodes(utterances, chosen, preset.max_gap),
    )


def _resolve(name: str) -> str:
    key = _ALIASES.get(name.strip().lower(), name.strip().lower())
    if key not in OUTPUTS:
        raise ValueError(f"Unknown output {name!r}. Choose from: {', '.join(OUTPUTS)}")
    return key


def _items(results: ResultResponse | Iterable[ResultItem | dict]) -> list[ResultItem]:
    if isinstance(results, ResultResponse):
        return list(results.results or [])
    return [r if isinstance(r, ResultItem) else ResultItem.model_validate(r) for r in results]


def _score(items: list[ResultItem], chosen: list[str]) -> list[FocusedUtterance]:
    by_id: dict[str, list[ResultItem]] = defaultdict(list)
    for item in items:
        if item.id is not None and item.st is not None and item.et is not None:
            by_id[item.id].append(item)

    wanted = {OUTPUTS[o][0] for o in chosen}
    wanted |= {"emotion"} if "negative_tone" in chosen else set()
    words = [o for o in chosen if o in WORDS]
    wanted |= {"asr"} if words else set()
    utterances = []
    for uid, rows in by_id.items():
        tasks = {r.task: r for r in rows}
        if not wanted & tasks.keys():
            continue  # e.g. utterances of 1 second or less, which have no behavioral tasks
        scores, labels, tone = {}, {}, None
        for output in chosen:
            if output in WORDS:
                continue  # scored below, for all utterances at once
            task, label = OUTPUTS[output]
            row = tasks.get(task)
            if row is None and not (output == "negative_tone" and "emotion" in tasks):
                continue
            scores[output] = _posteriors(row).get(label, 0.0)
            if row is not None:
                labels[task] = (row.finalLabel or "").strip()
            if output == "negative_tone":
                emotion = _posteriors(tasks.get("emotion"))
                scores[output] = max(
                    scores[output], emotion.get("angry", 0) + emotion.get("sad", 0)
                )
                strength = _posteriors(tasks.get("strength"))
                tone = (
                    "heated" if strength.get("strong", 0) >= strength.get("weak", 0) else "resigned"
                )
        speaker = tasks.get("diarization")
        asr = tasks.get("asr")
        text = (asr.finalLabel or "").strip() if asr else ""
        utterances.append(
            FocusedUtterance(
                id=uid,
                speaker=speaker.finalLabel if speaker else None,
                start=rows[0].st or 0.0,
                end=rows[0].et or 0.0,
                text=text or None,
                scores=scores,
                labels=labels,
                detected=[],
                above_baseline=[],
                hidden_by_neutral=[],
                tone=tone,
            )
        )
        if words and tasks.get("positivity") is not None:
            utterances[-1].labels["positivity"] = (tasks["positivity"].finalLabel or "").strip()
    if words:
        with_text = [u for u in utterances if u.text]
        for u, probs in zip(with_text, _words_scores([u.text or "" for u in with_text])):
            for output in words:
                u.scores[output] = probs.get(WORDS[output], 0.0)
    return sorted(utterances, key=lambda u: u.start)


@lru_cache(maxsize=1)
def _words_model():
    try:
        transformers = importlib.import_module("transformers")
    except ImportError as e:
        raise ImportError(
            "negative_words and positive_words need the words extra: "
            'pip install "behavioralsignals[words]"'
        ) from e
    return transformers.pipeline("sentiment-analysis", model=WORDS_MODEL, top_k=None)


def _words_scores(texts: list[str]) -> list[dict[str, float]]:
    """Negative, neutral and positive probabilities of each text."""
    if not texts:
        return []
    results = _words_model()([t[:512] for t in texts])
    return [{r["label"].lower(): float(r["score"]) for r in result} for result in results]


def _posteriors(row: ResultItem | None) -> dict[str, float]:
    if row is None:
        return {}
    return {p.label: float(p.posterior) for p in row.prediction or [] if p.label and p.posterior}


def _flag(
    utterances: list[FocusedUtterance],
    chosen: list[str],
    limits: dict[str, float],
    margin: float,
) -> None:
    for output in chosen:
        task = OUTPUTS[output][0]
        per_speaker: dict[str | None, list[float]] = defaultdict(list)
        for u in utterances:
            if output in u.scores:
                per_speaker[u.speaker].append(u.scores[output])
        averages = {s: sum(v) / len(v) for s, v in per_speaker.items()}
        for u in utterances:
            score = u.scores.get(output)
            if score is None:
                continue
            if score >= limits[output]:
                u.detected.append(output)
                if u.labels.get(task) == _RESTING_LABELS[task]:
                    u.hidden_by_neutral.append(output)
            if len(per_speaker[u.speaker]) > 1 and score - averages[u.speaker] >= margin:
                u.above_baseline.append(output)
    for u in utterances:
        if "negative_tone" not in u.detected:
            u.tone = None


def _episodes(
    utterances: list[FocusedUtterance], chosen: list[str], max_gap: float
) -> list[FocusEvent]:
    events: list[FocusEvent] = []
    for output in chosen:
        open_by_speaker: dict[str | None, FocusEvent] = {}
        for u in utterances:
            if output not in u.detected:
                continue
            current = open_by_speaker.get(u.speaker)
            if current and u.start - current.end <= max_gap:
                current.end = max(current.end, u.end)
                current.peak = max(current.peak, u.scores[output])
                current.utterance_ids.append(u.id)
            else:
                current = FocusEvent(
                    output=output,
                    speaker=u.speaker,
                    start=u.start,
                    end=u.end,
                    peak=u.scores[output],
                    utterance_ids=[u.id],
                )
                open_by_speaker[u.speaker] = current
                events.append(current)
    return sorted(events, key=lambda e: e.start)


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"
