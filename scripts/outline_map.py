# -*- coding: utf-8 -*-
"""게재작의 목차와 절별 분량을 뽑는다 (구조 지도의 1차 초안).

쓰임:
  python outline_map.py literature/_txt/<파일>.txt
  python outline_map.py --txt literature/_txt --journal TFSC --all   # 여러 편
  python outline_map.py <파일>.txt --paras                           # 문단 길이까지

뽑는 것
  - 절·하위절 제목을 나온 순서대로 (원문 낱말 그대로)
  - 절별 낱말 수와 전체에서 차지하는 비중, 문장 수
  - 문단 수와 문단당 문장 수 (셀 수 있을 때만)
  - 최상위 절 개수와 하위절 깊이

**이것은 초안이다.** PDF에서 뽑은 텍스트라 제목을 놓치거나 본문 한 줄을 제목으로
잘못 잡는 일이 있다. 반드시 원문을 눈으로 보며 고친다(`pdf_render.py`).
기계는 후보만 내고 판정은 사람이 한다.
"""
import io
import os
import re
import sys
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# "1. Introduction" / "2.1 Sectoral types" / "3.1.2 ..." 꼴
HEAD = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+([A-Z][^\n]{2,70})\s*$")
# 본문 문장이 번호 목록으로 시작하는 경우를 걸러내는 첫 낱말
SENT_START = re.compile(
    r"^(Table|Fig|Figure|Note|Source|In|That|Some|Certain|The|This|These|Those|"
    r"We|It|As|If|For|Although|While|Since|However|Moreover|First|Second|Third)\b")


def clean(t):
    return re.sub(r"-\s*\n\s*", "", t)          # 줄바꿈 하이픈 복원


def sentences(t):
    t = re.sub(r"\s+", " ", t)
    return [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", t)
            if len(x.split()) > 3]


def find_heads(lines):
    cand = []
    for i, ln in enumerate(lines):
        m = HEAD.match(ln)
        if not m:
            continue
        num, title = m.group(1), m.group(2).strip()
        if SENT_START.match(title):
            continue
        if len(title.split()) > 8:
            continue
        if re.search(r"[,;.]$|\d{4}|,\s", title):     # 문장 조각 배제
            continue
        cand.append((i, num, title))

    # 번호가 실제로 이어지는 것만 남긴다 (본문 번호 목록 배제)
    kept, expect_top, cur_top = [], 1, 0
    for i, num, title in cand:
        parts = [int(x) for x in num.split(".")]
        if len(parts) == 1:
            if parts[0] == expect_top:
                kept.append((i, num, title))
                cur_top = parts[0]
                expect_top += 1
        else:
            if kept and parts[0] == cur_top:          # 지금 절에 속한 하위절만
                kept.append((i, num, title))
    return kept


def outline(path, show_paras=False):
    raw = clean(open(path, encoding="utf-8", errors="replace").read())
    lines = raw.split("\n")
    heads = find_heads(lines)
    if not heads:
        print("  (제목을 못 찾았다. 원문을 렌더링해 눈으로 옮겨 적을 것)")
        return

    total_words = len(raw.split())
    print("| 번호 | 제목 | 낱말 | 비중 | 문장 | 문단 | 문단당 문장 |")
    print("|--|--|--|--|--|--|--|")
    for k, (i, num, title) in enumerate(heads):
        j = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = "\n".join(lines[i + 1:j])
        w = len(body.split())
        paras = [p for p in re.split(r"\n\s*\n", body) if len(p.split()) > 25]
        sents = sentences(body)
        # PDF 텍스트는 문단 경계가 뭉개진다. 믿을 만할 때만 보고한다
        reliable = len(paras) > 1 and (w / float(len(paras))) < 400
        depth = num.count(".")
        indent = "  " * depth
        pshow = str(len(paras)) if reliable else "?"
        sshow = ("%.1f" % (len(sents) / float(len(paras)))) if reliable else "-"
        print("| %s%s | %s%s | %d | %.0f%% | %d | %s | %s |"
              % (indent, num, indent, title[:52], w,
                 100.0 * w / max(1, total_words), len(sents), pshow, sshow))
        if show_paras and reliable:
            lens = sorted(len(sentences(p)) for p in paras)
            print("|  | ↳ 문단별 문장 수 %s |  |  |  |  |  |"
                  % ", ".join(str(x) for x in lens))

    tops = [h for h in heads if h[1].count(".") == 0]
    depths = set(n.count(".") for _, n, _ in heads)
    print("\n- 최상위 절 %d개, 하위절 깊이 %d층까지" % (len(tops), max(depths) + 1))
    print("- 전체 낱말 {:,}".format(total_words))
    print("- 문단 칸이 `?`이면 PDF 텍스트에서 문단 경계가 뭉개진 것이다. "
          "그 절은 원문을 눈으로 보고 센다")
    print("- **이 표는 초안이다. 원문을 보며 고칠 것**")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show = "--paras" in sys.argv
    if "--all" in sys.argv:
        txt = args[0] if args else "literature/_txt"
        if "--txt" in sys.argv:
            txt = sys.argv[sys.argv.index("--txt") + 1]
        mark = sys.argv[sys.argv.index("--journal") + 1] \
            if "--journal" in sys.argv else ""
        files = [f for f in sorted(glob.glob(txt + "/*.txt"))
                 if not mark or mark.lower() in os.path.basename(f).lower()]
        for f in files[:40]:
            print("\n## " + os.path.basename(f)[:70])
            outline(f, show)
        return
    if not args:
        print(__doc__)
        return
    print("# " + os.path.basename(args[0])[:70])
    outline(args[0], show)


if __name__ == "__main__":
    main()
