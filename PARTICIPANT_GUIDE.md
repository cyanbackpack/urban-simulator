# CityBench Participant Guide

CityBench submissions are vector master plans written as JSON. You can draw
them in the web editor, but the default intended workflow is AI-assisted
vibe coding in Codex, Claude Code, or a similar coding-agent environment.

## 5-Minute Run

```powershell
python web_server.py
```

Open `http://127.0.0.1:8765/web/`, load a terrain JSON, edit or inspect the
submission, then press `Validate` and `Score`.

For command-line validation:

```powershell
python validate.py terrain_lake_core.json submission_reference_lake_core.json
python score_v2.py terrain_lake_core.json submission_reference_lake_core.json
python render2.py terrain_lake_core.json submission_reference_lake_core.json plan.png
```

## Vibe-Coding Workflow

Give your coding agent the terrain JSON and ask it to produce or revise a
submission JSON. A good loop is:

1. Read terrain metadata: objective, budget, targets, rows, events, and
   planning layers.
2. Draft zones, facilities, transit, stations, and hubs in meters.
3. Run `validate.py`.
4. Fix hard-gate failures first.
5. Run `score_v2.py`.
6. Improve the weakest axis and event interactions.
7. Render with `render2.py` and inspect the map.

Suggested prompt:

```text
Read terrain_lake_core.json and submission_reference_lake_core.json.
Create a stronger CityBench submission JSON. Keep it under budget, avoid
water/steep cells, connect all developed zones to transit, exploit positive
events, buffer hazards with parks/greenbelts, then run validate.py and
score_v2.py until the result is OK.
```

## Submission Schema

Coordinates are meters from the top-left of the terrain.

```json
{
  "zones": [{"use": "CBD", "polygon": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]}],
  "facilities": [{"type": "airport", "x": 12000, "y": 8000}],
  "transit": [{"type": "subway", "path": [[0, 0], [5000, 0]]}],
  "stations": [{"type": "subway", "x": 2500, "y": 0}],
  "hubs": [{"x": 2500, "y": 0}]
}
```

## Hard Gates

The score is zero if any hard gate fails:

- No zones on water `~` or steep slope `^`.
- Total cost must stay within budget.
- The transport network must be mostly connected.
- Developed non-green zones must be close to the network.
- Residents and jobs must reach the required minimums.

Always fix hard gates before optimizing score.

## Scoring Priorities

- Economy: jobs, agglomeration, and budget efficiency.
- Transport: commute, mode share, congestion, and hubs.
- Environment: green coverage, sensitive-land protection, carbon, and water.
- Housing: supply, access, affordability, and quality.
- Urban form: compactness, proximity, centers, and sprawl control.

## Event Strategy

Positive events usually need matching land use or facilities:

- `deep_harbor`: add a port and logistics/industrial activity nearby.
- `mineral_deposit`: add industrial/logistics activity and freight access.
- `wind_corridor`: add power and compatible non-residential uses.
- `scenic_viewpoint`: favor parks, public, low-density, or tourism uses.
- `geothermal_spring`: favor public, university, medical, or park uses.

Hazards usually need buffers:

- `fault_line`, `landslide_zone`, `subsidence_zone`: avoid dense development.
- `floodplain`, `aquifer_recharge`: use parks/greenbelts and water treatment.
- `typhoon_corridor`: buffer hard development with green uses.

Some event combinations can create explicit synergy bonuses, such as a mineral
deposit connected by freight rail to a developed deep-water harbor.

## Reference And Elite Examples

Baseline:

```powershell
python make_reference.py terrain_lake_core.json submission_reference_lake_core.json
```

Event-aware stronger example:

```powershell
python make_elite.py terrain_twin_coast.json submissions_elite/elite_twin_coast_logistics.json
python score_v2.py terrain_twin_coast.json submissions_elite/elite_twin_coast_logistics.json
```

The bundled elite example is expected to clear the S threshold.
