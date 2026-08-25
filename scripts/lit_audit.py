# -*- coding: utf-8 -*-
"""이미 모아 둔 논문 폴더를 진단한다 - 무엇이 모자라고 무엇이 못 쓰는 파일인가.

쓰임:
  python lit_audit.py --lit literature --txt literature/_txt --journal TFSC
  python lit_audit.py --lit "폴더A,폴더B" --txt <게재작 코퍼스> --journal TFSC
                      --pdftxt <인용원문 캐시> --manuscript 원고.md

  --lit      논문 PDF 폴더. **쉼표로 여럿을 한 번에** 준다(여러 번 써도 된다)
  --txt      목표 저널 게재작 코퍼스(.txt). 게재작이 텍스트로만 있어도 센다
  --pdftxt   인용 원문 PDF의 텍스트 캐시. 없으면 각 폴더의 `_txt`를 본다
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


def opts(name):
    """같은 이름이 여러 번 나오거나 쉼표로 이어 붙은 값을 전부 돌려준다.

    논문이 한 폴더에 있다는 보장이 없다. 한 폴더만 보면 **다른 폴더에 있는
    논문을 "없다"고 보고한다.** 실제로 그렇게 헛된 공백 세 건이 나왔다.
    """
    out = []
    for i, a_ in enumerate(sys.argv):
        if a_ == name and i + 1 < len(sys.argv):
            out.extend(x.strip() for x in sys.argv[i + 1].split(",") if x.strip())
    return out


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


def section1(pdfs, lits, mark, corpus_txt):
    by_dir = Counter()
    for f in pdfs:
        base = None
        for lit in lits:
            try:
                rel = os.path.relpath(f, lit)
            except ValueError:
                continue
            if not rel.startswith(".."):
                base = os.path.basename(lit.rstrip(os.sep)) + (
                    os.sep + rel.split(os.sep)[0] if os.sep in rel else "")
                break
        by_dir[base or "(그 밖)"] += 1
    jn = [f for f in pdfs if mark and mark.lower() in os.path.basename(f).lower()]

    # 게재작이 PDF가 아니라 **텍스트로만** 있을 수 있다. 그것도 센다.
    # 파일 이름만 보고 "0편"이라 보고한 적이 있다. 0이 나오면 도구를 먼저
    # 의심한다(`14_할루시네이션_방지.md`).
    corpus = sorted(glob.glob(os.path.join(corpus_txt, "*.txt")))
    if mark:
        marked = [f for f in corpus if mark.lower() in os.path.basename(f).lower()]
        n_corpus = len(marked) if marked else len(corpus)
    else:
        n_corpus = len(corpus)
    n_journal = max(len(jn), n_corpus)

    print("## 1. 편수")
    print("")
    print("- PDF 전체 **%d편**" % len(pdfs))
    print("- 코퍼스 텍스트 **%d편** (`%s`)" % (len(corpus), corpus_txt))
    if mark:
        print("- 목표 저널(%s) 게재작 **%d편**" % (mark, n_journal))
        if len(jn) == 0 and n_corpus:
            print("  - PDF 이름에는 저널 표식이 없고 **텍스트 코퍼스에 %d편이"
                  " 있다.** 게재작을 텍스트로만 가지고 있는 경우다."
                  " 편수는 코퍼스 쪽으로 센다" % n_corpus)
        if n_journal < 40:
            print("  - **문체 대역 기준 40편에서 %d편 모자란다.** 표본이 작으면"
                  " 한 편이 들고 날 때마다 대역이 출렁인다"
                  % (40 - n_journal))
        elif n_journal < 60:
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


def section2(pdfs, cache_dirs):
    """PDF에서 글자가 뽑혀 있는가.

    **게재작 코퍼스 폴더에서 인용 원문의 캐시를 찾으면 안 된다.** 서로 다른
    것을 대조하는 것이라 "캐시 없음 80편" 같은 헛된 숫자가 나온다.
    캐시는 각 PDF 폴더의 `_txt` 에서 찾고, `--pdftxt` 로 바꿀 수 있다.
    """
    no_cache, scanlike, thin = [], [], []
    for f in pdfs:
        t = None
        for cd in cache_dirs:
            cand = txt_of(f, cd)
            if os.path.exists(cand):
                t = cand
                break
        if t is None:
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


def section5(pdfs, cache_dirs, ms):
    print("")
    print("## 5. 인용 공백 (원고가 인용했는데 폴더에 원문이 없는 것)")
    print("")
    if not ms:
        print("- (`--manuscript 원고.md` 를 주면 이 항목을 낸다)")
        return
    if not os.path.exists(ms):
        print("- 원고 파일을 못 찾았다: %s" % ms)
        return
    whole = open(ms, encoding="utf-8", errors="replace").read()
    parts = re.split(r"(?m)^#{0,4}\s*\**(?:References|Bibliography|참고문헌)"
                     r"\**\s*$", whole)
    body = parts[0]
    refs = parts[-1].lower() if len(parts) > 1 else ""
    # 달 이름과 구조 낱말은 저자가 아니다 ("June (2019)" 가 논문으로 잡혔다)
    NOT_AUTHOR = set("""January February March April May June July August
    September October November December Table Figure Fig Appendix Section
    Panel Note Source Model Study Data Article Chapter Volume Since During
    Between From Until After Before""".split())
    cites = set()
    pat = (r"([A-Z][A-Za-z'-]{2,})(?:\s+(?:and|&)\s+[A-Z][A-Za-z'-]{2,}"
           r"|\s+et\s+al\.?)?[,\s]*\(?((?:19|20)[0-9][0-9])")
    for m in re.finditer(pat, body):
        au = re.sub(r"['’]s$", "", m.group(1))   # Pavitt's -> Pavitt
        if au in NOT_AUTHOR:
            continue
        cites.add((au, m.group(2)))
    # 기관 이름과 자료 이름은 여러 낱말이라 앞 낱말 하나만 잡히면 엉뚱해진다.
    # (Ministry of Employment and Labor, 2024) 가 "Ministry (2024)" 로 잡혀
    # 논문이 없다고 보고된 적이 있다. 통째로 다시 잡아 따로 센다.
    inst = set()
    ipat = (r"((?:[A-Z][A-Za-z'-]+\s+(?:of|and|for|the)?\s*){2,6}"
            r"[A-Z][A-Za-z'-]+)[,\s]+\(?((?:19|20)[0-9][0-9])")
    for m in re.finditer(ipat, body):
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(name.split()) >= 3:
            inst.add((name, m.group(2)))
            # 기관 이름 안의 낱말이 저자처럼 잡힌 것을 전부 뺀다
            # ("Ministry of Employment and Labor" 에서 Employment 가 샜다)
            for w in name.split():
                cites.discard((w, m.group(2)))
    if not cites:
        print("- 본문에서 인용을 못 찾았다. 인용 형식을 확인하라")
        return
    # **논문 앞머리(제목·저자)에서만** 찾는다. 본문 아무 데나 그 이름이
    # 나왔다고 원문을 가진 것이 아니다. 게재작이 인용한 이름을 우리가 가진
    # 것으로 착각해 공백을 놓친 적이 있다.
    caches = []
    for cd in dict.fromkeys(cache_dirs):
        for t in glob.glob(os.path.join(cd, "*.txt")):
            caches.append(open(t, encoding="utf-8", errors="replace")
                          .read()[:1200].lower())
    names = " || ".join(os.path.basename(f).lower() for f in pdfs)
    missing, not_in_refs = [], []
    for au, yr in sorted(cites):
        a = au.lower()
        # 참고문헌에 없는 이름은 인용이 아닐 가능성이 크다(문장 첫머리의
        # 보통 낱말이 저자처럼 잡힌다). 따로 세서 눈으로 보게 한다
        if refs and a not in refs:
            not_in_refs.append("%s (%s)" % (au, yr))
            continue
        if a in names:
            continue
        if any(a in h and yr in h for h in caches):
            continue
        missing.append("%s (%s)" % (au, yr))
    print("- 본문 인용 **%d종** 중 폴더에서 원문을 못 찾은 것 **%d종**"
          % (len(cites), len(missing)))
    for x in missing[:30]:
        print("    - %s" % x)
    if len(missing) > 30:
        print("    - (외 %d종)" % (len(missing) - 30))
    if not_in_refs:
        print("")
        print("- 참고문헌에 같은 이름이 없어 **인용이 아닐 수 있는 것 %d종**"
              " (문장 첫머리의 보통 낱말이 저자처럼 잡힌다):" % len(not_in_refs))
        print("    " + ", ".join(not_in_refs[:20]))
        print("    → 진짜 인용인데 참고문헌에 없다면 **그것이 더 큰 문제다.**"
              " 한 줄씩 확인한다")
    if inst:
        print("")
        print("- **기관·자료 이름으로 보이는 인용 %d종**(논문 PDF가 아닌 것이"
              " 정상이다. 다만 **출처 문서를 손에 들고 수치를 대조**해야 한다):"
              % len(inst))
        for nm, yr in sorted(inst)[:12]:
            print("    - %s (%s)" % (nm[:64], yr))
        if len(inst) > 12:
            print("    - (외 %d종)" % (len(inst) - 12))
    if not missing:
        return
    print("")
    print("  → **이 목록이 인용 검증을 못 하는 자리다**(`17_인용검증.md`)."
          " 원문 없이 판정하지 않는다")
    print("  → 저자 표기가 달라서 못 찾은 것도 섞인다. 한 줄씩 눈으로 확인한"
          " 뒤 받을 목록을 만든다")


def main():
    lits = opts("--lit") or ["literature"]
    corpus_txt = opt("--txt", "literature/_txt")
    cache_dirs = opts("--pdftxt") or [os.path.join(l, "_txt") for l in lits]
    cache_dirs.append(corpus_txt)     # 같은 폴더를 쓰는 경우도 받아 준다
    mark = opt("--journal", "")
    ms = opt("--manuscript")

    pdfs = []
    for lit in lits:
        pdfs.extend(glob.glob(os.path.join(lit, "**", "*.pdf"), recursive=True))
    pdfs = sorted(set(pdfs))
    if not pdfs:
        print("아래에 PDF가 없다. --lit 경로를 확인하라: %s" % ", ".join(lits))
        return

    print("# 논문 폴더 진단 · %s" % ", ".join(lits))
    print("")
    if len(lits) > 1:
        print("- 폴더 %d곳을 **한 번에** 봤다. 한 곳씩 보면 다른 곳에 있는"
              " 논문을 없다고 보고한다" % len(lits))
        print("")
    section1(pdfs, lits, mark, corpus_txt)
    section2(pdfs, cache_dirs)
    section3(pdfs)
    section4(pdfs)
    section5(pdfs, cache_dirs, ms)
    print("")
    print("---")
    print("**판정은 후보다.** 무엇을 더 받을지는 저자가 정한다. 부족한 채로"
          " 진행하기로 했다면 그 사실을 기록에 남긴다.")


if __name__ == "__main__":
    main()
