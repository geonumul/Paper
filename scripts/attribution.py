# -*- coding: utf-8 -*-
"""**우리 논리가 인용한 저자의 주장처럼 읽히는 자리**를 찾는다.

쓰임:

  python attribution.py 원고.md --txt <인용원문폴더>

  python attribution.py 원고.md --txt <인용원문폴더> --min 2

      한 마디에 원문에 없는 말이 몇 개부터 걸릴지 (기본 2)

왜 이 검사가 있나

  인용이 진짜고 따옴표 안 문장도 원문 그대로인데, **그 뒤에 이어 붙인 우리
  말이 저자의 주장처럼 읽히는** 자리가 있다. 되짚기는 이것을 못 잡는다.
  인용문은 원문에 있고 논문 이름도 맞기 때문이다.

  실제로 잡힌 것.

      O'Brien (2007) cautions against reading such thresholds mechanically,
      since the variance of a coefficient depends on more than the variance
      inflation factor alone, and dummies drawn from one categorical
      variable are mutually dependent by construction rather than through
      redundant information.

  앞의 둘은 원문에 있다. 세 번째 마디는 **원문 8,172낱말에 `dummy` 0회,
  `categorical` 0회, `binary` 0회, `nominal` 0회, `by construction` 0회**다.
  맞는 말이지만 우리 말이고, 저자 이름으로 열린 한 문장 안에 있으면 그의
  말로 읽힌다.

무엇을 보나

  1 `저자 (연도)`로 열리거나 그것을 주어로 삼은 문장을 모은다
  2 그 저자의 원문을 인용 원문 폴더에서 찾는다
  3 문장을 마디로 가른다 (`, since` `, and` `; ` `because` `so that`)
  4 마디마다 **그 원문에 0회인 내용어**를 센다

**0회는 어림이 아니라 셈이다.** 그래서 이 검사는 후보를 적게 낸다. 걸린
자리는 원문을 열어 그 개념이 다른 말로 있는지 본다. 없으면 문장을 나눠
우리 말을 우리 이름으로 돌린다.

  고친 예: `... alone. Dummies drawn from one categorical variable are
  mutually dependent by construction, so the threshold is read in that
  light here.`

**이것도 후보다.** 개념이 다른 말로 그 논문에 있을 수 있다. 판정은 원문을
열어 사람이 한다.
"""
import io
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _norm import norm_text                                    # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

# `Surname (2007)` / `Surname et al. (2013)` / `Surname and Other (2011)`
CITE = re.compile(
    r"\b([A-Z][A-Za-zÀ-ÿ'’-]{2,})"
    r"(?:\s+(?:et\s+al\.|and\s+[A-Z][A-Za-z'’-]+|&\s*[A-Z][A-Za-z'’-]+))?"
    r"\s*\((\d{4})[a-z]?\)")

# 마디를 가르는 자리. 이어 붙인 우리 말은 대개 여기 뒤에 온다
CLAUSE = re.compile(r",\s+(?:since|because|as|and|while|whereas|so)\s+|"
                    r";\s+|\s+so\s+that\s+|\s+in\s+that\s+")

STOP = set("""the a an of to in on at and or for with by is are was were be
been it its this that these those not no than then so such can could may will
would have has had do does did which who what when where while also more most
each every both all any some one two three four five our we us their there
here into from over under between among against about after before during
study studies paper papers article research results result finding findings
show shows shown found note notes noted report reports reported argue argues
argued suggest suggests suggested conclude concludes concluded cautions
caution warns warn state states stated write writes wrote
rather covers cover applied apply applies reasoning separately together
instead within without through across whether because since given used using
same different other another following above below here there present
current recent later earlier further additional overall general specific""".split())

# **일반 학술어는 걸러낸다.** `rather`나 `applied`가 그 원문에 없다는 것은
# 그 저자가 안 쓴 말이라는 뜻일 뿐 우리가 그의 주장을 넓혔다는 뜻이 아니다.
# 노이즈가 많은 검사는 사람이 출력을 안 읽게 만든다


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def flat(t):
    t = norm_text(t, fold_accents=True)
    # 정렬된 두 단 글에서 줄 끝 붙임표를 잇는다 (con- tinue)
    t = re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", t)
    return re.sub(r"\s+", " ", t).lower()


def load_sources(txt_dir):
    """파일 이름에서 성과 연도를 뽑아 둔다."""
    out = []
    for p in sorted(glob.glob(os.path.join(txt_dir, "*.txt"))):
        name = os.path.splitext(os.path.basename(p))[0]
        m = re.match(r"([A-Za-z'’-]+?)([A-Z][a-z]+)?(\d{4})", name)
        if not m:
            continue
        out.append((name, m.group(1).lower(), m.group(3), p))
    return out


