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

## Current Verification

- [x] `python -m py_compile geometry.py terrain_gen.py score_v2.py render2.py render_terrain.py preview_terrains.py validate.py make_fitted.py`
- [x] Generate all five v0.4 terrain JSON files.
- [x] Generate Lake Core fitted demo submission.
- [x] Score Lake Core demo submission.
- [x] Render planning map PNG.
- [x] Render detailed terrain PNG.
- [x] Render five-terrain preview PNG.
- [x] Validate demo submission with `validate.py`.

## Remaining Work

- [ ] Write full benchmark spec v0.4.
- [ ] Add participant guide for vector polygon authoring.
- [ ] Create reference solutions for all five objectives.
- [ ] Run 25-combination balance test: 5 terrains x 5 objectives.
- [ ] Add leaderboard batch scoring script.
- [ ] Add event synergy rules where useful, such as mineral + freight rail + harbor.
- [ ] Add optional GIS/OSM/DEM data pipeline for real-world map fidelity.
- [ ] Add web submission and visualization UI.

## Terrain Fidelity Note

The current renderer is a deterministic procedural visualization, not Google Maps imagery. Reaching actual Google Maps-level fidelity would require external geographic data such as DEM elevation, land-cover rasters, hydrography, roads, OSM features, or licensed map tiles. The current next-best path is to keep improving generated layers while keeping the benchmark deterministic and redistributable.
