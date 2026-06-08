#!/usr/bin/env python3
"""
CityBench v0.2 scorer.

Static, deterministic. Input = terrain (coarse raster) + submission (VECTOR:
polygons / points / polylines, in meters). Scorer rasterizes the submission
internally and scores on the GDD 1,000-point, 5-axis system, then applies an
objective-fit bonus and a terrain difficulty multiplier, and assigns a grade.

    python3 score_v2.py terrain.json submission.json
"""
import json
import sys
import heapq
import math
from collections import deque

import geometry as G

# ===========================================================================
# CONFIG  (the published rulebook; everything tunable lives here)
# ===========================================================================
CELL_KM2 = None  # set from cell_size at runtime

# zone use -> residents/km2, jobs/km2, cost/km2, flags
ZONES = {
    "CBD":        dict(res=0,     job=40000, cost=5000),
    "COMMERCIAL": dict(res=1500,  job=12000, cost=2000),
    "RES_HIGH":   dict(res=15000, job=0,     cost=2500),
    "RES_MED":    dict(res=6000,  job=0,     cost=1200),
    "RES_LOW":    dict(res=2000,  job=0,     cost=500),
    "SUBURB":     dict(res=800,   job=0,     cost=200),
    "UNIVERSITY": dict(res=0,     job=6000,  cost=2500),
    "MEDICAL":    dict(res=0,     job=7000,  cost=3000),
    "INDUSTRIAL": dict(res=0,     job=5000,  cost=1500, dirty=True),
    "LOGISTICS":  dict(res=0,     job=3000,  cost=1000, dirty=True),
    "PUBLIC":     dict(res=0,     job=4000,  cost=1200),
    "PARK":       dict(res=0,     job=0,     cost=150,  green=True),
    "GREENBELT":  dict(res=0,     job=0,     cost=50,   green=True),
}
FACILITY_COST = {"airport": 30000, "port": 20000, "freight_terminal": 8000,
                 "power": 10000, "water_treatment": 5000, "waste": 4000, "hub": 6000}
DIRTY_FACILITY = {"airport", "port", "freight_terminal", "power", "waste"}

# transit type -> speed km/h, cost/km, freight?
TRANSIT = {
    "subway":      dict(speed=60, cost=4000),
    "brt":         dict(speed=35, cost=800),
    "rail":        dict(speed=80, cost=2500),
    "freight_rail":dict(speed=70, cost=2000, freight=True),
    "highway":     dict(speed=90, cost=1500),
    "arterial":    dict(speed=40, cost=300),
}
WALK_SPEED = 4.0  # km/h off-network

# terrain row classes
NON_BUILDABLE = {"~", "^"}
NATURAL_GREEN = {"T", "w"}
SENSITIVE_LAND = {"T", "w"}

# normalisation references
REF_COMMUTE_H = 1.0      # commute hours mapping to 0
REF_GREEN = 0.35         # green ratio mapping to 1.0
REF_RG_KM = 22.0         # radius of gyration mapping to 0 (sprawl)
TRANSIT_WALK_CELLS = 2   # within this many cells of transit = "served"
PARK_WALK_CELLS = 2
WATER_BUFFER = 1         # dirty cell must keep this clear of water

AXIS_W = {"economy": 200, "transport": 200, "environment": 200,
          "housing": 200, "urban_form": 200}

GRADES = [(950, "S"), (850, "A"), (720, "B"), (580, "C"), (0, "D")]

# ===========================================================================
# Terrain / raster build
# ===========================================================================
def load(path):
    with open(path) as f:
        return json.load(f)


def build_terrain(t):
    rows = t["rows"]
    h = len(rows); w = len(rows[0])
    land = [list(r) for r in rows]
    return land, w, h


