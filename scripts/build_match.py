# -*- coding: utf-8 -*-
"""작업본과 **투고물**이 같은 글인지 맞춰 본다.

쓰임:

  python build_match.py 원고.md 빌드본.pdf

  python build_match.py 원고.md 원고.tex

  python build_match.py 원고.md 빌드본.pdf --show 20

      안 맞는 문장을 몇 개까지 보여 줄지 (기본 12)

왜 이 검사가 있나

  **검수한 것과 내는 것이 다른 파일일 수 있다.** 작업은 마크다운으로 하고
  투고는 tex로 짠 PDF를 내면, 둘이 갈라진 줄 모르고 없는 잘못을 고치게 된다.

  실제로 그 일이 났다. 한 원고에서 이렇게 나왔다.

  | 지적한 것 | 작업본 .md | 투고물 tex·PDF |
  |--|--|--|
  | `Note.` 를 `Note:` 로 | 8곳 | 이미 `Note:` 8곳 |
  | 제목 뒤 `?.` 겹침 | 2곳 | 0곳 |
  | Shmueli 쪽 번호 빠짐 | 빠짐 | `289--310` 있음 |
  | 서지 형식이 게재작과 다름 | `(2013).` | `Abad, J., ..., 2013.` |

  마지막이 제일 크다. **투고본 서지는 이미 게재작과 같은 형식**이었다.
  스타일 파일이 그렇게 찍기 때문이다. 작업본만 보고 지적했다.

  반대 방향도 났다. 원고를 고치고 다시 빌드하지 않아, **투고 폴더의 PDF에
  그날 고친 열한 곳이 하나도 없었다.**

무엇을 보나

  1 작업본의 문장이 투고물에 있는가 (없으면 **빌드가 옛것**이거나 안 실린 글)
  2 몇 %가 맞는가

**붙임표를 양쪽에서 지운다.** 정렬된 두 단 글은 `con- tinue`로 끊기므로,
안 이으면 멀쩡한 문장이 무더기로 "없다"고 나온다(실제로 85개가 그랬다).

**한 방향만 본다.** 작업본에 있고 투고물에 없는 것을 찾는다. 그 반대는
표·서지처럼 스타일 파일이 만들어 내는 글이 많아 셈이 안 된다.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _norm import norm_text, mask_currency                     # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

SENT_END = re.compile(r"(?<!et al)(?<!e\.g)(?<!i\.e)(?<!cf)(?<!Fig)(?<!vs)"
                      r"(?<![A-Z])[.!?](?=\s+[\"'(]?[A-Z0-9])")


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def key(s):
    """대조용으로 다듬는다. **양쪽에 똑같이 쓴다.**"""
    s = norm_text(s, fold_accents=True)
    # **붙임표를 아예 지운다.** 줄 끝에서 끊긴 것만 이으면,
    # `site-level`처럼 원래 붙임표가 있는 말이 한쪽에서만 이어져
    # `site level` 대 `sitelevel`로 갈린다. 양쪽에서 똑같이 지우면
    # 어느 쪽이 끊겼든 같은 글자가 된다
    s = re.sub(r"-\s*", "", s)
    # **통화의 달러를 먼저 가린다.** `US$ 4 million`의 달러가 수식
    # 구분자로 읽혀, 그 뒤 달러까지 사이가 통째로 지워진다. 한 번에
    # PDF 6,400자가 사라져 멀쩡한 문장 쉰 개가 "투고물에 없다"로
    # 나왔다. 사례집에 이미 적힌 사고를 그대로 되풀이했다
    s = mask_currency(s)
    s = re.sub(r"\$[^$]*\$", " ", s)                   # 수식은 조판이 바꾼다
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", s)   # tex 명령
    s = re.sub(r"\([^)]*\)", " ", s)                   # 인용 괄호는 줄바꿈이 는다
    s = re.sub(r"[^A-Za-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def read_any(path):
    if path.lower().endswith(".pdf"):
        try:
            import fitz
        except ImportError:
            print("PDF를 읽으려면 PyMuPDF가 필요하다: pip install pymupdf")
            sys.exit(2)
        # **단 순서로 읽는다.** 줄 순서로 읽으면 왼쪽 단과 오른쪽 단이
        # 한 줄씩 섞여, 멀쩡한 문장이 무더기로 "투고물에 없다"고 나온다.
        # `pdf_text.py`가 고친 것과 같은 자리다
        from pdf_text import page_text
        d = fitz.open(path)
        # 면주와 쪽 번호를 버린다. 그것이 문장 한가운데 박힌다
        t = " ".join(" ".join(page_text(p, 0.08).split())
                     for p in d)
        d.close()
        return t
    return io.open(path, encoding="utf-8", errors="replace").read()


def source_sentences(t):
    """작업본의 본문 문장. 표·수식·서지는 뺀다."""
    m = re.search(r"(?im)^#{0,4}\s*\**(references|bibliography)\**\s*$", t)
    if m:
        t = t[:m.start()]
    t = "\n".join(l for l in t.split("\n")
                  if l.strip() and not l.strip().startswith(("|", "#", "$$")))
    t = re.sub(r"\s+", " ", t)
    out, last = [], 0
    for m in SENT_END.finditer(t):
        s = t[last:m.end()].strip()
        if s:
            out.append(s)
        last = m.end()
    if t[last:].strip():
        out.append(t[last:].strip())
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return
    src_path, out_path = args[0], args[1]
    show = int(opt("--show", 12))
    for p in (src_path, out_path):
        if not os.path.exists(p):
            print("파일이 없다: %s" % p)
            return

    src = read_any(src_path)
    dst = key(read_any(out_path))
    sents = source_sentences(src)

    miss, checked = [], 0
    for s in sents:
        k = key(s)
        if len(k.split()) < 8:
            continue          # 짧은 조각은 우연히 맞고 우연히 틀린다
        checked += 1
        if " ".join(k.split()[:10]) not in dst:
            miss.append(s)

    print("# 작업본과 투고물 맞추기")
    print("")
    print("- 작업본: %s" % os.path.basename(src_path))
    print("- 투고물: %s" % os.path.basename(out_path))
    print("")
    if not checked:
        print("**잴 문장이 없다.** 작업본에서 본문을 못 뽑았다.")
        return
    hit = checked - len(miss)
    print("- 잰 문장 **%d개** 중 투고물에 있는 것 **%d개 (%.1f%%)**"
          % (checked, hit, 100.0 * hit / checked))
    print("")
    if not miss:
        print("**둘이 같은 글이다.** 작업본의 모든 문장이 투고물에 있다.")
        return

    # **조판이 바꾸는 자리는 갈라 놓는다.** 수식과 표·그림 표시가 든
    # 문장은 작업본과 투고물의 글자가 원래 다르다. 그것을 지적과 섞어
    # 내놓으면 읽는 쪽이 스무 개를 다 들여다보게 된다
    typeset = [x for x in miss if "$" in x or "**" in x]
    real = [x for x in miss if x not in typeset]
    if real:
        print("## 투고물에 없는 문장 **%d개**" % len(real))
        print("")
        for x in real[:show]:
            print("    - %s" % " ".join(x.split())[:150])
        if len(real) > show:
            print("    - ... 외 %d개" % (len(real) - show))
        print("")
    if typeset:
        print("## 조판이 바꾸는 자리 %d개 (수식·표 표시가 든 문장)"
              % len(typeset))
        print("")
        print("    작업본의 `$p$`나 `**Table 1 ...**`는 투고물에서 다른 글자로")
        print("    찍힌다. **이것은 지적이 아니다.** 다만 그 문장이 정말")
        print("    실렸는지는 인쇄면을 열어 눈으로 본다")
        print("")
        for x in typeset[:4]:
            print("    - %s" % " ".join(x.split())[:120])
        if len(typeset) > 4:
            print("    - ... 외 %d개" % (len(typeset) - 4))
        print("")
    if not real:
        print("**투고물에 안 실린 문장은 없다.** 안 맞는 %d개는 전부 조판이"
              " 바꾸는 자리다" % len(typeset))
        return
    print("")
    print("---")
    print("**둘 중 하나다.**")
    print("")
    print("1. **빌드가 옛것이다.** 작업본을 고치고 다시 안 짰다. 다시 짜고")
    print("   이 검사를 다시 돌린다")
    print("2. **작업본에만 있는 글이다.** 투고물에 안 실렸다면 그것이")
    print("   지적이다")
    print("")
    print("**어느 쪽이든 검수는 투고물을 보고 한다.** 작업본만 보고 고치면")
    print("내는 글은 안 고쳐진다. 반대로 투고물에만 있는 것을 못 보게 된다.")
    sys.exit(1)


if __name__ == "__main__":
    main()
