# -*- coding: utf-8 -*-
"""이미 모아 둔 논문 폴더를 진단한다 - 무엇이 모자라고 무엇이 못 쓰는 파일인가.

쓰임:
  python lit_audit.py --lit literature --txt literature/_txt --journal TFSC
  python lit_audit.py --lit literature --txt literature/_txt --journal TFSC
                      --manuscript 원고.md
      원고를 같이 주면 "인용했는데 폴더에 원문이 없는 것"까지 낸다.

무엇을 보나
  1 편수       전체·목표 저널·폴더별, 기준 대비 부족분
  2 못 쓰는 것 텍스트 캐시 없음, 스캔본 의심, 분량 부족(대역 실측에서 빠짐)
  3 연도       최근 3년치 비율 (문체 대역은 최근 것이 기준)
  4 중복       같은 논문이 두 번 들어온 후보
  5 인용 공백  원고가 인용했는데 폴더에 원문이 없는 것 (인용 검증 불가 목록)

**이 도구는 후보만 낸다.** 부족분을 실제로 받을지는 저자가 정한다.
"""
import io
import os
import re
import sys
import glob
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CUR_YEAR = 2026

# 갈래별 최소 편수 (01_게재작수집_실측.md §1-2)
NEED = [("목표 저널 게재작(문체 대역용)", 40, "대역이 안 흔들리려면 40편 이상. 읽지 않고 기계로 잰다"),
        ("기준 논문", 2, "우리와 방법·자료가 가장 가까운 것"),
        ("주제가 겹치는 것", 10, "현상·수치 배경"),
        ("방법이 겹치는 것", 10, "절차 서술과 검증 설계의 근거"),
        ("이론", 5, "논의 절의 어휘와 틀")]


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def txt_of(pdf, txt_dir):
    return os.path.join(txt_dir, os.path.basename(pdf)[:-4] + ".txt")


def year_of(name):
    ys = [int(y) for y in re.findall(r"((?:19|20)[0-9][0-9])", name)
          if 1980 <= int(y) <= CUR_YEAR + 1]
    return max(ys) if ys else None


def title_key(name):
    """중복 판정용 열쇠. 확장자·괄호·기호를 걷어낸 앞부분."""
    s = re.sub(r"\.[A-Za-z]+$", "", os.path.basename(name)).lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join([w for w in s.split() if len(w) > 2][:6])


def section1(pdfs, lit, mark):
    by_dir = Counter()
    for f in pdfs:
        rel = os.path.relpath(f, lit)
        by_dir[rel.split(os.sep)[0] if os.sep in rel else "(폴더 없이 바로)"] += 1
    jn = [f for f in pdfs if mark and mark.lower() in os.path.basename(f).lower()]

    print("## 1. 편수")
    print("")
    print("- 전체 **%d편**" % len(pdfs))
    if mark:
        print("- 목표 저널(%s) 게재작 **%d편**" % (mark, len(jn)))
        if len(jn) < 40:
            print("  - **문체 대역 기준 40편에서 %d편 모자란다.** 표본이 작으면"
                  " 한 편이 들고 날 때마다 대역이 출렁인다" % (40 - len(jn)))
        elif len(jn) < 60:
            print("  - 40편은 넘었다. 60편까지 채우면 대역이 더 안정된다."
                  " `check_ngram.py --calibrate --stability` 로 확인한다")
    else:
        print("- (`--journal 표식`을 주면 목표 저널 게재작을 따로 센다)")
    print("")
    print("| 폴더 | 편수 |")
    print("|--|--|")
    for d, n in by_dir.most_common():
        print("| %s | %d |" % (d, n))
    print("")
    print("갈래별 기준은 아래와 같다. **폴더 이름이 갈래와 다르면 사람이"
          " 대조한다**(이 도구는 폴더 이름만 본다).")
    print("")
    print("| 갈래 | 최소 | 왜 |")
    print("|--|--|--|")
    for nm, k, why in NEED:
        print("| %s | %d | %s |" % (nm, k, why))


def section2(pdfs, txt_dir):
    no_cache, scanlike, thin = [], [], []
    for f in pdfs:
        t = txt_of(f, txt_dir)
        if not os.path.exists(t):
            no_cache.append(os.path.basename(f))
            continue
        raw = open(t, encoding="utf-8", errors="replace").read()
        letters = len(re.findall(r"[A-Za-z가-힣]", raw))
        if letters < 3000:
            scanlike.append((os.path.basename(f), letters))
            continue
        sents = len(re.findall(r"[.!?] +[A-Z]", raw))
        if sents < 50:
            thin.append((os.path.basename(f), sents))

    print("")
    print("## 2. 못 쓰는 파일")
    print("")
    print("- 실측에 쓸 수 있는 것 **%d편** / 전체 %d편"
          % (len(pdfs) - len(no_cache) - len(scanlike), len(pdfs)))
    if no_cache:
        print("- **텍스트 캐시 없음 %d편** (추출을 안 했거나 실패했다):"
              % len(no_cache))
        for b in no_cache[:12]:
            print("    - %s" % b[:78])
        if len(no_cache) > 12:
            print("    - (외 %d편)" % (len(no_cache) - 12))
        print("    → `check_ngram.py --extract` 를 먼저 돌린다. 돌린 뒤에도"
              " 남으면 그 파일이 스캔본이다")
    if scanlike:
        print("- **스캔본 의심 %d편** (글자가 거의 안 뽑힌다):" % len(scanlike))
        for b, n in scanlike[:10]:
            print("    - %s  (글자 %d자)" % (b[:64], n))
        print("    → 문체 실측·5-gram 대조에 못 쓴다. 원본을 다시 받는다")
    if thin:
        print("- 분량 부족 %d편 (문장 50개 미만. 대역 실측에서 빠진다):"
              % len(thin))
        for b, n in thin[:8]:
            print("    - %s  (문장 %d개)" % (b[:64], n))
    if not (no_cache or scanlike or thin):
        print("- 없음. 전부 쓸 수 있다")


