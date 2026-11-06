# Choose an object detection confidence threshold

A conveyor camera reports candidate locations for clips. Choose the score cutoff on one set of runs and measure what happens when you keep it fixed on new runs. The data are invented to make every count traceable. No model, camera, GPU or robot is needed.

Full lesson: https://wifarobotics.com/learn/object-detection-confidence-threshold/

## Start from zero

1. Install [Python 3.11 or newer](https://www.python.org/downloads/). Check it with `python3 --version` on macOS or Linux, or `py -3 --version` on Windows.
2. Use GitHub's **Code → Download ZIP**, extract it, and open a terminal in the extracted folder. Check that it contains `threshold.py` and `examples`.
3. Run the following commands. Use `py -3` instead of `python3` on Windows. There are no Python packages to install. An optional local environment can be created with `python3 -m venv --without-pip .venv`.

```sh
python3 threshold.py examples/conveyor.json --fp-cost 1 --fn-cost 4
python3 threshold.py examples/conveyor.json --fp-cost 5 --fn-cost 1
python3 threshold.py examples/all-off.json --fp-cost 1 --fn-cost 1
python3 -m unittest discover -s tests -v
```

| Example | Selected score | Tune TP/FP/FN | Holdout TP/FP/FN | Tune and holdout cost |
| --- | ---: | --- | --- | --- |
| Missing a clip costs more | 0.620 | 4/2/1 | 2/2/2 | 6 and 10 |
| False alarms cost more | 0.940 | 1/0/4 | 0/0/4 | 4 and 4 |
| Accept none wins a tie | OFF (1001) | 0/0/1 | 0/0/1 | 1 and 1 |

Costs are user supplied positive integer units per event. Compare policies under the same costs and evaluation set. The holdout set does not participate in selection.

## Data format and matching contract

The top-level keys are `tune` and `holdout`. Each frame has a unique `frame` string, a capture `run` string, a list of `targets` labeled for one class and a list of postprocessing `detections`. Keep capture runs independent across splits. A detection has an integer `score_milli` from 0 to 1000 and a `match` equal to a target ID from its frame, or JSON `null` if it is unmatched. For example:

```json
{"frame":"a17","run":"shift-A","targets":["clip-1"],"detections":[{"score_milli":620,"match":"clip-1"},{"score_milli":410,"match":null}]}
```

Before supplying real data, freeze your model and postprocessing. For this lab, keep one class and assign matches in descending score order to unused same-class labels under a fixed box overlap rule. Define a stable tie order before matching. Preserve all target labels and frames, including misses and empty scenes. The script consumes these assignments and does not calculate boxes or rerun NMS. Any fixed assignments must remain valid when only a suffix of low-score predictions is removed. Record how scores were converted to thousandths and avoid rounding if it would merge scores whose distinction matters; this lab uses a discrete grid by design.

The script accepts scores greater than or equal to the cutoff, sweeps distinct scores together and includes a separate OFF policy at 1001. An accepted matched detection is a true positive (TP). An accepted unmatched detection is a false positive (FP). Every target without an accepted match is a false negative (FN), including targets for which the model produced no detection. The tuning winner minimizes `FP × FP cost + FN × FN cost`, with the higher cutoff winning exact ties. There is no count of true negative boxes in this model.

## Experiments and troubleshooting

* Add a matched score of 620 to the missed target in holdout frame h4. The selected threshold stays at 620 and holdout cost falls from 10 to 6. This is a demonstration on a disposable fixture, not a reason to tune on holdout.
* At cutoff 700 the tuning example accepts both boxes scored 700, so TP and FP increase together. Inspect `tune_sweep` to verify it.
* If you see `unknown or reused matched target`, check that labels exist in the same frame and that no two boxes claim one target. Leave duplicate boxes unmatched if they survived postprocessing.
* If all tuning cutoffs look bad, inspect the never-detected targets, capture conditions and export floor. A higher threshold cannot recover a box the model never emitted.
* If the two split IDs overlap, split by physical capture run before assigning filenames. This check cannot detect duplicated images renamed under different IDs.

## Figures and limits

The editable SVGs and WebPs are in `diagrams/`. To rebuild them, run `python3 diagrams/draw.py`. With [Node.js](https://nodejs.org/en/download) installed, run `npm install --no-save --package-lock=false sharp` in the project root, then `node diagrams/webp.cjs` to export both WebPs. Node and sharp are only needed to edit figures.

This is an offline replay of synthetic, one-class detection records. Score is a model signal, not a calibrated probability by default. Loss is a simple per-box teaching objective, not production throughput, money or a safety assessment. Before hardware use, validate on more independent lots, materials, lighting conditions and failures; check matching rules, classification errors, latency and downstream false actions separately. Never use this script as a safety interlock.

References: [Ultralytics prediction settings](https://docs.ultralytics.com/modes/predict/) and [scikit-learn decision threshold tuning](https://scikit-learn.org/stable/modules/classification_threshold.html), which describes the general decision and evaluation split principle for classifiers.
