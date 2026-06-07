#!/usr/bin/env python3
"""
CityBench renderer v2 — planning-diagram quality (matplotlib).

Smooth lake/coast outlines, hierarchical curved roads with casing, filled zone
polygons, labels, facility icons, and a scorecard panel. Same data as the
scorer; nothing is invented beyond what the submission contains.

    python3 render2.py terrain.json submission.json [out.png]
"""
import json, sys
import os
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly, Circle, Rectangle, FancyBboxPatch
    import matplotlib.patheffects as pe
    from matplotlib import font_manager as fm
    from skimage import measure
    HAVE_MPL = True
except ImportError:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_MPL = False

import score_v2 as S

# Korean font
def _first_existing(paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


_FP = _first_existing([
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/arial.ttf",
])
_FPB = _first_existing([
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
])
if HAVE_MPL:
    KR = fm.FontProperties(fname=_FP) if _FP else fm.FontProperties()
    KRB = fm.FontProperties(fname=_FPB) if _FPB else fm.FontProperties()
else:
    KR = KRB = None

LAND = "#eef0ea"; WATER = "#a9d2ee"; FOREST = "#cfe3c4"; STEEP = "#cfcdc9"
FARMLAND = "#e9dfaa"; WETLAND = "#b9d8c8"
ZONE = {
    "CBD": "#d62839", "COMMERCIAL": "#f08c28", "RES_HIGH": "#f3cf2a",
    "RES_MED": "#ecd982", "RES_LOW": "#bcd77a", "SUBURB": "#d3e1ac",
    "UNIVERSITY": "#a878d2", "MEDICAL": "#cda0dc", "INDUSTRIAL": "#8c8073",
    "LOGISTICS": "#a89a86", "PUBLIC": "#4f74cf", "PARK": "#5aa54f",
    "GREENBELT": "#79b95f",
}
ZONE_KR = {"CBD": "CBD", "COMMERCIAL": "상업/업무", "RES_HIGH": "고밀주거",
           "RES_MED": "중밀주거", "RES_LOW": "저밀주거", "SUBURB": "교외",
           "UNIVERSITY": "대학", "MEDICAL": "의료", "INDUSTRIAL": "산업",
           "LOGISTICS": "물류", "PUBLIC": "공공", "PARK": "공원", "GREENBELT": "그린벨트"}
# road type -> (color, core width, casing width, dashed)
ROAD = {
    "arterial":     ("#c8ccd2", 0.9, 0,   False),
    "brt":          ("#2aa0dc", 2.2, 0,   False),
    "rail":         ("#8a8f98", 1.8, 0,   True),
    "freight_rail": ("#9c7b5a", 1.8, 0,   True),
    "highway":      ("#ffffff", 3.0, 5.2, False),
    "subway":       ("#1f2430", 2.6, 4.6, False),
}
FAC = {"airport": ("A", "#3a7bd5"), "port": ("P", "#2a6f97"),
       "freight_terminal": ("F", "#9c6b3f"), "power": ("E", "#e0a020"),
       "water_treatment": ("W", "#3aa0c0"), "waste": ("X", "#7a8a5a")}
# event type -> (letter, class)   class -> ring color
EVENT_VIS = {"mineral_deposit": ("M", "opportunity"), "deep_harbor": ("H", "opportunity"),
             "oil_field": ("O", "mixed"), "fault_line": ("!", "hazard"),
             "floodplain": ("F", "mixed"), "heritage_site": ("G", "mixed"),
             "natural_reserve": ("N", "mixed"), "landslide_zone": ("L", "hazard"),
             "typhoon_corridor": ("T", "hazard"), "wind_corridor": ("W", "opportunity"),
             "aquifer_recharge": ("A", "mixed"), "scenic_viewpoint": ("V", "opportunity"),
             "geothermal_spring": ("S", "opportunity"), "fertile_soil": ("Y", "mixed"),
             "subsidence_zone": ("D", "hazard"), "bridge_chokepoint": ("B", "opportunity")}
EVENT_KR = {"mineral_deposit": "광맥", "deep_harbor": "심해항", "oil_field": "유전",
            "fault_line": "단층", "floodplain": "범람원", "heritage_site": "유산지",
            "natural_reserve": "보호구역", "landslide_zone": "산사태", "typhoon_corridor": "태풍",
            "wind_corridor": "풍력", "aquifer_recharge": "대수층", "scenic_viewpoint": "경관",
            "geothermal_spring": "온천", "fertile_soil": "비옥토", "subsidence_zone": "침하",
            "bridge_chokepoint": "교량지점"}
RING = {"opportunity": "#3fae54", "hazard": "#e05050", "mixed": "#e0a020"}


def event_style(event):
    letter, klass = EVENT_VIS.get(
        event.get("type"),
        (event.get("type", "?")[:1].upper(), event.get("class", "mixed")),
    )
    klass = event.get("class", klass)
    return letter, klass, RING.get(klass, RING["mixed"])


def _pil_font(size, bold=False):
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


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _shade(color, factor):
    r, g, b = _hex_to_rgb(color)
    return tuple(max(0, min(255, int(c * factor))) for c in (r, g, b))


def _hillshade(t):
    elev = np.array(t.get("elevation_m", []), dtype=float)
    if elev.shape != (t.get("height"), t.get("width")):
        return None
    gy, gx = np.gradient(elev)
    light = -0.7 * gx - 0.45 * gy
    light = (light - light.min()) / (light.max() - light.min() + 1e-9)
    return 0.82 + light * 0.28


def _render_pil(t, sub, out):
    cell = t["cell_size_m"]
    width = t["width"]
    height = t["height"]
    scale = 6
    map_w = width * scale
    map_h = height * scale
    panel_w = 360
    img = Image.new("RGB", (map_w + panel_w, map_h), "#191b1e")
    draw = ImageDraw.Draw(img)

    terrain_colors = {".": LAND, "T": FOREST, "F": FARMLAND, "w": WETLAND, "^": STEEP, "~": WATER}
    hillshade = _hillshade(t)
    for y, row in enumerate(t["rows"]):
        for x, ch in enumerate(row):
            color = terrain_colors.get(ch, LAND)
            if hillshade is not None and ch != "~":
                color = _shade(color, hillshade[y, x])
            draw.rectangle(
                (x * scale, y * scale, (x + 1) * scale, (y + 1) * scale),
                fill=color,
            )

    def xy(pt):
        return (pt[0] / cell * scale, pt[1] / cell * scale)

    for zone in sub.get("zones", []):
        fill = ZONE.get(zone.get("use"), "#999999")
        pts = [xy(p) for p in zone.get("polygon", [])]
        if len(pts) >= 3:
            draw.polygon(pts, fill=fill, outline="white")

    road_order = ["arterial", "rail", "freight_rail", "brt", "highway", "subway"]
    lines = sorted(
        sub.get("transit", []),
        key=lambda line: road_order.index(line["type"]) if line.get("type") in road_order else 0,
    )
    for line in lines:
        spec = ROAD.get(line.get("type"))
        pts = [xy(p) for p in line.get("path", [])]
        if spec and len(pts) >= 2:
            color, width_core, width_case, dashed = spec
            if width_case:
                draw.line(pts, fill="#23262e", width=max(1, int(width_case * 1.2)), joint="curve")
            draw.line(pts, fill=color, width=max(1, int(width_core * 1.4)), joint="curve")

    small = _pil_font(11, bold=True)
    label_font = _pil_font(12, bold=True)
    for station in sub.get("stations", []):
        x, y = xy((station["x"], station["y"]))
        r = 3
        draw.ellipse((x - r, y - r, x + r, y + r), fill="white", outline="#222222")
    for hub in sub.get("hubs", []):
        x, y = xy((hub["x"], hub["y"]))
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill="#1f2430", outline="white", width=2)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="white")
    for facility in sub.get("facilities", []):
        sym, color = FAC.get(facility.get("type"), ("?", "#888888"))
        x, y = xy((facility["x"], facility["y"]))
        r = 8
        draw.rounded_rectangle((x - r, y - r, x + r, y + r), radius=3, fill="white", outline=color, width=2)
        draw.text((x, y), sym, fill=color, font=small, anchor="mm")

    for event in t.get("events", []):
        letter, klass, color = event_style(event)
        x, y = xy((event["x"], event["y"]))
        r = event["radius"] / cell * scale
        draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=2)
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill="white", outline=color, width=2)
        draw.text((x, y), letter, fill=color, font=small, anchor="mm")

    for zone in sub.get("zones", []):
        pts = [xy(p) for p in zone.get("polygon", [])]
        if len(pts) >= 3 and zone.get("use") in ("CBD", "COMMERCIAL", "RES_HIGH", "INDUSTRIAL"):
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            draw.text((cx, cy), zone["use"], fill="#222222", font=label_font, anchor="mm")

    panel_x = map_w
    draw.rectangle((panel_x, 0, map_w + panel_w, map_h), fill="#191b1e")
    title = _pil_font(22, bold=True)
    body = _pil_font(15)
    body_b = _pil_font(16, bold=True)
    score_font = _pil_font(42, bold=True)
    res = S.run(t, sub)
    y = 24
    draw.text((panel_x + 24, y), t.get("name", "City"), fill="white", font=title)
    y += 34
    draw.text((panel_x + 24, y), f"{t.get('terrain_type', '')} / {t.get('objective', '')}", fill="#aab0ba", font=body)
    y += 48
    if res["status"] == "OK":
        draw.text((panel_x + 24, y), str(res["score"]), fill="#ffd95a", font=score_font)
        draw.text((panel_x + 210, y + 15), f"({res['grade']})", fill="#ffd95a", font=body_b)
        y += 70
        for key in ("economy", "transport", "environment", "housing", "urban_form"):
            value = res["axes"][key]
            draw.text((panel_x + 24, y), key, fill="#cfd4db", font=body)
            draw.text((panel_x + panel_w - 24, y), f"{value:.0f}", fill="#cfd4db", font=body, anchor="ra")
            y += 25
        y += 20
        draw.text((panel_x + 24, y), f"Fit bonus {res['fit_bonus']}", fill="#aab0ba", font=body)
        y += 24
        draw.text((panel_x + 24, y), f"Events {res['event_score']}", fill="#aab0ba", font=body)
        y += 24
        draw.text((panel_x + 24, y), f"Spent {res['stats']['spent']} / {res['stats']['budget']}", fill="#aab0ba", font=body)
    else:
        draw.text((panel_x + 24, y), "FAILED", fill="#ff6b6b", font=score_font)
        y += 70
        for reason in res.get("reasons", [])[:8]:
            draw.text((panel_x + 24, y), reason[:42], fill="#cfd4db", font=body)
            y += 24

    img.save(out)
    return out


