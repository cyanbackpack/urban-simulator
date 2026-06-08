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
- 제출물 하드 게이트 검증기 + 구조 스키마 검증기 (`schema.py`)
- 25개 모범답안(elite) 세트 + 베이스라인(reference) 세트
- 웹 뷰어 + 채점 UI + 지형×목적 비교 대시보드
- 회귀 테스트 + GitHub Actions CI

## 채점 풀 구조 (모범답안 vs 베이스라인)

두 가지 결정론적 제출물 풀로 채점 분포를 고정합니다.

- **베이스라인** (`make_reference.py`): 벤치마크의 바닥. 멀티시드에서 S가
  나오지 않고 B 중심으로 모입니다. 목표 분포는 `balance_multiseed.py --check`로
  강제합니다 (실패 0, S 0%, A ≤ 30%, 지형 간 평균 격차 ≤ 110점).
- **엘리트(모범답안)** (`make_elite.py`): 공개 모범답안. 모든 케이스가 **최소 A**,
  일부는 **S 도달을 증명**합니다. 25개 세트는 `make_elite_set.py`로 생성되어
  `submissions_elite/`에 저장됩니다.

```bash
python balance_multiseed.py --check       # 베이스라인 분포가 목표 안에 있는지
python make_elite_set.py --check          # 25개 모범답안 A-바닥/S-증명 + 파일 생성
python run_tests.py                        # 전체 회귀 테스트 (stdlib unittest)
```

## 빠른 실행

```powershell
python terrain_gen.py lake_core "Financial Capital" 3 terrain_lake_core.json
python make_fitted.py
python make_reference.py terrain_lake_core.json submission_reference_lake_core.json
python make_elite.py terrain_lake_core.json submission_elite_lake_core.json
python validate.py terrain_lake_core.json submission_lakecore3.json
python schema.py submission_lakecore3.json
python score_v2.py terrain_lake_core.json submission_lakecore3.json
python render2.py terrain_lake_core.json submission_lakecore3.json plan_v04.png
python render_terrain.py terrain_lake_core.json terrain_lake_core_detailed.png
python preview_terrains.py terrain_preview_v04.png
python leaderboard.py terrain_lake_core.json submissions_demo leaderboard_lakecore
python balance_multiseed.py
```

## 웹 UI (뷰어 + 채점)

의존성 없이 표준 라이브러리만으로 동작하는 로컬 웹 서버입니다. 기존 채점기
(`score_v2.py`)와 기준 제출물 생성기(`make_reference.py`)를 그대로 호출하므로
"화면에 보이는 도시 = 채점된 도시"가 보장됩니다.

```bash
python webapp.py 8000        # 포트 생략 시 8000
# 브라우저에서 http://localhost:8000 접속
```

- 지형 드롭다운에서 시나리오 선택 → Canvas에 지형/이벤트 렌더링
- "기준 제출물"로 베이스라인을 즉시 채점, 제출 JSON 업로드/내보내기
- 5축 막대, 등급, 목적 적합/이벤트 점수, 예산·용량, 게이트 실패 사유 표시
- 색상 팔레트는 `render2.py`(PNG 렌더러)와 동일

### 편집기 (브라우저 내 도시 설계)

- **도구**: 선택/이동(V), 구역(Z), 교통(T), 시설(F), 역(S), 허브(H), 이벤트(E) — 단축키 지원
- **역·허브**: 캔버스에서 직접 배치/드래그/삭제. 허브 개수는 교통축 점수
  (`t_hub`)와 예산에 반영(역은 시각화/스키마용)
- **구역 그리기**: 클릭으로 정점 추가, 시작점 근처 클릭/Enter/더블클릭으로 자동
  닫기, 그리는 동안 면적(km²) 실시간 표시, 기존 구역과 **겹침 경고**
- **점 드래그**: 선택 모드에서 구역 정점·시설·이벤트를 끌어 이동, 드래그 중
  좌표/면적 표시
- **Undo / Redo**: 모든 편집에 대해 (Ctrl+Z / Ctrl+Y, 버튼)
- **스냅/그리드**: 격자(0.5/1/2.5 km) 표시 + 정점·점 배치/드래그를 격자에 스냅
- **구역 색상·라벨**: 중심·상업 / 주거 / 산업·물류 / 공공·교육·의료 / 녹지
  카테고리로 그룹화한 팔레트와 범례, 지도 위 색상 라벨 칩
