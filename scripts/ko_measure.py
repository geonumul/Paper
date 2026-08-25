# -*- coding: utf-8 -*-
"""국문 원고의 문체를 잰다 (문장 길이·리듬·종결어미·문단).

쓰임:
  python ko_measure.py 원고_국문.md
  python ko_measure.py 원고_국문.md --ref 정본원고.txt      # 정본과 나란히
  python ko_measure.py --ref 정본원고.txt                    # 정본만 재기

왜 쓰나
  국문 문체의 정본은 사용자가 이미 쓴 학술 원고다(`06_국문문체.md`).
  "어색하다"는 감으로 고치지 않고, **정본을 재서 대역을 만들고 그 대역과
  대조한다.** 영문 도구(check_ngram)는 국문 문장을 못 센다.

재는 것
  - 문장 길이(어절 수) 평균·중앙값, 그리고 얼마나 들쭉날쭉한지(편차/평균)
  - 문단당 문장 수
  - **종결어미 분포**: 사실 보고 / 해석 / 함의 / 제안 / 의의
  - 기둥 구문("~한 결과, ~하였다") 빈도
  - 걷어낼 버릇: 도치·구어·모호한 기간
"""
import io
import os
import re
import sys
import statistics
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 기능별 종결어미 (06_국문문체.md 2항)
ENDINGS = [
    ("사실 보고", r"(하였다|되었다|나타났다|확인되었다|보였다|이다|였다)\."),
    ("해석", r"(로 해석된다|해석할 수 있다|볼 수 있다|판단된다)\."),
    ("함의", r"(를 시사한다|을 시사한다|보여 준다|보여준다)\."),
    ("제안", r"(할 필요가 있다|해야 한다|요구된다)\."),
    ("의의", r"(의의를 지닌다|의의가 있다|기여한다)\."),
]

HABITS = [
    ("도치·강조", r"볼 곳은|변한 것은|주목할 것은"),
    ("구어 어휘", r"(?<![가-힣])(답|판|무늬|몫)(이|은|을|에)|세게|엄청"),
    ("모호한 기간", r"십여 년간|십수 년간|최근 [0-9]+년 사이|근래"),
    ("번역투", r"에 의해 특징지어|~인지 규명하기 위해|는지 규명하기 위해"),
    ("금지 문구", r"널리 도입된|널리 활용되고"),
]

PILLAR = r"[가-힣] 결과,"


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def body_of(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    lines = []
    in_code = False
    for ln in raw.split("\n"):
        st = ln.strip()
        if st.startswith("```"):
            in_code = not in_code
            continue
        if in_code or st.startswith(("#", ">", "|")):
            continue
        if re.match(r"^([-*+]|\d+\.)\s", st):
            continue
        lines.append(ln)
    return "\n".join(lines)


def sentences_ko(text):
    t = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=다\.)\s+|(?<=요\.)\s+|(?<=\?)\s+", t)
    return [p.strip() for p in parts if len(p.split()) >= 3]


