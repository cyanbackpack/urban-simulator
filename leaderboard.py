#!/usr/bin/env python3
"""Batch-score CityBench submissions and write a leaderboard CSV/PNG.

    python leaderboard.py terrain.json submissions_dir leaderboard
"""

import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import score_v2 as S


AXES = ["economy", "transport", "environment", "housing", "urban_form"]


def font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def score_folder(terrain_path, submissions_dir):
    terrain = S.load(terrain_path)
    rows = []
    for path in sorted(Path(submissions_dir).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            submission = json.load(f)
        result = S.run(terrain, submission)
        row = {
            "submission": path.stem,
            "status": result["status"],
            "score": result.get("score", 0),
            "grade": result.get("grade", "D"),
            "base_1000": result.get("base_1000", 0),
            "fit_bonus": result.get("fit_bonus", 0),
            "event_score": result.get("event_score", 0),
            "difficulty": result.get("difficulty", terrain.get("difficulty", 1.0)),
            "spent": result.get("stats", {}).get("spent", 0),
            "budget": result.get("stats", {}).get("budget", terrain.get("budget", 0)),
            "reasons": "; ".join(result.get("reasons", [])),
        }
        for axis in AXES:
            row[axis] = result.get("axes", {}).get(axis, 0)
        rows.append(row)
    rows.sort(key=lambda r: (r["status"] == "OK", float(r["score"])), reverse=True)
    return terrain, rows


def write_csv(rows, out_csv):
    fields = ["submission", "status", "score", "grade", *AXES, "base_1000", "fit_bonus",
              "event_score", "difficulty", "spent", "budget", "reasons"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_chart(terrain, rows, out_png):
    width = 1280
    row_h = 44
    top = 110
    height = max(260, top + row_h * max(1, len(rows)) + 40)
    img = Image.new("RGB", (width, height), "#f4f2ea")
    draw = ImageDraw.Draw(img)
    title_font = font(28, bold=True)
    body = font(15)
    small = font(13)

    title = f"{terrain.get('name', 'Terrain')} / {terrain.get('objective', '')}"
    draw.text((30, 24), "CityBench Leaderboard", fill="#20242a", font=title_font)
    draw.text((30, 62), title, fill="#59616b", font=body)

    colors = {
        "economy": "#4472c4",
        "transport": "#70ad47",
        "environment": "#5aa56a",
        "housing": "#ed7d31",
        "urban_form": "#a878d2",
    }
    x0 = 260
    bar_w = 690
    for idx, row in enumerate(rows):
        y = top + idx * row_h
        fill = "#ffffff" if idx % 2 == 0 else "#ece9df"
        draw.rectangle((20, y - 8, width - 20, y + row_h - 10), fill=fill)
        draw.text((32, y), f"{idx + 1}. {row['submission']}", fill="#20242a", font=body)
        draw.text((980, y), f"{row['score']}", fill="#20242a", font=body)
        draw.text((1050, y), row["grade"], fill="#20242a", font=body)
        draw.text((1110, y), row["status"], fill="#59616b", font=small)

        cursor = x0
        total_axis = max(1, sum(float(row[a]) for a in AXES))
        for axis in AXES:
            seg = int((float(row[axis]) / 1000.0) * bar_w)
            draw.rectangle((cursor, y + 4, cursor + seg, y + 24), fill=colors[axis])
            cursor += seg
        draw.rectangle((x0, y + 4, x0 + bar_w, y + 24), outline="#d6d0bf")

    legend_x = 30
    legend_y = height - 28
    for axis in AXES:
        draw.rectangle((legend_x, legend_y, legend_x + 14, legend_y + 14), fill=colors[axis])
        draw.text((legend_x + 20, legend_y - 2), axis, fill="#59616b", font=small)
        legend_x += 160
    img.save(out_png)


def main():
    if len(sys.argv) < 3:
        print("usage: python leaderboard.py terrain.json submissions_dir [prefix]")
        sys.exit(1)
    prefix = sys.argv[3] if len(sys.argv) > 3 else "leaderboard"
    terrain, rows = score_folder(sys.argv[1], sys.argv[2])
    write_csv(rows, f"{prefix}.csv")
    write_chart(terrain, rows, f"{prefix}.png")
    for row in rows:
        print(f"{row['submission']:24} {row['status']:7} {row['score']:>7} {row['grade']}")
    print(f"wrote {prefix}.csv and {prefix}.png")


if __name__ == "__main__":
    main()