_TXT = {}


def source_text(path):
    if path not in _TXT:
        _TXT[path] = flat(io.open(path, encoding="utf-8",
                                  errors="replace").read())
    return _TXT[path]


def find_source(sources, surname, year):
    """그 저자 그 해의 원문. 성이 파일 이름 앞머리와 맞아야 한다."""
    s = re.sub(r"[^a-z]", "", surname.lower())
    cand = [x for x in sources
            if x[2] == year and (x[1].startswith(s[:6]) or s.startswith(x[1][:6]))]
    if len(cand) == 1:
        return cand[0]
    # 연도가 한 해 어긋나는 판(온라인 우선 공개)까지 본다
    near = [x for x in sources
            if abs(int(x[2]) - int(year)) <= 1
            and (x[1].startswith(s[:6]) or s.startswith(x[1][:6]))]
    return near[0] if len(near) == 1 else None


def terms_of(clause):
    """그 마디에서 내용을 지고 있는 말."""
    ws = re.findall(r"[A-Za-z][A-Za-z-]{4,}", clause)
    out, seen = [], set()
    for w in ws:
        k = w.lower()
        if k in STOP or k in seen:
            continue
        seen.add(k)
        out.append(w)
    return out


def body_of(md):
    m = re.search(r"(?im)^#{0,4}\s*\**(references|bibliography)\**\s*$", md)
    t = md[:m.start()] if m else md
    t = re.sub(r"(?m)^\s*\|.*$", " ", t)          # 표
    t = re.sub(r"\$\$?[^$]{0,400}\$\$?", " ", t)  # 수식
    return re.sub(r"\s+", " ", t)


def sentences(t):
    out, last = [], 0
    end = re.compile(r"(?<!et al)(?<!e\.g)(?<!i\.e)(?<!cf)(?<!Fig)(?<![A-Z])"
                     r"[.!?](?=\s+[\"'(“]?[A-Z0-9])")
    for m in end.finditer(t):
        s = t[last:m.end()].strip()
        if s:
            out.append(s)
        last = m.end()
    if t[last:].strip():
        out.append(t[last:].strip())
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return
    md_path = args[0]
    txt_dir = opt("--txt", "literature/_txt")
    least = int(opt("--min", 2))

    sources = load_sources(txt_dir)
    if not sources:
        print("인용 원문이 없다: %s" % txt_dir)
        return
    body = body_of(io.open(md_path, encoding="utf-8",
                           errors="replace").read())

    print("# 귀속 검사 · %s" % os.path.basename(md_path))
    print("")
    print("- 인용 원문 %d편 · 한 마디에 원문에 없는 말이 **%d개 이상**이면"
          " 올린다" % (len(sources), least))
    print("")

    checked = flagged = no_src = 0
    rows = []
    for s in sentences(body):
        m = CITE.search(s)
        if not m or m.start() > 60:
            continue          # 저자를 주어로 삼은 문장만 본다
        surname, year = m.group(1), m.group(2)
        src = find_source(sources, surname, year)
        if not src:
            no_src += 1
            continue
        checked += 1
        t = source_text(src[3])
        parts = [p for p in CLAUSE.split(s[m.end():]) if p and p.strip()]
        for i, cl in enumerate(parts):
            if i == 0 or len(cl.split()) < 6:
                continue      # 첫 마디는 인용의 본체다
            miss = [w for w in terms_of(cl)
                    if t.find(w.lower()) < 0]
            if len(miss) >= least:
                rows.append((src[0], " ".join(s.split())[:190],
                             " ".join(cl.split())[:150], miss))
                flagged += 1

    print("- 저자를 주어로 삼은 문장 **%d개**를 원문과 맞췄다" % checked)
    if no_src:
        print("- 원문을 못 찾은 인용 %d개는 건너뛰었다" % no_src)
    print("")
    if not rows:
        print("**걸린 자리가 없다.** 저자 이름으로 연 문장의 이어 붙은 마디가"
              " 모두 그 원문의 말로 되어 있다.")
        return
    print("## 원문에 없는 말로 이어진 마디 **%d개**" % flagged)
    print("")
    for name, sent, cl, miss in rows:
        print("### [%s]" % name)
        print("- 우리: %s" % sent)
        print("- 이어 붙은 마디: %s" % cl)
        print("- **그 원문에 0회인 말: %s**" % ", ".join(miss[:8]))
        print("")
    print("---")
    print("**후보다.** 그 개념이 다른 말로 원문에 있을 수 있으니 원문을 열어")
    print("본다. 없으면 문장을 나눠 우리 말을 우리 이름으로 돌린다. 저자")
    print("이름으로 연 한 문장 안에 두면 그의 주장으로 읽힌다.")


if __name__ == "__main__":
    main()
