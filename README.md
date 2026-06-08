# urban-simulator

CityBench / Urban Master Planner prototype.

도시설계 벤치마크 플랫폼 프로토타입입니다. 참가자는 지형 위에 도시를 벡터 데이터로 설계하고, 정적·결정론적 채점기가 점수와 등급을 계산합니다.

## 현재 포함된 기능

- 절차적 지형 생성: 호수권, 해안권, 산악 분지, 하구 삼각주, 대평원
- 지형 레이어: 고도, 수계, 경사, 숲, 습지, 농지, 기후 메타데이터
- 정적 이벤트: 자원, 항만 입지, 단층, 범람원, 태풍, 풍력, 대수층, 침하 등
- 벡터 제출물 채점: 구역 폴리곤, 시설 점, 교통 폴리라인
- 1,000점 5축 평가: 경제, 교통, 환경, 주거, 도시구조
- 목적 적합 보너스, 이벤트 점수, 난이도 계수
- PNG 마스터플랜 렌더링
- 위성지도/지형도 스타일의 상세 지형 렌더링
- 제출물 하드 게이트 검증기

## 빠른 실행

```powershell
python terrain_gen.py lake_core "Financial Capital" 3 terrain_lake_core.json
python make_fitted.py
python make_reference.py terrain_lake_core.json submission_reference_lake_core.json
python validate.py terrain_lake_core.json submission_lakecore3.json
python score_v2.py terrain_lake_core.json submission_lakecore3.json
python render2.py terrain_lake_core.json submission_lakecore3.json plan_v04.png
python render_terrain.py terrain_lake_core.json terrain_lake_core_detailed.png
python preview_terrains.py terrain_preview_v04.png
python leaderboard.py terrain_lake_core.json submissions_demo leaderboard_lakecore
python balance_test.py balance_report.csv 3
```

`terrain_gen.py`와 `render2.py`는 SciPy/Matplotlib이 없어도 fallback으로 동작합니다. 기본적으로는 `numpy`와 `Pillow`가 필요합니다.

## 주요 파일

- `terrain_gen.py`: 지형/이벤트 생성기
- `score_v2.py`: 채점기 본체
- `geometry.py`: 벡터 폴리곤/폴리라인 래스터화 유틸
- `render2.py`: 마스터플랜 렌더러
- `render_terrain.py`: 상세 지형 전용 렌더러
- `preview_terrains.py`: 5개 지형 미리보기 몽타주 생성기
- `validate.py`: 제출물 하드 게이트 검증기
- `make_reference.py`: 지형별 기준 제출물 생성기
- `leaderboard.py`: 제출물 폴더 일괄 채점 및 CSV/PNG 리더보드 생성
- `balance_test.py`: 5지형 x 5목적 기준 밸런스 테스트
- `web/`: 폴리곤 편집기와 리더보드 비교 대시보드
- `BENCHMARK_SPEC_v04.md`: 현재 벤치마크 스펙
- `make_fitted.py`: Lake Core 데모 제출물 생성기
- `HANDOFF.md`: 인수인계 메모
- `PROJECT_STATUS.md`: 진행 상태와 남은 작업 체크리스트

## 지형 타입

- `lake_core`
- `twin_coast`
- `mountain_gate`
- `great_delta`
- `central_plain`

## 제출물 스키마 요약

```json
{
  "zones": [{"use": "CBD", "polygon": [[x, y], [x, y], [x, y]]}],
  "facilities": [{"type": "airport", "x": 12000, "y": 8000}],
  "transit": [{"type": "subway", "path": [[x, y], [x, y]]}],
  "stations": [{"type": "subway", "x": 54000, "y": 57000}],
  "hubs": [{"x": 54000, "y": 57000}]
}
```

좌표 단위는 미터이며, 원점은 좌상단입니다.

## 다음 작업 후보

- 참가자용 `validate.py`
- 참가자 가이드 문서
- 목적별 reference solution 고도화
- 5지형 x 5목적 밸런스 보정
- 웹 UI 또는 비교 대시보드
- 실제 GIS/OSM/DEM 데이터 파이프라인

## Terrain planning layers

Terrain JSON files now include optional `planning_layers` data for map-like urban planning views:

- `contours`: elevation contour segments with minor/major intervals.
- `hydrology`: river centerlines, shorelines, watershed edges, floodplain edges, and basin/floodplain masks.
- `boundaries`: farmland, wetland, and steep-slope boundary segments.
- `development`: prime, conditional, restricted, and no-build suitability rows.
- `corridors`: low-impact road and rail/freight candidate axes.

These layers are visual/planning aids. The deterministic scorer still uses the compact `rows`, vector submission geometry, terrain events, and terrain metadata.

## Web UI

```powershell
python web_server.py
```

Open `http://127.0.0.1:8765/web/`.

The editor can load terrain/submission JSON, show planning-grade terrain overlays, add or edit zone polygons, insert/delete vertices, place facilities, draw transit paths, run live validation/scoring through the local API, and export a submission JSON. The dashboard can load leaderboard and balance CSV files for score comparison.
