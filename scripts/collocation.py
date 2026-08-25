# -*- coding: utf-8 -*-
"""한 낱말이 **어떤 구문으로** 쓰이는지 우리와 게재작을 견준다.

쓰임:
  python collocation.py 원고.md --txt <코퍼스> --word read
  python collocation.py 원고.md --txt <코퍼스> --top 12
      원고에서 많이 쓰는 낱말 12개를 자동으로 골라 본다

왜 필요한가
  **낱말 빈도만 보면 못 잡는 것이 있다.** `read`는 게재작 10편이 쓴다.
  그러나 게재작의 read는 *문서를 읽는다*이고 우리 것은 *결과를 해석한다*
  였다. `read as`, `read against`는 게재작 51편에 **0편**인데 우리는 여덟
  번 썼고, 같은 자리에 게재작이 쓰는 `understood as`(7편), `in light of`
  (11편), `taken as`(6편)는 우리가 한 번도 안 썼다.

  한 원고에서 여덟 번 쓰이고 게재작 쉰한 편에서 한 번도 안 쓰이는 구문은
  **어휘가 아니라 말버릇**이다. 낱말 대장은 그것을 못 본다.

**0편만으로는 지적이 안 된다.** 우리가 네 번 이상 쓰는 이음의 상당수(한 원고에서 28%)가
게재작 전체에 없다. 그래서 도구가 **기저율을 먼저 재서** 보여 준다. 걸리는 것은
게재작이 같은 자리에 쓰는 표현을 **우리가 하나도 안 쓸 때**다.

무엇을 내나
  - 우리가 그 낱말과 함께 쓰는 이음(뒤 한두 낱말)과 횟수
  - 그 이음을 게재작 몇 편이 쓰는가
  - **게재작이 0편인데 우리가 두 번 이상 쓰는 이음** (읽어야 할 것)

읽는 법 - 두 갈래로 갈린다
  1 **우리가 만든 개념어**: `external institutional`(11회) `external
    intervention`(9회)처럼 되풀이되는 명사구가 게재작 0편이면, 그건 우리가
    만든 말이다. 정의를 붙였는지, 그 저널의 말로 바꿀 수 있는지 본다
  2 **흔한 이음**: `housekeeping is`, `sites that` 같은 것은 게재작이 그
    주제를 안 다뤄서 0편일 뿐이다. 지적이 아니다

**이것도 후보다.** 바꿀지는 저자가 정한다. 문장 자리가 그 구문을 요구하는
경우도 있다.
"""
import io
import os
import re
import sys
import glob
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REFHEAD = re.compile(r"(?im)^#{0,4}\s*\**(references|bibliography|참고문헌)\**\s*$")
STOP_NEXT = set("the a an of to in on at and or for with by is are was were be"
                " that this these those it its as from".split())


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def body_of(md):
    m = REFHEAD.search(md)
    t = md[:m.start()] if m else md
    t = re.sub(r"\$\$?[^$]{0,400}\$\$?", " ", t)
    t = re.sub(r"(?m)^\s*\|.*$", " ", t)
    return re.sub(r"\s+", " ", t)


def corpus_prose(t):
    cands = [m.start() for m in re.finditer("References|Bibliography", t)
             if m.start() > len(t) * 0.5]
    return re.sub(r"\s+", " ", t[:cands[0]] if cands else t)


def follows(text, w, n=2):
    """그 낱말 뒤에 오는 한두 낱말을 모은다."""
    out = Counter()
    rx = re.compile(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])\s+"
                    r"([A-Za-z][A-Za-z'-]*)(?:\s+([A-Za-z][A-Za-z'-]*))?",
                    re.I)
    for m in rx.finditer(text):
        a = (m.group(1) or "").lower()
        b = (m.group(2) or "").lower()
        if a:
            out[w + " " + a] += 1
        if a in STOP_NEXT and b:
            out[w + " " + a + " " + b] += 1
    return out


