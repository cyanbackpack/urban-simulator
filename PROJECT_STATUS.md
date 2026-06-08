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
- [x] Browser-based polygon editor prototype.
- [x] Browser-based leaderboard comparison dashboard.

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

Latest balance sweep, seed 3:

- Cases: 25
- OK: 25
- Failed: 0
- Average OK score: 905.5
- Grade spread: S 11, A 4, B 7, C 3
- Note: baseline plans are currently strong enough that score calibration is likely too generous.

## Remaining Work

- [x] Write full benchmark spec v0.4.
- [ ] Add participant guide for vector polygon authoring.
- [x] Create baseline reference solutions for all five objectives.
- [x] Run 25-combination balance test: 5 terrains x 5 objectives.
- [x] Add leaderboard batch scoring script.
- [ ] Tune baseline reference solutions into high-scoring examples.
- [ ] Calibrate difficulty multipliers and axis normalization after the first 25-combination sweep.
- [ ] Add event synergy rules where useful, such as mineral + freight rail + harbor.
- [ ] Add optional GIS/OSM/DEM data pipeline for real-world map fidelity.
- [x] Add web submission and visualization UI.
- [ ] Connect the web editor directly to local scorer/validator through a backend service.

## Terrain Fidelity Note

The current renderer is a deterministic procedural visualization, not Google Maps imagery. Reaching actual Google Maps-level fidelity would require external geographic data such as DEM elevation, land-cover rasters, hydrography, roads, OSM features, or licensed map tiles. The current next-best path is to keep improving generated layers while keeping the benchmark deterministic and redistributable.
