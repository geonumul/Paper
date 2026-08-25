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
  - `--all`이면 **여러 편의 대역**(절 개수 최소·Q1·중위·Q3·최대)까지

2단 PDF에서 뽑은 글은 표제 뒤에 옆 단 본문이 붙는다. 줄 앵커로 절을 셋도
못 찾으면 글 전체에서 **1, 2, 3… 번호 사슬**을 훑어 되돌린다.

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
# 줄 끝까지가 표제인 경우와, **뒤에 옆 단 본문이 붙은 경우**를 함께 잡는다.
# 2단 PDF에서 뽑으면 "1. Introduction international bodies and ..."처럼 표제
# 뒤에 다른 단의 글이 이어 붙는다. 이것 때문에 51편 중 50편에서 표제를 하나도
# 못 찾은 적이 있다.
HEAD = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+([A-Z][^\n]{2,120})$")
# 표제 안에 들어갈 수 있는 소문자 낱말(기능어). 그 밖의 소문자 낱말이 나오면
# 거기부터는 표제가 아니라 옆 단 본문이다
TITLE_LOWER = set("of and the in for to on with a an as from by".split())
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
        # 표제 뒤에 옆 단 본문이 붙어 있을 수 있다. **어디까지가 표제인지는
        # 글자만 보고 알 수 없다**(표제도 "Literature review"처럼 소문자를
        # 쓴다). 그래서 앞 여섯 낱말만 남기고 잘렸음을 표시한다.
        # 절 개수·번호·분량을 재는 데는 지장이 없고, 제목 글자는 어차피
        # 원문을 눈으로 보고 고쳐야 한다.
        words = title.split()
        title = " ".join(words[:6]).strip(" ,;:.")
        if len(words) > 6:
            title += " …"
        if not title:
            continue
        if re.search(r"\d{4}", title):                # 연도가 있으면 서지 조각
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


def find_heads_inline(text, lines):
    """표제가 줄 맨 앞에 없을 때, 글 전체에서 번호 사슬을 찾는다.

    2단 PDF에서 뽑으면 3장부터가 옆 단 본문 한가운데에 박힌다. 줄 앵커로는
    한 편에서 절 두 개밖에 못 찾는다. 그래서 **1, 2, 3… 으로 이어지는
    번호만** 글 전체에서 훑는다. 사슬이 끊기면 거기서 멈춘다.

    이것도 초안이다. 절이 몇 개인지와 분량 비중을 보는 용도이고,
    제목 글자는 원문을 눈으로 보고 고친다.
    """
    starts = {}
    # 점 뒤의 `.`은 줄바꿈을 안 먹는다. 그래서 표제 후보는 한 줄 안에서만 잡힌다
    for m in re.finditer(r"(?:^|[.\s])(\d{1,2})\.\s+([A-Z][A-Za-z].{2,60})",
                         text):
        n = int(m.group(1))
        if SENT_START.match(m.group(2)):
            continue
        starts.setdefault(n, m)
    kept, pos = [], -1
    for n in range(1, 15):
        m = starts.get(n)
        if not m or m.start() < pos:
            break
        title = " ".join(m.group(2).split()[:6]).strip(" ,;:.")
        line_i = text.count(chr(10), 0, m.start())
        kept.append((line_i, str(n), title + " …"))
        pos = m.start()
    return kept if len(kept) >= 3 else []


def outline(path, show_paras=False):
    raw = clean(open(path, encoding="utf-8", errors="replace").read())
    lines = raw.split("\n")
    heads = find_heads(lines)
    if len([h for h in heads if '.' not in h[1]]) < 3:
        # 줄 앵커로 절을 세 개도 못 찾았다. 2단 병합 텍스트다
        alt = find_heads_inline(raw, lines)
        if alt:
            heads = alt
    if not heads:
        print("  (제목을 못 찾았다. 원문을 렌더링해 눈으로 옮겨 적을 것)")
        return None

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
    return len(tops), len(heads) - len(tops)


def summary(tops, subs, failed, n_files):
    """여러 편을 돌린 뒤 **대역**을 낸다. 이것이 5단계의 산출물이다."""
    print("")
    print("# 구조 대역 (게재작 %d편)" % n_files)
    print("")
    if failed:
        print("- 표제를 못 찾은 것 **%d편**. 나머지 %d편으로 낸 대역이다"
              % (failed, len(tops)))
    if not tops:
        print("- 잰 것이 없다. 캐시를 확인한다")
        return

    def q(arr, p_):
        arr = sorted(arr)
        return arr[min(len(arr) - 1, int(len(arr) * p_))]

    print("")
    print("| 항목 | 최소 | Q1 | **중위** | Q3 | 최대 |")
    print("|--|--|--|--|--|--|")
    for name, arr in (("최상위 절 개수", tops), ("하위절 개수", subs)):
        print("| %s | %d | %d | **%d** | %d | %d |"
              % (name, min(arr), q(arr, .25), q(arr, .5), q(arr, .75),
                 max(arr)))
    print("")
    print("**우리 원고를 이 대역에 대 본다.** 대역 밖이면 왜 그런지 답할 수"
          " 있어야 한다.")
    print("제목 글자는 초안이다. 2단 PDF에서 뽑으면 옆 단 본문이 섞이므로"
          " 원문을 눈으로 보고 고친다.")


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
        tops, subs, failed = [], [], 0
        for f in files:
            print("")
            print("## " + os.path.basename(f)[:70])
            r = outline(f, show)
            if r is None:
                failed += 1
            else:
                tops.append(r[0])
                subs.append(r[1])
        summary(tops, subs, failed, len(files))
        return
    if not args:
        print(__doc__)
        return
    print("# " + os.path.basename(args[0])[:70])
    outline(args[0], show)


if __name__ == "__main__":
    main()