- **이벤트 레이어 편집**: 지도의 이벤트를 클릭해 종류·성격(기회/재난/양면)·효과
  설명·점수 반영을 확인, 원하는 좌표에 이벤트(반경 지정) 추가/이동/삭제.
  편집한 이벤트는 `POST /api/score`의 `events` 오버라이드로 전달되어 **실제
  채점기로 점수 변화를 즉시 확인** 가능

### 리더보드 · 비교

헤더의 "리더보드" 버튼은 제출물 폴더(`submissions_demo/`)를 현재 지형으로 일괄
채점해 순위표를 보여줍니다. 5축 미니 막대로 제출물을 비교하고, 현재 편집 중인
제출물이 채점되어 있으면 같은 표에 "현재 작업" 행으로 끼워 넣어 내 순위를
확인할 수 있습니다. 각 행의 "불러오기"로 해당 제출물을 편집기에 띄울 수 있습니다.

### 비교 대시보드 (지형 × 목적 매트릭스)

헤더의 "대시보드" 버튼은 `GET /api/dashboard`로 **모범답안(elite)과 베이스라인
(reference) 세트를 전 지형 × 전 목적 매트릭스로 즉시 채점**합니다. 각 세트를
등급 히트맵(행=난이도순 지형, 열=목적, 셀=등급+점수, 우측=지형별 평균)으로
보여주고, 하단에 등급 분포 요약을 출력해 엘리트(A 이상, S 다수)와 베이스라인
(B 중심, S 없음)의 분리를 한눈에 확인할 수 있습니다.

엔드포인트: `GET /api/terrains`, `GET /api/terrain?file=`,
`GET /api/reference?file=`, `GET /api/submissions?dir=`,
`GET /api/submission?dir=&file=`, `GET /api/leaderboard?file=&dir=`,
`GET /api/dashboard?dir=`, `POST /api/score`(`{terrain_file, submission, events?}`).

`terrain_gen.py`와 `render2.py`는 SciPy/Matplotlib이 없어도 fallback으로 동작합니다. 기본적으로는 `numpy`와 `Pillow`가 필요합니다.

## 주요 파일

- `terrain_gen.py`: 지형/이벤트 생성기
- `score_v2.py`: 채점기 본체
- `geometry.py`: 벡터 폴리곤/폴리라인 래스터화 유틸
- `render2.py`: 마스터플랜 렌더러
- `render_terrain.py`: 상세 지형 전용 렌더러
- `preview_terrains.py`: 5개 지형 미리보기 몽타주 생성기
- `validate.py`: 제출물 하드 게이트 검증기
- `make_reference.py`: 베이스라인(기준) 제출물 생성기
- `make_elite.py`: 모범답안(elite) 제출물 생성기 (목표치 기반 면적, hazard 회피
  컴팩트 앵커, 다핵 일자리, 6개 허브, 이벤트 정렬 시설)
- `make_elite_set.py`: 5지형 x 5목적 = 25개 모범답안 + 베이스라인 세트 생성·채점
- `leaderboard.py`: 제출물 폴더 일괄 채점 및 CSV/PNG 리더보드 생성
- `balance_test.py`: 5지형 x 5목적 단일 시드 밸런스 테스트
- `balance_multiseed.py`: 멀티시드 베이스라인 스윕 + 목표 분포 검사(`--check`)
- `schema.py`: 제출물 구조 스키마 검증기 (의존성 없음)
- `run_tests.py` / `tests/`: 회귀 테스트 (golden 점수, 밸런스 envelope,
  엘리트 A-바닥/S-증명, 스키마)
- `.github/workflows/ci.yml`: 푸시/PR마다 컴파일 + 테스트 + 밸런스/엘리트 검사
- `BENCHMARK_SPEC_v04.md`: 현재 벤치마크 스펙
- `make_fitted.py`: Lake Core 데모 제출물 생성기
- `webapp.py`: 웹 뷰어 + 채점 서버 (stdlib), 프론트엔드는 `web/`
- `web/`: 웹 UI 정적 자산 (`index.html`, `app.js`, `style.css`)
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
- 5지형 x 5목적 밸런스 보정 (완료)
- 웹 UI: 브라우저 내 폴리곤 편집, 리더보드/비교 대시보드
- 실제 GIS/OSM/DEM 데이터 파이프라인