def base_rate(body, docs, least=4, sample=40):
    """우리가 자주 쓰는 이음 중 몇 %가 게재작에 아예 없는가.

    **0편이라는 사실은 생각보다 흔하다.** 실제로 네 번 이상 쓰는 이음의
    28%가 게재작 51편 전체에 없었다. 그 비율을 모르면 평범한 이음을
    지적으로 올리게 된다. 그래서 먼저 기저율을 재서 함께 보여 준다.
    """
    bi = Counter()
    ws = re.findall(r"[A-Za-z][A-Za-z'-]*", body.lower())
    for i in range(len(ws) - 1):
        if ws[i] in STOP_NEXT or len(ws[i]) < 4:
            continue
        bi[ws[i] + " " + ws[i + 1]] += 1
    cand = [p_ for p_, n in bi.most_common() if n >= least][:sample]
    if not cand:
        return 0.0
    zero = 0
    for p_ in cand:
        hit = any(re.search(r"(?<![A-Za-z])" + re.escape(p_) + r"(?![A-Za-z])",
                            t, re.I) for t in docs)
        if not hit:
            zero += 1
    return 100.0 * zero / len(cand)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return
    md_path = args[0]
    txt_dir = opt("--txt", "literature/_txt")
    word = opt("--word")
    top = int(opt("--top", 10))

    body = body_of(io.open(md_path, encoding="utf-8", errors="replace").read())
    docs = []
    for f in sorted(glob.glob(os.path.join(txt_dir, "*.txt"))):
        docs.append(corpus_prose(io.open(f, encoding="utf-8",
                                         errors="replace").read()))
    if not docs:
        print("코퍼스가 없다: %s" % txt_dir)
        return

    if word:
        words = [word]
    else:
        freq = Counter(x.lower() for x in re.findall(r"[A-Za-z]{4,}", body))
        words = [w for w, _ in freq.most_common(200)
                 if w not in STOP_NEXT][:top]

    print("# 이음 대조 · 원고 대 게재작 %d편" % len(docs))
    print("")
    base = base_rate(body, docs)
    print("- **기저율: 우리가 네 번 이상 쓰는 이음 중 %.0f%%가 게재작 0편이다.**"
          % base)
    print("  0편이라는 사실 하나만으로는 지적이 못 된다. **걸리는 것은 게재작이"
          " 같은 자리에 쓰는 표현을 우리가 하나도 안 쓸 때다.**")
    print("")
    flagged = 0
    for w in words:
        ours = follows(body, w)
        if not ours:
            continue
        # **그 낱말 자체가 게재작에 드물면 이음을 견줄 바탕이 없다.**
        # SHAP처럼 게재작이 안 쓰는 말은 뒤에 무엇이 붙어도 0편이 나온다.
        # 그건 이음의 문제가 아니라 낱말의 문제이고, 낱말 대장이 이미 잡았다
        base = sum(1 for t in docs
                   if re.search(r"(?<![A-Za-z])" + re.escape(w)
                                + r"(?![A-Za-z])", t, re.I))
        if base < 3:
            continue
        rows = []
        for phrase, n in ours.most_common(12):
            cnt = sum(1 for t in docs
                      if re.search(r"(?<![A-Za-z])" + re.escape(phrase)
                                   + r"(?![A-Za-z])", t, re.I))
            rows.append((phrase, n, cnt))
        # 뒤에 붙은 말도 게재작에 있어야 이음을 견줄 수 있다. 우리 자료
        # 이름이 붙은 것(construction module 같은)은 이음 문제가 아니다
        def tail_known(phrase):
            tail = phrase.split()[-1]
            return sum(1 for t in docs
                       if re.search(r"(?<![A-Za-z])" + re.escape(tail)
                                    + r"(?![A-Za-z])", t, re.I)) >= 3

        # 낱말을 지정해 볼 때는 두 번부터, 여러 낱말을 훑을 때는 세 번 부터
        # 본다. 두 번짜리를 다 올리면 읽을 수 없을 만큼 나온다
        least = 2 if word else 3
        bad = [r for r in rows
               if r[2] == 0 and r[1] >= least and tail_known(r[0])]
        if not bad:
            continue
        flagged += 1
        print("## %s (원고 %d회)" % (w, sum(ours.values())))
        print("")
        print("| 이음 | 우리 | 게재작 편수 |")
        print("|--|--|--|")
        for phrase, n, cnt in rows:
            mark = " **0편**" if cnt == 0 and n >= 2 else ""
            print("| %s | %d | %d%s |" % (phrase, n, cnt, mark))
        # 게재작이 그 낱말과 함께 즐겨 쓰는 이음 중 우리가 안 쓰는 것
        theirs = Counter()
        for t in docs:
            for phrase in follows(t, w):
                theirs[phrase] += 1
        miss = [(p, c) for p, c in theirs.most_common(30)
                if c >= 3 and p not in ours]
        if miss:
            print("")
            print("- 게재작이 쓰는데 우리는 안 쓰는 이음: %s"
                  % ", ".join("%s(%d편)" % (p, c) for p, c in miss[:6]))
        print("")
        print("→ **게재작 0편인 이음을 우리가 되풀이하면 말버릇이다.**"
              " 문장 자리가 그 구문을 요구하는지 보고, 아니면 저자가 정한다")
        print("")

    if not flagged:
        print("게재작이 안 쓰는 이음을 되풀이하는 낱말은 없다.")


if __name__ == "__main__":
    main()