def measure(path, label):
    body = body_of(path)
    sents = sentences_ko(body)
    if not sents:
        print("%s: 국문 문장을 못 찾았다." % label)
        return None
    lens = [len(s.split()) for s in sents]
    # 띄어쓰기가 깨진 텍스트인지 본다 (PDF 추출본에서 흔하다)
    chars = sum(len(re.sub(r"\s", "", s)) for s in sents)
    words = sum(lens)
    per_word = chars / float(max(1, words))
    broken = per_word > 6 or max(lens) > 200
    if broken:
        print("\n## %s" % label)
        print("- **잴 수 없다.** 어절당 글자 수가 %.1f자로, 띄어쓰기가 깨진"
              " 텍스트다(PDF 추출본에서 흔하다)." % per_word)
        print("- 문장 길이·리듬·문단 수치는 **믿을 수 없으므로 내지 않는다.**")
        print("- 할 일: 띄어쓰기가 살아 있는 원본(원고 파일·한글 문서에서 복사한"
              " 텍스트)으로 다시 재거나, 이 항목은 **'재지 못했다'고 기록**한다.")
        end0 = Counter()
        for name, pat in ENDINGS:
            end0[name] = len(re.findall(pat, body))
        t0 = sum(end0.values()) or 1
        print("- 종결어미 분포는 띄어쓰기와 무관하므로 참고로만 적는다:")
        for name, _ in ENDINGS:
            print("    %-8s %4d회 (%4.1f%%)" % (name, end0[name],
                                                100.0 * end0[name] / t0))
        return None
    paras = [p for p in re.split(r"\n\s*\n", body) if len(p.split()) > 10]
    spp = [len(sentences_ko(p)) for p in paras] or [0]
    cv = statistics.stdev(lens) / statistics.mean(lens) if len(lens) > 1 else 0

    end = Counter()
    for name, pat in ENDINGS:
        end[name] = len(re.findall(pat, body))
    total_end = sum(end.values()) or 1

    print("\n## %s" % label)
    print("- 문장 %d개 / 문단 %d개" % (len(sents), len(paras)))
    print("- 문장 길이(어절): 평균 %.1f, 중앙값 %d, 최소 %d, 최대 %d"
          % (statistics.mean(lens), statistics.median(lens), min(lens), max(lens)))
    print("- **문장 길이가 들쭉날쭉한 정도(편차/평균): %.2f**" % cv)
    print("- 문단당 문장 수: 중앙값 %d (최소 %d, 최대 %d)"
          % (statistics.median(spp), min(spp), max(spp)))
    print("- 기둥 구문('~한 결과,'): %d회" % len(re.findall(PILLAR, body)))
    print("- 종결어미 분포:")
    for name, _ in ENDINGS:
        n = end[name]
        print("    %-8s %4d회 (%4.1f%%)" % (name, n, 100.0 * n / total_end))

    hits = []
    for name, pat in HABITS:
        found = re.findall(pat, body)
        if found:
            hits.append((name, len(found)))
    if hits:
        print("- 걷어낼 버릇: " + ", ".join("%s %d건" % h for h in hits))
    else:
        print("- 걷어낼 버릇: 없음")

    return {"cv": cv, "mean": statistics.mean(lens),
            "med_spp": statistics.median(spp), "end": end, "total": total_end}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ref = opt("--ref")
    if not args and not ref:
        print(__doc__)
        return

    r = measure(ref, "정본 (%s)" % os.path.basename(ref)) if ref else None
    m = measure(args[0], "우리 원고 (%s)" % os.path.basename(args[0])) if args else None

    if r and m:
        print("\n## 나란히 보기")
        print("| 항목 | 정본 | 우리 | 판정 |")
        print("|--|--|--|--|")
        print("| 문장 길이 평균 | %.1f | %.1f | %s |"
              % (r["mean"], m["mean"], "비슷" if abs(r["mean"] - m["mean"]) < 3
                 else "**다름**"))
        print("| 변동계수 | %.2f | %.2f | %s |"
              % (r["cv"], m["cv"], "비슷" if abs(r["cv"] - m["cv"]) < 0.12
                 else "**다름**"))
        print("| 문단당 문장 | %d | %d | %s |"
              % (r["med_spp"], m["med_spp"],
                 "비슷" if abs(r["med_spp"] - m["med_spp"]) <= 1 else "**다름**"))
        for name, _ in ENDINGS:
            a = 100.0 * r["end"][name] / r["total"]
            b = 100.0 * m["end"][name] / m["total"]
            print("| 종결 %s | %.1f%% | %.1f%% | %s |"
                  % (name, a, b, "비슷" if abs(a - b) < 10 else "**다름**"))
        print("\n판정은 후보일 뿐이다. **다름으로 나온 항목은 두 글을 나란히"
              " 놓고 사람이 읽어서 정한다.**")


if __name__ == "__main__":
    main()
