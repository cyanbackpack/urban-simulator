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

## 빠른 실행

```powershell
python terrain_gen.py lake_core "Financial Capital" 3 terrain_lake_core.json
python make_fitted.py
python score_v2.py terrain_lake_core.json submission_lakecore3.json
python render2.py terrain_lake_core.json submission_lakecore3.json plan_v04.png
```

`terrain_gen.py`와 `render2.py`는 SciPy/Matplotlib이 없어도 fallback으로 동작합니다. 기본적으로는 `numpy`와 `Pillow`가 필요합니다.

## 주요 파일

- `terrain_gen.py`: 지형/이벤트 생성기
- `score_v2.py`: 채점기 본체
- `geometry.py`: 벡터 폴리곤/폴리라인 래스터화 유틸
- `render2.py`: 마스터플랜 렌더러
- `make_fitted.py`: Lake Core 데모 제출물 생성기
- `HANDOFF.md`: 인수인계 메모

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
- v0.3/v0.4 스펙 문서 정리
- 목적별 reference solution
- 5지형 x 5목적 밸런스 테스트
- 웹 UI 또는 비교 대시보드
