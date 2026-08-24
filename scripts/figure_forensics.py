# -*- coding: utf-8 -*-
"""게재작 PDF에서 그림·표의 양식을 수치로 뽑아낸다 (베끼기 수준 대조용).

쓰임:
  python figure_forensics.py <pdf> --scan              # 어느 쪽에 그림·표가 있나
  python figure_forensics.py <pdf> 7                   # 7쪽의 양식을 전부 뽑는다
  python figure_forensics.py <pdf> 7 --box 60 300 540 640   # 그 쪽의 일부 영역만
  python figure_forensics.py <pdf> 7 --png             # 같이 렌더링해서 눈으로도 본다

뽑는 것
  - 글자: 폰트 이름, 크기, 굵기, 색. 캡션·축이름·눈금·범례·표 본문을 나눠서
  - 선: 두께(pt), 색, 실선/점선, 수평·수직·사선 개수
  - 면: 채움 색과 그 면적
  - 이미지: 래스터가 박혀 있으면 벡터 측정이 안 된다는 표시

읽는 법
  **수치만으로 끝내지 않는다. 반드시 --png로 렌더링해 눈으로도 본다.**
  폰트 이름은 subset 코드(AdvOT..., ABCDEF+Times)로 나오는 경우가 많아 세리프
  여부를 이름으로 판정할 수 없고, 배치·정렬·여백·격자 유무는 수치로 안 잡힌다.
  래스터 이미지로 들어간 그림은 선 두께를 못 잰다. 그럴 때는 --png로 렌더링해
  눈으로 재고, "재지 못했다"고 기록한다. 벡터로 들어간 그림은 아래 수치가
  그대로 우리 그림의 설정값이 된다.
"""
import io
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def rgb(c):
    if c is None:
        return "none"
    if isinstance(c, (int, float)):
        v = int(c)
        return "#%06x" % (v & 0xFFFFFF)
    try:
        r, g, b = c[:3]
        return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
    except Exception:
        return str(c)


def int_color(v):
    if v is None:
        return "none"
    return "#%06x" % (int(v) & 0xFFFFFF)


def scan(doc):
    print("| 쪽 | 선·도형 | 글자 조각 | 래스터 이미지 | 짐작 |")
    print("|--|--|--|--|--|")
    for i in range(doc.page_count):
        p = doc.load_page(i)
        d = len(p.get_drawings())
        t = len(p.get_text("dict")["blocks"])
        im = len(p.get_images(full=True))
        guess = ""
        txt = p.get_text()[:4000]
        if re.search(r"\bFig(\.|ure)\s*\d", txt):
            guess += "그림 캡션 "
        if re.search(r"\bTable\s*\d", txt):
            guess += "표 캡션 "
        if d > 40 and not im:
            guess += "(벡터 그림 가능성)"
        if im:
            guess += "(래스터 있음)"
        print("| %d | %d | %d | %d | %s |" % (i + 1, d, t, im, guess.strip()))


