#!/usr/bin/env python3
"""
CityBench Participant Rulebook Generator
Usage: python make_rulebook.py [output.pdf]
Generates a comprehensive Korean-language rulebook PDF.
"""

import os, sys, json, subprocess, tempfile
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, HRFlowable, PageBreak, KeepTogether, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rlcanvas
from PIL import Image

# ── Fonts ────────────────────────────────────────────────────────────────────
_WQY  = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
_MONO = '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf'
_MONOB= '/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf'

pdfmetrics.registerFont(TTFont('WQY',   _WQY))
pdfmetrics.registerFont(TTFont('Mono',  _MONO))
pdfmetrics.registerFont(TTFont('MonoB', _MONOB))

# ── Colour palette ────────────────────────────────────────────────────────────
C_NAVY   = HexColor('#1e3a5f')
C_BLUE   = HexColor('#2563eb')
C_TEAL   = HexColor('#0891b2')
C_SKY    = HexColor('#e0f2fe')
C_SLATE  = HexColor('#475569')
C_LIGHT  = HexColor('#f1f5f9')
C_YELLOW = HexColor('#fef3c7')
C_AMBER  = HexColor('#d97706')
C_RED    = HexColor('#dc2626')
C_GREEN  = HexColor('#16a34a')
C_PURPLE = HexColor('#7c3aed')

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

# ── Style helpers ─────────────────────────────────────────────────────────────
def S(name, **kw):
    defaults = dict(fontName='WQY', fontSize=10, leading=16, textColor=C_SLATE,
                    spaceAfter=4, spaceBefore=0)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

STYLES = {
    'h1':    S('h1',  fontSize=26, leading=34, textColor=C_NAVY,  fontName='WQY', spaceAfter=6, spaceBefore=8),
    'h2':    S('h2',  fontSize=18, leading=26, textColor=C_NAVY,  fontName='WQY', spaceAfter=4, spaceBefore=10),
    'h3':    S('h3',  fontSize=13, leading=20, textColor=C_BLUE,  fontName='WQY', spaceAfter=3, spaceBefore=7),
    'body':  S('body',fontSize=10, leading=16, textColor=C_SLATE, spaceAfter=4),
    'small': S('small',fontSize=8.5, leading=13, textColor=C_SLATE, spaceAfter=2),
    'code':  S('code', fontName='Mono', fontSize=8.5, leading=13,
                textColor=HexColor('#1e293b'), backColor=C_LIGHT,
                leftIndent=8, rightIndent=8, spaceBefore=3, spaceAfter=3),
    'caption': S('caption', fontSize=8, leading=12, textColor=C_SLATE,
                  alignment=TA_CENTER),
    'center': S('center', fontSize=10, leading=16, textColor=C_SLATE,
                  alignment=TA_CENTER),
    'label':  S('label',  fontSize=8.5, leading=12, textColor=white,
                  fontName='WQY', alignment=TA_CENTER),
}

# ── Coloured box flowable ─────────────────────────────────────────────────────
class ColorBox(Flowable):
    def __init__(self, content_para, bg=C_SKY, border=C_BLUE, radius=4, pad=8):
        super().__init__()
        self.content = content_para
        self.bg = bg; self.border = border
        self.radius = radius; self.pad = pad
        self._width = CONTENT_W

    def wrap(self, aW, aH):
        w, h = self.content.wrap(aW - 2*self.pad, aH)
        self._ch = h + 2*self.pad
        return aW, self._ch

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.setStrokeColor(self.border)
        c.setLineWidth(1)
        c.roundRect(0, 0, self._width, self._ch, self.radius, fill=1, stroke=1)
        self.content.drawOn(c, self.pad, self.pad)


# ── Section header banner ─────────────────────────────────────────────────────
class SectionBanner(Flowable):
    def __init__(self, number, title, color=C_NAVY):
        super().__init__()
        self.number = number; self.title = title; self.color = color
        self._height = 28

    def wrap(self, aW, aH):
        self._width = aW
        return aW, self._height

    def draw(self):
        c = self.canv
        # background band
        c.setFillColor(self.color)
        c.rect(0, 0, self._width, self._height, fill=1, stroke=0)
        # number badge
        c.setFillColor(HexColor('#ffffff30'))
        c.circle(self._height/2, self._height/2, self._height/2 - 2, fill=1, stroke=0)
        # text
        c.setFillColor(white)
        c.setFont('WQY', 10)
        c.drawCentredString(self._height/2, (self._height - 10)/2 + 1, self.number)
        c.setFont('WQY', 14)
        c.drawString(self._height + 10, (self._height - 14)/2 + 2, self.title)


# ── Utility: scale a PIL image to fit width, return BytesIO ──────────────────
def pil_to_rl(img_path, max_w_pt, max_h_pt=None):
    img = Image.open(img_path).convert('RGB')
    iw, ih = img.size
    scale = max_w_pt / iw
    if max_h_pt and ih * scale > max_h_pt:
        scale = max_h_pt / ih
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return buf, nw, nh


def rl_image(img_path, max_w_pt, max_h_pt=None):
    buf, w, h = pil_to_rl(img_path, max_w_pt, max_h_pt)
    return RLImage(buf, width=w, height=h)


# ── Generate terrain & plan images ───────────────────────────────────────────
TERRAINS = [
    ('lake_core',     '호수권 (Lake Core)',     'terrain_lake_core.json'),
    ('twin_coast',    '쌍해안 (Twin Coast)',    'terrain_twin_coast.json'),
    ('mountain_gate', '산악 분지 (Mountain Gate)', 'terrain_mountain_gate.json'),
    ('great_delta',   '하구 삼각주 (Great Delta)', 'terrain_great_delta.json'),
    ('central_plain', '대평원 (Central Plain)',  'terrain_central_plain.json'),
]