def rasterize(t, sub):
    global CELL_KM2
    cell = t["cell_size_m"]
    CELL_KM2 = (cell / 1000.0) ** 2
    land, w, h = build_terrain(t)

    use = [[None] * w for _ in range(h)]
    res = [[0.0] * w for _ in range(h)]
    job = [[0.0] * w for _ in range(h)]
    green = [[False] * w for _ in range(h)]
    dirty = [[False] * w for _ in range(h)]
    speed = [[WALK_SPEED] * w for _ in range(h)]
    net = [[False] * w for _ in range(h)]

    # zones (later polygons overwrite earlier on overlap)
    for z in sub.get("zones", []):
        u = z["use"]
        if u not in ZONES:
            continue
        spec = ZONES[u]
        for cx, cy in G.fill_polygon(z["polygon"], cell, w, h):
            use[cy][cx] = u
            res[cy][cx] = spec["res"] * CELL_KM2
            job[cy][cx] = spec["job"] * CELL_KM2
            green[cy][cx] = spec.get("green", False)
            if spec.get("dirty"):
                dirty[cy][cx] = True

    # transit / roads
    for line in sub.get("transit", []):
        ty = line["type"]
        if ty not in TRANSIT:
            continue
        sp = TRANSIT[ty]["speed"]
        for cx, cy in G.raster_line(line["path"], cell, w, h):
            net[cy][cx] = True
            if sp > speed[cy][cx]:
                speed[cy][cx] = sp

    # facilities mark cells dirty
    for f in sub.get("facilities", []):
        cx, cy = G.m_to_cell(f["x"], f["y"], cell)
        if 0 <= cx < w and 0 <= cy < h and f["type"] in DIRTY_FACILITY:
            dirty[cy][cx] = True

    natural_green = [[land[y][x] in NATURAL_GREEN for x in range(w)] for y in range(h)]
    sensitive = [[land[y][x] in SENSITIVE_LAND for x in range(w)] for y in range(h)]

    return dict(cell=cell, w=w, h=h, land=land, use=use, res=res, job=job,
                green=green, natural_green=natural_green, sensitive=sensitive,
                dirty=dirty, speed=speed, net=net)


# ===========================================================================
# Cost & gates
# ===========================================================================
def total_cost(sub):
    c = 0.0
    for z in sub.get("zones", []):
        if z["use"] in ZONES:
            area = polygon_area_km2(z["polygon"])
            c += ZONES[z["use"]]["cost"] * area
    for f in sub.get("facilities", []):
        c += FACILITY_COST.get(f["type"], 0)
    for line in sub.get("transit", []):
        if line["type"] in TRANSIT:
            c += TRANSIT[line["type"]]["cost"] * G.polyline_length_km(line["path"])
    c += FACILITY_COST["hub"] * len(sub.get("hubs", []))
    return c


