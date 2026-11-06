import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

from threshold import OFF, evaluate

ROOT = Path(__file__).resolve().parents[1]


def fixture(name="conveyor"):
    return json.loads((ROOT / f"examples/{name}.json").read_text())


def cli(*args):
    return subprocess.run([sys.executable, "threshold.py", *args], cwd=ROOT,
                          text=True, capture_output=True)


class ThresholdTests(unittest.TestCase):
    def test_hand_count_miss_cost(self):
        result = evaluate(fixture(), 1, 4)
        self.assertEqual(result["tune"], dict(threshold_milli=620, tp=4, fp=2, fn=1, cost=6))
        self.assertEqual(result["holdout"], dict(threshold_milli=620, tp=2, fp=2, fn=2, cost=10))

    def test_hand_count_false_alarm_cost(self):
        result = evaluate(fixture(), 5, 1)
        self.assertEqual(result["tune"], dict(threshold_milli=940, tp=1, fp=0, fn=4, cost=4))
        self.assertEqual(result["holdout"], dict(threshold_milli=940, tp=0, fp=0, fn=4, cost=4))

    def test_equal_scores_move_together_and_comparison_is_inclusive(self):
        rows = {r["threshold_milli"]: r for r in evaluate(fixture(), 1, 4)["tune_sweep"]}
        self.assertEqual((rows[820]["tp"], rows[820]["fp"]), (2, 1))
        self.assertEqual((rows[700]["tp"], rows[700]["fp"]), (3, 2))

    def test_tie_goes_to_stricter_policy_even_at_score_one(self):
        result = evaluate(fixture("all-off"), 1, 1)
        self.assertEqual(result["selected_threshold_milli"], OFF)
        self.assertEqual((result["holdout"]["tp"], result["holdout"]["fn"]), (0, 1))

    def test_holdout_cannot_change_selection(self):
        data = fixture()
        old = evaluate(data, 1, 4)
        data["holdout"][0]["detections"][0]["score_milli"] = 0
        new = evaluate(data, 1, 4)
        self.assertEqual(old["tune"], new["tune"])
        self.assertEqual(new["holdout"]["cost"] - old["holdout"]["cost"], 4)

    def test_capture_run_and_frame_overlap_fail(self):
        for key in ("run", "frame"):
            with self.subTest(key=key):
                data = fixture()
                data["holdout"][0][key] = data["tune"][0][key]
                with self.assertRaisesRegex(ValueError, "disjoint"):
                    evaluate(data, 1, 4)

    def test_bad_matches_fail(self):
        for match in ("other", "clip"):
            with self.subTest(match=match):
                data = fixture()
                data["tune"][0]["detections"][1]["match"] = match
                with self.assertRaisesRegex(ValueError, "unknown or reused"):
                    evaluate(data, 1, 4)

    def test_bad_scores_and_costs_fail(self):
        for value in (True, 620.0, 1001, -1):
            with self.subTest(value=value):
                data = fixture()
                data["tune"][0]["detections"][0]["score_milli"] = value
                with self.assertRaisesRegex(ValueError, "score_milli"):
                    evaluate(data, 1, 4)
        with self.assertRaisesRegex(ValueError, "FP cost"):
            evaluate(fixture(), 0, 4)

    def test_empty_detection_split_preserves_missed_target(self):
        data = fixture("all-off")
        data["tune"][0]["detections"] = []
        self.assertEqual(evaluate(data, 1, 4)["tune"],
                         dict(threshold_milli=1001, tp=0, fp=0, fn=1, cost=4))

    def test_against_every_integer_cutoff(self):
        rng = random.Random(323)
        for _ in range(64):
            data = copy.deepcopy(fixture())
            for part in data.values():
                for frame in part:
                    for det in frame["detections"]:
                        det["score_milli"] = rng.choice((0, 100, 500, 510, 1000))
            a, b = rng.randint(1, 8), rng.randint(1, 8)

            def counts(part, cutoff):
                accepted = [det for frame in part for det in frame["detections"]
                            if det["score_milli"] >= cutoff]
                total = sum(len(frame["targets"]) for frame in part)
                tp = sum(det["match"] is not None for det in accepted)
                fp = len(accepted) - tp
                fn = total - tp
                return tp, fp, fn, a * fp + b * fn

            best = min(range(1002), key=lambda cutoff: (counts(data["tune"], cutoff)[3], -cutoff))
            result = evaluate(data, a, b)
            self.assertEqual(result["selected_threshold_milli"], best)
            for name in ("tune", "holdout"):
                self.assertEqual(tuple(result[name][key] for key in ("tp", "fp", "fn", "cost")),
                                 counts(data[name], best))

    def test_cli_success_and_bad_input(self):
        success = cli("examples/conveyor.json", "--fp-cost", "1", "--fn-cost", "4")
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(json.loads(success.stdout)["selected_threshold_milli"], 620)
        failure = cli("examples/conveyor.json", "--fp-cost", "0", "--fn-cost", "4")
        self.assertEqual(failure.returncode, 2)
        self.assertIn("FP cost", failure.stderr)
        self.assertEqual(failure.stdout, "")


if __name__ == "__main__":
    unittest.main()
