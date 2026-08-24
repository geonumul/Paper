# -*- coding: utf-8 -*-
"""원고에서 보이지 않는 문자와 AI 티 나는 기호를 찾는다 (치환도 한다).

쓰임:
  python check_invisible.py 원고.md            # 검사만 (개수와 위치)
  python check_invisible.py 원고.md --fix      # 원고.fixed.md 로 치환
  diff 원고.md 원고.fixed.md                    # 반드시 대조한다

무엇을 보나
  ① 보이지 않는 문자: 폭 없는 공백, 특수 공백, 양방향 제어, 태그 문자
  ② 눈에 보이지만 티가 나는 기호: em dash, en dash, 곡선 따옴표, 불릿, 이모지,
     화살표, 물결표, 줄임표

치환 규칙 (--fix)
  —  →  " - "        ‘ ’ → '        “ ” → "
  –  →  "-"(숫자 사이) 또는 " - "
  • ▪ ‣ → "-"        이모지 → 삭제      보이지 않는 문자 → 삭제

**치환은 문자만 바꾼다. 낱말과 문장은 건드리지 않는다.**
줄바꿈 없는 공백(U+00A0), 줄임표(…), 화살표(→)는 정당하게 쓰이는 자리가 있어
자동으로 안 바꾼다. 보고만 하고 눈으로 판단한다.
"""
import io
import os
import re
import sys
import unicodedata
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ① 보이지 않는 문자 (삭제 대상)
INVISIBLE = set(
    [0x00AD, 0x061C, 0x180E, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F,
     0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0x2065, 0xFEFF]
    + list(range(0x2000, 0x200B))      # 특수 공백
    + list(range(0x2066, 0x206A))      # 양방향 격리
    + list(range(0xFFF0, 0xFFF9))
    + list(range(0xE0000, 0xE1000))    # 태그 문자
)

# ② 보이는 기호: (문자, 설명, 자동 치환값 또는 None)
VISIBLE = {
    "—": ("em dash", " - "),
    "–": ("en dash", None),          # 숫자 사이면 "-", 아니면 " - "
    "‘": ("곡선 작은따옴표(여는)", "'"),
    "’": ("곡선 작은따옴표(닫는)", "'"),
    "“": ("곡선 큰따옴표(여는)", '"'),
    "”": ("곡선 큰따옴표(닫는)", '"'),
    "•": ("불릿", "-"),
    "▪": ("불릿(사각)", "-"),
    "‣": ("불릿(삼각)", "-"),
    "…": ("줄임표", None),           # 인용 생략이면 정당
    "→": ("화살표", None),           # 그림·표 안이면 정당
    "⇒": ("두 줄 화살표", None),
    "~": ("물결표", None),                # 범위는 하이픈, 근사는 approximately
    " ": ("줄바꿈 없는 공백", None),  # Table 1, 5 kg 등 정당한 자리 있음
}

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")


def scan(text):
    hits = Counter()
    lines_hit = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for ch in line:
            o = ord(ch)
            if o in INVISIBLE:
                name = unicodedata.name(ch, "UNNAMED")
                hits[("보이지 않음", "U+%04X %s" % (o, name))] += 1
                lines_hit.append((lineno, "U+%04X %s" % (o, name)))
            elif ch in VISIBLE:
                hits[("기호", "%s (%s)" % (ch, VISIBLE[ch][0]))] += 1
        for m in EMOJI.finditer(line):
            hits[("기호", "%s (이모지)" % m.group(0))] += 1
            lines_hit.append((lineno, "이모지 %s" % m.group(0)))
    return hits, lines_hit


def fix(text):
    n = Counter()
    out = []
    for ch in text:
        o = ord(ch)
        if o in INVISIBLE:
            n["보이지 않는 문자 삭제"] += 1
            continue
        if EMOJI.match(ch):
            n["이모지 삭제"] += 1
            continue
        if ch in VISIBLE and VISIBLE[ch][1] is not None:
            n["%s → %r" % (VISIBLE[ch][0], VISIBLE[ch][1])] += 1
            out.append(VISIBLE[ch][1])
            continue
        out.append(ch)
    s = "".join(out)
    # en dash: 숫자 사이면 하이픈, 그 밖에는 " - "
    s, k1 = re.subn(r"(?<=\d)–(?=\d)", "-", s)
    s, k2 = re.subn("–", " - ", s)
    if k1:
        n["en dash → '-' (숫자 사이)"] = k1
    if k2:
        n["en dash → ' - '"] = k2
    s = re.sub(r" {2,}-", " -", s)          # 공백 중복 정리
    s = re.sub(r"- {2,}", "- ", s)
    return s, n


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    text = open(path, encoding="utf-8").read()
    hits, lines_hit = scan(text)

    print("# 문자 검사 · %s\n" % os.path.basename(path))
    inv = [(k, v) for k, v in hits.items() if k[0] == "보이지 않음"]
    vis = [(k, v) for k, v in hits.items() if k[0] == "기호"]

    print("## 보이지 않는 문자")
    if inv:
        for (_, name), c in sorted(inv, key=lambda x: -x[1]):
            print("  %s  %d개" % (name, c))
        for ln, what in lines_hit[:30]:
            print("    %d행  %s" % (ln, what))
    else:
        print("  없음")

    print("\n## 눈에 보이는 기호")
    if vis:
        for (_, name), c in sorted(vis, key=lambda x: -x[1]):
            auto = ""
            ch = name.split(" ")[0]
            if ch in VISIBLE and VISIBLE[ch][1] is not None:
                auto = "  → --fix로 %r 로 바꿈" % VISIBLE[ch][1]
            elif ch == "–":
                auto = "  → --fix로 하이픈 또는 ' - '"
            elif "이모지" in name:
                auto = "  → --fix로 삭제"
            else:
                auto = "  → **자동 치환 안 함. 눈으로 판단**"
            print("  %s  %d개%s" % (name, c, auto))
    else:
        print("  없음")

    if "--fix" in sys.argv:
        new, n = fix(text)
        out = os.path.splitext(path)[0] + ".fixed" + os.path.splitext(path)[1]
        open(out, "w", encoding="utf-8").write(new)
        print("\n## 치환 결과 → %s" % out)
        for k, v in n.most_common():
            print("  %s  %d건" % (k, v))
        print("\n**반드시 대조한다**:  diff %s %s" % (path, out))
        print("보이지 않는 문자와 기호만 바뀌어야 한다. 글자가 바뀌었으면 되돌린다.")
    else:
        print("\n치환하려면 --fix. 줄바꿈 없는 공백·줄임표·화살표는 정당한 자리가"
              " 있어 자동으로 안 바꾼다.")


if __name__ == "__main__":
    main()