def polygon_area_km2(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0 / 1_000_000.0


def gates(t, sub, R):
    reasons = []
    land, w, h = R["land"], R["w"], R["h"]
    # 1 no build on water/steep
    for cy in range(h):
        for cx in range(w):
            if R["use"][cy][cx] and land[cy][cx] in NON_BUILDABLE:
                reasons.append(f"zone on non-buildable cell ({cx},{cy}) [{land[cy][cx]}]")
                break
        if reasons:
            break
    # 2 budget
    cost = total_cost(sub)
    if cost > t["budget"]:
        reasons.append(f"over budget: {int(cost)} > {t['budget']}")
    # 3 connectivity: network single component; developed cells near network
    comps = net_components(R["net"], w, h)
    if comps and max(comps) / sum(comps) < 0.95:
        reasons.append(f"transport network fragmented: largest piece only "
                       f"{max(comps)}/{sum(comps)} cells")
    near = near_network_grid(R)
    for cy in range(h):
        for cx in range(w):
            if R["use"][cy][cx] in ZONES and not ZONES[R["use"][cy][cx]].get("green"):
                if not near[cy][cx]:
                    reasons.append(f"developed cell ({cx},{cy}) not reachable from network")
                    break
        else:
            continue
        break
    # 4 minimum residents & jobs
    res = sum(sum(r) for r in R["res"]); job = sum(sum(j) for j in R["job"])
    tgt = t["targets"]
    if res < 0.4 * tgt["residents"]:
        reasons.append(f"too few residents: {int(res)} < {int(0.4*tgt['residents'])}")
    if job < 0.4 * tgt["jobs"]:
        reasons.append(f"too few jobs: {int(job)} < {int(0.4*tgt['jobs'])}")
    return reasons, cost


def net_components(net, w, h):
    seen = [[False] * w for _ in range(h)]
    comps = []
    for sy in range(h):
        for sx in range(w):
            if net[sy][sx] and not seen[sy][sx]:
                q = deque([(sx, sy)]); seen[sy][sx] = True; n = 0
                while q:
                    x, y = q.popleft(); n += 1
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx, ny = x+dx, y+dy
                        if 0<=nx<w and 0<=ny<h and net[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx]=True; q.append((nx,ny))
                comps.append(n)
    return comps


def near_network_grid(R):
    """BFS distance (cells) from network; True if within TRANSIT_WALK_CELLS+2."""
    w, h, net = R["w"], R["h"], R["net"]
    INF = 10**9
    dist = [[INF]*w for _ in range(h)]
    q = deque()
    for y in range(h):
        for x in range(w):
            if net[y][x]:
                dist[y][x]=0; q.append((x,y))
    while q:
        x,y=q.popleft()
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx,ny=x+dx,y+dy
            if 0<=nx<w and 0<=ny<h and dist[ny][nx]==INF:
                dist[ny][nx]=dist[y][x]+1; q.append((nx,ny))
    lim = TRANSIT_WALK_CELLS + 2
    return [[dist[y][x] <= lim for x in range(w)] for y in range(h)]


# ===========================================================================
# Travel-time field (network-aware Dijkstra from all job cells)
# ===========================================================================
def commute_field(R):
    w, h, cell = R["w"], R["h"], R["cell"]
    km = cell / 1000.0
    INF = float("inf")
    time = [[INF]*w for _ in range(h)]
    pq = []
    for y in range(h):
        for x in range(w):
            if R["job"][y][x] > 0:
                time[y][x] = 0.0
                heapq.heappush(pq, (0.0, x, y))
    while pq:
        t0, x, y = heapq.heappop(pq)
        if t0 > time[y][x]:
            continue
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if 0<=nx<w and 0<=ny<h and R["land"][ny][nx] != "~":
                step = km / R["speed"][ny][nx]  # hours to enter neighbour
                nt = t0 + step
                if nt < time[ny][nx]:
                    time[ny][nx] = nt
                    heapq.heappush(pq, (nt, nx, ny))
    return time


def multi_bfs(sources, R, blocked_water=True):
    w, h = R["w"], R["h"]
    INF = 10**9
    dist = [[INF]*w for _ in range(h)]
    q = deque()
    for x, y in sources:
        if 0<=x<w and 0<=y<h:
            dist[y][x]=0; q.append((x,y))
    while q:
        x,y=q.popleft()
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx,ny=x+dx,y+dy
            if 0<=nx<w and 0<=ny<h and dist[ny][nx]==INF:
                if blocked_water and R["land"][ny][nx]=="~":
                    continue
                dist[ny][nx]=dist[y][x]+1; q.append((nx,ny))
    return dist


# ===========================================================================
# Helpers for metrics
# ===========================================================================
def totals(R):
    res = sum(sum(r) for r in R["res"]); job = sum(sum(j) for j in R["job"])
    return res, job


def transit_served_fraction(R, sub):
    w, h, cell = R["w"], R["h"], R["cell"]
    stops = [(G.m_to_cell(s["x"], s["y"], cell)) for s in sub.get("stations", [])]
    stops += [(G.m_to_cell(hb["x"], hb["y"], cell)) for hb in sub.get("hubs", [])]
    # any transit cell also acts as accessible corridor
    src = [(x, y) for y in range(h) for x in range(w) if R["net"][y][x]]
    dist = multi_bfs(src, R, blocked_water=False) if src else None
    served = total = 0.0
    for y in range(h):
        for x in range(w):
            r = R["res"][y][x]
            if r > 0:
                total += r
                if dist and dist[y][x] <= TRANSIT_WALK_CELLS:
                    served += r
    return (served / total) if total else 0.0


def park_served_fraction(R):
    w, h = R["w"], R["h"]
    parks = [(x, y) for y in range(h) for x in range(w) if R["green"][y][x]]
    if not parks:
        return 0.0
    dist = multi_bfs(parks, R, blocked_water=False)
    served = total = 0.0
    for y in range(h):
        for x in range(w):
            r = R["res"][y][x]
            if r > 0:
                total += r
                if dist[y][x] <= PARK_WALK_CELLS:
                    served += r
    return (served / total) if total else 0.0


def industry_penalty_fraction(R):
    """fraction of residents within 1 cell of a dirty cell."""
    w, h = R["w"], R["h"]
    dirty = [(x, y) for y in range(h) for x in range(w) if R["dirty"][y][x]]
    if not dirty:
        return 0.0
    dist = multi_bfs(dirty, R, blocked_water=False)
    near = total = 0.0
    for y in range(h):
        for x in range(w):
            r = R["res"][y][x]
            if r > 0:
                total += r
                if dist[y][x] <= 1:
                    near += r
    return (near / total) if total else 0.0


def green_components(R):
    w, h = R["w"], R["h"]
    seen = [[False]*w for _ in range(h)]
    sizes = []
    for sy in range(h):
        for sx in range(w):
            if is_green_cell(R, sx, sy) and not seen[sy][sx]:
                q=deque([(sx,sy)]); seen[sy][sx]=True; n=0
                while q:
                    x,y=q.popleft(); n+=1
                    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=x+dx,y+dy
                        if 0<=nx<w and 0<=ny<h and is_green_cell(R, nx, ny) and not seen[ny][nx]:
                            seen[ny][nx]=True; q.append((nx,ny))
                sizes.append(n)
    return sizes


def is_green_cell(R, x, y):
    return R["green"][y][x] or (R["natural_green"][y][x] and R["use"][y][x] is None)


def sensitive_development_fraction(R):
    total = hit = 0
    for y in range(R["h"]):
        for x in range(R["w"]):
            if R["sensitive"][y][x]:
                total += 1
                if R["use"][y][x] and not R["green"][y][x]:
                    hit += 1
    return (hit / total) if total else 0.0


def job_clusters(R, thresh_frac=0.3):
    """connected components of high-job cells; returns list of total-jobs."""
    w, h = R["w"], R["h"]
    maxj = max((R["job"][y][x] for y in range(h) for x in range(w)), default=0)
    if maxj <= 0:
        return []
    thr = maxj * thresh_frac
    seen = [[False]*w for _ in range(h)]
    clusters = []
    for sy in range(h):
        for sx in range(w):
            if R["job"][sy][sx] >= thr and not seen[sy][sx]:
                q=deque([(sx,sy)]); seen[sy][sx]=True; tot=0.0
                while q:
                    x,y=q.popleft(); tot+=R["job"][y][x]
                    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=x+dx,y+dy
                        if 0<=nx<w and 0<=ny<h and R["job"][ny][nx]>=thr and not seen[ny][nx]:
                            seen[ny][nx]=True; q.append((nx,ny))
                clusters.append(tot)
    return sorted(clusters, reverse=True)


def radius_of_gyration_km(R):
    w, h, cell = R["w"], R["h"], R["cell"]
    km = cell/1000.0
    tot=0.0; cxm=0.0; cym=0.0
    for y in range(h):
        for x in range(w):
            r=R["res"][y][x]
            if r>0:
                tot+=r; cxm+=r*x; cym+=r*y
    if tot==0:
        return 0.0
    cxm/=tot; cym/=tot
    s=0.0
    for y in range(h):
        for x in range(w):
            r=R["res"][y][x]
            if r>0:
                s += r * (((x-cxm)**2 + (y-cym)**2) * km*km)
    return math.sqrt(s/tot)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


# ===========================================================================
# Axis scores
# ===========================================================================
def axis_economy(R, t):
    res, job = totals(R)
    e_jobs = clamp(job / t["targets"]["jobs"])
    clusters = job_clusters(R)
    total_j = sum(clusters) if clusters else 0
    top_share = (clusters[0] / job) if (clusters and job) else 0
    e_aggl = clamp((top_share - 0.15) / 0.45)
    taxbase = job * 2 + res
    e_fiscal = clamp(taxbase / (t["targets"]["jobs"] * 2 + t["targets"]["residents"]))
    sub = 0.4*e_jobs + 0.3*e_aggl + 0.3*e_fiscal
    return sub, dict(jobs=e_jobs, agglomeration=e_aggl, fiscal=e_fiscal)


def axis_transport(R, sub_in, t):
    time = commute_field(R)
    wsum=tot=0.0
    for y in range(R["h"]):
        for x in range(R["w"]):
            r=R["res"][y][x]
            if r>0:
                d=time[y][x]
                d=REF_COMMUTE_H*2 if d==float("inf") else d
                wsum+=d*r; tot+=r
    avg=wsum/tot if tot else REF_COMMUTE_H
    t_commute = clamp(1 - avg/REF_COMMUTE_H)
    t_mode = transit_served_fraction(R, sub_in)
    res, job = totals(R)
    net_km = sum(G.polyline_length_km(l["path"]) for l in sub_in.get("transit", []))
    load = (res+job)/(net_km*1000) if net_km else 9
    t_cong = clamp(1 - load/4.0)
    n_hub = len(sub_in.get("hubs", []))
    t_hub = clamp(n_hub/6.0)
    s = 0.35*t_commute + 0.30*t_mode + 0.20*t_cong + 0.15*t_hub
    return s, dict(commute=t_commute, mode_share=t_mode, congestion=t_cong, hubs=t_hub, avg_commute_h=round(avg,2))


def axis_environment(R, t):
    dev = sum(1 for y in range(R["h"]) for x in range(R["w"]) if R["use"][y][x])
    grn = sum(1 for y in range(R["h"]) for x in range(R["w"]) if R["green"][y][x])
    green_ratio = grn/dev if dev else 0
    env_green = clamp(green_ratio/REF_GREEN)
    sizes = green_components(R)
    env_eco = (max(sizes)/sum(sizes)) if sizes else 0
    habitat_impact = sensitive_development_fraction(R)
    env_eco = clamp(env_eco * (1 - 0.65 * habitat_impact))
    # carbon: better with transit share & compactness, worse with industry/sprawl
    mode = transit_served_fraction(R, {"stations": [], "hubs": []})
    rg = radius_of_gyration_km(R)
    dirty_cells = sum(1 for y in range(R["h"]) for x in range(R["w"]) if R["dirty"][y][x])
    carbon_idx = clamp(0.5*(rg/REF_RG_KM) + 0.3*(dirty_cells/max(1,dev)) + 0.2*(1-mode))
    env_carbon = clamp(1 - carbon_idx)
    # water: dirty cells adjacent to water hurt
    viol = water_violation(R)
    env_water = clamp(1 - viol)
    s = 0.30*env_green + 0.25*env_eco + 0.25*env_carbon + 0.20*env_water
    return s, dict(green=env_green, eco_continuity=round(env_eco,2),
                   carbon=round(env_carbon,2), water=round(env_water,2),
                   green_ratio=round(green_ratio,2),
                   sensitive_impact=round(habitat_impact,2))


def water_violation(R):
    w, h = R["w"], R["h"]
    dirty_n = bad = 0
    for y in range(h):
        for x in range(w):
            if R["dirty"][y][x]:
                dirty_n += 1
                touch = any(0<=x+dx<w and 0<=y+dy<h and R["land"][y+dy][x+dx] in ("~", "w")
                            for dx in (-1,0,1) for dy in (-1,0,1))
                if touch:
                    bad += 1
    return (bad/dirty_n) if dirty_n else 0.0


def axis_housing(R, t):
    res, job = totals(R)
    h_supply = clamp(res / t["targets"]["residents"])
    ratio = job/res if res else 0
    h_afford = clamp(1 - abs(ratio - 0.45)/0.45)
    # access: residents near network AND near jobs
    h_access = transit_served_fraction(R, {"stations": [], "hubs": []})
    park = park_served_fraction(R)
    ind = industry_penalty_fraction(R)
    h_qol = clamp(park - 0.5*ind)
    s = 0.30*h_supply + 0.25*h_afford + 0.25*h_access + 0.20*h_qol
    return s, dict(supply=round(h_supply,2), affordability=round(h_afford,2),
                   access=round(h_access,2), quality=round(h_qol,2))


def axis_urban_form(R, t):
    # structural jobs-housing proximity (nearest job, network-aware time)
    time = commute_field(R)
    wsum=tot=0.0
    for y in range(R["h"]):
        for x in range(R["w"]):
            r=R["res"][y][x]
            if r>0:
                d=time[y][x]; d=REF_COMMUTE_H*2 if d==float("inf") else d
                wsum+=d*r; tot+=r
    avg=wsum/tot if tot else REF_COMMUTE_H
    u_prox = clamp(1 - avg/REF_COMMUTE_H)
    clusters = job_clusters(R)
    n_centers = len(clusters)
    u_poly = clamp((n_centers-1)/3.0) if n_centers else 0    # reward 2-4 centers
    top_share = (clusters[0]/sum(clusters)) if clusters else 0
    u_cbd = clamp((top_share-0.2)/0.5)
    rg = radius_of_gyration_km(R)
    u_sprawl = clamp(1 - rg/REF_RG_KM)
    s = 0.30*u_prox + 0.20*u_poly + 0.20*u_cbd + 0.30*u_sprawl
    return s, dict(proximity=round(u_prox,2), polycentricity=round(u_poly,2),
                   cbd_concentration=round(u_cbd,2), sprawl_control=round(u_sprawl,2),
                   centers=n_centers, rg_km=round(rg,1))


# ===========================================================================
# Objective fit  (bonus up to +100)
# ===========================================================================
def objective_fit(R, sub_in, t, parts):
    obj = t.get("objective", "")
    fac = [f["type"] for f in sub_in.get("facilities", [])]
    tt = [l["type"] for l in sub_in.get("transit", [])]
    has = lambda *xs: all(x in fac or x in tt for x in xs)
    e, tr, en, ho, uf = parts
    if obj == "Financial Capital":
        f = 0.4*uf["cbd_concentration"] + 0.3*tr["mode_share"] + 0.3*(1 if "airport" in fac else 0)
    elif obj == "Innovation City":
        uni = any(z["use"] in ("UNIVERSITY","MEDICAL") for z in sub_in.get("zones",[]))
        f = 0.4*(1 if uni else 0) + 0.3*ho["access"] + 0.3*en["green"]
    elif obj == "Logistics Hub":
        f = 0.4*(1 if has("freight_rail") else 0) + 0.3*(1 if ("port" in fac or "freight_terminal" in fac) else 0) + 0.3*(1 if "highway" in tt else 0)
    elif obj == "Eco Metropolis":
        f = 0.4*en["carbon"] + 0.3*en["green"] + 0.3*tr["mode_share"]
    elif obj == "Tourism Capital":
        f = 0.4*en["green"] + 0.3*ho["quality"] + 0.3*tr["mode_share"]
    else:
        f = 0.0
    return clamp(f)


def grade(score):
    for thr, g in GRADES:
        if score >= thr:
            return g
    return "D"


# ===========================================================================
# Events  (coordinate features; effect computed from the plan, deterministic)
# ===========================================================================
EVENT_CLAMP = 180
IND = {"INDUSTRIAL", "LOGISTICS"}
GREEN_USE = {"PARK", "GREENBELT"}
PEOPLE = {"CBD", "RES_HIGH", "RES_MED", "RES_LOW", "SUBURB"}


def disc_coverage(R, ex, ey, radius, pred):
    """fraction of land cells within radius (m) of (ex,ey) satisfying pred(use)."""
    cell = R["cell"]; w, h = R["w"], R["h"]
    rc = radius / cell
    cx, cy = ex / cell, ey / cell
    x0, x1 = max(0, int(cx - rc)), min(w - 1, int(cx + rc))
    y0, y1 = max(0, int(cy - rc)), min(h - 1, int(cy + rc))
    land = hit = 0
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            if (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 > rc * rc:
                continue
            if R["land"][yy][xx] in NON_BUILDABLE:
                continue
            land += 1
            if pred(R["use"][yy][xx]):
                hit += 1
    return (hit / land) if land else 0.0


def disc_dirty_coverage(R, ex, ey, radius):
    cell = R["cell"]; w, h = R["w"], R["h"]
    rc = radius / cell
    cx, cy = ex / cell, ey / cell
    x0, x1 = max(0, int(cx - rc)), min(w - 1, int(cx + rc))
    y0, y1 = max(0, int(cy - rc)), min(h - 1, int(cy + rc))
    land = hit = 0
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            if (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 > rc * rc:
                continue
            if R["land"][yy][xx] in NON_BUILDABLE:
                continue
            land += 1
            if R["dirty"][yy][xx]:
                hit += 1
    return (hit / land) if land else 0.0


def network_within(R, ex, ey, radius):
    cell = R["cell"]
    cx, cy = ex / cell, ey / cell
    rc2 = (radius / cell) ** 2
    for y in range(R["h"]):
        for x in range(R["w"]):
            if R["net"][y][x] and (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= rc2:
                return True
    return False


def facility_within(sub, ex, ey, radius, ftype):
    for f in sub.get("facilities", []):
        if f["type"] == ftype and (f["x"] - ex) ** 2 + (f["y"] - ey) ** 2 <= radius ** 2:
            return True
    return False


def _point_segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def transit_within(sub, ex, ey, radius, ttype):
    for line in sub.get("transit", []):
        if line.get("type") != ttype:
            continue
        path = line.get("path", [])
        for a, b in zip(path, path[1:]):
            if _point_segment_distance(ex, ey, a[0], a[1], b[0], b[1]) <= radius:
                return True
    return False


def event_by_type(t, etype):
    for event in t.get("events", []):
        if event.get("type") == etype:
            return event
    return None


def score_event_synergies(R, sub, t):
    out = []
    total = 0.0
    mineral = event_by_type(t, "mineral_deposit")
    harbor = event_by_type(t, "deep_harbor")
    if mineral and harbor:
        mx, my, mr = mineral["x"], mineral["y"], mineral["radius"]
        hx, hy, hr = harbor["x"], harbor["y"], harbor["radius"]
        mineral_industry = disc_coverage(R, mx, my, mr, lambda z: z in IND) >= 0.12
        freight_access = transit_within(sub, mx, my, mr * 1.35, "freight_rail")
        port_access = facility_within(sub, hx, hy, hr * 1.2, "port")
        if mineral_industry and freight_access and port_access:
            gain = 35.0
            total += gain
            out.append({
                "type": "mineral_harbor_freight_synergy",
                "class": "opportunity",
                "name": "Mineral export chain",
                "resource": mineral.get("resource"),
                "gain": gain,
                "loss": 0.0,
                "net": gain,
            })
    return total, out


def score_events(R, sub, t):
    out = []
    total = 0.0
    for e in t.get("events", []):
        ty = e["type"]; ex, ey, rad = e["x"], e["y"], e["radius"]
        pos = neg = 0.0
        if ty == "mineral_deposit":
            u = disc_coverage(R, ex, ey, rad, lambda z: z in IND)
            pos = min(1, u / 0.25) * 45
        elif ty == "deep_harbor":
            pos = 50 if facility_within(sub, ex, ey, rad, "port") else 0
            pos += min(1, disc_coverage(R, ex, ey, rad, lambda z: z in IND) / 0.25) * 20
        elif ty == "oil_field":
            u = disc_coverage(R, ex, ey, rad, lambda z: z in IND)
            pos = min(1, u / 0.25) * 60
            neg = min(1, u / 0.25) * 40           # pollution
        elif ty == "fault_line":
            u = disc_coverage(R, ex, ey, rad, lambda z: z in PEOPLE or z in IND)
            neg = min(1, u / 0.30) * 70           # building on a fault = risk
        elif ty == "floodplain":
            g = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE)
            s = disc_coverage(R, ex, ey, rad, lambda z: z in PEOPLE)
            pos = min(1, g / 0.40) * 30
            neg = min(1, s / 0.30) * 50
        elif ty == "heritage_site":
            good = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE or z == "RES_LOW")
            bad = disc_coverage(R, ex, ey, rad, lambda z: z in IND or z in ("RES_HIGH", "CBD"))
            pos = min(1, good / 0.30) * 35
            neg = min(1, bad / 0.30) * 45
        elif ty == "natural_reserve":
            good = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE)
            bad = disc_coverage(R, ex, ey, rad, lambda z: z in PEOPLE or z in IND)
            pos = min(1, good / 0.35) * 45
            neg = min(1, bad / 0.25) * 70
        elif ty == "landslide_zone":
            u = disc_coverage(R, ex, ey, rad, lambda z: z in PEOPLE or z in IND)
            neg = min(1, u / 0.22) * 70
        elif ty == "typhoon_corridor":
            hard = disc_coverage(R, ex, ey, rad, lambda z: z in PEOPLE or z in IND)
            buffer = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE)
            pos = min(1, buffer / 0.35) * 25
            neg = min(1, hard / 0.30) * 65
        elif ty == "wind_corridor":
            pos = 40 if facility_within(sub, ex, ey, rad, "power") else 0
            pos += min(1, disc_coverage(R, ex, ey, rad, lambda z: z in ("INDUSTRIAL", "LOGISTICS", "PUBLIC")) / 0.25) * 15
            neg = min(1, disc_coverage(R, ex, ey, rad, lambda z: z in ("RES_HIGH", "CBD")) / 0.25) * 20
        elif ty == "aquifer_recharge":
            green = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE)
            people = disc_coverage(R, ex, ey, rad, lambda z: z in PEOPLE)
            dirty = disc_dirty_coverage(R, ex, ey, rad)
            pos = (35 if facility_within(sub, ex, ey, rad, "water_treatment") else 0)
            pos += min(1, green / 0.35) * 25
            neg = min(1, dirty / 0.12) * 45 + min(1, people / 0.35) * 20
        elif ty == "scenic_viewpoint":
            good = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE or z in ("RES_LOW", "SUBURB", "UNIVERSITY", "PUBLIC"))
            bad = disc_coverage(R, ex, ey, rad, lambda z: z in IND or z in ("CBD", "RES_HIGH"))
            pos = min(1, good / 0.32) * 40
            neg = min(1, bad / 0.25) * 35
        elif ty == "geothermal_spring":
            good = disc_coverage(R, ex, ey, rad, lambda z: z in ("UNIVERSITY", "MEDICAL", "PUBLIC", "PARK"))
            bad = disc_coverage(R, ex, ey, rad, lambda z: z in IND)
            pos = min(1, good / 0.25) * 45
            neg = min(1, bad / 0.25) * 25
        elif ty == "fertile_soil":
            low = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE or z in ("SUBURB", "RES_LOW"))
            hard = disc_coverage(R, ex, ey, rad, lambda z: z in IND or z in ("CBD", "RES_HIGH"))
            pos = min(1, low / 0.40) * 30
            neg = min(1, hard / 0.28) * 45
        elif ty == "subsidence_zone":
            buffer = disc_coverage(R, ex, ey, rad, lambda z: z in GREEN_USE)
            hard = disc_coverage(R, ex, ey, rad, lambda z: z in PEOPLE or z in IND)
            pos = min(1, buffer / 0.35) * 20
            neg = min(1, hard / 0.25) * 75
        elif ty == "bridge_chokepoint":
            if network_within(R, ex, ey, rad) or any((h["x"] - ex) ** 2 + (h["y"] - ey) ** 2 <= rad ** 2 for h in sub.get("hubs", [])):
                pos = 45
        net = pos - neg
        total += net
        out.append({"type": ty, "class": e.get("class"), "name": e.get("name"),
                    "resource": e.get("resource"),
                    "gain": round(pos, 1), "loss": round(neg, 1), "net": round(net, 1)})
    synergy_total, synergy_detail = score_event_synergies(R, sub, t)
    total += synergy_total
    out.extend(synergy_detail)
    total = max(-EVENT_CLAMP, min(EVENT_CLAMP, total))
    return total, out


