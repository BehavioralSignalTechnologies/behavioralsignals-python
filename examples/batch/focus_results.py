"""Find the moments that stand out in calls, in one command.

Give it audio files or a folder and the outputs you care about: it uploads them all, waits for the
results, saves them, and prints the moments where those outputs reach their threshold, including
those the API labeled neutral. For each call it saves, next to the input:
  <name>_results.json        the API results, untouched
  <name>_results_focus.json  with negative_tone or negative_words: the results plus their rows,
                             marked "source": "focus"
  <name>_focus.csv           the flagged moments, one per row, to open in a spreadsheet
With more than one call it also saves, in the folder of the first input:
  focus_summary.csv          one row per call
  focus_all.csv              every flagged moment of every call

Give it saved results files instead to run again without uploading (and paying) again.

    python focus_results.py call.wav --outputs angry hesitation
    python focus_results.py call1.wav call2.wav --outputs negative_tone
    python focus_results.py calls/ --outputs angry
    python focus_results.py call_results.json --outputs negative hesitation

With several calls it prints one line per call; add --details to also print every flagged moment.
"""

import os
import csv
import json
import argparse
from pathlib import Path

from behavioralsignals import Client, BehavioralSignalsError, focus
from behavioralsignals.focus import DERIVED, OUTPUTS, CONTEXTS


# Keep the text model (negative_words) quiet while it loads (it is imported on first use).
for name, value in {
    "TRANSFORMERS_VERBOSITY": "error",
    "HF_HUB_VERBOSITY": "error",
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
}.items():
    os.environ.setdefault(name, value)

AUDIO = {".wav", ".mp3"}
# What one bad file can raise: an API error, an invalid file, or a file or network problem.
FAILURES = (BehavioralSignalsError, ValueError, OSError)
COLUMNS = ["start", "end", "speaker", "output", "score", "tone", "label_said_neutral", "text"]


def parse_args():
    parser = argparse.ArgumentParser(description="Find the moments that stand out in calls")
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Audio files, folders, or results JSON files saved before",
    )
    parser.add_argument(
        "--outputs", nargs="+", required=True, choices=sorted(OUTPUTS), help="Outputs to look for"
    )
    parser.add_argument("--context", type=str, default="general", choices=sorted(CONTEXTS))
    parser.add_argument("--details", action="store_true", help="Print every flagged moment")
    return parser.parse_args()


def expand(inputs: list[Path]) -> list[Path]:
    """Files as given; a folder becomes the audio files in it."""
    files = []
    for path in inputs:
        if path.is_dir():
            files += sorted(p for p in path.iterdir() if p.suffix.lower() in AUDIO)
        elif path.is_file():
            files.append(path)
        else:
            print(f"Skipping {path}: no such file or folder")
    return files


def make_client():
    try:  # optional: read credentials from a .env file
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    try:
        return Client()
    except ValueError as e:
        raise SystemExit(f"{e}\nSet BEHAVIORALSIGNALS_CID and BEHAVIORALSIGNALS_API_KEY first.")


def load_saved(path: Path) -> dict:
    data = json.loads(path.read_text())
    data = data if isinstance(data, dict) else {"results": data}
    # Drop rows added by an earlier run, so they are not added twice.
    data["results"] = [r for r in data.get("results") or [] if r.get("source") != "focus"]
    return data


def get_all_results(files: list[Path]) -> dict:
    """Results per file: saved files are read; audio files are all uploaded first, then collected."""
    results: dict[Path, dict | str] = {}
    audio = [f for f in files if f.suffix.lower() != ".json"]
    for f in files:
        if f.suffix.lower() == ".json":
            results[f] = load_saved(f)
    if not audio:
        return results

    client = make_client().behavioral
    pids = {}
    print(f"Uploading {len(audio)} file(s)...")
    for f in audio:
        try:
            pids[f] = client.upload_audio(file_path=str(f)).pid
        except FAILURES as e:  # one bad file should not stop the others
            results[f] = f"upload failed: {e}"
    failed = len(audio) - len(pids)
    print(f"Uploaded {len(pids)}" + (f", failed {failed} (listed at the end)" if failed else ""))
    for done, (f, pid) in enumerate(pids.items(), 1):
        print(
            f"\rProcessing, this can take some time... {done - 1}/{len(pids)} done",
            end="",
            flush=True,
        )
        try:
            result = client.wait_for_result(pid=pid)
            # st and et are numeric copies of the times that the SDK adds; keep the API's fields only.
            data = result.model_dump(exclude={"results": {"__all__": {"st", "et"}}})
        except FAILURES as e:
            results[f] = f"processing failed: {e}"
            continue
        f.with_name(f"{f.stem}_results.json").write_text(json.dumps(data, indent=2))
        results[f] = data
    if pids:
        print(f"\rProcessing, this can take some time... {len(pids)}/{len(pids)} done")
    return results


