"""Focus viewer: pick audio (a file or a folder), outputs and thresholds; compare, tune and listen.

Audio with a saved <name>_results.json next to it is never uploaded again. Subfolders of the chosen
folder become groups (e.g. two sets of calls you want to compare), shown side by side.

From the repository root:

    uv run --extra words --with streamlit streamlit run examples/batch/focus_app.py

or, with pip: pip install "behavioralsignals[words]" streamlit, then streamlit run focus_app.py
"""

import json
from pathlib import Path
from collections import defaultdict

import altair as alt
import pandas as pd
import streamlit as st

from behavioralsignals import Client, BehavioralSignalsError, focus
from behavioralsignals.focus import OUTPUTS, CONTEXTS


AUDIO = {".wav", ".mp3"}
API_TASKS = [
    "positivity",
    "emotion",
    "strength",
    "engagement",
    "hesitation",
    "speaking_rate",
    "intensity",
    "gender",
    "age",
    "language",
]
FINAL_ONLY = {"gender", "age", "language"}
FAILURES = (BehavioralSignalsError, ValueError, OSError)
FLAG, PLAIN, RULE = "#d97706", "#cbd5e1", "#ef4444"
GROUPS = alt.Scale(scheme="tableau10")
SWEEP = [round(0.05 * i, 2) for i in range(21)]

st.set_page_config(page_title="Focus viewer", layout="wide")


