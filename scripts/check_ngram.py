# -*- coding: utf-8 -*-
"""n-gram 겹침 스캔 + 문장 리듬(변동계수) 계측 (저널 무관 일반판).

쓰임:
  python check_ngram.py --extract  [--lit literature] [--txt literature/_txt]
      문헌 PDF를 텍스트로 뽑아 캐시한다 (PyMuPDF 필요). 한 번만.

  python check_ngram.py --calibrate [--txt ...] [--journal 5_journal]
      목표 저널 게재작의 문장 리듬 대역을 실측해 저장한다.
      --journal 은 캐시 파일 이름에 들어 있는 표식(폴더명·저널명 조각).
      생략하면 캐시 전체를 쓴다.

  python check_ngram.py 원고.md
      원고의 영문 5단어 연쇄가 문헌 원문에 그대로 있는지 대조하고,
      문장 길이 변동계수를 실측 대역과 비교한다.

- 5-gram이 걸리면: 귀속 인용(따옴표+출처)이거나 완전 재구성이거나 둘 중
  하나만 한다. 어중간한 근접 의역이 가장 나쁘다.
- 변동계수(CV)는 문장 길이의 표준편차를 평균으로 나눈 값이다. 균일한 리듬은
  AI 티의 1순위 지표다. 사람이 쓴 글은 대개 0.5-0.8에 들어온다.
"""
import io
import os
import re
import sys
import glob
import json
import statistics

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

N = 5
DEF_LIT = "literature"
DEF_TXT = "literature/_txt"
BAND_F = "_burstiness_band.json"
ALLOW_F = "_ngram_allow.txt"     # 사람이 통과시킨 관용구 (한 줄 하나)


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def norm_words(text):
    text = re.sub(r"[^A-Za-z ]+", " ", text.lower())
    return [w for w in text.split() if w]


def sentences_en(text):
    text = re.sub(r"\((?:[^()]*\d{4}[^()]*)\)", "", text)     # 인용 괄호 제거
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    out = []
    for p in parts:
        w = norm_words(p)
        if 4 <= len(w) <= 120:
            out.append(len(w))
    return out


def extract(lit, txt_dir):
    try:
        import fitz
    except ImportError:
        print("PyMuPDF가 필요합니다:  pip install pymupdf")
        return
    os.makedirs(txt_dir, exist_ok=True)
    pdfs = glob.glob(os.path.join(lit, "**", "*.pdf"), recursive=True)
    done = 0
    for f in pdfs:
        out = os.path.join(txt_dir, os.path.basename(f)[:-4] + ".txt")
        if os.path.exists(out):
            continue
        try:
            doc = fitz.open(f)
            open(out, "w", encoding="utf-8").write(
                "\n".join(page.get_text() for page in doc))
            doc.close()
            done += 1
        except Exception as e:
            print("FAIL", os.path.basename(f)[:50], str(e)[:40])
    print("추출 %d편 (총 캐시 %d편)"
          % (done, len(glob.glob(txt_dir + "/*.txt"))))


def calibrate(txt_dir, mark, band_f):
    rows = []
    for f in sorted(glob.glob(txt_dir + "/*.txt")):
        if mark and mark.lower() not in os.path.basename(f).lower():
            continue
        lens = sentences_en(open(f, encoding="utf-8", errors="replace").read())
        if len(lens) < 50:
            continue
        cv = statistics.stdev(lens) / statistics.mean(lens)
        rows.append((os.path.basename(f)[:44], round(statistics.mean(lens), 1),
                     round(cv, 2)))
    if not rows:
        print("대상 파일이 없습니다. --txt 경로나 --journal 표식을 확인하세요.")
        print("(게재작 파일 이름에 저널 표식이 없으면 그 논문들만 따로 폴더에"
              " 두고 --txt로 그 폴더를 지정하세요.)")
        return
    cvs = [r[2] for r in rows]
    means = [r[1] for r in rows]
    band = {"cv_lo": min(cvs), "cv_hi": max(cvs),
            "cv_med": round(statistics.median(cvs), 2),
            "len_lo": min(means), "len_hi": max(means), "n_papers": len(rows)}
    json.dump(band, open(band_f, "w"))
    print("게재작 %d편 실측" % len(rows))
    for nm, m, cv in rows:
        print("  %-46s 평균 %5.1f단어  CV %.2f" % (nm, m, cv))
    print("\n대역: 문장 평균 %s-%s단어, CV %s-%s (중앙값 %s)  → %s"
          % (band["len_lo"], band["len_hi"], band["cv_lo"], band["cv_hi"],
             band["cv_med"], band_f))
    if len(rows) < 20:
        print("주의: 20편 미만이면 대역이 흔들립니다. 논문을 더 모으세요.")


