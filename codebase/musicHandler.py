import os
import pickle
from typing import TextIO

import jams
import librosa
import numpy as np

try:
    import codebase.path_handler as path_handler
    import codebase.classify as classify
except ModuleNotFoundError:
    import path_handler
    import classify
finally:
    from sklearn.ensemble import RandomForestClassifier

annotations_path = path_handler.path_to_specific_dataset("annotations")
musics_path = path_handler.path_to_specific_dataset("musics")


def build_model() -> RandomForestClassifier:
    """Constructs a model"""
    model = RandomForestClassifier(n_jobs=-1)
    return model


def getAnnotation(timeStamp: float, jamFile: jams.JAMS) -> str:
    ic = jamFile.search(namespace="chord")
    for annotation in ic[1]["data"]:
        if annotation.time < timeStamp < annotation.time + annotation.duration:
            return annotation.value


def teach(model: RandomForestClassifier, how_many: str | int, overSamplingRate: int = 48, n_features=128):
    """teaches a model"""
    assert isinstance(how_many, int) or how_many.strip(' -\t\n')

    embedder, note_count = classify.readyEmbedder(annotations_path)
    print("\033[36;1mStarting to parse database\033[0m to established twinned x and y data")
    x: list[list[float]] = []
    y: list[int] = []
    file: TextIO

    try:
        with open(path_handler.GNRL_PATH_TO_DATA_SET + "xy.pickle", "r") as file:
            x, y = pickle.load(file)
    except (FileNotFoundError, pickle.PickleError) as e:
        print(f"\033[31;1m{e}\033[0m")

        sacr = [el2.split(".")[0][:-len("_hex")] for el2 in os.listdir(musics_path)]
        choices = [
            el.split(".")[0]
            for el in os.listdir(annotations_path)
            if el.split(".")[0] in sacr
        ]
        del sacr

        for i, choice in enumerate(choices):
            sound_y, sr = librosa.load(musics_path + (
                "/" if not musics_path.endswith("/") else ""
            ) + choice + "_hex.wav")
            # onset_env = librosa.onset.onset_strength(y=sound_y, sr=sr)
            tempo = librosa.beat.tempo(y=sound_y, sr=sr)
            tps = tempo[0] / 60
            jamFile = jams.load(annotations_path + (
                "/" if not annotations_path.endswith("/") else ""
            ) + choice + ".jams")

            hop_len = int(sr / (tps * overSamplingRate) + .5)
            # tps in beats/s, overSamplingRate in measures/beats, sr in measures/s

            specs = np.abs(librosa.core.stft(sound_y, n_fft=n_features, hop_length=hop_len))
            times = librosa.core.frames_to_time(specs[0], sr=sr, n_fft=n_features, hop_length=hop_len)

            for time_idx, timeStamp in enumerate(times):
                if time_idx % 50 == 0:
                    print(f"\rDatabase \033[33;1mconnecting \033[0m(file \033[36;1m{i}\033[0m /",
                          f"\033[34m{len(choices)}\033[0m",
                          f"TimeIndex : \033[36;1m{time_idx}\033[0m).",
                          end="")
                token = getAnnotation(timeStamp, jamFile)
                try:
                    x.append(list(specs[:, time_idx]))
                    y.append(embedder.map[token][0])
                except KeyError as k:
                    print("\r\033[33;1mCaught", k, " "*72)
        with open(path_handler.GNRL_PATH_TO_DATA_SET + "xy.pickle", "w") as file:
            pickle.dump((x, y), file)
    print(x, y, sep="\n")
    model.fit(x, y)


if __name__ == '__main__':
    m = build_model()
    teach(m, "full data-set")
    models_path = path_handler.GNRL_PATH_TO_DATA_SET + "../models/"
    with open(models_path + "RTF.pickle", "w") as file:
        pickle.dump(m, file)
    del file
