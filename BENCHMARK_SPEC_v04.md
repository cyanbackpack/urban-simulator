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
  "planning_layers": {},
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

### Optional Planning Layers

Terrain files may include `planning_layers` for visualization and authoring support. These layers are deterministic map aids, not separate hidden scoring inputs.

- `contours`: elevation contour segments.
- `hydrology`: river centerlines, shorelines, watershed edges, floodplain edges, and basin/floodplain masks.
- `boundaries`: farmland, wetland, and steep-slope boundary segments.
- `development`: prime, conditional, restricted, and no-build suitability rows.
- `corridors`: road and rail/freight candidate axes.

The scorer remains compatible with terrain files that omit `planning_layers`.

## Terrain Archetypes

- `lake_core`: lake district with scenic waterfronts, aquifer constraints, mineral/upland events, and fault risk.
- `twin_coast`: coastal bay with harbor opportunity, typhoon exposure, wind corridors, and oil fields.
- `mountain_gate`: mountain basin with mineral resources, landslide risk, scenic ridges, and geothermal springs.
- `great_delta`: river delta with floodplain, harbor, aquifer, and subsidence events.
- `central_plain`: great plain with fertile soil, wind corridors, floodplain, and mineral events.

Each generated scenario also receives one deterministic seed-selected supplemental event, such as a heritage site, natural reserve, geothermal spring, wind corridor, or extra mineral deposit depending on terrain type. This keeps event mixes varied across seeds while preserving reproducibility.

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
final = (base_1000 + fit_bonus + event_score) * difficulty
```

`base_1000` is the sum of five 200-point axes.

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

### Event Synergy

Events can also interact. Current explicit synergy:

- `mineral_harbor_freight_synergy`: +35 event score when a terrain contains both `mineral_deposit` and `deep_harbor`, the mineral area has meaningful industrial/logistics development, a `freight_rail` line reaches the mineral area, and a `port` is placed near the deep harbor.

Synergy details are reported in the scorer's `events` output alongside normal event effects.

## CLI Tools

```powershell
python terrain_gen.py lake_core "Financial Capital" 3 terrain_lake_core.json
python make_reference.py terrain_lake_core.json submission_reference.json
python validate.py terrain_lake_core.json submission_reference.json
python score_v2.py terrain_lake_core.json submission_reference.json
python render2.py terrain_lake_core.json submission_reference.json plan.png
python render_terrain.py terrain_lake_core.json terrain_detail.png
python leaderboard.py terrain_lake_core.json submissions leaderboard
python balance_test.py balance_report.csv 3
```

## Current Limitations

- The terrain is procedural, not real GIS data.
- The reference generator is a baseline for testing, not a competitive solver.
- Balance is preliminary; difficulty multipliers and event effects need more calibration.
- No web submission UI exists yet.
