"""Draw the two SVG figures directly from the synthetic conveyor fixture."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from threshold import evaluate

DARK, MUTED, GRID = "#172e3c", "#405a68", "#d7e6eb"
BLUE, RUST = "#096681", "#9b3d1d"


def start(title, subtitle):
    return ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="570" viewBox="0 0 960 570">',
            '<rect width="960" height="570" rx="24" fill="#f5fafb"/>',
            '<g font-family="DejaVu Sans, sans-serif">', text(43, 67, title, 43, DARK, bold=True),
            text(44, 112, subtitle, 26, MUTED)]


def text(x, y, value, size, color=DARK, anchor="start", bold=False):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}"'
            f' font-weight="{700 if bold else 400}">{value}</text>')


def line(x1, y1, x2, y2, color, width=2):
    return f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{color}" stroke-width="{width}"/>'


def save(name, body):
    (HERE / (name + ".svg")).write_text("\n".join(body + ["</g></svg>", ""]), encoding="utf-8")


def cost_chart(miss, alarm):
    chart = start("Same detections, different choices", "Costs on the tuning runs · illustrative data")
    cuts = [r["threshold_milli"] for r in miss["tune_sweep"]]
    x = [114 + i * 122 for i in range(len(cuts))]
    y = lambda cost: 414 - cost * 10
    for cost in range(0, 26, 5):
        chart += [line(102, y(cost), 870, y(cost), GRID), text(86, y(cost) + 7, cost, 23, MUTED, "end")]
    for name, result, color, offset in [("Miss cost ×4", miss, BLUE, 110), ("False alarm cost ×5", alarm, RUST, 452)]:
        ys = [y(r["cost"]) for r in result["tune_sweep"]]
        for i in range(len(x) - 1):
            chart.append(line(x[i], ys[i], x[i+1], ys[i+1], color, 3))
        for xx, yy, cut in zip(x, ys, cuts):
            radius = 10 if cut == result["selected_threshold_milli"] else 5
            chart.append(f'<circle cx="{xx}" cy="{yy}" r="{radius}" fill="{color}"/>')
        chart += [line(offset, 526, offset + 35, 526, color, 4), text(offset + 48, 535, name, 27, color)]
    for xx, cut in zip(x, cuts):
        label = "OFF" if cut == 1001 else f"{cut/1000:.2f}"
        chart.append(text(xx, 460, label, 25, DARK, "middle"))
    chart.append(text(490, 495, "Candidate cutoffs · equally spaced categories", 23, MUTED, "middle"))
    save("confidence-cost-sweep", chart)


def split_chart(result):
    chart = start("Lock 0.620 before holdout", "The same threshold keeps different detections on fresh runs.")
    for k, (key, title) in enumerate([("tune", "Tune"), ("holdout", "Holdout")]):
        y = 214 + 140 * k
        values = result[key]
        chart += [text(47, y + 15, title, 31, DARK, bold=True),
                  text(48, y + 52, f'{values["cost"]} cost units', 23, MUTED)]
        for i, (field, label, color) in enumerate([("tp", "Correct", BLUE),
                                                    ("fp", "False alarms", RUST),
                                                    ("fn", "Missed", "#654785")]):
            x = 255 + i * 223
            chart += [text(x, y - 8, label, 23, DARK),
                      f'<rect x="{x}" y="{y+8}" width="{values[field]*33}" height="24" rx="6" fill="{color}"/>',
                      text(x + values[field] * 33 + 11, y + 30, values[field], 26, color, bold=True)]
    chart.append(text(44, 518, "One miss costs 4; one false alarm costs 1.", 27, MUTED))
    save("confidence-frozen-holdout", chart)


if __name__ == "__main__":
    data = json.loads((HERE.parent / "examples/conveyor.json").read_text())
    miss, alarm = evaluate(data, 1, 4), evaluate(data, 5, 1)
    cost_chart(miss, alarm)
    split_chart(miss)
