# Project Status

Last checked: 2026-06-07

## Completed

- [x] Initial GitHub repository push.
- [x] Deterministic vector submission scorer.
- [x] Five terrain archetypes.
- [x] Richer v0.4 procedural terrain layers: elevation, water, slope, forest, wetland, farmland, climate metadata.
- [x] Static event system with opportunity, hazard, and mixed event classes.
- [x] Event scoring for resources, harbor, flood, fault, wind, aquifer, scenic, geothermal, fertile soil, landslide, typhoon, and subsidence.
- [x] Master-plan renderer with fallback PIL path.
- [x] Detailed terrain-only renderer for map-like visual QA.
- [x] Five-terrain preview montage.
- [x] Submission hard-gate validator.
- [x] Benchmark spec v0.4.
- [x] Baseline reference submission generator.
- [x] Leaderboard batch scoring script.
- [x] 5 terrain x 5 objective balance-test runner.

## Current Verification

- [x] `python -m py_compile geometry.py terrain_gen.py score_v2.py render2.py render_terrain.py preview_terrains.py validate.py make_fitted.py`
- [x] Generate all five v0.4 terrain JSON files.
- [x] Generate Lake Core fitted demo submission.
- [x] Score Lake Core demo submission.
- [x] Render planning map PNG.
- [x] Render detailed terrain PNG.
- [x] Render five-terrain preview PNG.
- [x] Validate demo submission with `validate.py`.
- [x] Generate Lake Core reference submission with `make_reference.py`.
- [x] Generate leaderboard CSV/PNG with `leaderboard.py`.
- [x] Run 25-combination balance test with `balance_test.py`.

Balance sweep before calibration, seed 3:

- Cases: 25, OK: 25, Failed: 0
- Average OK score: 878.4
- Grade spread: S 7, A 8, B 8, C 2
- Note: baseline reference plans were reaching S far too often. The terrain
  difficulty factor multiplied the whole (already-high) score, and the economy
  axis saturated near 200 for any plan that merely met its targets.

## Calibration target distribution (decided)

The benchmark is tuned around two named pools:

- **Baseline pool** (`make_reference.py`): the floor -- competent but
  unoptimised plans. Target envelope (enforced by `balance_multiseed.py
  --check` and `tests/test_balance.py`): no hard-gate failures, **no S**,
  A <= 30%, C <= 30%, per-terrain mean spread <= 110 pts.
- **Elite pool** (`make_elite.py`): public model answers. Every case must
  reach **at least A**, and **S must be provably achievable** (the headroom
  above the baseline is real, not free).

Multi-seed baseline sweep (`balance_multiseed.py`, seeds 1,2,3,7,11):

- 125 cases, 125 OK, 0 failed (the reference arterial mesh now hugs the far
  edges, fixing the great_delta seed-7 connectivity failures).
- Grade spread: S 0 / A 15 / B 94 / C 16; average ~782.
- `DIFF_GAIN` 0.5 -> 0.4 compresses the per-terrain spread from ~115 to ~96
  while keeping harder maps rewarded (central_plain ~717 -> twin_coast ~813).
- Calibration knobs in `score_v2.py`: `DIFF_GAIN` (difficulty compression),
  `ECONOMY_STRETCH` (axis headroom), `FIT_BONUS_MAX` (fit cap), and
  `EVENT_POS_GAIN` (opportunity damping; hazard penalties kept full).

Elite model-answer set (`make_elite_set.py`, committed terrains, seed 3):

- 25 cases (5 terrains x 5 objectives), all A or better: **A 14 / S 11**.
- S proven on great_delta and mountain_gate across all objectives, plus
  several lake_core/twin_coast cases; baselines on the same matrix stay
  A 4 / B 18 / C 3 and never reach S -- clean separation.
- Saved as JSON pairs in `submissions_elite/` and `submissions_reference/`
  (+ `elite_set_report.csv`).

## Remaining Work

- [x] Write full benchmark spec v0.4.
- [ ] Add participant guide for vector polygon authoring.
- [x] Create baseline reference solutions for all five objectives.
- [x] Run 25-combination balance test: 5 terrains x 5 objectives.
- [x] Add leaderboard batch scoring script.
- [x] Tune reference solutions into high-scoring examples -- delivered as a
  separate elite model-answer set (`make_elite.py` / `make_elite_set.py`)
  so the baseline stays a genuine floor.
- [x] Calibrate difficulty multipliers and axis normalization, with a
  decided target distribution and multi-seed verification.
- [x] Regression tests + CI: golden scores, baseline envelope, elite
  A-floor/S-proof, schema validation (`tests/`, `run_tests.py`,
  `.github/workflows/ci.yml`); structural validator in `schema.py`.
- [ ] Add event synergy rules where useful, such as mineral + freight rail + harbor.
- [ ] Add participant package (prompt templates, good/bad examples) -- deferred.
- [ ] Add optional GIS/OSM/DEM data pipeline for real-world map fidelity -- deferred to v1.5+.
- [x] Add web submission and visualization UI. `webapp.py` + `web/` (stdlib
  server reusing `score_v2.run`) now includes an in-browser editor: draw/drag
  zones, transit, facilities; undo/redo; live area/coordinate readout; overlap
  warning; grouped zone palette/labels; and an editable event layer that scores
  through the real scorer via the `events` override on `POST /api/score`.
  Stations and hubs are editable in-canvas too (place/drag/delete; hub count
  feeds the transport axis). Snap-to-grid with a visible grid, plus a web
  leaderboard/comparison modal (batch-scores a submissions folder against the
  current terrain and ranks it alongside the working plan) are also in. A
  multi-terrain comparison dashboard (`GET /api/dashboard`, "대시보드" button)
  scores the elite and baseline sets across the whole terrain x objective
  matrix and renders them as grade heatmaps with a distribution summary.
  Remaining polish: richer charts and an in-browser submission gallery.

## Terrain Fidelity Note

The current renderer is a deterministic procedural visualization, not Google Maps imagery. Reaching actual Google Maps-level fidelity would require external geographic data such as DEM elevation, land-cover rasters, hydrography, roads, OSM features, or licensed map tiles. The current next-best path is to keep improving generated layers while keeping the benchmark deterministic and redistributable.
