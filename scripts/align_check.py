# -*- coding: utf-8 -*-
"""두 판(국문·영문)을 대조한다 - 단위 수, 수치, 인용, 약어.

쓰임:
  python align_check.py 원고_영문.md 원고_국문.md
  python align_check.py 영문.md 국문.md --out outputs/번역대조.md
  python align_check.py 영문.md 국문.md --with-refs   # 참고문헌까지 포함해 대조

무엇을 보나
  ① 단위 수     절·문단·문장 개수가 맞는가 (문단이 갈라지거나 합쳐졌는가)
  ② 수치        한쪽에만 있는 수치, 값이 다른 수치
  ③ 인용        한쪽에만 있는 (저자, 연도)
  ④ 약어        한쪽에만 있는 대문자 약어

**의미가 같은지는 이 도구가 못 본다.** 여기서 나오는 것은 "어긋난 자리 후보"이고,
문단쌍을 나란히 놓고 사람이 읽어서 판정한다(`18_번역대조.md`).
"""
import io
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def body(path, with_refs=False):
    """본문만 돌려준다. 참고문헌 절부터는 자른다(저자·연도가 대량으로 나온다)."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    out, in_code, cut = [], False, False
    for ln in raw.split("\n"):
        st = ln.strip()
        if st.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not with_refs and re.match(
                r"^#{1,4}\s*(References|Bibliography|참고문헌)", st, re.I):
            cut = True
        if cut:
            continue
        out.append(ln)
    return "\n".join(out)


def units(text):
    secs = len(re.findall(r"^#{1,4}\s+\S", text, re.M))
    paras, cur = 0, []
    for ln in text.split("\n") + [""]:
        st = ln.strip()
        if not st:
            if cur:
                paras += 1
                cur = []
            continue
        if st.startswith(("#", "|", ">")) or re.match(r"^([-*+]|\d+\.)\s", st):
            continue
        cur.append(st)
    en = len(re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text))
    ko = len(re.split(r"(?<=다\.)\s+", text))
    return secs, paras, max(en, ko)


def numbers(text):
    """본문 수치. 표 안의 값도 포함한다."""
    vals = re.findall(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?\s?%?(?![\w])", text)
    keep = Counter()
    for v in vals:
        v = v.strip()
        if re.fullmatch(r"(19|20)\d{2}", v.rstrip("%")):     # 연도는 뺀다
            continue
        if len(v.rstrip("%")) <= 1:                          # 한 자리 수는 뺀다
            continue
        keep[v] += 1
    return keep


def cites(text):
    out = Counter()
    for m in re.finditer(r"([A-Z][A-Za-z'’-]+)(?:\s+(?:and|&|et\s+al\.?|과|와)"
                         r"\s*[A-Za-z'’-]*)?[,\s]*\(?((?:19|20)\d{2})[a-z]?\)?",
                         text):
        out[(m.group(1), m.group(2))] += 1
    return out


def abbrs(text):
    return Counter(re.findall(r"(?<![A-Za-z])([A-Z]{2,6})(?![A-Za-z])", text))


def diff_table(title, a, b, la, lb, limit=25):
    only_a = [k for k in a if k not in b]
    only_b = [k for k in b if k not in a]
    print("\n## %s" % title)
    print("- %s %d종 / %s %d종" % (la, len(a), lb, len(b)))
    if not only_a and not only_b:
        print("- 양쪽이 같다")
        return 0
    if only_a:
        print("- **%s에만 있음 %d종**: %s" % (la, len(only_a),
              ", ".join(str(x) for x in sorted(map(str, only_a))[:limit])))
    if only_b:
        print("- **%s에만 있음 %d종**: %s" % (lb, len(only_b),
              ", ".join(str(x) for x in sorted(map(str, only_b))[:limit])))
    return len(only_a) + len(only_b)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return
    pa, pb = args[0], args[1]
    la, lb = os.path.basename(pa)[:22], os.path.basename(pb)[:22]
    wr = "--with-refs" in sys.argv
    ta, tb = body(pa, wr), body(pb, wr)

    buf = io.StringIO()
    old = sys.stdout
    out_path = opt("--out")
    if out_path:
        sys.stdout = buf

    print("# 두 판 대조 · %s ↔ %s" % (la, lb))

    sa, paa, sea = units(ta)
    sb, pab, seb = units(tb)
    print("\n## ① 단위 수")
    print("| 단위 | %s | %s | 차이 |" % (la, lb))
    print("|--|--|--|--|")
    for name, x, y in (("절", sa, sb), ("문단", paa, pab), ("문장", sea, seb)):
        mark = "" if x == y else "  **다름**"
        print("| %s | %d | %d | %+d%s |" % (name, x, y, y - x, mark))
    print("\n문단 수가 다르면 **문단이 갈라졌거나 합쳐진 자리**가 있다는 뜻이다."
          " 어느 절에서 갈라졌는지는 unit_census.py로 절별 개수를 뽑아 대조한다.")

    n = 0
    n += diff_table("② 수치", numbers(ta), numbers(tb), la, lb)

    # 인용은 두 단계로 본다. 국문은 "A와 B(2000)"처럼 둘째 저자를 쓰기도 해서
    # 저자 이름만으로 대조하면 잡음이 많다.
    ca, cb = cites(ta), cites(tb)
    ya, yb = {}, {}
    for (au, yr) in ca:
        ya.setdefault(yr, set()).add(au)
    for (au, yr) in cb:
        yb.setdefault(yr, set()).add(au)
    print("\n## ③ 인용")
    print("- %s %d종 / %s %d종" % (la, len(ca), lb, len(cb)))
    only_ya = sorted(set(ya) - set(yb))
    only_yb = sorted(set(yb) - set(ya))
    if only_ya or only_yb:
        if only_ya:
            print("- **%s에만 있는 연도 %d개**(누락 후보): %s"
                  % (la, len(only_ya), ", ".join(
                      "%s(%s)" % (y, "/".join(sorted(ya[y]))[:28]) for y in only_ya[:15])))
        if only_yb:
            print("- **%s에만 있는 연도 %d개**(누락 후보): %s"
                  % (lb, len(only_yb), ", ".join(
                      "%s(%s)" % (y, "/".join(sorted(yb[y]))[:28]) for y in only_yb[:15])))
        n += len(only_ya) + len(only_yb)
    else:
        print("- 연도 집합은 양쪽이 같다")
    diffauth = [y for y in set(ya) & set(yb) if not (ya[y] & yb[y])]
    if diffauth:
        print("- 연도는 같은데 저자 표기가 다른 것 %d개(표기 차이일 수 있다):"
              " %s" % (len(diffauth), ", ".join(
                  "%s %s↔%s" % (y, "/".join(sorted(ya[y]))[:14],
                                "/".join(sorted(yb[y]))[:14])
                  for y in sorted(diffauth)[:10])))

    n += diff_table("④ 약어", abbrs(ta), abbrs(tb), la, lb)

    print("\n---")
    print("**어긋난 자리 후보 %d건.**" % n)
    print("수치가 한쪽에만 있으면 옮기다 빠졌거나 한쪽에서만 새로 계산한 것이다.")
    print("인용이 한쪽에만 있으면 번역하며 빠뜨렸거나 더한 것이다.")
    print("**의미·수위가 같은지는 이 도구가 못 본다. 문단쌍을 나란히 놓고 읽는다.**")

    if out_path:
        sys.stdout = old
        open(out_path, "w", encoding="utf-8").write(buf.getvalue())
        print("저장: %s" % out_path)
        print("어긋난 자리 후보 %d건" % n)


if __name__ == "__main__":
    main()
