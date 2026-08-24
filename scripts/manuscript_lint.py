# -*- coding: utf-8 -*-
"""원고의 정합을 기계로 검사한다 (규격·부동체 참조·구성 예고·문단·수치).

쓰임:
  python manuscript_lint.py 원고.md
  python manuscript_lint.py 원고.md --abstract-max 250 --hl-max 85 --kw-max 7

검사
  ① 규격        초록 낱말 수 / 하이라이트 개수·글자 수 / 키워드 개수
  ② 부동체 참조 본문이 부르는 표·그림·부록이 실제로 있는가, 있는데 안 부르는가
  ③ 구성 예고   "Section N에서 …"가 실제 절과 맞는가
  ④ 문단        1-2문장짜리 문단 (최소 3문장 규칙)
  ⑤ 수치 정합   초록·본문·표에 흩어진 수치가 서로 맞는가

**후보만 낸다. 판정은 사람이 한다.** 특히 ⑤는 같은 수가 다른 뜻일 수 있으니
반드시 눈으로 확인한다.
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


def sections(lines):
    """(절 번호, 제목, 시작줄) 목록."""
    out = []
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", ln)
        if m:
            t = m.group(2)
            nm = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", t)
            out.append((nm.group(1) if nm else "", nm.group(2) if nm else t, i))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    src = sys.argv[1]
    ab_max = int(opt("--abstract-max", 250))
    hl_max = int(opt("--hl-max", 85))
    hl_n = opt("--hl-n", "3-5")
    kw_max = int(opt("--kw-max", 7))

    raw = open(src, encoding="utf-8", errors="replace").read()
    lines = raw.split("\n")
    secs = sections(lines)
    issues = 0
    print("# 원고 정합 검사 · %s\n" % os.path.basename(src))

    # ── ① 규격 ─────────────────────────────────────────────
    print("## ① 규격")
    def grab(title_pat):
        for num, title, i in secs:
            if re.search(title_pat, title, re.I):
                j = next((k for (_, _, k) in secs if k > i), len(lines))
                return "\n".join(lines[i + 1:j]).strip()
        return None

    ab = grab(r"^abstract|초록")
    if ab:
        n = len([w for w in re.split(r"\s+", ab) if w])
        ok = n <= ab_max
        print("- 초록 %d낱말 (상한 %d) %s" % (n, ab_max, "OK" if ok else "**초과**"))
        issues += 0 if ok else 1
        if re.search(r"\([A-Za-z][^)]*,\s*(19|20)\d{2}\)", ab):
            print("- **초록에 인용이 있다**")
            issues += 1
    else:
        print("- 초록 절을 못 찾았다(제목이 'Abstract'인지 확인)")

    hl = grab(r"^highlights|하이라이트")
    if hl:
        items = [re.sub(r"^[-*+]\s*", "", l).strip()
                 for l in hl.split("\n") if l.strip().startswith(("-", "*", "+"))]
        lo, hi = (int(x) for x in hl_n.split("-"))
        print("- 하이라이트 %d개 (규정 %s) %s"
              % (len(items), hl_n, "OK" if lo <= len(items) <= hi else "**규정 밖**"))
        for k, it in enumerate(items, 1):
            c = len(it)
            if c > hl_max:
                print("  - %d번 **%d자 (상한 %d 초과)**: %s…" % (k, c, hl_max, it[:40]))
                issues += 1
            else:
                print("  - %d번 %d자" % (k, c))
    kw = grab(r"^keywords|주요어|키워드")
    if kw:
        parts = [p for p in re.split(r"[;,]|\\sep", kw) if p.strip()]
        print("- 키워드 %d개 (상한 %d) %s"
              % (len(parts), kw_max, "OK" if len(parts) <= kw_max else "**초과**"))

    # ── ② 부동체 참조 ──────────────────────────────────────
    print("\n## ② 표·그림·부록 참조")
    body = raw
    ref_t = Counter(int(m) for m in re.findall(r"(?<!Appendix )\bTable\s+(\d+)", body))
    ref_f = Counter(int(m) for m in re.findall(r"\bFig(?:\.|ure)\s+(\d+)", body))
    cap_t = set(int(m) for m in re.findall(r"^\**Table\s+(\d+)", body, re.M))
    cap_f = set(int(m) for m in re.findall(r"^\**Fig(?:\.|ure)\s+(\d+)", body, re.M))
    for name, ref, cap in (("표", ref_t, cap_t), ("그림", ref_f, cap_f)):
        used = set(ref) - cap
        unused = cap - set(ref)
        if cap:
            missing = set(range(1, max(cap) + 1)) - cap
        else:
            missing = set()
        print("- %s: 본문 언급 %s / 캡션 %s"
              % (name, sorted(set(ref)) or "없음", sorted(cap) or "없음"))
        if used:
            print("  - **본문이 부르는데 캡션이 없다: %s**" % sorted(used))
            issues += len(used)
        if unused:
            print("  - **캡션은 있는데 본문이 안 부른다: %s**" % sorted(unused))
            issues += len(unused)
        if missing:
            print("  - **번호가 빠졌다: %s**" % sorted(missing))
            issues += len(missing)
    ap_ref = set(re.findall(r"Appendix\s+([A-G])", body))
    ap_cap = set(re.findall(r"^\**Appendix\s+([A-G])", body, re.M))
    if ap_ref or ap_cap:
        print("- 부록: 본문 언급 %s / 절 %s" % (sorted(ap_ref), sorted(ap_cap)))
        if ap_ref - ap_cap:
            print("  - **본문이 부르는데 절이 없다: %s**" % sorted(ap_ref - ap_cap))
            issues += 1

    # ── ③ 구성 예고 ────────────────────────────────────────
    print("\n## ③ 구성 예고와 실제 절")
    promised = re.findall(r"Section\s+(\d+)\s+([a-z][^.;]{5,60})", body)
    if promised:
        titles = {n: t for n, t, _ in secs if n}
        for num, what in promised:
            actual = titles.get(num, "**없음**")
            print("- 예고: Section %s %s → 실제 %s절 \"%s\""
                  % (num, what.strip()[:40], num, actual))
            if actual == "**없음**":
                issues += 1
    else:
        print("- 구성 예고 문장을 못 찾았다(있어야 하는 저널이면 확인)")

    # ── ④ 문단 ─────────────────────────────────────────────
    print("\n## ④ 문단 길이 (최소 3문장)")
    short = []
    cur, sec_now = [], ""
    for i, ln in enumerate(lines + [""]):
        m = re.match(r"^#{1,4}\s+(.+)$", ln)
        if m:
            sec_now = m.group(1)[:24]
            cur = []
            continue
        if re.match(r"^(References|Bibliography|참고문헌)", sec_now, re.I):
            continue        # 참고문헌 항목은 문단이 아니다
        st = ln.strip()
        if not st:
            if cur:
                p = " ".join(cur)
                ns = len([x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z(])|(?<=다\.)\s+", p) if len(x.split()) > 2])
                skip = re.match(
                    r"^(\*\*)?(Table|Fig(\.|ure)?|Note|Source|RQ\d|Keywords|"
                    r"표|그림|주|주요어)", p.strip())
                if 0 < ns < 3 and len(p.split()) > 12 and not skip:
                    short.append((sec_now, ns, p[:60]))
                cur = []
            continue
        if st.startswith(("|", ">", "#", "```")) or re.match(r"^([-*+]|\d+\.)\s", st):
            continue
        cur.append(st)
    if short:
        print("- %d개 (캡션·목록은 제외했으나 오탐이 있을 수 있다)" % len(short))
        for s_, n_, t_ in short[:12]:
            print("  - [%s] %d문장: %s…" % (s_, n_, t_))
        issues += len(short)
    else:
        print("- 없음")

    # ── ⑤ 수치 정합 ────────────────────────────────────────
    print("\n## ⑤ 수치 (초록·본문·표에 흩어진 값)")
    where = defaultdict(set)
    ab_i = next((i for (_, t, i) in secs if re.search(r"^abstract|초록", t, re.I)), None)
    for i, ln in enumerate(lines):
        zone = "표" if ln.strip().startswith("|") else (
            "초록" if ab_i is not None and ab_i < i < ab_i + 12 else "본문")
        for v in re.findall(r"(?<![\w.])\d+\.\d+(?![\w])|(?<![\w.])\d+\.\d+\s*%", ln):
            where[v.strip()].add(zone)
    only_ab = [v for v, z in where.items() if z == {"초록"}]
    only_tb = [v for v, z in where.items() if z == {"표"}]
    print("- 수치 %d종. 초록에만 %d종, 표에만 %d종"
          % (len(where), len(only_ab), len(only_tb)))
    if only_ab:
        print("  - **초록에만 있는 값(본문·표에 없다): %s**" % ", ".join(sorted(only_ab)[:15]))
        issues += len(only_ab)
    dec = Counter(len(v.split(".")[1].rstrip("%").strip()) for v in where)
    if len(dec) > 1:
        print("  - 소수 자리 혼재: " + ", ".join("%d자리 %d종" % kv for kv in sorted(dec.items())))

    print("\n---")
    print("**걸린 것 %d건.** 전부 후보다. 하나씩 눈으로 판정한다." % issues)


if __name__ == "__main__":
    main()
