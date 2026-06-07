# CityBench — 인수인계 메모 (v0.3)

## 1. 목표 (무엇을 만드는가)

게임 엔진이 아니라 **도시설계 벤치마크 플랫폼**이다. 흐름은:

> 출제자가 [지형 데이터셋 + 목표 + 예산 + 이벤트]를 제공 → 참가자가 그 위에 도시를
> **벡터(폴리곤/점/폴리라인)**로 설계해 제출 → **정적·결정론적 채점기**가 0~1000+점과
> 등급을 매기고 → 마스터플랜으로 시각화하고 → 리더보드로 순위를 낸다.

핵심 원칙:
- **정적 채점**: 시뮬레이션 없음. 채점기는 `(지형, 제출물) → 점수`인 순수 함수. 같은 입력 → 항상 같은 점수. 규칙 전부 공개 가능, 참가자가 로컬에서 자기 점수 확인 가능.
- **기능 기반 채점**(정답지 유사도 아님): 정답 맵이 없고, 도시의 성질로 채점. 서로 당기는 목표 + 하드 게이트로 "꼼수 만점"을 막는다.
- **규모**: 광역권(현재 100km×75km, 약 7,500km²). 도심뿐 아니라 교외·광역시설(공항/항만/발전소/화물철도 등)까지 계획.

## 2. 현재 상태 (동작하는 것)

전체 파이프라인이 닫혀 있고 전부 실행·검증됨:

`지형 생성 → (참가자) 벡터 제출 → 채점 → 시각화 → 리더보드`

- 지형 5종 생성기 (fBm 표고 기반, 이벤트 포함) ✅
- 채점기: GDD 1,000점 5축 + 목적적합 보너스 + 이벤트 +난이도 계수 + 등급 ✅
- 하드 게이트 4종 (수면/급경사 건설 금지, 예산, 연결성, 최소 용량) ✅
- 렌더러: 부드러운 호수/해안선, 곡선 도로, 폴리곤 구역, 라벨, 이벤트 링, 점수판 ✅
- 리더보드: 폴더 일괄 채점 + CSV + 누적막대 차트 ✅