def scan(path, txt_dir, band_f, allow_f):
    raw = open(path, encoding="utf-8").read()
    # 영문 산문만 (국문 대역·기록 블록 제외)
    en_parts = []
    for para in raw.split("\n\n"):
        w = norm_words(para)
        if w and sum(1 for x in w if len(x) > 1) / max(1, len(w)) > 0.6 \
                and not re.search(r"[가-힣]", para):
            en_parts.append(para)
    prose = " ".join(en_parts)
    prose_scan = re.sub(r"\((?:[^()]*\d{4}[^()]*)\)", " ", prose)
    words = norm_words(prose_scan)
    if len(words) < N:
        print("영문 산문이 부족합니다.")
        return

    grams = {}
    for i in range(len(words) - N + 1):
        grams.setdefault(" ".join(words[i:i + N]), i)

    print("# n-gram·리듬 검사 · %s" % os.path.basename(path))
    print("- 영문 단어 {:,}, 5-gram {:,}종\n".format(len(words), len(grams)))

    allow = set()
    if os.path.exists(allow_f):
        allow = {l.strip() for l in open(allow_f, encoding="utf-8") if l.strip()}
    grams = {g: i for g, i in grams.items() if g not in allow}

    hits = []
    files = sorted(glob.glob(txt_dir + "/*.txt"))
    if not files:
        print("(문헌 캐시가 없어 5-gram 대조를 건너뜁니다. --extract 먼저)")
    for f in files:
        cw = norm_words(open(f, encoding="utf-8", errors="replace").read())
        cg = set(" ".join(cw[i:i + N]) for i in range(len(cw) - N + 1))
        for g in grams:
            if g in cg:
                hits.append((g, os.path.basename(f)[:48]))
    if hits:
        print("## 문헌과 겹치는 5-gram %d건" % len(hits))
        for g, src in hits[:25]:
            print('  - "%s"  <- %s' % (g, src))
        print("  → 귀속 인용이 아니면 문장을 재구성할 것."
              " 관용구면 %s에 등재." % allow_f)
    elif files:
        print("## 5-gram 겹침 없음")

    lens = sentences_en(prose)
    if len(lens) >= 5:
        cv = statistics.stdev(lens) / statistics.mean(lens)
        line = "\n## 문장 리듬: 평균 %.1f단어, CV %.2f" % (statistics.mean(lens), cv)
        if os.path.exists(band_f):
            b = json.load(open(band_f))
            ok = b["cv_lo"] <= cv <= b["cv_hi"]
            line += ("  (실측 대역 %s-%s) %s"
                     % (b["cv_lo"], b["cv_hi"],
                        "OK" if ok else
                        ("대역 밖 - 리듬이 균일함(AI 티)" if cv < b["cv_lo"]
                         else "대역 밖 - 리듬이 과함")))
        else:
            line += "  (대역 미실측: --calibrate 먼저)"
        print(line)
    else:
        print("\n(문장이 적어 리듬 계측 생략)")


if __name__ == "__main__":
    txt = opt("--txt", DEF_TXT)
    band = opt("--band", BAND_F)
    allow = opt("--allow", ALLOW_F)
    if "--extract" in sys.argv:
        extract(opt("--lit", DEF_LIT), txt)
    elif "--calibrate" in sys.argv:
        calibrate(txt, opt("--journal", ""), band)
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--")
                and a not in (txt, band, allow, opt("--lit", DEF_LIT),
                              opt("--journal", ""))]
        if not args:
            print(__doc__)
            sys.exit(1)
        scan(args[0], txt, band, allow)