# Data -----------------------------------------------------------------------------------------------
def find_audio(path: Path) -> list[tuple[str, Path]]:
    """(group, audio) pairs: the file itself, or a folder's audio plus one level of subfolders."""
    if path.is_file():
        return [("", path)] if path.suffix.lower() in AUDIO else []
    found = [("", p) for p in sorted(path.iterdir()) if p.suffix.lower() in AUDIO]
    for sub in sorted(p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")):
        found += [(sub.name, p) for p in sorted(sub.iterdir()) if p.suffix.lower() in AUDIO]
    return found


def results_path(audio: Path) -> Path:
    return audio.with_name(f"{audio.stem}_results.json")


def fetch_missing(files: list[Path]) -> None:
    """Upload the audio without saved results, wait for each and save it next to the audio."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    try:
        client = Client().behavioral
    except ValueError as e:
        st.error(f"{e} Set BEHAVIORALSIGNALS_CID and BEHAVIORALSIGNALS_API_KEY first.")
        return
    with st.status(f"Uploading {len(files)} file(s)...", expanded=True) as status:
        pids = {}
        for f in files:
            try:
                pids[f] = client.upload_audio(file_path=str(f)).pid
            except FAILURES as e:
                st.write(f"{f.name}: upload failed: {e}")
        for i, (f, pid) in enumerate(pids.items(), 1):
            status.update(label=f"Processing {i}/{len(pids)}, this can take some time: {f.name}")
            try:
                result = client.wait_for_result(pid=pid)
            except FAILURES as e:
                st.write(f"{f.name}: processing failed: {e}")
                continue
            data = result.model_dump(exclude={"results": {"__all__": {"st", "et"}}})
            results_path(f).write_text(json.dumps(data, indent=2))
        status.update(label="Done", state="complete", expanded=False)


def probs(row: dict) -> dict[str, float]:
    return {
        p["label"]: float(p["posterior"]) for p in row.get("prediction") or [] if p.get("posterior")
    }


def api_output(row: dict) -> tuple[str, dict[str, float]]:
    """The task's finalLabel (or score, for intensity) and its label probabilities."""
    score = (row.get("prediction") or [{}])[0].get("score")
    return (row.get("finalLabel") or score or "").strip(), probs(row)


def top_two(final: str, ps: dict[str, float]) -> str:
    if not ps:
        return final
    best = sorted(ps.items(), key=lambda kv: -kv[1])[:2]
    return " · ".join(f"{k} {v:.2f}" for k, v in best)


@st.cache_data(show_spinner="Scoring utterances...")
def analyze(path: str, mtime: float, outputs: tuple[str, ...], context: str) -> list[dict]:
    """Every utterance with its scores on the chosen outputs. Flags are applied later, so moving a
    threshold never re-scores. mtime is only part of the cache key."""
    rows = json.loads(Path(path).read_text())["results"]
    view = focus(rows, list(outputs), context=context, thresholds=dict.fromkeys(outputs, 0.0))
    by_id: dict[str, dict] = defaultdict(dict)
    for r in rows:
        by_id[r["id"]][r["task"]] = r
    return [
        {
            "start": u.start,
            "end": u.end,
            "speaker": u.speaker or "",
            "text": u.text or "",
            "scores": dict(u.scores),
            "neutral_label": list(u.hidden_by_neutral),
            "tone": u.tone,
            "api": {t: api_output(by_id[u.id][t]) for t in API_TASKS if t in by_id[u.id]},
        }
        for u in view.utterances
    ]


def clock(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


# Sidebar ----------------------------------------------------------------------------------------------
source = st.sidebar.text_input("Audio file or folder", placeholder="~/calls  or  ~/calls/call.wav")
outputs = st.sidebar.multiselect(
    "Outputs", sorted(OUTPUTS), default=["negative_tone", "negative_words"]
)
context = st.sidebar.selectbox("Context", list(CONTEXTS))
preset = CONTEXTS[context]
st.sidebar.markdown("**Thresholds**")
limits = {
    o: st.sidebar.slider(
        o, 0.0, 1.0, float(preset.per_output.get(o, preset.threshold)), 0.05, key=f"t-{context}-{o}"
    )
    for o in outputs
}
st.sidebar.caption(
    "negative_tone = max(P(negative), P(angry) + P(sad)); heated if strong ≥ weak, else resigned. "
    "negative_words / positive_words = P(negative) / P(positive) of the transcript, from a local "
    "text model."
)
st.sidebar.caption(
    "Scores are model estimates of how the speech sounds or reads, not decisions about the speaker."
)

st.title("Focus viewer")
if not source or not outputs:
    st.info("Enter an audio file or folder and pick at least one output in the sidebar.")
    st.stop()
path = Path(source.strip()).expanduser()
if not path.exists():
    st.error(f"{path} does not exist.")
    st.stop()
files = find_audio(path)
if not files:
    st.error("No .wav or .mp3 files found there.")
    st.stop()

missing = [f for _, f in files if not results_path(f).exists()]
if missing:
    st.warning(
        f"{len(missing)} of {len(files)} file(s) have no saved results. Processing them uploads them to the API "
        "(and uses minutes). The others are read from their saved results."
    )
    if st.button(f"Upload and process {len(missing)} file(s)", type="primary"):
        fetch_missing(missing)
        st.rerun()

calls = []
for group, f in files:
    rp = results_path(f)
    if rp.exists():
        calls.append(
            {
                "group": group,
                "audio": f,
                "utts": analyze(str(rp), rp.stat().st_mtime, tuple(outputs), context),
            }
        )
if not calls:
    st.stop()


def flagged(u: dict, o: str) -> bool:
    return o in u["scores"] and u["scores"][o] >= limits[o]


has_groups = any(c["group"] for c in calls)
long = pd.DataFrame(
    [
        {
            "group": c["group"] or "all",
            "call": c["audio"].name,
            "output": o,
            "score": u["scores"][o],
            "tone": u["tone"] if o == "negative_tone" else None,
        }
        for c in calls
        for u in c["utts"]
        for o in outputs
        if o in u["scores"]
    ]
)

overview, thresholds, listen = st.tabs(["Overview", "Thresholds", "Listen"])

# Overview -------------------------------------------------------------------------------------------
with overview:
    per_group = []
    for g in sorted({c["group"] or "all" for c in calls}):
        cs = [c for c in calls if (c["group"] or "all") == g]
        us = [u for c in cs for u in c["utts"]]
        row = {"group": g, "calls": len(cs), "utterances": len(us)}
        for o in outputs:
            scored = [u for u in us if o in u["scores"]]
            hits = sum(flagged(u, o) for u in scored)
            row[f"{o}: utterances"] = (
                f"{hits}/{len(scored)} ({100 * hits / max(len(scored), 1):.0f}%)"
            )
            row[f"{o}: calls"] = (
                f"{sum(any(flagged(u, o) for u in c['utts']) for c in cs)}/{len(cs)}"
            )
        if len(outputs) > 1:
            row["flagged by all chosen"] = sum(all(flagged(u, o) for o in outputs) for u in us)
        if "negative_tone" in outputs:
            tones = [u["tone"] for u in us if flagged(u, "negative_tone")]
            row["heated / resigned"] = f"{tones.count('heated')} / {tones.count('resigned')}"
        per_group.append(row)
    st.dataframe(pd.DataFrame(per_group), hide_index=True, width="stretch")
    st.caption(
        "Flagged when "
        + ", ".join(f"{o} ≥ {t:.2f}" for o, t in limits.items())
        + ". Move the sliders to update."
    )

    if "negative_tone" in outputs:
        tone_df = long[(long.output == "negative_tone") & (long.score >= limits["negative_tone"])]
        if not tone_df.empty:
            st.markdown("**negative_tone flags: heated vs resigned**")
            st.altair_chart(
                alt.Chart(tone_df)
                .mark_bar()
                .encode(
                    y=alt.Y("group:N", title=None),
                    x=alt.X("count():Q", title="flagged utterances"),
                    color=alt.Color(
                        "tone:N",
                        scale=alt.Scale(
                            domain=["heated", "resigned"], range=["#b91c1c", "#6a8eab"]
                        ),
                    ),
                )
                .properties(height=40 + 40 * tone_df.group.nunique()),
                width="stretch",
            )

    per_call = []
    for c in calls:
        row = {"group": c["group"], "call": c["audio"].name, "utterances": len(c["utts"])}
        for o in outputs:
            row[o] = sum(flagged(u, o) for u in c["utts"])
        if "negative_tone" in outputs:
            row["heated"] = sum(
                flagged(u, "negative_tone") and u["tone"] == "heated" for u in c["utts"]
            )
            row["resigned"] = sum(
                flagged(u, "negative_tone") and u["tone"] == "resigned" for u in c["utts"]
            )
        per_call.append(row)
    calls_df = pd.DataFrame(per_call)
    if not has_groups:
        calls_df = calls_df.drop(columns="group")
    st.markdown("**Per call**")
    st.dataframe(calls_df, hide_index=True, width="stretch")

# Thresholds -----------------------------------------------------------------------------------------
with thresholds:
    st.caption(
        "Left: how each output's scores are spread, per group, with the current threshold. "
        "Right: what share would be flagged at each threshold (solid: calls with at least one flag, "
        "dashed: utterances). The red dashed line is the current threshold."
    )
    for o in outputs:
        d = long[long.output == o]
        if d.empty:
            continue
        st.markdown(f"#### {o}")
        left, right = st.columns(2)
        rule = (
            alt.Chart(pd.DataFrame({"t": [limits[o]]}))
            .mark_rule(color=RULE, strokeDash=[5, 3], size=2)
            .encode(x="t:Q")
        )
        # Side-by-side bars per 0.05 bin: the share of each group's utterances in that bin.
        names = sorted(d.group.unique())
        bins = []
        for g, part in d.groupby("group"):
            counts = pd.cut(
                part.score, [b / 20 for b in range(21)], include_lowest=True
            ).value_counts()
            for interval, n in counts.items():
                width = 0.05 / len(names)
                lo = interval.left if interval.left > 0 else 0.0
                x0 = lo + names.index(g) * width
                bins.append(
                    {
                        "group": g,
                        "x0": x0,
                        "x1": x0 + width,
                        "share": n / len(part),
                        "range": f"{lo:.2f}-{interval.right:.2f}",
                    }
                )
        hist = (
            alt.Chart(pd.DataFrame(bins))
            .mark_bar()
            .encode(
                x=alt.X("x0:Q", title="score", scale=alt.Scale(domain=[0, 1])),
                x2="x1:Q",
                y=alt.Y(
                    "share:Q",
                    title="share of utterances (sqrt)",
                    axis=alt.Axis(format="%"),
                    scale=alt.Scale(type="sqrt"),
                ),
                y2=alt.datum(0),
                color=alt.Color(
                    "group:N", scale=GROUPS, legend=alt.Legend(orient="top", title=None)
                ),
                tooltip=["group:N", "range:N", alt.Tooltip("share:Q", format=".1%")],
            )
        )
        left.altair_chart((hist + rule).properties(height=260), width="stretch")

        sweep = []
        for g, part in d.groupby("group"):
            per_call_max = part.groupby("call").score.max()
            for t in SWEEP:
                sweep += [
                    {
                        "group": g,
                        "threshold": t,
                        "measure": "utterances",
                        "share": (part.score >= t).mean(),
                    },
                    {
                        "group": g,
                        "threshold": t,
                        "measure": "calls",
                        "share": (per_call_max >= t).mean(),
                    },
                ]
        lines = (
            alt.Chart(pd.DataFrame(sweep))
            .mark_line(point=alt.OverlayMarkDef(size=20))
            .encode(
                x=alt.X("threshold:Q", title="threshold", scale=alt.Scale(domain=[0, 1])),
                y=alt.Y(
                    "share:Q",
                    title="share flagged",
                    axis=alt.Axis(format="%"),
                    scale=alt.Scale(domain=[0, 1]),
                ),
                color=alt.Color(
                    "group:N", scale=GROUPS, legend=alt.Legend(orient="top", title=None)
                ),
                strokeDash=alt.StrokeDash("measure:N", legend=None),
                tooltip=[
                    "group:N",
                    "measure:N",
                    "threshold:Q",
                    alt.Tooltip("share:Q", format=".0%"),
                ],
            )
        )
        right.altair_chart((lines + rule).properties(height=260), width="stretch")

# Listen ----------------------------------------------------------------------------------------------
with listen:
    only_flagged = st.checkbox("Only calls with a flag", value=False)
    choices = [
        i
        for i, c in enumerate(calls)
        if not only_flagged or any(flagged(u, o) for u in c["utts"] for o in outputs)
    ]
    if not choices:
        st.info("No call has a flag at these thresholds.")
        st.stop()

    def label(i: int) -> str:
        c = calls[i]
        n = sum(any(flagged(u, o) for o in outputs) for u in c["utts"])
        return f"{c['group'] + ' / ' if c['group'] else ''}{c['audio'].name}  ·  {n} flagged"

    pick = st.selectbox("Call", choices, format_func=label)
    call, utts = calls[pick], calls[pick]["utts"]

    lanes = [
        {
            "output": o,
            "start": u["start"],
            "end": u["end"],
            "score": round(u["scores"][o], 2),
            "flag": "flagged" if flagged(u, o) else "not flagged",
            "time": clock(u["start"]),
            "text": u["text"][:90],
        }
        for u in utts
        for o in outputs
        if o in u["scores"]
    ]
    if lanes:
        st.altair_chart(
            alt.Chart(pd.DataFrame(lanes))
            .mark_bar(cornerRadius=2)
            .encode(
                x=alt.X("start:Q", title="seconds"),
                x2="end:Q",
                y=alt.Y("output:N", title=None, scale=alt.Scale(paddingInner=0.35)),
                color=alt.Color(
                    "flag:N",
                    scale=alt.Scale(domain=["flagged", "not flagged"], range=[FLAG, PLAIN]),
                    legend=alt.Legend(orient="top", title=None),
                ),
                tooltip=["time", "output", "score", "text"],
            )
            .properties(height=alt.Step(40)),
            width="stretch",
        )

    show_api = st.checkbox(
        "Show API outputs in the table (top two labels of each task; final label for gender, age, language)",
        value=True,
    )
    rows = []
    for u in utts:
        r = {"time": clock(u["start"]), "speaker": u["speaker"]}
        for o in outputs:
            s = u["scores"].get(o)
            hit = s is not None and flagged(u, o)
            tone = f" {u['tone']}" if o == "negative_tone" and hit and u["tone"] else ""
            r[o] = "–" if s is None else f"{'● ' if hit else ''}{s:.2f}{tone}"
        r["label said neutral"] = ", ".join(o for o in u["neutral_label"] if flagged(u, o))
        if show_api:
            for task in API_TASKS:
                if task not in u["api"]:
                    r[task] = "–"
                elif task in FINAL_ONLY:
                    r[task] = u["api"][task][0]
                else:
                    r[task] = top_two(*u["api"][task])
        r["text"] = u["text"]
        rows.append(r)
    st.caption(
        "● flagged. Click a row (or pick it below) to play from there and see every API output."
    )
    picked = st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=f"rows-{pick}",
    )
    clicked = picked.selection.rows[0] if picked.selection.rows else None
    first_flag = next((i for i, u in enumerate(utts) if any(flagged(u, o) for o in outputs)), 0)
    sel = st.selectbox(
        "Utterance",
        range(len(utts)),
        index=clicked if clicked is not None else first_flag,
        format_func=lambda i: (
            f"{clock(utts[i]['start'])}  {utts[i]['speaker']}  {utts[i]['text'][:90]}"
        ),
        key=f"utt-{pick}-{clicked}",
    )
    u = utts[sel]
    st.audio(str(call["audio"]), start_time=int(u["start"]), autoplay=clicked is not None)

    st.markdown(f"**{clock(u['start'])}–{clock(u['end'])}  ·  {u['speaker']}**  ·  {u['text']}")
    if "negative_tone" in u["scores"]:
        pos, emo = u["api"].get("positivity", ("", {}))[1], u["api"].get("emotion", ("", {}))[1]
        st.caption(
            f"negative_tone = max(negative {pos.get('negative', 0):.2f}, angry {emo.get('angry', 0):.2f} + "
            f"sad {emo.get('sad', 0):.2f}) = {u['scores']['negative_tone']:.2f}"
        )
    labeled = {t: v for t, v in u["api"].items() if v[1]}
    if not u["api"]:
        st.caption("No behavioral outputs for this utterance: it is 1 second or less.")
    for start_at in range(0, len(labeled), 5):
        cols = st.columns(5)
        for col, (task, (final, ps)) in zip(cols, list(labeled.items())[start_at : start_at + 5]):
            bars = pd.DataFrame([{"label": k, "p": v, "top": k == final} for k, v in ps.items()])
            col.markdown(f"**{task}**")
            base = alt.Chart(bars).encode(
                y=alt.Y("label:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),
                x=alt.X("p:Q", scale=alt.Scale(domain=[0, 1.15]), title=None, axis=None),
            )
            col.altair_chart(
                (
                    base.mark_bar().encode(
                        color=alt.condition("datum.top", alt.value("#1766a6"), alt.value(PLAIN))
                    )
                    + base.mark_text(align="left", dx=4, color="#94a3b8").encode(
                        text=alt.Text("p:Q", format=".2f")
                    )
                ).properties(height=alt.Step(24)),
                width="stretch",
            )
    if "intensity" in u["api"]:
        st.caption(f"intensity score: {u['api']['intensity'][0]}")
