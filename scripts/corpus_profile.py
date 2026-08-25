# -*- coding: utf-8 -*-
"""게재작 대역과 우리 원고를 같은 항목으로 재서 나란히 놓는다.

쓰임:
  python corpus_profile.py --txt literature/_txt --journal TFSC            # 대역만
  python corpus_profile.py 원고.md --txt literature/_txt --journal TFSC    # 대조
  python corpus_profile.py 원고.md --self "Technological Forecasting"      # 자기 저널 인용
  python corpus_profile.py 원고.md --out outputs/프로필.md

재는 것 (게재작 편마다 재고 대역을 낸 뒤, 원고와 견준다)
  문장   개수, 평균 낱말, 중앙값, 변동계수(리듬)
  문단   1000낱말당 문단 수
  연결   이음말 밀도(1000낱말당)
  인용   인용 밀도(1000낱말당), 괄호 인용 대 서술 인용 비율,
         한 문장 최대 인용 수, 참고문헌 개수, 최신 연도, 자기 저널 비율
  어조   완곡어 강도 분포(suggest/indicate/show/demonstrate/prove),
         we 빈도, 수동태 근사 빈도
  표기   문장당 쉼표, 소수 자리 분포
  참조   표·그림 언급 수

**대역은 게재작을 잰 결과이고, 판정은 사람이 한다.** 대역 밖이라고 전부
틀린 것이 아니다. 왜 벗어났는지 설명할 수 있으면 그대로 두면 된다.
"""
import io
import os
import re
import sys
import glob
import statistics
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CONN = ["however", "therefore", "moreover", "furthermore", "specifically",
        "thus", "in addition", "nevertheless", "in contrast", "consequently",
        "nonetheless", "accordingly", "likewise", "instead", "by contrast"]
HEDGE = ["suggest", "indicate", "show", "demonstrate", "prove"]
REF_HEAD = re.compile(
    r"^\s*#{0,4}\s*(References|REFERENCES|Bibliography|참고문헌)\s*:?\s*$", re.M)
THIS_YEAR = 2026
CITE_PAREN = re.compile(r"\([^()]*?[A-Z][A-Za-z'’-]+[^()]*?(19|20)\d{2}[a-z]?[^()]*?\)")
CITE_NARR = re.compile(r"[A-Z][A-Za-z'’-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’-]+|"
                       r"\s+et\s+al\.)?\s*\((19|20)\d{2}[a-z]?\)")


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def split_body_refs(text):
    text = re.sub(r"-\s*\n\s*", "", text)
    m = list(REF_HEAD.finditer(text))
    if not m:
        return text, ""
    return text[:m[-1].start()], text[m[-1].end():]


def sentences(text):
    t = re.sub(r"\s+", " ", text)
    t = re.sub(r"\b(et al|e\.g|i\.e|Fig|Eq|No|vs|cf|approx|p)\.", r"\1<D>", t)
    out = []
    for p in re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'])", t):
        p = p.replace("<D>", ".").strip()
        w = len(p.split())
        if 4 <= w <= 150:
            out.append(p)
    return out


def profile(text, label):
    body, refs = split_body_refs(text)
    words = len(re.findall(r"[A-Za-z]+", body)) or 1
    k = words / 1000.0
    sents = sentences(body)
    lens = [len(s.split()) for s in sents] or [0]
    p = {}
    p["낱말 수"] = words
    p["문장 수"] = len(sents)
    p["문장 길이 평균"] = round(statistics.mean(lens), 1) if sents else 0
    p["문장 길이 중앙값"] = statistics.median(lens) if sents else 0
    p["변동계수(리듬)"] = (round(statistics.stdev(lens) / statistics.mean(lens), 2)
                       if len(lens) > 1 and statistics.mean(lens) else 0)
    p["문장당 쉼표"] = round(sum(s.count(",") for s in sents) / max(1, len(sents)), 2)
    low = body.lower()
    p["이음말/1000낱말"] = round(sum(low.count(c) for c in CONN) / k, 1)
    par = CITE_PAREN.findall(body)
    nar = CITE_NARR.findall(body)
    p["인용/1000낱말"] = round((len(par) + len(nar)) / k, 1)
    tot_c = len(par) + len(nar)
    p["괄호 인용 비율"] = round(100.0 * len(par) / tot_c, 0) if tot_c else 0
    p["한 문장 최대 인용"] = max(
        [len(CITE_PAREN.findall(s)) + len(CITE_NARR.findall(s)) for s in sents] or [0])
    for h in HEDGE:
        p["%s/1000낱말" % h] = round(len(re.findall(r"\b%ss?\b" % h, low)) / k, 2)
    p["we/1000낱말"] = round(len(re.findall(r"\bwe\b", low)) / k, 1)
    p["수동태 근사/1000낱말"] = round(
        len(re.findall(r"\b(?:is|are|was|were|been|being)\s+\w+ed\b", low)) / k, 1)
    p["Table 언급"] = len(re.findall(r"\bTable\s+\d", body))
    p["Fig 언급"] = len(re.findall(r"\bFig(?:\.|ure)\s+\d", body))
    dec = Counter(len(x.split(".")[1]) for x in re.findall(r"\d+\.\d+", body))
    p["소수 자리 종류"] = len(dec)
    if refs:
        # 참고문헌 항목 수는 줄바꿈이 아니라 "연도" 개수로 센다
        # (PDF 텍스트는 한 항목이 여러 줄로 쪼개진다)
        years = [int(m.group(0)) for m in re.finditer(r"\b(?:19|20)\d{2}\b", refs)
                 if 1900 <= int(m.group(0)) <= THIS_YEAR + 1]
        p["참고문헌 개수(연도 기준)"] = len(years)
        if years:
            p["참고문헌 최신 연도"] = max(years)
            p["참고문헌 연도 중앙값"] = int(statistics.median(years))
    return p