def analyse(page, box=None):
    import fitz
    clip = fitz.Rect(*box) if box else None

    # ── 글자 ────────────────────────────────────────────────
    fonts = Counter()
    sizes = Counter()
    colors = Counter()
    samples = defaultdict(list)
    td = page.get_text("dict", clip=clip)
    for b in td["blocks"]:
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                txt = s["text"].strip()
                if not txt:
                    continue
                key = (s["font"], round(s["size"], 1))
                fonts[s["font"]] += len(txt)
                sizes[round(s["size"], 1)] += len(txt)
                colors[int_color(s.get("color"))] += len(txt)
                if len(samples[key]) < 3:
                    samples[key].append(txt[:60])

    print("## 글자")
    print("\n| 폰트 | 크기(pt) | 글자수 | 예시 |")
    print("|--|--|--|--|")
    for (f, sz), ex in sorted(samples.items(), key=lambda kv: -len(kv[1])):
        n = sum(1 for b in td["blocks"] for l in b.get("lines", [])
                for s in l.get("spans", [])
                if s["font"] == f and round(s["size"], 1) == sz)
        print("| %s | %s | %d조각 | %s |" % (f, sz, n, " / ".join(ex)))
    print("\n- 폰트 분포: " + ", ".join("%s %d자" % kv for kv in fonts.most_common(6)))
    print("- 크기 분포: " + ", ".join("%.1fpt %d자" % kv for kv in sizes.most_common(8)))
    print("- 글자 색: " + ", ".join("%s %d자" % kv for kv in colors.most_common(5)))
    serif = sum(v for k, v in fonts.items()
                if re.search(r"times|serif|roman|minion|garamond|nimbusrom",
                             k, re.I))
    total = sum(fonts.values()) or 1
    subset = re.match(r"^(AdvOT|[A-Z]{6}\+)", (fonts.most_common(1) or [("", 0)])[0][0] or "")
    if subset:
        print("- 세리프 판정: **불가**. 폰트 이름이 subset 코드라 이름으로는 알 수 없다."
              " --png로 렌더링해 눈으로 판정할 것")
    else:
        print("- 세리프 비율: %.0f%% (100%%에 가까우면 세리프, 0%%면 산세리프)"
              % (100.0 * serif / total))

    # ── 선과 면 ──────────────────────────────────────────────
    widths = Counter()
    strokes = Counter()
    fills = Counter()
    dashes = Counter()
    orient = Counter()
    n_draw = 0
    for d in page.get_drawings():
        if clip and not fitz.Rect(d["rect"]).intersects(clip):
            continue
        n_draw += 1
        w = d.get("width")
        if w:
            widths[round(float(w), 2)] += 1
        if d.get("color") is not None:
            strokes[rgb(d["color"])] += 1
        if d.get("fill") is not None:
            fills[rgb(d["fill"])] += 1
        dashes[(d.get("dashes") or "[] 0").strip()] += 1
        for item in d["items"]:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) < 0.6:
                    orient["수평선"] += 1
                elif abs(p1.x - p2.x) < 0.6:
                    orient["수직선"] += 1
                else:
                    orient["사선"] += 1
            elif item[0] == "re":
                orient["사각형"] += 1
            elif item[0] in ("c", "qu"):
                orient["곡선"] += 1

    print("\n## 선과 면 (도형 %d개)" % n_draw)
    print("- 선 두께: " + (", ".join("%.2fpt %d개" % kv
                                    for kv in widths.most_common(6)) or "없음"))
    print("- 선 색: " + (", ".join("%s %d개" % kv
                                  for kv in strokes.most_common(6)) or "없음"))
    print("- 채움 색: " + (", ".join("%s %d개" % kv
                                   for kv in fills.most_common(6)) or "없음"))
    print("- 점선 여부: " + ", ".join("%s %d개" % kv for kv in dashes.most_common(4)))
    print("- 도형 종류: " + (", ".join("%s %d" % kv for kv in orient.most_common())
                          or "없음"))
    if orient.get("곡선") and not orient.get("사각형"):
        print("  (곡선만 있으면 둥근 모서리일 수 있다. 렌더링해서 확인)")

    ims = page.get_images(full=True)
    if ims:
        print("\n## 래스터 이미지 %d개" % len(ims))
        print("  벡터 측정이 안 되는 부분이 있다. --png로 렌더링해 눈으로 재고,")
        print("  '재지 못했다'고 기록한다.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = sys.argv[1]
    try:
        import fitz
    except ImportError:
        print("PyMuPDF가 필요합니다:  pip install pymupdf")
        return
    doc = fitz.open(path)
    if "--scan" in sys.argv:
        scan(doc)
        return
    nums = [a for a in sys.argv[2:] if a.isdigit()]
    if not nums:
        print("쪽 번호를 주거나 --scan을 쓰세요.")
        return
    pno = int(nums[0])
    page = doc.load_page(pno - 1)
    box = None
    if "--box" in sys.argv:
        i = sys.argv.index("--box")
        box = [float(x) for x in sys.argv[i + 1:i + 5]]
    print("# %s  %d쪽%s\n" % (os.path.basename(path)[:60], pno,
                             ("  영역 %s" % box) if box else ""))
    analyse(page, box)
    if "--png" in sys.argv:
        pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), clip=(
            fitz.Rect(*box) if box else None))
        out = "%s_p%03d.png" % (os.path.splitext(os.path.basename(path))[0][:30],
                                pno)
        pix.save(out)
        print("\n렌더링: %s (확인 후 지운다)" % out)


if __name__ == "__main__":
    main()