OBJECTIVES = [
    ('financial_capital', '금융 수도'),
    ('eco_metropolis',    '생태 메트로폴리스'),
    ('innovation_city',   '혁신 도시'),
    ('logistics_hub',     '물류 허브'),
    ('tourism_capital',   '관광 수도'),
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(cmd, cwd=BASE_DIR):
    result = subprocess.run(
        [sys.executable] + cmd, cwd=cwd,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  WARN: {' '.join(cmd[:2])} -> {result.stderr.strip()[:120]}")


def gen_images(tmp):
    """Generate terrain + plan images. Returns dicts: terrain_imgs, plan_imgs."""
    terrain_imgs = {}
    plan_imgs    = {}

    for key, label, tfile in TERRAINS:
        tpath = os.path.join(BASE_DIR, tfile)
        if not os.path.exists(tpath):
            print(f"  Generating terrain {key}...")
            parts = tfile.replace('terrain_','').replace('.json','').split('_',1)
            arch = parts[0]+'_'+parts[1] if len(parts)>1 else parts[0]
            run_script(['terrain_gen.py', arch, 'Financial Capital', '3', tpath])

        # terrain image
        timg = os.path.join(tmp, f'terrain_{key}.png')
        print(f"  Rendering terrain {label}...")
        run_script(['render_terrain.py', tpath, timg])
        if os.path.exists(timg):
            terrain_imgs[key] = timg

        # elite plan image (Financial Capital)
        elite_file = os.path.join(BASE_DIR,
            f'submissions_elite/elite_{key}_financial_capital.json')
        if os.path.exists(elite_file):
            pimg = os.path.join(tmp, f'plan_{key}.png')
            print(f"  Rendering plan {label}...")
            run_script(['render2.py', tpath, elite_file, pimg])
            if os.path.exists(pimg):
                plan_imgs[key] = pimg

    return terrain_imgs, plan_imgs


# ── Zone colour table (matches render2.py palette) ──────────────────────────
ZONE_TABLE_DATA = [
    ['구역 유형', '주민 밀도\n(명/km²)', '일자리\n(명/km²)', '비용\n(백만/km²)', '특성', '색상'],
    ['CBD',        '-',      '40,000', '5,000',  '핵심 업무지구',         '#e63946'],
    ['COMMERCIAL', '1,500',  '12,000', '2,000',  '상업·혼합용도',         '#f4a261'],
    ['RES_HIGH',   '15,000', '-',      '2,500',  '고밀 주거',             '#2a9d8f'],
    ['RES_MED',    '6,000',  '-',      '1,200',  '중밀 주거',             '#57cc99'],
    ['RES_LOW',    '2,000',  '-',      '500',    '저밀 주거',             '#80ed99'],
    ['SUBURB',     '800',    '-',      '200',    '외곽 주거',             '#c7f9cc'],
    ['UNIVERSITY', '-',      '6,000',  '2,500',  '대학·연구',             '#4895ef'],
    ['MEDICAL',    '-',      '7,000',  '3,000',  '의료 복합',             '#7b2d8b'],
    ['INDUSTRIAL', '-',      '5,000',  '1,500',  '제조·공업 (오염)',       '#adb5bd'],
    ['LOGISTICS',  '-',      '3,000',  '1,000',  '물류·창고 (오염)',       '#6c757d'],
    ['PUBLIC',     '-',      '4,000',  '1,200',  '공공·행정',             '#ffd166'],
    ['PARK',       '-',      '-',      '150',    '도시공원 (녹지)',        '#52b788'],
    ['GREENBELT',  '-',      '-',      '50',     '그린벨트 (녹지)',        '#1b4332'],
]

FACILITY_DATA = [
    ['시설 유형', '비용 (백만)', '설명'],
    ['airport',        '30,000', '공항 — 경제·물류 보너스'],
    ['port',           '20,000', '항만 — 심해항 이벤트 시너지'],
    ['freight_terminal', '8,000','화물 터미널 — 물류 허브 필수'],
    ['power',          '10,000', '발전소 — 도시 전력 공급'],
    ['water_treatment', '5,000', '수처리장 — 환경 점수'],
    ['waste',           '4,000', '폐기물 처리장 — 환경 점수'],
]

TRANSIT_DATA = [
    ['교통 유형', '속도 (km/h)', '비용 (백만/km)', '특성'],
    ['subway',       '60', '4,000', '지하철 — 고용량, 고비용'],
    ['brt',          '35',   '800', 'BRT — 버스 급행'],
    ['rail',         '80', '2,500', '철도 — 광역 도시연결'],
    ['freight_rail', '70', '2,000', '화물철도 — 물류 필수'],
    ['highway',      '90', '1,500', '고속도로 — 통행속도 최고'],
    ['arterial',     '40',   '300', '간선도로 — 기본 네트워크 (저비용)'],
]

EVENT_DATA = [
    ['이벤트 유형', '종류', '영향'],
    ['광물 매장지 (mineral)',      '기회', 'INDUSTRIAL + freight_rail 시너지'],
    ['심해 항만 (deep harbor)',    '기회', 'port 배치 시 물류·경제 보너스'],
    ['유전 (oil field)',           '기회/혼합', 'INDUSTRIAL + 근접 시 경제 보너스'],
    ['단층선 (fault line)',        '위험', '반경 내 개발 페널티'],
    ['범람원 (floodplain)',        '혼합', '비개발·습지 보존 시 환경 보너스'],
    ['문화유산 (heritage site)',   '혼합', 'GREENBELT 보호 시 보너스'],
    ['자연보전 (natural reserve)', '혼합', '미개발 유지 시 환경 보너스'],
    ['산사태 위험 (landslide)',    '위험', '반경 내 개발 페널티'],
    ['태풍 경로 (typhoon corridor)','위험', '고밀 개발 노출 페널티'],
    ['풍력 회랑 (wind corridor)',  '기회', '중밀 이하 개발 시 환경 보너스'],
    ['대수층 충전 (aquifer)',      '혼합', '불투수 면적 최소화 보너스'],
    ['경관 조망 (scenic viewpoint)','기회', 'PARK/GREENBELT 근접 시 주거 보너스'],
    ['지열 온천 (geothermal)',     '기회', '시설 배치 시 경제 보너스'],
    ['비옥 토지 (fertile soil)',   '기회', '농업·녹지 유지 시 환경 보너스'],
    ['침하 지역 (subsidence)',     '위험', '고밀 개발 구조물 페널티'],
]


# ── Scoring axes explanation ──────────────────────────────────────────────────
AXIS_DATA = [
    ('경제 (Economy)',       '200점', C_RED,
     '일자리 수, 집적 효과, 재정 기반. 목표 일자리 달성률 + COMMERCIAL/CBD 인접 보너스 + '
     '재정 수입(구역·시설 세수). ECONOMY_STRETCH로 단순 목표 달성 시 만점 미달.'),
    ('교통 (Transport)',     '200점', C_BLUE,
     '통근 시간, 대중교통 서비스율, 혼잡도, 환승 허브 수. 네트워크 속도 기반 평균 통근시간 '
     '계산 + 교통망 커버리지 + hub 개수 보너스.'),
    ('환경 (Environment)',   '200점', C_GREEN,
     '녹지 비율, 생태 연속성, 탄소 발자국, 수변 보호. 전체 면적 대비 PARK+GREENBELT 비율 + '
     '자연지(숲·습지) 보전 + 오염시설 거리.'),
    ('주거 (Housing)',       '200점', C_PURPLE,
     '주택 공급량, 주거 접근성, 삶의 질. 목표 인구 달성률 + 공원 접근 거리 + '
     '고밀/저밀 혼합 + 교통망 접근성.'),
    ('도시구조 (Urban Form)', '200점', C_AMBER,
     '직주 근접, 다핵 구조, CBD 집중, 스프롤 억제. 반경 집중도(Radius of Gyration) + '
     '고용 중심 다핵화 + CBD 면적 집중 + 개발 경계.'),
]


# ── Hard gates ───────────────────────────────────────────────────────────────
GATE_DATA = [
    ('수변·급경사 금지',  '물(~) 또는 급경사(^) 셀 위에 구역을 배치하면 즉시 FAILED.'),
    ('예산 초과',        '구역 면적×단가 + 시설비 + 교통망 연장×단가의 합이 budget을 초과하면 FAILED.'),
    ('교통망 연결성',    '교통 링크의 80% 이상이 하나의 연결 컴포넌트를 형성해야 함.'),
    ('개발지 접근성',    '비녹지 개발 구역은 반드시 교통망 셀 2칸 이내에 위치해야 함.'),
    ('목표 달성 최소선', '주민과 일자리가 각각 terrain 목표치의 40% 이상을 충족해야 함.'),
]

GRADE_DATA = [
    ('S', '950점 이상', C_PURPLE,  '세계 수준 — 최적화된 다핵 계획, 이벤트 완전 활용'),
    ('A', '850점 이상', C_BLUE,    '우수 — 모든 축 고르게 달성, 이벤트 반영'),
    ('B', '720점 이상', C_GREEN,   '양호 — 게이트 통과, 기본 구조 갖춤'),
    ('C', '580점 이상', C_AMBER,   '미흡 — 일부 축 약점'),
    ('D', '580점 미만', C_RED,     '불합격 수준 (게이트 통과 시에도)'),
]


# ── Build PDF ─────────────────────────────────────────────────────────────────
def p(text, style='body', **kw):
    return Paragraph(text, STYLES[style])


def sp(n=4):
    return Spacer(1, n)


def hr():
    return HRFlowable(width='100%', thickness=0.5, color=HexColor('#cbd5e1'),
                      spaceAfter=4, spaceBefore=4)


def table(data, col_widths=None, header_bg=C_NAVY, stripe=C_LIGHT):
    if col_widths is None:
        col_widths = [CONTENT_W / len(data[0])] * len(data[0])
    ncols = len(data[0])
    nrows = len(data)

    # convert strings to Paragraphs
    styled = []
    for ri, row in enumerate(data):
        sr = []
        for ci, cell in enumerate(row):
            if ri == 0:
                sr.append(Paragraph(str(cell), S('th', fontSize=8.5, textColor=white,
                                                   fontName='WQY', leading=13,
                                                   alignment=TA_CENTER)))
            else:
                align = TA_CENTER if ci > 0 else TA_LEFT
                sr.append(Paragraph(str(cell), S('td', fontSize=8.5,
                                                   fontName='WQY' if ci == 0 else 'WQY',
                                                   leading=13, alignment=align,
                                                   textColor=C_SLATE)))
        styled.append(sr)

    t = Table(styled, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('GRID',       (0, 0), (-1, -1), 0.3, HexColor('#94a3b8')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, stripe]),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0,0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',(0, 0), (-1, -1), 5),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def colored_badge(text, bg):
    return Paragraph(
        f'<font color="white">{text}</font>',
        S('badge', fontSize=9, backColor=bg, fontName='WQY',
          leading=14, alignment=TA_CENTER,
          leftIndent=4, rightIndent=4, borderPadding=2))


def build_pdf(out_path, terrain_imgs, plan_imgs):
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title='CityBench 참가자 룰북',
        author='CityBench Team',
    )
    story = []

    # ── 1. Cover ──────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 30 * mm),
        p('CityBench', 'h1'),
        p('참가자 룰북 (Participant Rulebook)', 'h2'),
        sp(6),
        HRFlowable(width='60%', thickness=2, color=C_BLUE, spaceAfter=8),
        sp(4),
        p('도시 마스터플랜 벤치마크 — v0.4', 'body'),
        sp(20),
        ColorBox(
            p('이 룰북은 CityBench 참가자를 위한 공식 안내서입니다.<br/>'
              '지형 종류, 제출물 형식, 채점 방식, 모범답안 예시,<br/>'
              'CLI 사용법까지 한 권에 담았습니다.', 'body'),
            bg=C_SKY, border=C_BLUE
        ),
        PageBreak(),
    ]

    # ── 2. Table of Contents ──────────────────────────────────────────────────
    story += [
        SectionBanner('', 'CityBench란 무엇인가?'),
        sp(6),
        p('CityBench는 <b>결정론적 도시설계 벤치마크</b>입니다. 참가자는 주어진 지형 위에 '
          '구역(Zone), 시설(Facility), 교통망(Transit)으로 이루어진 벡터 마스터플랜을 제출하고, '
          '채점기가 <b>1,000점 5축</b> 시스템으로 즉시 점수를 반환합니다.', 'body'),
        sp(4),
        p('<b>핵심 특징:</b>', 'body'),
        p('• 숨겨진 시뮬레이션 상태 없음 — 동일 입력 = 동일 점수 (결정론적).<br/>'
          '• 지형 파일(terrain JSON) + 제출물 파일(submission JSON) → 점수 + 등급.<br/>'
          '• 5개 지형 타입, 5개 목적 목표, 15+ 이벤트 유형.<br/>'
          '• 하드 게이트: 통과 못 하면 점수 0점 (FAILED).', 'body'),
        sp(8),

        SectionBanner('', '목차 (Contents)'),
        sp(4),
        p('1. 지형 유형 (Terrain Types)<br/>'
          '2. 제출물 형식 (Submission Format)<br/>'
          '3. 구역 종류 (Zone Types)<br/>'
          '4. 시설 및 교통 (Facilities & Transit)<br/>'
          '5. 채점 시스템 (Scoring System)<br/>'
          '6. 하드 게이트 & 등급 (Hard Gates & Grades)<br/>'
          '7. 이벤트 시스템 (Event System)<br/>'
          '8. 지형 갤러리 (Terrain Gallery)<br/>'
          '9. 모범답안 예시 (Elite Plan Examples)<br/>'
          '10. CLI 사용법 (CLI Workflow)', 'body'),
        PageBreak(),
    ]

    # ── 3. Terrain Types ──────────────────────────────────────────────────────
    story += [
        SectionBanner('1', '지형 유형 (Terrain Types)'),
        sp(6),
        p('모든 지형은 500m 셀 기준 200 × 150 그리드(100km × 75km)입니다.<br/>'
          '지형 파일은 고도, 수계, 경사, 숲, 습지, 농지 레이어와 이벤트 목록을 포함합니다.', 'body'),
        sp(6),
    ]

    terrain_descs = {
        'lake_core':
            ('<b>호수권 (Lake Core)</b><br/>'
             '호수가 지형 중앙부를 차지하는 경관 중심 도시 입지. '
             '수변 건물 배치 금지, 대수층 이벤트, 단층 리스크. '
             '경관 조망 이벤트로 고급 주거·관광 플랜에 유리.<br/>'
             '난이도: ★★★☆☆ | 특이 이벤트: 대수층 충전, 경관 조망, 광물 매장지'),
        'twin_coast':
            ('<b>쌍해안 (Twin Coast)</b><br/>'
             '남북 두 해안선과 그 사이 내륙을 개발하는 항만 중심 지형. '
             '태풍 경로 이벤트가 고밀 개발을 제한하고, 심해 항만 이벤트로 '
             '물류·금융 보너스. 유전 이벤트 활용이 중요.<br/>'
             '난이도: ★★★★☆ | 특이 이벤트: 심해 항만, 유전, 태풍 경로, 풍력 회랑'),
        'mountain_gate':
            ('<b>산악 분지 (Mountain Gate)</b><br/>'
             '산능선으로 둘러싸인 분지 지형. 경사 제한으로 건축 가능 면적 축소. '
             '광물·지열·경관 이벤트가 풍부해 올바른 위치 선정이 핵심. '
             '산사태 위험 구역 회피 필수.<br/>'
             '난이도: ★★★★☆ | 특이 이벤트: 광물 매장지, 지열 온천, 경관 조망, 산사태'),
        'great_delta':
            ('<b>하구 삼각주 (Great Delta)</b><br/>'
             '강 하구 삼각주의 평탄하고 넓은 충적 지형. 범람원과 습지가 많아 '
             '환경 제약이 크지만 심해 항만과 비옥 토지 이벤트로 물류·농업 시너지. '
             '침하 위험 구역에 주의.<br/>'
             '난이도: ★★★☆☆ | 특이 이벤트: 범람원, 침하, 심해 항만, 비옥 토지'),
        'central_plain':
            ('<b>대평원 (Central Plain)</b><br/>'
             '광활한 평원 지형. 건축 가능 면적이 가장 넓어 계획 자유도가 높지만 '
             '스프롤 억제가 고난이도 과제. 풍력 회랑과 비옥 토지가 '
             '에너지·농업 시너지를 제공.<br/>'
             '난이도: ★★☆☆☆ | 특이 이벤트: 풍력 회랑, 비옥 토지, 광물 매장지, 범람원'),
    }

    for key, label, _ in TERRAINS:
        story += [
            p(terrain_descs.get(key, label), 'body'),
            sp(3),
        ]
    story.append(PageBreak())

    # ── 3b. Row Legend ────────────────────────────────────────────────────────
    story += [
        SectionBanner('1', '지형 셀 범례 & 목적(Objective)'),
        sp(6),
        p('<b>지형 셀 기호 (행 문자열 rows[] 내):</b>', 'body'),
    ]

    legend_data = [
        ['기호', '지형', '건축 가능', '주의사항'],
        ['.', '건축 가능 오픈 랜드', '✔', '기본 개발지'],
        ['T', '숲/삼림', '✔', '환경 민감 — 개발 시 환경 점수 감점'],
        ['F', '농지/경작지', '✔', '환경 민감 — 비옥 이벤트 시 보존 유리'],
        ['w', '습지/범람 취약지', '✔', '환경 민감 — 범람원 이벤트 주의'],
        ['^', '급경사/절벽',  '✗', '건축 불가 — 배치 시 FAILED'],
        ['~', '수면/호수/바다', '✗', '건축 불가 — 배치 시 FAILED'],
    ]
    story += [
        table(legend_data, col_widths=[15*mm, 50*mm, 25*mm, CONTENT_W-90*mm]),
        sp(8),
        p('<b>목적 유형 (Objective) — 지형 파일마다 하나씩 지정됩니다:</b>', 'body'),
    ]

    obj_data = [
        ['목적', '설명', '유리한 구역/시설'],
        ['Financial Capital 금융 수도',  'CBD·상업 집중, 고소득 일자리', 'CBD, COMMERCIAL, airport'],
        ['Eco Metropolis 생태 메트로폴리스', '녹지 비율 극대화, 탄소 최소화', 'PARK, GREENBELT, 환경 이벤트 활용'],
        ['Innovation City 혁신 도시', '대학·의료·R&D 집중', 'UNIVERSITY, MEDICAL, COMMERCIAL'],
        ['Logistics Hub 물류 허브', '화물 네트워크 최적화', 'LOGISTICS, freight_terminal, freight_rail, port'],
        ['Tourism Capital 관광 수도', '경관·문화유산·여가 극대화', 'PARK, COMMERCIAL, 경관/온천/유산 이벤트'],
    ]
    story += [
        table(obj_data, col_widths=[55*mm, 60*mm, CONTENT_W-115*mm]),
        sp(6),
        ColorBox(
            p('<b>팁:</b> 목적 적합 보너스(최대 +85점)는 해당 목적에 맞는 구역·시설·이벤트 조합에서 발생합니다. '
              '지형 파일의 objective 필드를 먼저 확인하세요.', 'body'),
            bg=C_YELLOW, border=C_AMBER),
        PageBreak(),
    ]

    # ── 4. Submission Format ──────────────────────────────────────────────────
    story += [
        SectionBanner('2', '제출물 형식 (Submission Format)'),
        sp(6),
        p('제출물은 JSON 파일입니다. 좌표 단위는 <b>미터(m)</b>이며, 원점은 지형 <b>좌상단</b>입니다. '
          'x는 동쪽, y는 남쪽 방향으로 증가합니다.', 'body'),
        sp(6),
        p('<b>전체 구조:</b>', 'body'),
        p(
            'zones      : 구역 폴리곤 목록<br/>'
            'facilities : 점 시설 목록<br/>'
            'transit    : 교통 폴리라인 목록<br/>'
            'stations   : 역/정류장 점 목록 (시각화·스키마용)<br/>'
            'hubs       : 환승 허브 점 목록 (교통 점수에 직접 반영)',
            'code'),
        sp(6),
        p('<b>JSON 예시:</b>', 'body'),
        p(
            '{\n'
            '  "zones": [\n'
            '    {"use": "CBD",     "polygon": [[0,0],[5000,0],[5000,5000],[0,5000]]},\n'
            '    {"use": "RES_MED", "polygon": [[5000,0],[10000,0],[10000,5000],[5000,5000]]}\n'
            '  ],\n'
            '  "facilities": [\n'
            '    {"type": "airport",  "x": 25000, "y": 10000},\n'
            '    {"type": "port",     "x": 5000,  "y": 60000}\n'
            '  ],\n'
            '  "transit": [\n'
            '    {"type": "subway",   "path": [[2500,2500],[30000,2500]]},\n'
            '    {"type": "arterial", "path": [[0,5000],[100000,5000]]}\n'
            '  ],\n'
            '  "stations": [{"type": "subway", "x": 15000, "y": 2500}],\n'
            '  "hubs":     [{"x": 15000, "y": 2500}]\n'
            '}', 'code'),
        sp(6),
        ColorBox(
            p('<b>좌표 계산 팁:</b><br/>'
              '지형 그리드 크기: 200×150셀, 셀 크기 500m<br/>'
              '전체 크기: 100,000m × 75,000m (100km × 75km)<br/>'
              '셀 (col, row)의 미터 좌표: x = col×500, y = row×500', 'body'),
            bg=C_SKY, border=C_BLUE),
        PageBreak(),
    ]

    # ── 5. Zone Types ─────────────────────────────────────────────────────────
    story += [
        SectionBanner('3', '구역 종류 (Zone Types)'),
        sp(6),
        p('구역은 <b>폴리곤</b>으로 정의합니다. 같은 셀에 여러 구역이 겹치면 마지막 정의가 우선합니다.', 'body'),
        sp(4),
    ]

    # Zone table with colour swatches
    zone_col_w = [30*mm, 22*mm, 22*mm, 20*mm, CONTENT_W-114*mm, 20*mm]
    story += [
        table(ZONE_TABLE_DATA, col_widths=zone_col_w),
        sp(6),
        ColorBox(
            p('<b>녹지(green) 구역</b>(PARK, GREENBELT)은 예산 저렴하고 환경 점수에 유리하지만 '
              '주민·일자리를 생성하지 않습니다. 전체 계획 면적의 20~35% 녹지 확보를 권장합니다.', 'body'),
            bg=HexColor('#f0fdf4'), border=C_GREEN),
        sp(4),
        ColorBox(
            p('<b>오염(dirty) 구역</b>(INDUSTRIAL, LOGISTICS)은 일자리는 많지만 주변 수계나 주거지에 '
              '근접하면 환경·주거 점수에 패널티를 줍니다. 도심에서 격리 배치하세요.', 'body'),
            bg=HexColor('#fef2f2'), border=C_RED),
        PageBreak(),
    ]

    # ── 6. Facilities & Transit ───────────────────────────────────────────────
    story += [
        SectionBanner('4', '시설 및 교통 (Facilities & Transit)'),
        sp(6),
        p('<b>시설 (Facilities) — 점(Point) 단위 배치:</b>', 'body'),
        sp(3),
        table(FACILITY_DATA,
              col_widths=[38*mm, 25*mm, CONTENT_W - 63*mm]),
        sp(8),
        p('<b>교통망 (Transit) — 폴리라인(Path) 단위 배치:</b>', 'body'),
        sp(3),
        table(TRANSIT_DATA,
              col_widths=[28*mm, 22*mm, 28*mm, CONTENT_W - 78*mm]),
        sp(6),
        ColorBox(
            p('<b>교통망 연결 주의사항:</b><br/>'
              '• 모든 링크의 80% 이상이 하나의 연결 컴포넌트를 이루어야 합니다.<br/>'
              '• 비녹지 구역은 반드시 교통 셀 2칸(1km) 이내에 있어야 합니다.<br/>'
              '• arterial(간선도로)은 비용이 가장 저렴하므로 기본 그리드로 활용하세요.', 'body'),
            bg=C_SKY, border=C_BLUE),
        sp(4),
        p('<b>허브 (Hubs):</b><br/>'
          '허브는 환승 편의시설로, hubs 배열에 좌표를 지정합니다. '
          'hub 1개당 비용 6,000만 발생하며, hub 수가 많을수록 교통 점수(t_hub)가 향상됩니다. '
          '최소 4개, 최대 6개를 권장합니다.', 'body'),
        PageBreak(),
    ]

    # ── 7. Scoring System ─────────────────────────────────────────────────────
    story += [
        SectionBanner('5', '채점 시스템 (Scoring System)'),
        sp(6),
        p('<b>점수 공식:</b>', 'body'),
        p('final = (base_1000 + fit_bonus + event_score) × effective_difficulty\n'
          'effective_difficulty = 1 + (difficulty − 1) × DIFF_GAIN(0.4)\n'
          'base_1000 = 경제(200) + 교통(200) + 환경(200) + 주거(200) + 도시구조(200)', 'code'),
        sp(6),
        p('<b>5개 채점 축 설명:</b>', 'body'),
        sp(4),
    ]

    for name, pts, color, desc in AXIS_DATA:
        inner = p(f'<b>{name}</b>  <font color="grey">[{pts}]</font><br/>{desc}', 'body')
        story += [
            ColorBox(inner, bg=C_LIGHT, border=color),
            sp(3),
        ]

    story += [
        sp(4),
        p('<b>보너스 항목:</b><br/>'
          '• <b>목적 적합 보너스(fit_bonus)</b>: 최대 +85점. 지형의 objective에 맞는 구역·시설·이벤트 활용.<br/>'
          '• <b>이벤트 점수(event_score)</b>: 이벤트별로 기회(보너스) 또는 위험(패널티).<br/>'
          '  — 기회 이벤트 보상은 0.75× 감쇠(EVENT_POS_GAIN) 적용.<br/>'
          '  — 위험 이벤트 패널티는 감쇠 없이 전액 적용.', 'body'),
        sp(4),
        ColorBox(
            p('<b>캘리브레이션 파라미터 (참고용):</b><br/>'
              'DIFF_GAIN = 0.4 (난이도 압축 — 어려운 지형에 소폭 가산점)<br/>'
              'ECONOMY_STRETCH = 1.20 (목표 달성만으로는 경제 축 만점 불가)<br/>'
              'FIT_BONUS_MAX = 85 (목적 적합 보너스 상한)<br/>'
              'EVENT_POS_GAIN = 0.75 (기회 이벤트 보상 감쇠)', 'small'),
            bg=C_LIGHT, border=C_SLATE),
        PageBreak(),
    ]

    # ── 8. Hard Gates & Grades ────────────────────────────────────────────────
    story += [
        SectionBanner('6', '하드 게이트 & 등급 (Hard Gates & Grades)'),
        sp(6),
        p('<b>하드 게이트 — 하나라도 실패하면 점수 0 / status: FAILED:</b>', 'body'),
        sp(4),
    ]

    for i, (name, desc) in enumerate(GATE_DATA, 1):
        inner = p(f'<b>Gate {i}: {name}</b><br/>{desc}', 'body')
        story.append(ColorBox(inner, bg=HexColor('#fff1f2'), border=C_RED))
        story.append(sp(3))

    story += [
        sp(8),
        p('<b>등급 기준:</b>', 'body'),
        sp(4),
    ]

    grade_tdata = [['등급', '커트라인', '의미']]
    for grade, cutline, color, meaning in GRADE_DATA:
        grade_tdata.append([grade, cutline, meaning])

    gt = Table(
        [[Paragraph(r[0], S('gc', fontSize=14, fontName='WQY', alignment=TA_CENTER,
                             textColor=white)),
          Paragraph(r[1], S('gc2', fontSize=10, fontName='WQY')),
          Paragraph(r[2], S('gc3', fontSize=9, fontName='WQY', textColor=C_SLATE))]
         for r in grade_tdata],
        colWidths=[18*mm, 35*mm, CONTENT_W-53*mm],
        repeatRows=1,
    )
    gt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
        ('BACKGROUND', (0, 1), (0, 1), C_PURPLE),
        ('BACKGROUND', (0, 2), (0, 2), C_BLUE),
        ('BACKGROUND', (0, 3), (0, 3), C_GREEN),
        ('BACKGROUND', (0, 4), (0, 4), C_AMBER),
        ('BACKGROUND', (0, 5), (0, 5), C_RED),
        ('TEXTCOLOR',  (0, 0), (-1, 0), white),
        ('TEXTCOLOR',  (0, 1), (0, -1), white),
        ('GRID',  (0, 0), (-1, -1), 0.4, HexColor('#94a3b8')),
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',  (0,0), (0,-1),  'CENTER'),
    ]))
    story += [gt, PageBreak()]

    # ── 9. Event System ───────────────────────────────────────────────────────
    story += [
        SectionBanner('7', '이벤트 시스템 (Event System)'),
        sp(6),
        p('이벤트는 지형 파일의 events 배열에 포함됩니다. 각 이벤트는 좌표, 반경, '
          '종류(기회/위험/혼합) 속성을 가집니다. '
          '<b>기회(Opportunity)</b>는 적절한 개발로 보너스를, '
          '<b>위험(Hazard)</b>은 노출 시 패널티를, '
          '<b>혼합(Mixed)</b>은 보존 또는 개발 방식에 따라 달라집니다.', 'body'),
        sp(4),
        table(EVENT_DATA,
              col_widths=[55*mm, 22*mm, CONTENT_W-77*mm]),
        sp(6),
        ColorBox(
            p('<b>이벤트 활용 전략:</b><br/>'
              '1. 지형 파일의 events 배열을 먼저 파악합니다.<br/>'
              '2. 위험 이벤트(단층, 산사태, 태풍) 반경 내에는 개발을 최소화합니다.<br/>'
              '3. 기회 이벤트에 맞는 시설을 인접 배치합니다 (예: 심해 항만 → port).<br/>'
              '4. 혼합 이벤트는 보전(GREENBELT) vs 개발을 점수로 비교해 선택합니다.', 'body'),
            bg=C_YELLOW, border=C_AMBER),
        PageBreak(),
    ]

    # ── 10. Terrain Gallery ───────────────────────────────────────────────────
    story += [
        SectionBanner('8', '지형 갤러리 (Terrain Gallery)'),
        sp(6),
    ]

    col_w = (CONTENT_W - 6 * mm) / 2
    available = [(key, label) for key, label, _ in TERRAINS if key in terrain_imgs]
    for i in range(0, len(available), 2):
        pair = available[i:i+2]
        if len(pair) == 2:
            (k0, l0), (k1, l1) = pair
            t2 = Table(
                [[rl_image(terrain_imgs[k0], col_w, 58*mm), rl_image(terrain_imgs[k1], col_w, 58*mm)],
                 [Paragraph(l0, STYLES['caption']),          Paragraph(l1, STYLES['caption'])]],
                colWidths=[col_w, col_w],
            )
        else:
            k0, l0 = pair[0]
            t2 = Table(
                [[rl_image(terrain_imgs[k0], col_w, 58*mm), ''],
                 [Paragraph(l0, STYLES['caption']),          '']],
                colWidths=[col_w, col_w],
            )
        t2.setStyle(TableStyle([
            ('ALIGN',  (0,0),(-1,-1), 'CENTER'),
            ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0),(-1,-1), 3),
            ('TOPPADDING',    (0,0),(-1,-1), 3),
        ]))
        story += [t2, sp(4)]

    story += [
        sp(4),
        p('위 이미지는 절차적으로 생성된 지형 시각화입니다. '
          '실제 게임에서는 seed 번호에 따라 지형 세부 내용이 다를 수 있습니다.', 'small'),
        PageBreak(),
    ]

    # ── 11. Elite Plan Examples ───────────────────────────────────────────────
    story += [
        SectionBanner('9', '모범답안 예시 (Elite Plan Examples)'),
        sp(6),
        p('각 지형의 Financial Capital 목적 모범답안(elite) 예시입니다. '
          '왼쪽은 순수 지형, 오른쪽은 모범 마스터플랜입니다.', 'body'),
        sp(4),
    ]

    elite_scores = {}
    try:
        with open(os.path.join(BASE_DIR, 'elite_set_report.csv')) as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split(',')
                # terrain,objective,elite_score,elite_grade,elite_status,ref_score,...
                if len(parts) >= 6 and 'financial' in parts[1].lower():
                    elite_scores[parts[0]] = (parts[2], parts[3], parts[5], parts[6])
    except Exception:
        pass

    for key, label, _ in TERRAINS:
        if key not in terrain_imgs or key not in plan_imgs:
            continue

        score_str = ''
        if key in elite_scores:
            es, eg, rs, rg = elite_scores[key]
            try:
                score_str = (f' | 모범답안: {float(es):.0f}점 ({eg})'
                             f'  베이스라인: {float(rs):.0f}점 ({rg})')
            except ValueError:
                pass

        story += [
            p(f'<b>{label}</b>{score_str}', 'h3'),
            sp(3),
        ]

        ti = rl_image(terrain_imgs[key], (CONTENT_W-4*mm)/2, 52*mm)
        pi = rl_image(plan_imgs[key],    (CONTENT_W-4*mm)/2, 52*mm)

        row = Table(
            [[ti, pi],
             [Paragraph('지형', STYLES['caption']), Paragraph('모범 마스터플랜', STYLES['caption'])]],
            colWidths=[(CONTENT_W-4*mm)/2]*2,
        )
        row.setStyle(TableStyle([
            ('ALIGN',  (0,0),(-1,-1), 'CENTER'),
            ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING',(0,0),(-1,-1),2),
        ]))
        story += [row, sp(6)]

    story.append(PageBreak())

    # ── 12. CLI Workflow ──────────────────────────────────────────────────────
    story += [
        SectionBanner('10', 'CLI 사용법 (CLI Workflow)'),
        sp(6),
        p('<b>Step 1 — 지형 파일 생성:</b>', 'body'),
        p('python terrain_gen.py lake_core "Financial Capital" 3 terrain.json\n'
          '# 인자: 지형 유형 | 목적 | seed | 출력 파일', 'code'),
        sp(4),

        p('<b>Step 2 — 지형 상세 렌더링 (확인용):</b>', 'body'),
        p('python render_terrain.py terrain.json terrain_map.png', 'code'),
        sp(4),

        p('<b>Step 3 — 제출물 JSON 작성 후 스키마 검증:</b>', 'body'),
        p('python schema.py my_submission.json\n'
          '# 구조 오류(키 누락, 좌표 형식 등)를 즉시 확인', 'code'),
        sp(4),

        p('<b>Step 4 — 하드 게이트 검증:</b>', 'body'),
        p('python validate.py terrain.json my_submission.json\n'
          '# 게이트 실패 시 실패 이유와 위치를 출력', 'code'),
        sp(4),

        p('<b>Step 5 — 채점:</b>', 'body'),
        p('python score_v2.py terrain.json my_submission.json\n'
          '# 점수, 등급, 5축 점수, 이벤트 점수 출력', 'code'),
        sp(4),

        p('<b>Step 6 — 마스터플랜 렌더링:</b>', 'body'),
        p('python render2.py terrain.json my_submission.json plan.png', 'code'),
        sp(4),

        p('<b>모범답안 생성 (참고용):</b>', 'body'),
        p('python make_elite.py terrain.json elite.json\n'
          'python make_reference.py terrain.json baseline.json', 'code'),
        sp(4),

        p('<b>웹 UI (브라우저 편집기 + 즉시 채점):</b>', 'body'),
        p('python webapp.py 8000\n'
          '# http://localhost:8000 접속\n'
          '# 지형 선택 → 구역/교통/시설 배치 → 즉시 채점 → 대시보드 비교', 'code'),
        sp(4),

        p('<b>멀티시드 밸런스 검증 (개발자용):</b>', 'body'),
        p('python balance_multiseed.py --check   # 베이스라인 분포 검증\n'
          'python make_elite_set.py --check      # 25개 모범답안 A-바닥 검증\n'
          'python run_tests.py                    # 전체 회귀 테스트', 'code'),
        sp(6),

        ColorBox(
            p('<b>지형 유형 목록:</b> lake_core | twin_coast | mountain_gate | great_delta | central_plain<br/>'
              '<b>목적 목록:</b> "Financial Capital" | "Eco Metropolis" | "Innovation City" | "Logistics Hub" | "Tourism Capital"', 'body'),
            bg=C_SKY, border=C_BLUE),
        sp(6),

        hr(),
        sp(4),
        p('CityBench v0.4 — 결정론적 도시설계 벤치마크', 'center'),
        p('문의: GitHub Issues', 'center'),
    ]

    print(f"Building PDF ({len(story)} flowables)...")
    doc.build(story)
    print(f"Done: {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'citybench_rulebook.pdf'
    out = os.path.abspath(out)

    with tempfile.TemporaryDirectory() as tmp:
        print("Generating terrain and plan images...")
        terrain_imgs, plan_imgs = gen_images(tmp)
        print(f"  Terrain images: {list(terrain_imgs.keys())}")
        print(f"  Plan images:    {list(plan_imgs.keys())}")

        build_pdf(out, terrain_imgs, plan_imgs)

    size_kb = os.path.getsize(out) / 1024
    print(f"\nOutput: {out}  ({size_kb:.0f} KB)")


if __name__ == '__main__':
    main()
