import os
import time

import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv
from datasets import Dataset, load_dataset
from sklearn.metrics import confusion_matrix

from behavioralsignals import Client


def upload_dataset(ds: Dataset, client: Client) -> list[int]:
    """ Uploads audio files from the dataset to the Behavioral Signals API (batch mode).

    Args:
        ds (Dataset): The dataset containing audio files and labels.
        client (Client): The Behavioral Signals API client.
    Returns:
        list[int]: A list of process IDs corresponding to the uploaded audio files.
    """
    pids = []
    for _, row in enumerate(ds):
        process = client.upload_audio(file_path=row["audio"]["path"])
        pids.append(process.pid)

    return pids


def get_all_results(ds: Dataset, client: Client) -> list[str]:
    """ Retrieves results for all processes in the dataset. It returns the final labels
    for each audio file.

    Args:
        ds (Dataset): The dataset containing audio files and their process IDs.
        client (Client): The Behavioral Signals API client.

    Returns:
        list[str]: A list of final labels for each audio file, indicating whether it is
        "spoofed" or "bonafide". If the results cannot be retrieved, it returns "failed" for that file.
    """
    pbar = tqdm(total=len(ds), desc="Waiting all processes to be finished ...", unit="processes")
    done = [False] * len(ds)

    while not all(done):
        for i, row in enumerate(ds):
            if done[i]:
                continue
            pid = row["pid"]
            process = client.get_process(pid=pid)
            if not process.is_pending and not done[i]:
                if process.is_failed:
                    print(f"Process {pid} failed: {process.statusmsg}")
                done[i] = True
                pbar.update(1)
        time.sleep(1.0)

    predicted = []
    for _, row in enumerate(ds):
        pid = row["pid"]
        process = client.get_process(pid=pid)
        final_label = "failed"

        if process.is_completed:
            data = client.get_result(pid=pid)
            results = [item for item in data.results if item.task == "deepfake"]

            # NOTE: Here, each audio file (which is, in principle, a single utterance)
            # may have multiple results - maybe because diarization has segmented it
            # into multiple parts. We only keep the first result for the sake of simplicity
            if len(results) > 1:
                print(f"Process {pid} has multiple results: {len(results)} ... Keeping the first one.")

            if len(results) == 0:
                print(f"Process {pid} has no results.")
            else:
                final_label = results[0].finalLabel

        predicted.append(final_label)

    return predicted


def main():
    load_dotenv()
    client = Client(user_id=os.getenv("USER_ID"), api_key=os.getenv("API_KEY"))

    ds = load_dataset("behavioralsignals/audio-deepfakes-demo", split="test")
    pids = upload_dataset(ds, client)

    ds = ds.add_column("pid", pids)
    pred = get_all_results(ds, client)
    ds = ds.add_column("prediction", pred)
    y_true, y_pred = np.array(ds["deepfake"]), np.array(ds["prediction"])
    valid_indices = np.where(y_pred != "failed")[0]
    y_true, y_pred = y_true[valid_indices], y_pred[valid_indices]

    labels = ["spoofed", "bonafide"]
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    print(f"Labels = {labels} | Confusion Matrix:")
    print(cm)


if __name__ == "__main__":
    main()