데모 검증 점수(Lake Core #3 / Financial): **720.8 B**, 이벤트 +48(광맥 +45, 단층 0(회피), 유산지 +3).

## 3. 중요한 결정 (왜 이렇게 했는가)

1. **격자 제출 → 벡터 제출**: 7,500km²를 셀 격자로 제출하면 수십만 칸이라 LLM/참가자가 못 만든다. 그래서 제출은 폴리곤+점+폴리라인. 채점기가 내부에서 격자로 래스터화(현재 500m 셀). **래스터 해상도는 채점기 내부 노브일 뿐 제출 형식과 무관.**
2. **채점 = GDD 1,000점 5축**: 경제/교통/환경/주거/**도시구조** 각 200점. 도시구조축(스프롤 억제=인구 회전반경, 직주근접, 다핵화, CBD집중)이 광역+교외 설계의 핵심. 안 넣으면 외곽 확산이 이득이 됨.
3. **경쟁하는 목표 + 하드 게이트**: 녹지↔용량(같은 땅), 접근성↔예산(같은 돈)이 싸우게 설계. 단일 지표 몰빵 방지.
4. **목적적합 보너스(+최대 100)**: 같은 도시라도 목적(금융/물류/혁신/에코/관광)에 맞으면 가산. 금융용 도시를 물류로 채점하면 점수 하락(검증됨).
5. **난이도 계수(최종에 곱셈)**: Mountain Gate ×1.3 등. 어려운 맵 성공 시 더 높은 평가(GDD 의도).
6. **이벤트 = 좌표 기반 정적 피처**: "발견"이지만 정적 벤치마크이므로 시나리오에 미리 포함. 효과는 참가자 plan과의 관계로 계산(결정론 유지). 기회/재난/양면 3종 성격.
7. **렌더러는 matplotlib**(cairosvg 미설치). 채점기와 동일한 `rasterize()`를 써서 "보이는 도시 = 채점된 도시" 보장.

## 4. 파일 구성 (작업 디렉터리: 모든 파일 동일 폴더)

| 파일 | 역할 |
|---|---|
| `score_v2.py` | **채점기 본체**. 벡터→래스터, 5축, 목적적합, 이벤트, 난이도, 등급. `run(terrain, sub)` 반환 dict. CLI: `python3 score_v2.py terrain.json submission.json` |
| `geometry.py` | 폴리곤/폴리라인 래스터화 (`fill_polygon`, `raster_line`, `polyline_length_km`). score_v2가 import |
| `terrain_gen.py` | **지형 생성기 v0.3**. fBm 표고 → 물/경사/강/산림 + 이벤트. CLI: `python3 terrain_gen.py <type> <objective> [seed] [out.json]` |
| `render2.py` | **렌더러**(matplotlib). 마스터플랜 PNG + 점수판 + 이벤트. CLI: `python3 render2.py terrain.json submission.json [out.png]` |
| `leaderboard.py` | 폴더 일괄 채점 → 콘솔표 + CSV + 누적막대 PNG. CLI: `python3 leaderboard.py terrain.json submissions_dir/ [prefix]` |
| `render.py` | (구버전 PIL 렌더러, 격자 방식) — render2로 대체됨, 참고용 |
| `make_demo.py` | v0.2 데모 시나리오/제출물 생성기 (160×126 타원 호수) |
| `make_fitted.py` | 새 200×150 지형에 맞는 제출물 생성 + 지형 검증(buildable 체크) 예시 |
| `make_variants.py` | 리더보드용 제출물 변형(면적보존 이동) 생성 |
| `preview_terrains.py` | 5종 지형 몽타주 PNG |
| `BENCHMARK_SPEC_v2.md` | v0.2 스펙 문서 (이벤트/v0.3 반영은 아직 안 됨 → 갱신 필요) |
| `terrain_*.json` | 생성된 시나리오들 |
| `submission_*.json`, `submissions/` | 제출물 예시 |

## 5. 데이터 스키마

### 지형 `terrain.json`
```json
{
  "name": "...", "terrain_type": "Lake Core", "objective": "Financial Capital",
  "difficulty": 1.0, "cell_size_m": 500, "width": 200, "height": 150,
  "budget": 4736200, "targets": {"residents": 2960125, "jobs": 1480062},
  "events": [ {"type":"mineral_deposit","x":88250,"y":72250,"radius":4000,"resource":"iron"} ],
  "rows": ["....~~~~....", ...]   // '.' 건축가능 '~' 수면 '^' 급경사 'T' 산림
}
```
좌표 단위 = 미터, 원점 좌상단(x 동, y 남). `targets`/`budget`는 건축가능 면적에 자동 스케일.

### 제출 `submission.json`
```json
{
  "zones":      [ {"use":"CBD", "polygon":[[x,y],...]}, ... ],
  "facilities": [ {"type":"airport", "x":.., "y":..}, ... ],
  "transit":    [ {"type":"subway", "path":[[x,y],...]}, ... ],
  "stations":   [ {"x":.., "y":.., "type":"subway"} ],
  "hubs":       [ {"x":.., "y":..} ]
}
```
- zone use: `CBD COMMERCIAL RES_HIGH RES_MED RES_LOW SUBURB UNIVERSITY MEDICAL INDUSTRIAL LOGISTICS PUBLIC PARK GREENBELT`
- facility: `airport port freight_terminal power water_treatment waste`
- transit: `subway rail freight_rail highway brt arterial`
- 밀도/비용/속도 표는 `score_v2.py` 상단 `ZONES/FACILITY_COST/TRANSIT` 상수에 있음(전부 공개·튜닝용).

## 6. 채점 동작 요약

```
gates 통과 못하면 → status FAILED, score 0, reasons[]
통과 시 final = (5축합(0~1000) + 목적적합(0~100) + 이벤트(-180~+180)) × 난이도계수
등급 S≥950 / A≥850 / B≥720 / C≥580 / D
```
- **5축**: 각 200점, 하위지표는 score_v2의 `axis_*` 함수 참고.
- **이벤트 6종 효과**(`score_events`): mineral_deposit(산업 근접 +), deep_harbor(항만 +), oil_field(산업 +econ/−env), fault_line(개발 −), floodplain(녹지 +/주거 −), heritage_site(공원·저밀 +/산업·고밀 −).
- 게이트 연결성: 도로망 최대 컴포넌트가 95%+ & 모든 개발 존이 망 2km 내.

## 7. 알려진 이슈 / 함정

1. **벡터 제출물이 호수에 걸리면 게이트 FAIL**. 유기적(fBm) 호수는 불규칙해서 띠형 그린벨트/큰 사각형이 쉽게 물에 걸린다. → 제출 생성 시 buildable 검증 필요(`make_fitted.py`의 `buildable()` 패턴 참고). 참가자 가이드/검증기 제공 권장.
2. **이벤트 좌표가 호수변(coast)일 때** 인접 land가 좁아 녹지 배치가 까다로움(heritage가 종종 호숫가에 생성됨).
3. **렌더러 폰트**: 이모지 글리프는 Noto에 없음 → 시설/이벤트는 **글자**(A/P/F/E/W/X, M/H/O/!/F/G)로 표기. 한글은 `NotoSansCJK-*.ttc` 경로 하드코딩.
4. **scipy/skimage/matplotlib/numpy 필요**(terrain_gen, render2). cairosvg는 없음(쓰지 않음).
5. `render.py`(구 PIL)는 격자 방식이라 v0.3 지형/이벤트 미지원 — `render2.py` 사용.
6. 리더보드 변형 중 `02_sprawl`은 의도적으로 외곽 확산이 도로망 커버리지를 벗어나 **FAILED**(교훈용). 점수 그라데이션은 compact > balanced > transit_poor.
7. **BENCHMARK_SPEC_v2.md는 v0.2 기준** — width/height(현재 200×150), 이벤트 섹션이 미반영. 갱신 필요.
8. 좌표/래스터 정합: find_contours/래스터화는 셀 중심 `(c+0.5)*cell` 기준. 약간의 오프셋 가정이 코드 곳곳에 있음(일관성 유지할 것).

## 8. 남은 작업 (우선순위 순 제안)

1. **스펙 문서 v0.3 갱신**: 200×150, 이벤트 6종 효과/점수식, 등급컷, 전체 CLI를 한 문서에. (BENCHMARK_SPEC_v2.md 확장)
2. **제출물 검증기 + 가이드**: 참가자용 `validate.py`(게이트만 빠르게 체크 + 호수/예산/연결성 위반 위치 리포트). 벡터 폴리곤 작성 가이드.
3. **목적별 모범답안(reference solutions)**: 5목적 각각 고득점 제출물 세트 → 채점 분포·밸런스 검증의 기준선.
4. **25개 조합 밸런스 테스트**: 지형5×목적5에서 난이도 계수가 실제로 공정한지(평균 점수 분포) 자동 측정 스크립트.
5. **이벤트 확장**: 효과 함수가 현재 단순 비례. 시너지(예: 광맥+화물철도+항만 동시 보유 시 추가 보너스), 이벤트 간 상호작용, 시드별 이벤트 다양화.
6. **지형 추가 디테일(욕심 항목)**: 강이 호수/바다로 실제 합류, 등고선/표고 음영 렌더, 토지피복 다양화(습지/농지), 해안선 더 자연스럽게.
7. **README + 실행 예시**: 신규 사용자가 5분 내 한 판 돌리는 walkthrough.
8. (선택) 웹 제출/시각화 UI, 결과 비교 대시보드.

## 9. 빠른 재현 (스모크 테스트)

```bash
# 지형 생성 (이벤트 포함)
python3 terrain_gen.py lake_core "Financial Capital" 3 terrain_lake_core.json

# 지형에 맞는 데모 제출물 생성 + 채점 (buildable 검증 포함)
python3 make_fitted.py            # -> submission_lakecore3.json, 점수/이벤트 출력

# 마스터플랜 렌더
python3 render2.py terrain_lake_core.json submission_lakecore3.json plan.png

# 리더보드 (구 v0.2 데모 시나리오 기준; 새 지형용은 제출물 폴더 별도 구성 필요)
python3 leaderboard.py terrain_lakecore.json submissions/ leaderboard
```

기대 결과: make_fitted → `OK 720.8 B event 48.4` (광맥 +45 / 단층 0 / 유산지 +3).

## 10. 튜닝 포인트 (값을 바꾸려면)

- 축 가중치/등급컷/난이도: `score_v2.py` 상단 `AXIS_W`, `GRADES`, terrain의 `difficulty`.
- 밀도/비용/속도: `score_v2.py` `ZONES / FACILITY_COST / TRANSIT`.
- 정규화 기준: `REF_COMMUTE_H, REF_GREEN, REF_RG_KM` 등.
- 이벤트 크기/반경/효과: `score_v2.py` `score_events()`와 terrain의 events.
- 지형 형태/해상도: `terrain_gen.py` `W,H,CELL`, `shape()`, `SEA`, river `thr`.