def section3(pdfs):
    years = [year_of(os.path.basename(f)) for f in pdfs]
    known = [y for y in years if y]
    print("")
    print("## 3. 연도")
    print("")
    if not known:
        print("- 파일 이름에 연도가 없어 못 셌다. `저자 (연도) - 제목.pdf`"
              " 형식으로 이름을 바꾸면 이 항목을 잰다")
        return
    recent = [y for y in known if y >= CUR_YEAR - 3]
    print("- 연도를 읽은 것 %d편 / 못 읽은 것 %d편"
          % (len(known), len(years) - len(known)))
    print("- 최근 3년(%d년 이후) **%d편 (%.0f%%)**"
          % (CUR_YEAR - 3, len(recent), 100.0 * len(recent) / len(known)))
    if len(recent) < 0.4 * len(known):
        print("  - **최근 것이 적다.** 문체와 방법이 지금 실리는 논문과 다를 수"
              " 있다. 최근 호에서 더 받는다")
    c = Counter(known)
    print("- 분포: " + ", ".join("%d년 %d편" % (y, c[y])
                                 for y in sorted(c, reverse=True)[:8]))


def section4(pdfs):
    keys = {}
    for f in pdfs:
        keys.setdefault(title_key(f), []).append(os.path.basename(f))
    dups = {k: v for k, v in keys.items() if len(v) > 1 and k}
    print("")
    print("## 4. 중복 후보")
    print("")
    if not dups:
        print("- 없음")
        return
    print("- **%d쌍**. 같은 논문이 두 번 들어오면 편수가 부풀고 대역이 한쪽으로"
          " 쏠린다" % len(dups))
    for k, v in list(dups.items())[:10]:
        print("    - %s" % " / ".join(x[:46] for x in v))


def section5(pdfs, txt_dir, ms):
    print("")
    print("## 5. 인용 공백 (원고가 인용했는데 폴더에 원문이 없는 것)")
    print("")
    if not ms:
        print("- (`--manuscript 원고.md` 를 주면 이 항목을 낸다)")
        return
    if not os.path.exists(ms):
        print("- 원고 파일을 못 찾았다: %s" % ms)
        return
    body = open(ms, encoding="utf-8", errors="replace").read()
    body = re.sub(r"(?m)^#{0,4}\s*(References|Bibliography|참고문헌).*$",
                  "@@CUT@@", body).split("@@CUT@@")[0]
    cites = set()
    pat = (r"([A-Z][A-Za-z'-]{2,})(?:\s+(?:and|&)\s+[A-Z][A-Za-z'-]{2,}"
           r"|\s+et\s+al\.?)?[,\s]*\(?((?:19|20)[0-9][0-9])")
    for m in re.finditer(pat, body):
        cites.add((m.group(1), m.group(2)))
    if not cites:
        print("- 본문에서 인용을 못 찾았다. 인용 형식을 확인하라")
        return
    caches = []
    for t in glob.glob(txt_dir + "/*.txt"):
        caches.append(open(t, encoding="utf-8", errors="replace")
                      .read()[:6000].lower())
    names = " || ".join(os.path.basename(f).lower() for f in pdfs)
    missing = []
    for au, yr in sorted(cites):
        a = au.lower()
        if a in names:
            continue
        if any(a in h and yr in h for h in caches):
            continue
        missing.append("%s (%s)" % (au, yr))
    print("- 본문 인용 **%d종** 중 폴더에서 원문을 못 찾은 것 **%d종**"
          % (len(cites), len(missing)))
    if not missing:
        return
    for x in missing[:30]:
        print("    - %s" % x)
    if len(missing) > 30:
        print("    - (외 %d종)" % (len(missing) - 30))
    print("")
    print("  → **이 목록이 인용 검증을 못 하는 자리다**(`17_인용검증.md`)."
          " 원문 없이 판정하지 않는다")
    print("  → 저자 표기가 달라서 못 찾은 것도 섞인다. 한 줄씩 눈으로 확인한"
          " 뒤 받을 목록을 만든다")


def main():
    lit = opt("--lit", "literature")
    txt_dir = opt("--txt", "literature/_txt")
    mark = opt("--journal", "")
    ms = opt("--manuscript")

    pdfs = sorted(glob.glob(os.path.join(lit, "**", "*.pdf"), recursive=True))
    if not pdfs:
        print("`%s` 아래에 PDF가 없다. --lit 경로를 확인하라." % lit)
        return

    print("# 논문 폴더 진단 · %s" % lit)
    print("")
    section1(pdfs, lit, mark)
    section2(pdfs, txt_dir)
    section3(pdfs)
    section4(pdfs)
    section5(pdfs, txt_dir, ms)
    print("")
    print("---")
    print("**판정은 후보다.** 무엇을 더 받을지는 저자가 정한다. 부족한 채로"
          " 진행하기로 했다면 그 사실을 기록에 남긴다.")


if __name__ == "__main__":
    main()