def with_added_rows(results: list, added: list) -> list:
    """The results with the added rows placed right after the last row of their utterance."""
    by_id: dict = {}
    for row in added:
        by_id.setdefault(row["id"], []).append(row)
    last = {row.get("id"): i for i, row in enumerate(results)}
    merged = []
    for i, row in enumerate(results):
        merged.append(row)
        if last.get(row.get("id")) == i:
            merged += by_id.get(row.get("id"), [])
    return merged


def moment_rows(view) -> list[list[str]]:
    rows = []
    for u in view.utterances:
        for output in u.detected:
            tone = u.tone if output == "negative_tone" else ""
            hidden = "yes" if output in u.hidden_by_neutral else "no"
            score = f"{u.scores[output]:.2f}"
            rows.append(
                [
                    f"{u.start:.2f}",
                    f"{u.end:.2f}",
                    u.speaker or "",
                    output,
                    score,
                    tone or "",
                    hidden,
                    u.text or "",
                ]
            )
    return rows


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def report(path: Path, data: dict, outputs: list[str], context: str, details: bool):
    """Run focus on one call, save its files, print its moments if asked, and return the view."""
    view = focus(data["results"], outputs, context=context)
    base = path.stem.removesuffix("_focus").removesuffix("_results")
    if details:
        print(f"\n=== {path.name}")
        print(view.summary())
        for u in (u for u in view.utterances if u.detected):
            scores = ", ".join(f"{o} {u.scores[o]:.2f}" for o in u.detected)
            tone = f" [{u.tone}]" if u.tone else ""
            print(f"  {clock(u.start)}  {u.speaker or ''}  {scores}{tone}  {(u.text or '')[:80]}")

    added = view.result_rows()
    if added:
        merged = with_added_rows(data["results"], added)
        path.with_name(f"{base}_results_focus.json").write_text(
            json.dumps({**data, "results": merged}, indent=2)
        )
    write_csv(path.with_name(f"{base}_focus.csv"), COLUMNS, moment_rows(view))
    return view


def strongest(view):
    """The flagged moment with the highest score, as (utterance, output), or None."""
    flagged = [(u, o) for u in view.utterances for o in u.detected]
    return max(flagged, key=lambda uo: uo[0].scores[uo[1]], default=None)


if __name__ == "__main__":
    args = parse_args()
    files = expand(args.inputs)
    if not files:
        raise SystemExit("No audio or results files to process.")

    results = get_all_results(files)
    details = args.details or len(results) == 1
    summary, everything, lines, failures = [], [], [], []
    for path, data in results.items():
        if isinstance(data, str):
            failures.append(f"  {path.name}: {data}")
            summary.append([path.name, "failed", "", "", "", "", data])
            continue
        view = report(path, data, args.outputs, args.context, details)
        top = strongest(view)
        counts = [sum(o in u.detected for u in view.utterances) for o in args.outputs]
        where = ""
        if top:
            tone = f", {top[0].tone}" if top[1] == "negative_tone" and top[0].tone else ""
            where = f"{top[0].scores[top[1]]:.2f} {top[1]}{tone}, {clock(top[0].start)}"
        lines.append([path.name, str(len(view.utterances)), *map(str, counts), where or "-"])
        summary.append(
            [
                path.name,
                str(len({u.id for u in view.utterances if u.detected})),
                f"{top[0].scores[top[1]]:.2f}" if top else "",
                top[1] if top else "",
                (top[0].tone or "") if top and top[1] == "negative_tone" else "",
                str(
                    len(
                        {
                            u.id
                            for u in view.utterances
                            for o in u.detected
                            if o in u.hidden_by_neutral
                        }
                    )
                ),
                "",
            ]
        )
        everything += [[path.name, *row] for row in moment_rows(view)]

    if len(lines) > 1:
        header = ["", "utterances", *args.outputs, "strongest"]
        widths = [max(len(r[i]) for r in [header, *lines]) for i in range(len(header))]
        print()
        for row in [header, *lines]:
            cells = [row[0].ljust(widths[0])] + [
                c.rjust(w) for c, w in zip(row[1:-1], widths[1:-1])
            ]
            print("  ".join(cells + [row[-1]]))
    if lines:
        thresholds = focus([], args.outputs, context=args.context).thresholds
        print("\nFlagged when " + ", ".join(f"{o} >= {t:.2f}" for o, t in thresholds.items()))
    if failures:
        print("\nFailed (run these again on their own):")
        print("\n".join(failures))
    added = "<name>_results_focus.json, " if any(o in DERIVED for o in args.outputs) else ""
    print(f"\nSaved next to each input: <name>_results.json, {added}<name>_focus.csv")
    if len(summary) > 1:
        folder = files[0].parent
        header = [
            "file",
            "flagged",
            "strongest",
            "strongest_output",
            "tone",
            "label_said_neutral",
            "error",
        ]
        write_csv(folder / "focus_summary.csv", header, summary)
        write_csv(folder / "focus_all.csv", ["file", *COLUMNS], everything)
        print(f"Saved for all calls: focus_summary.csv and focus_all.csv in {folder}")
        if not details:
            print("Add --details to print every flagged moment.")
    print(
        "\nScores are model estimates of how the speech sounds or reads, not decisions about the speaker."
    )
