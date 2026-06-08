# CityBench Benchmark Spec v0.4

This document describes the current deterministic benchmark prototype in this repository.

## Goal

CityBench is a city-design benchmark, not a real-time city-building game. A scenario author provides terrain, objective, budget, targets, and events. A participant submits a vector master plan. The scorer returns a deterministic score, grade, axis breakdown, event effects, and hard-gate failures.

## Determinism

The scoring function is:

```text
score = f(terrain_json, submission_json)
```

There is no hidden simulation state. The same inputs should always return the same result.

## Terrain Schema

Terrain files use 500m cells over a 200 x 150 grid, or 100km x 75km.

```json
{
  "name": "Lake Core #3",
  "terrain_type": "Lake Core",
  "terrain_key": "lake_core",
  "objective": "Financial Capital",
  "difficulty": 1.05,
  "cell_size_m": 500,
  "width": 200,
  "height": 150,
  "budget": 5321400,
  "targets": {"residents": 3325875, "jobs": 1662937},
  "landcover_legend": {"T": "forest"},
  "climate": {"profile": "temperate lake basin"},
  "layer_stats": {},
  "elevation_m": [[123, 124]],
  "events": [],
  "rows": ["..TT~~"]
}
```

### Row Legend

- `.` open urbanizable land
- `T` forest / woodland
- `F` farmland / cultivated plain
- `w` wetland / soft flood-prone land
- `^` steep slope / cliff
- `~` open water

Water and steep cells are non-buildable. Forest and wetland are buildable but environmentally sensitive.

## Terrain Archetypes

- `lake_core`: lake district with scenic waterfronts, aquifer constraints, mineral/upland events, and fault risk.
- `twin_coast`: coastal bay with harbor opportunity, typhoon exposure, wind corridors, and oil fields.
- `mountain_gate`: mountain basin with mineral resources, landslide risk, scenic ridges, and geothermal springs.
- `great_delta`: river delta with floodplain, harbor, aquifer, and subsidence events.
- `central_plain`: great plain with fertile soil, wind corridors, floodplain, and mineral events.

## Submission Schema

```json
{
  "zones": [{"use": "CBD", "polygon": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]}],
  "facilities": [{"type": "airport", "x": 12000, "y": 8000}],
  "transit": [{"type": "subway", "path": [[0, 0], [5000, 0]]}],
  "stations": [{"type": "subway", "x": 2500, "y": 0}],
  "hubs": [{"x": 2500, "y": 0}]
}
```

Coordinates are in meters. The origin is the top-left corner; x increases east and y increases south.

## Zone Types

- `CBD`
- `COMMERCIAL`
- `RES_HIGH`
- `RES_MED`
- `RES_LOW`
- `SUBURB`
- `UNIVERSITY`
- `MEDICAL`
- `INDUSTRIAL`
- `LOGISTICS`
- `PUBLIC`
- `PARK`
- `GREENBELT`

Zone densities, costs, and dirty/green flags are published in `score_v2.py`.

## Facility Types

- `airport`
- `port`
- `freight_terminal`
- `power`
- `water_treatment`
- `waste`

## Transit Types

- `subway`
- `brt`
- `rail`
- `freight_rail`
- `highway`
- `arterial`

## Hard Gates

If any gate fails, the submission receives `status: FAILED`, score 0, and a list of reasons.

- No zones on water or steep cells.
- Total cost must be within budget.
- Transport network must be mostly connected.
- Every developed non-green zone must be near the network.
- Residents and jobs must each reach at least 40% of terrain targets.

## Score Formula

```text
effective_difficulty = 1 + (difficulty - 1) * DIFF_GAIN
final = (base_1000 + fit_bonus + event_score) * effective_difficulty
```

`base_1000` is the sum of five 200-point axes. The raw terrain `difficulty`
is compressed by `DIFF_GAIN` so that hard terrains stay rewarded without the
multiplier inflating an already-high base into an automatic S.

### Calibration Knobs

All live at the top of `score_v2.py` and are part of the published rulebook:

- `DIFF_GAIN` (0.4): how strongly terrain difficulty scales the final score.
  Lowered from 0.5 to compress the per-terrain spread (~115 -> ~96 pts) while
  still rewarding harder maps.
- `ECONOMY_STRETCH` (1.20): meeting the resident/job targets maps below 1.0 on
  the economy axis, so a plan that merely hits its targets does not max it out.
- `FIT_BONUS_MAX` (85): ceiling of the objective-fit bonus.
- `EVENT_POS_GAIN` (0.75): opportunity rewards are damped; hazard penalties are
  applied at full strength.

### Target Distribution (two pools)

The calibration is anchored by two deterministic submission pools:

- **Baseline** (`make_reference.py`): the floor. Verified by
  `balance_multiseed.py --check` over seeds 1,2,3,7,11: 125/125 OK, no S,
  A <= 30%, per-terrain mean spread <= 110 pts (grade spread S0/A15/B94/C16).
- **Elite** (`make_elite.py` / `make_elite_set.py`): public model answers.
  Every one of the 25 terrain x objective cases reaches at least A, and S is
  provably achievable (A14/S11 on the committed terrains). The same baselines
  on that matrix stay A4/B18/C3 -- the S headroom above the baseline is real,
  not free.

- Economy: jobs, agglomeration, fiscal base
- Transport: commute, transit service, congestion, hubs
- Environment: green ratio, ecological continuity, carbon, water protection
- Housing: supply, affordability, access, quality of life
- Urban form: jobs-housing proximity, polycentricity, CBD concentration, sprawl control

## Grades

- S: 950+
- A: 850+
- B: 720+
- C: 580+
- D: below 580

## Event Classes

- Opportunity: rewards aligned development or infrastructure.
- Hazard: penalizes exposed development.
- Mixed: can reward preservation/mitigation or penalize careless development.

Current event types include mineral deposits, deep harbor, oil field, fault line, floodplain, heritage site, natural reserve, landslide zone, typhoon corridor, wind corridor, aquifer recharge, scenic viewpoint, geothermal spring, fertile soil, and subsidence zone.

## CLI Tools

```powershell
python terrain_gen.py lake_core "Financial Capital" 3 terrain_lake_core.json
python make_reference.py terrain_lake_core.json submission_reference.json
python validate.py terrain_lake_core.json submission_reference.json
python score_v2.py terrain_lake_core.json submission_reference.json
python render2.py terrain_lake_core.json submission_reference.json plan.png
python render_terrain.py terrain_lake_core.json terrain_detail.png
python make_elite.py terrain_lake_core.json submission_elite.json
python make_elite_set.py --check
python schema.py submission_reference.json
python leaderboard.py terrain_lake_core.json submissions leaderboard
python balance_multiseed.py
python run_tests.py
```

## Current Limitations

- The terrain is procedural, not real GIS data.
- The reference generator is a deliberate baseline (the floor); the elite
  generator (`make_elite.py`) provides the competitive model answers.
- Difficulty multipliers, axis normalization, and event bonuses are calibrated
  to a decided two-pool target distribution and verified across seeds by the
  regression suite. Event-effect synergies can still be refined.
- GIS/OSM/DEM real-map fidelity is deferred to a later version.
