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
- 웹 뷰어 + 채점 UI (브라우저에서 지형/제출물 시각화 + 점수 확인)

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
- **구역 색상·라벨**: 중심·상업 / 주거 / 산업·물류 / 공공·교육·의료 / 녹지
  카테고리로 그룹화한 팔레트와 범례, 지도 위 색상 라벨 칩
- **이벤트 레이어 편집**: 지도의 이벤트를 클릭해 종류·성격(기회/재난/양면)·효과
  설명·점수 반영을 확인, 원하는 좌표에 이벤트(반경 지정) 추가/이동/삭제.
  편집한 이벤트는 `POST /api/score`의 `events` 오버라이드로 전달되어 **실제
  채점기로 점수 변화를 즉시 확인** 가능

엔드포인트: `GET /api/terrains`, `GET /api/terrain?file=`,
`GET /api/reference?file=`, `POST /api/score`(`{terrain_file, submission, events?}`).

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
