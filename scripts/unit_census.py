# -*- coding: utf-8 -*-
"""원고를 절·문단·문장으로 쪼개 번호를 매긴다 (전수 판정용 대장 만들기).

쓰임:
  python unit_census.py 원고.md                 # 개수만 (몇 절, 몇 문단, 몇 문장)
  python unit_census.py 원고.md --paras         # 문단 대장
  python unit_census.py 원고.md --sents         # 문장 대장
  python unit_census.py 원고.md --paras --out outputs/문단_대장.md
  python unit_census.py 원고.md --sec 4         # 4장만

왜 쓰나
  문장 층·문단 층 검수는 **전수**여야 한다. 개수가 정해지지 않으면 "몇 개
  보았다"로 끝난다. 이 대장은 행 개수가 정해져 있으므로, 모든 행에 판정이
  붙어야 그 층이 닫힌다.

번호
  `4.2-P3`     4.2절의 세 번째 문단
  `4.2-P3-S2`  그 문단의 두 번째 문장

빠지는 것
  표, 코드 블록, 인용 블록(>), 그림·표 캡션 줄, 목록 줄.
  **빠진 것도 개수를 보고한다.** 검수 대상이 아니라고 판단한 근거를 남기기 위해서다.
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def split_sentences(p):
    t = re.sub(r"\s+", " ", p).strip()
    t = re.sub(r"\b(et al|e\.g|i\.e|Fig|Eq|No|vs|cf|Dr|approx|p)\.", r"\1<DOT>", t)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'])", t)          # 영문
    out = []
    for x in parts:
        x = x.replace("<DOT>", ".").strip()
        if not x:
            continue
        # 국문은 종결어미로 한 번 더 쪼갠다
        if re.search(r"[가-힣]", x):
            ko = re.split(r"(?<=다\.)\s+", x)
            out.extend([k.strip() for k in ko if k.strip()])
        else:
            out.append(x)
    return out


def parse(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    lines = raw.split("\n")
    blocks, cur, in_code = [], [], False
    sec, sec_title = "0", "(제목 앞)"
    skipped = {"표": 0, "코드": 0, "인용": 0, "목록": 0, "캡션": 0}
    p_idx = 0
    for ln in lines + [""]:
        if ln.strip().startswith("```"):
            in_code = not in_code
            if not in_code:
                skipped["코드"] += 1
            continue
        if in_code:
            continue
        m = HEAD.match(ln)
        if m:
            if cur:
                p_idx += 1
                blocks.append((sec, sec_title, p_idx, "\n".join(cur)))
                cur = []
            title = m.group(2)
            nm = NUMBERED.match(title)
            sec = nm.group(1) if nm else title[:20]
            sec_title = nm.group(2) if nm else title
            p_idx = 0
            continue
        if not ln.strip():
            if cur:
                p_idx += 1
                blocks.append((sec, sec_title, p_idx, "\n".join(cur)))
                cur = []
            continue
        st = ln.lstrip()
        if st.startswith("|"):
            skipped["표"] += 1
            continue
        if st.startswith(">"):
            skipped["인용"] += 1
            continue
        if re.match(r"^([-*+]|\d+\.)\s", st):
            skipped["목록"] += 1
            continue
        if re.match(r"^(Table|Fig(ure)?|표|그림)\s*\d", st):
            skipped["캡션"] += 1
            continue
        cur.append(ln)
    return blocks, skipped


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return
    src = args[0]
    only = opt("--sec")
    out = opt("--out")
    blocks, skipped = parse(src)
    if only:
        blocks = [b for b in blocks if b[0].split(".")[0] == only]

    secs = []
    for sec, title, _, _ in blocks:
        if not secs or secs[-1][0] != sec:
            secs.append((sec, title))
    n_par = len(blocks)
    n_sen = sum(len(split_sentences(b[3])) for b in blocks)

    L = ["# 단위 대장 · %s" % os.path.basename(src), ""]
    L.append("- 절 **%d개** / 문단 **%d개** / 문장 **%d개**" % (len(secs), n_par, n_sen))
    L.append("- 검수 대상에서 뺀 줄: " +
             ", ".join("%s %d" % kv for kv in skipped.items()))
    L.append("")
    L.append("**전수 판정이다.** 아래 모든 행에 판정을 적기 전에는 그 층을 닫지"
             " 않는다. 표본으로 몇 개만 보지 않는다.")
    L.append("")

    if "--paras" in sys.argv:
        L.append("## 문단 대장 (%d행)" % n_par)
        L.append("")
        L.append("| 번호 | 절 | 문장 수 | 첫머리 | 메시지 한 줄 | 빌드업 | 근거 게재작 | 판정 |")
        L.append("|--|--|--|--|--|--|--|--|")
        for sec, title, idx, body in blocks:
            sents = split_sentences(body)
            head = re.sub(r"\s+", " ", body)[:46]
            L.append("| %s-P%d | %s | %d | %s… |  |  |  |  |"
                     % (sec, idx, title[:18], len(sents), head))
    elif "--sents" in sys.argv:
        L.append("## 문장 대장 (%d행)" % n_sen)
        L.append("")
        L.append("| 번호 | 절 | 문장 | 기능 | 게재작 근거 | 문법 | 논리 | 흐름 | 판정 |")
        L.append("|--|--|--|--|--|--|--|--|--|")
        for sec, title, idx, body in blocks:
            for k, sent in enumerate(split_sentences(body), 1):
                L.append("| %s-P%d-S%d | %s | %s | | | | | | |"
                         % (sec, idx, k, title[:14],
                            sent[:70].replace("|", "/")))
    else:
        L.append("## 절별 개수")
        L.append("")
        L.append("| 절 | 제목 | 문단 | 문장 |")
        L.append("|--|--|--|--|")
        for sec, title in secs:
            bs = [b for b in blocks if b[0] == sec]
            L.append("| %s | %s | %d | %d |"
                     % (sec, title[:40], len(bs),
                        sum(len(split_sentences(b[3])) for b in bs)))
        L.append("")
        L.append("`--paras` 또는 `--sents`로 대장을 만든다.")

    if not out:
        # 대화창에 수백 행을 찍지 않는다. 전체는 --out 으로 파일에 쓴다
        top = int(opt("--top", 30))
        idx = [i for i, l in enumerate(L)
               if l.startswith("| ") and "번호" not in l]
        if len(idx) > top:
            L = L[:idx[top]] + ["",
                 "**화면에는 %d행만 찍었다. 전체 %d행은 `--out 파일.md` 로"
                 " 받는다.**" % (top, len(idx)),
                 "판정은 파일에서 하고, 대화에는 개수와 결론만 남긴다."]
    text = "\n".join(L)
    if out:
        open(out, "w", encoding="utf-8").write(text)
        print("저장: %s" % out)
        print("절 %d / 문단 %d / 문장 %d" % (len(secs), n_par, n_sen))
    else:
        print(text)


if __name__ == "__main__":
    main()
