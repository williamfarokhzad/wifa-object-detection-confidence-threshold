"""Choose one score threshold from frozen, one-to-one detection matches."""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path

OFF = 1001


@dataclass(frozen=True)
class Row:
    threshold_milli: int
    tp: int
    fp: int
    fn: int
    cost: int


def integer(value, name, low, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        span = f"{low}..{high}" if high is not None else f">= {low}"
        raise ValueError(f"{name} must be an integer ({span})")
    return value


def identifier(value, name):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be a nonempty string without surrounding whitespace")
    return value


def load_split(frames):
    if not isinstance(frames, list) or not frames:
        raise ValueError("each split needs a nonempty list of frames")
    frame_ids, runs = set(), set()
    targets = 0
    detections = []
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != {"frame", "run", "targets", "detections"}:
            raise ValueError("each frame needs frame, run, targets and detections")
        key = identifier(frame["frame"], "frame")
        if key in frame_ids:
            raise ValueError(f"duplicate frame: {key}")
        frame_ids.add(key)
        runs.add(identifier(frame["run"], "run"))
        labels, boxes = frame["targets"], frame["detections"]
        if not isinstance(labels, list) or not isinstance(boxes, list):
            raise ValueError("targets and detections must be lists")
        labels_set = {identifier(label, "target") for label in labels}
        if len(labels_set) != len(labels):
            raise ValueError(f"duplicate target in frame {key}")
        targets += len(labels)
        used = set()
        for box in boxes:
            if not isinstance(box, dict) or set(box) != {"score_milli", "match"}:
                raise ValueError("each detection needs score_milli and match")
            score = integer(box["score_milli"], "score_milli", 0, 1000)
            match = box["match"]
            if match is not None:
                identifier(match, "match")
                if match not in labels_set or match in used:
                    raise ValueError(f"unknown or reused matched target in frame {key}: {match}")
                used.add(match)
            detections.append((score, match is not None))
    if targets == 0:
        raise ValueError("each split needs at least one labeled target")
    return targets, detections, frame_ids, runs


def row(threshold, tp, fp, total, fp_cost, fn_cost):
    fn = total - tp
    return Row(threshold, tp, fp, fn, fp * fp_cost + fn * fn_cost)


def sweep(total, detections, fp_cost, fn_cost):
    hits = Counter(score for score, matched in detections if matched)
    errors = Counter(score for score, matched in detections if not matched)
    tp = fp = 0
    yield row(OFF, tp, fp, total, fp_cost, fn_cost)
    for threshold in sorted(hits.keys() | errors.keys(), reverse=True):
        tp += hits[threshold]
        fp += errors[threshold]
        yield row(threshold, tp, fp, total, fp_cost, fn_cost)


def evaluate(dataset, fp_cost, fn_cost):
    integer(fp_cost, "FP cost", 1)
    integer(fn_cost, "FN cost", 1)
    if not isinstance(dataset, dict) or set(dataset) != {"tune", "holdout"}:
        raise ValueError("dataset needs tune and holdout splits")
    total, detections, frames, runs = load_split(dataset["tune"])
    holdout_total, holdout, holdout_frames, holdout_runs = load_split(dataset["holdout"])
    if frames & holdout_frames or runs & holdout_runs:
        raise ValueError("tune and holdout must have disjoint frame IDs and capture runs")
    rows = list(sweep(total, detections, fp_cost, fn_cost))
    winner = min(rows, key=lambda item: (item.cost, -item.threshold_milli))
    accepted = [matched for score, matched in holdout if score >= winner.threshold_milli]
    tp = sum(accepted)
    result = row(winner.threshold_milli, tp, len(accepted) - tp, holdout_total, fp_cost, fn_cost)
    return {"selected_threshold_milli": winner.threshold_milli, "tune": asdict(winner),
            "holdout": asdict(result), "tune_sweep": [asdict(item) for item in rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--fp-cost", type=int, required=True)
    parser.add_argument("--fn-cost", type=int, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.dataset.read_text(encoding="utf-8"))
        result = evaluate(data, args.fp_cost, args.fn_cost)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