def chaikin(pts, iters=2, closed=False):
    pts = np.asarray(pts, float)
    for _ in range(iters):
        new = []
        n = len(pts)
        rng = range(n) if closed else range(n - 1)
        if not closed:
            new.append(pts[0])
        for i in rng:
            p, q = pts[i], pts[(i + 1) % n]
            new.append(0.75 * p + 0.25 * q)
            new.append(0.25 * p + 0.75 * q)
        if not closed:
            new.append(pts[-1])
        pts = np.array(new)
    return pts


def mask_contours(mask, cell, smooth=2):
    out = []
    for c in measure.find_contours(mask.astype(float), 0.5):
        xy = np.column_stack([(c[:, 1] + 0.5) * cell, (c[:, 0] + 0.5) * cell])
        if len(xy) >= 4:
            xy = chaikin(xy, smooth, closed=True)
        out.append(xy)
    return out


def render(t, sub, out):
    if not HAVE_MPL:
        return _render_pil(t, sub, out)

    cell = t["cell_size_m"]; W = t["width"]; H = t["height"]
    EX, EY = W * cell, H * cell
    rows = t["rows"]
    grid = np.array([[ch for ch in r] for r in rows])
    water = grid == "~"; forest = grid == "T"; steep = grid == "^"
    farmland = grid == "F"; wetland = grid == "w"

    fig = plt.figure(figsize=(15.5, 9.2), dpi=150)
    gs = fig.add_gridspec(1, 2, width_ratios=[4.1, 1.0], wspace=0.02)
    ax = fig.add_subplot(gs[0]); panel = fig.add_subplot(gs[1])
    fig.patch.set_facecolor("#191b1e")

    ax.set_xlim(0, EX); ax.set_ylim(EY, 0)  # y down (north up)
    ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((0, 0), EX, EY, facecolor=LAND, edgecolor="none", zorder=0))
    shade = _hillshade(t)
    if shade is not None:
        ax.imshow(shade, extent=(0, EX, EY, 0), cmap="Greys", alpha=0.12,
                  vmin=0.82, vmax=1.10, zorder=0.2)

    # terrain fills as smooth polygons
    for m, col, z in [(farmland, FARMLAND, 0.8), (forest, FOREST, 1),
                      (wetland, WETLAND, 1.2), (steep, STEEP, 1.4), (water, WATER, 2)]:
        if m.any():
            for xy in mask_contours(m, cell):
                ax.add_patch(MplPoly(xy, closed=True, facecolor=col,
                                     edgecolor="none", zorder=z))

    # zones as filled polygons (later ones on top), light edge
    patches, colors = [], []
    for z in sub.get("zones", []):
        if z["use"] not in ZONE:
            continue
        poly = np.array(z["polygon"], float)
        patches.append(MplPoly(poly, closed=True))
        colors.append(ZONE[z["use"]])
    for p, c in zip(patches, colors):
        p.set_facecolor(c); p.set_edgecolor("white"); p.set_linewidth(0.6)
        p.set_alpha(0.92); p.set_zorder(3)
        ax.add_patch(p)

    # roads (draw faint first, rapid transit last) with smoothing + casing
    order = ["arterial", "rail", "freight_rail", "brt", "highway", "subway"]
    lines = sorted(sub.get("transit", []),
                   key=lambda l: order.index(l["type"]) if l["type"] in order else 0)
    for ln in lines:
        if ln["type"] not in ROAD:
            continue
        col, wcore, wcase, dashed = ROAD[ln["type"]]
        pts = np.array(ln["path"], float)
        sm = chaikin(pts, 2) if len(pts) >= 3 else pts
        if wcase:
            ax.plot(sm[:, 0], sm[:, 1], color="#23262e", lw=wcase,
                    solid_capstyle="round", zorder=4)
        ax.plot(sm[:, 0], sm[:, 1], color=col, lw=wcore,
                ls="--" if dashed else "-", solid_capstyle="round", zorder=4.1)

    # stations, hubs, facilities
    for s in sub.get("stations", []):
        ax.add_patch(Circle((s["x"], s["y"]), cell * 0.45, facecolor="white",
                            edgecolor="#222", lw=0.7, zorder=5))
    for hb in sub.get("hubs", []):
        ax.add_patch(Circle((hb["x"], hb["y"]), cell * 1.6, facecolor="#1f2430",
                            edgecolor="white", lw=1.6, zorder=6))
        ax.add_patch(Circle((hb["x"], hb["y"]), cell * 0.55, facecolor="white", zorder=6.1))
    for f in sub.get("facilities", []):
        sym, c = FAC.get(f["type"], ("?", "#888"))
        ax.add_patch(FancyBboxPatch((f["x"] - cell * 1.3, f["y"] - cell * 1.3),
                                    cell * 2.6, cell * 2.6,
                                    boxstyle="round,pad=0,rounding_size=300",
                                    facecolor="white", edgecolor=c, lw=1.6, zorder=6))
        ax.text(f["x"], f["y"], sym, ha="center", va="center", fontsize=10,
                color=c, zorder=6.2, fontproperties=KRB)

    # events: dashed radius ring + center badge with letter
    for e in t.get("events", []):
        letter, klass, rc = event_style(e)
        ax.add_patch(Circle((e["x"], e["y"]), e["radius"], fill=False,
                            edgecolor=rc, ls="--", lw=1.2, alpha=0.85, zorder=5.5))
        ax.add_patch(Circle((e["x"], e["y"]), cell * 1.7, facecolor="white",
                            edgecolor=rc, lw=1.8, zorder=6.5))
        ax.text(e["x"], e["y"], letter, ha="center", va="center", fontsize=9.5,
                color=rc, fontproperties=KRB, zorder=6.6)

    # zone labels for sizeable polygons
    for z in sub.get("zones", []):
        if z["use"] not in ZONE_KR:
            continue
        poly = np.array(z["polygon"], float)
        area = abs(np.dot(poly[:, 0], np.roll(poly[:, 1], 1)) -
                   np.dot(poly[:, 1], np.roll(poly[:, 0], 1))) / 2 / 1e6
        if area < 12 and z["use"] not in ("CBD",):
            continue
        cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
        ax.text(cx, cy, ZONE_KR[z["use"]], ha="center", va="center",
                fontsize=8.5, color="#2a2a2a", fontproperties=KRB, zorder=7,
                path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])

    # lake label
    if water.any():
        ys, xs = np.where(water)
        ax.text(xs.mean() * cell, ys.mean() * cell, "호수", ha="center", va="center",
                fontsize=11, color="#3a6a90", fontproperties=KR, zorder=3.5,
                path_effects=[pe.withStroke(linewidth=2, foreground=WATER)])

    draw_panel(panel, t, sub)
    fig.savefig(out, facecolor="#191b1e", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return out


def draw_panel(ax, t, sub):
    ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    res = S.run(t, sub)
    y = 0.98
    ax.text(0, y, t.get("name", "City"), fontsize=15, color="white",
            fontproperties=KRB, va="top"); y -= 0.035
    ax.text(0, y, f"{t.get('terrain_type','')} · {t.get('objective','')}",
            fontsize=9.5, color="#aab0ba", fontproperties=KR, va="top"); y -= 0.05
    if res["status"] == "OK":
        ax.text(0, y, f"{res['score']}", fontsize=30, color="#ffd95a",
                fontproperties=KRB, va="top")
        ax.text(0.62, y - 0.005, f"({res['grade']})", fontsize=18, color="#ffd95a",
                fontproperties=KRB, va="top"); y -= 0.075
        for k in ("economy", "transport", "environment", "housing", "urban_form"):
            v = res["axes"][k]
            ax.text(0, y, k, fontsize=9, color="#cfd4db", fontproperties=KR, va="top")
            ax.text(1.0, y, f"{v:.0f}", fontsize=9, color="#cfd4db",
                    fontproperties=KR, va="top", ha="right"); y -= 0.022
            ax.add_patch(Rectangle((0, y), 1.0, 0.012, facecolor="#3a3e45",
                                   transform=ax.transData, clip_on=False))
            ax.add_patch(Rectangle((0, y), v / 200, 0.012, facecolor="#78c88c",
                                   transform=ax.transData, clip_on=False)); y -= 0.03
        y -= 0.01
        ax.text(0, y, f"목적적합 +{res['fit_bonus']}   난이도 ×{res['difficulty']}",
                fontsize=8.5, color="#aab0ba", fontproperties=KR, va="top"); y -= 0.03
        if res.get("events"):
            ax.text(0, y, f"이벤트 {res['event_score']:+.0f}", fontsize=9,
                    color="#e0c060", fontproperties=KRB, va="top"); y -= 0.025
            for e in res["events"]:
                c = "#8fdc8f" if e["net"] >= 0 else "#e09090"
                nm = EVENT_KR.get(e["type"], e.get("name") or e["type"])
                ax.text(0.04, y, f"{nm} {e['net']:+.0f}", fontsize=8,
                        color=c, fontproperties=KR, va="top"); y -= 0.022
            y -= 0.01
    else:
        ax.text(0, y, "FAILED", fontsize=18, color="#e65a5a",
                fontproperties=KRB, va="top"); y -= 0.05
        for r in res["reasons"][:4]:
            ax.text(0, y, "• " + r[:34], fontsize=7.5, color="#d69696",
                    fontproperties=KR, va="top"); y -= 0.025
        y -= 0.02

    present = [z["use"] for z in sub.get("zones", [])]
    seen = []
    ax.text(0, y, "구역", fontsize=11, color="white", fontproperties=KRB, va="top"); y -= 0.03
    for u in ZONE:
        if u in present and u not in seen:
            seen.append(u)
            ax.add_patch(Rectangle((0, y - 0.018), 0.05, 0.022, facecolor=ZONE[u],
                                   clip_on=False))
            ax.text(0.07, y, ZONE_KR[u], fontsize=8.5, color="#cfd4db",
                    fontproperties=KR, va="top"); y -= 0.027


def main():
    if len(sys.argv) < 3:
        print("usage: python3 render2.py terrain.json submission.json [out.png]"); sys.exit(1)
    out = sys.argv[3] if len(sys.argv) > 3 else "plan2.png"
    t = json.load(open(sys.argv[1])); sub = json.load(open(sys.argv[2]))
    print("rendered:", render(t, sub, out))


if __name__ == "__main__":
    main()