# ===========================================================================
# Top level
# ===========================================================================
def run(t, sub):
    R = rasterize(t, sub)
    reasons, cost = gates(t, sub, R)
    if reasons:
        return {"status": "FAILED", "score": 0, "grade": "D", "reasons": reasons}

    e, ed = axis_economy(R, t)
    tr, trd = axis_transport(R, sub, t)
    en, end = axis_environment(R, t)
    ho, hod = axis_housing(R, t)
    uf, ufd = axis_urban_form(R, t)
    parts = (ed, trd, end, hod, ufd)

    axes = {"economy": e*200, "transport": tr*200, "environment": en*200,
            "housing": ho*200, "urban_form": uf*200}
    base = sum(axes.values())
    fit = objective_fit(R, sub, t, parts)
    bonus = fit * 100
    ev_total, ev_detail = score_events(R, sub, t)
    diff = t.get("difficulty", 1.0)
    final = (base + bonus + ev_total) * diff

    res, job = totals(R)
    return {
        "status": "OK",
        "score": round(final, 1),
        "grade": grade(final),
        "axes": {k: round(v, 1) for k, v in axes.items()},
        "objective": t.get("objective"),
        "objective_fit": round(fit, 2),
        "fit_bonus": round(bonus, 1),
        "event_score": round(ev_total, 1),
        "events": ev_detail,
        "difficulty": diff,
        "base_1000": round(base, 1),
        "detail": {"economy": ed, "transport": trd, "environment": end,
                   "housing": hod, "urban_form": ufd},
        "stats": {"residents": int(res), "jobs": int(job),
                  "spent": int(cost), "budget": t["budget"]},
    }


def main():
    if len(sys.argv) != 3:
        print("usage: python3 score_v2.py terrain.json submission.json"); sys.exit(1)
    t = load(sys.argv[1]); sub = load(sys.argv[2])
    print(json.dumps(run(t, sub), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