def band(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    return (round(min(vals), 2), round(statistics.median(vals), 2),
            round(max(vals), 2))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    txt_dir = opt("--txt", "literature/_txt")
    mark = opt("--journal", "")
    self_name = opt("--self")
    out_path = opt("--out")

    files = [f for f in sorted(glob.glob(txt_dir + "/*.txt"))
             if not mark or mark.lower() in os.path.basename(f).lower()]
    if not files:
        print("게재작 텍스트가 없다: %s (check_ngram.py --extract 먼저)" % txt_dir)
        return

    profs = []
    self_hits, ref_lines = 0, 0
    for f in files:
        t = open(f, encoding="utf-8", errors="replace").read()
        if len(t.split()) < 1500:
            continue
        profs.append(profile(t, os.path.basename(f)))
        if self_name:
            _, refs = split_body_refs(t)
            self_hits += len(re.findall(re.escape(self_name), refs, re.I))
            ref_lines += len([m for m in re.finditer(r"\b(?:19|20)\d{2}\b", refs)
                              if 1900 <= int(m.group(0)) <= THIS_YEAR + 1])

    keys = []
    for p in profs:
        for k in p:
            if k not in keys:
                keys.append(k)

    mine = None
    if args:
        mine = profile(open(args[0], encoding="utf-8", errors="replace").read(),
                       os.path.basename(args[0]))

    L = ["# 게재작 대역과 원고 대조"]
    L.append("")
    L.append("- 게재작 **%d편**%s" % (len(profs), (", 표식 '%s'" % mark) if mark else ""))
    if mine:
        L.append("- 원고: %s" % os.path.basename(args[0]))
    L.append("")
    L.append("| 항목 | 게재작 최소 | 중앙값 | 최대 |" + (" 우리 원고 | 판정 |" if mine else ""))
    L.append("|--|--|--|--|" + ("--|--|" if mine else ""))
    out_of = 0
    for k in keys:
        b = band([p.get(k) for p in profs])
        if not b:
            continue
        lo, med, hi = b
        row = "| %s | %s | %s | %s |" % (k, lo, med, hi)
        if mine:
            v = mine.get(k, "-")
            if isinstance(v, (int, float)):
                if v < lo:
                    verdict = "**낮음**"
                    out_of += 1
                elif v > hi:
                    verdict = "**높음**"
                    out_of += 1
                else:
                    verdict = "안"
            else:
                verdict = "-"
            row += " %s | %s |" % (v, verdict)
        L.append(row)

    if self_name and ref_lines:
        L.append("")
        L.append("**게재작의 자기 저널 인용**: 참고문헌 %d개 중 %d개가 '%s'"
                 " (%.1f%%)" % (ref_lines, self_hits, self_name,
                                100.0 * self_hits / ref_lines))
        if mine and args:
            _, my_refs = split_body_refs(
                open(args[0], encoding="utf-8", errors="replace").read())
            my_n = len([m for m in re.finditer(r"\b(?:19|20)\d{2}\b", my_refs)
                        if 1900 <= int(m.group(0)) <= THIS_YEAR + 1])
            my_hits = len(re.findall(re.escape(self_name), my_refs, re.I))
            if my_n:
                L.append("**우리 원고**: 참고문헌 %d개 중 %d개 (%.1f%%)"
                         % (my_n, my_hits, 100.0 * my_hits / my_n))
                L.append("차이가 크면 그 저널 독자가 아는 논문을 안 읽은 것이다."
                         " 반대로 지나치게 높으면 억지로 채운 것으로 읽힌다.")

    L.append("")
    if mine:
        L.append("**대역 밖 항목 %d개.**" % out_of)
    L.append("대역은 게재작을 잰 결과이고 **판정은 사람이 한다.** 대역 밖이라고"
             " 전부 틀린 것이 아니다. 왜 벗어났는지 설명할 수 있으면 그대로 둔다.")
    L.append("")
    L.append("주의: PDF에서 뽑은 텍스트라 문단 경계와 참고문헌 줄 수는 정확하지"
             " 않다. 문장·낱말 기반 항목이 더 믿을 만하다.")

    text = "\n".join(L)
    if out_path:
        open(out_path, "w", encoding="utf-8").write(text)
        print("저장: %s (게재작 %d편)" % (out_path, len(profs)))
    else:
        print(text)


if __name__ == "__main__":
    main()
