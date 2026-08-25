# -*- coding: utf-8 -*-
"""n-gram 겹침 스캔 + 문장 리듬(변동계수) 계측 (저널 무관 일반판).

쓰임:
  python check_ngram.py --extract  [--lit literature] [--txt literature/_txt]
      문헌 PDF를 텍스트로 뽑아 캐시한다 (PyMuPDF 필요). 한 번만.

  python check_ngram.py --calibrate [--txt ...] [--journal 5_journal]
      목표 저널 게재작의 문장 리듬 대역을 실측해 저장한다.
      --stability 를 붙이면 편수별로 대역이 얼마나 흔들리는지
      함께 낸다(몇 편이면 충분한지 판단용).
      --journal 은 캐시 파일 이름에 들어 있는 표식(폴더명·저널명 조각).
      생략하면 캐시 전체를 쓴다.

  python check_ngram.py 원고.md [--band <파일>] [--allow <파일>]
      원고의 영문 5단어 연쇄가 문헌 원문에 그대로 있는지 대조하고,
      --band 는 리듬 대역 파일(기본 _burstiness_band.json),
      --allow 는 사람이 통과시킨 관용구 목록(기본 _ngram_allow.txt).
      문장 길이 변동계수를 실측 대역과 비교한다.

- **양쪽에서 참고문헌을 걷어내고 센다.** 같은 논문을 인용한 두 글은 그 제목과
  저널명을 필연적으로 공유한다. 그것까지 세면 겹침이 열 배로 부푼다.
- 겹친 것은 **몇 편에 나오는가**로 나눈다. 세 편 이상이면 그 분야의 말이고,
  한두 편에만 나오면 읽어야 하는 것이다.
- `--journal` 표식으로 걸러 0편이 되면 **거르지 않고 전부 쓴다.** 캐시 이름에
  저널 표식이 없는 경우가 흔하다.
- 5-gram이 걸리면: 귀속 인용(따옴표+출처)이거나 완전 재구성이거나 둘 중
  하나만 한다. 어중간한 근접 의역이 가장 나쁘다.
- 문장 길이가 얼마나 들쭉날쭉한지를 **표준편차 / 평균**으로 잰다.
  **이 값에 줄임말을 붙이지 않는다.** 게재작 51편에 `CV`도
  `coefficient of variation`도 0편이었다. 도구가 지어낸 줄임말을
  찍으면 보고하는 쪽이 그 말을 기준어로 옮겨 쓴다. 균일한 리듬은
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
# 재는 방식의 이름. 방식이 바뀌면 옛 대역과 새 측정을 섞으면 안 된다.
# 참고문헌·표를 빼기 전에 만든 대역에 뺀 뒤의 값을 대면 판정이 뒤집힌다.
METHOD = "prose_only_v2"
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


REF_HEAD = re.compile(r"(?im)^[ 	]*#{0,4}[ 	]*\**(references|bibliography"
                      r"|참고문헌)\**[ 	]*$")


def prose_only(text, drop_floats=True):
    """참고문헌·표·캡션·수식을 걷어내고 **산문만** 남긴다.

    같은 논문을 인용한 두 글은 그 제목과 저널명을 필연적으로 공유한다.
    그것까지 세면 겹침이 열 배로 부풀어 진짜 겹침이 묻힌다. 실제로
    1,645건 중 실제로 읽어야 할 것은 131종이었다.
    """
    m = list(REF_HEAD.finditer(text))
    if m:
        text = text[:m[-1].start()]
    else:
        # PDF에서 뽑은 글은 줄바꿈이 거의 없어 "References"가 문장 한가운데
        # 처럼 보인다. 그래서 줄 단위로는 못 찾는다. 글의 절반을 지난 뒤
        # **처음 나오는** References를 참고문헌 시작으로 본다.
        cands = [m2.start() for m2 in
                 re.finditer(r"References|Bibliography|참고문헌", text)
                 if m2.start() > len(text) * 0.5]
        if cands:
            text = text[:cands[0]]
    if not drop_floats:
        # 리듬을 잴 때는 표·캡션을 빼지 않는다. PDF에서 뽑은 게재작 쪽은
        # 표를 가려낼 수 없어서, 원고에서만 빼면 **서로 다른 것을 재게 된다.**
        # 실제로 그렇게 해서 그 값이 0.68에서 0.49로 떨어져 판정이 뒤집혔다.
        return re.sub(r"\$[^$]{0,200}\$", " ", text)
    keep = []
    for ln in text.split(chr(10)):
        st = ln.strip()
        if st.startswith(("|", ">", "!")):
            continue                      # 표, 인용 블록, 그림
        if re.match(r"^\**(Table|Fig(\.|ure)?|Note|Source|Appendix)", st):
            continue                      # 캡션·주석
        keep.append(ln)
    t = chr(10).join(keep)
    t = re.sub(r"\$[^$]{0,200}\$", " ", t)          # 수식
    t = re.sub(r"`[^`]{0,200}`", " ", t)            # 코드 조각
    return t


def by_mark(files, mark, what="게재작"):
    """파일 이름으로 거르되, **0편이 나오면 거르지 않은 것을 쓴다.**

    캐시 파일 이름에 저널 표식이 없는 경우가 흔하다. 그때 필터를 그대로
    믿으면 "게재작 0편"이 되어 대역을 못 잰다. 실제로 그렇게 막힌 적이 있다.
    """
    if not mark:
        return files
    hit = [f for f in files if mark.lower() in os.path.basename(f).lower()]
    if hit:
        return hit
    print("주의: 파일 이름에 '%s' 표식이 있는 %s가 없다."
          " **이름으로 거르지 않고 %d편을 전부 쓴다.**"
          % (mark, what, len(files)))
    print("      (그 폴더에 목표 저널 것만 들어 있다면 이대로가 맞다)")
    return files


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


def stability(rows):
    """편수를 10편씩 늘려 가며 대역이 얼마나 변하는지 본다.

    "몇 편이면 충분한가"를 숫자로 못 박지 않고 재서 정하기 위한 것이다.
    대역 폭이 더 안 변하면 그만 받아도 된다.
    """
    print("")
    print("## 대역 안정성 (몇 편이면 충분한가)")
    print("")
    print("| 편수 | 편차/평균 대역 | 폭 | 직전 대비 폭 변화 |")
    print("|--|--|--|--|")
    prev = None
    steps = list(range(10, len(rows) + 1, 10))
    if not steps or steps[-1] != len(rows):
        steps.append(len(rows))
    for k in steps:
        if k < 5:
            continue
        sub = [r[2] for r in rows[:k]]
        lo, hi = min(sub), max(sub)
        w = hi - lo
        ch = "-" if prev is None else "%+.0f%%" % (100.0 * (w - prev) / prev
                                                   if prev else 0)
        print("| %d편 | %.2f-%.2f | %.2f | %s |" % (k, lo, hi, w, ch))
        prev = w
    print("")
    print("**마지막 칸의 변화가 5% 미만이면 그만 받아도 된다.** 계속 출렁이면"
          " 표본이 아직 적다는 뜻이므로 더 받는다.")
    print("표본을 늘리는 순서가 파일 이름 순이라 우연에 좌우된다."
          " 경향만 읽는다.")


def calibrate(txt_dir, mark, band_f):
    rows = []
    for f in by_mark(sorted(glob.glob(txt_dir + "/*.txt")), mark):
        lens = sentences_en(prose_only(
            open(f, encoding="utf-8", errors="replace").read(),
            drop_floats=False))
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
    if "--stability" in sys.argv:
        stability(rows)
    band = {"method": METHOD,
            "cv_lo": min(cvs), "cv_hi": max(cvs),
            "cv_med": round(statistics.median(cvs), 2),
            "len_lo": min(means), "len_hi": max(means), "n_papers": len(rows)}
    json.dump(band, open(band_f, "w"))
    print("게재작 %d편 실측" % len(rows))
    for nm, m, cv in rows:
        print("  %-46s 평균 %5.1f단어  편차/평균 %.2f" % (nm, m, cv))
    print("\n대역: 문장 평균 %s-%s단어, 길이 편차/평균 %s-%s (중앙값 %s)  → %s"
          % (band["len_lo"], band["len_hi"], band["cv_lo"], band["cv_hi"],
             band["cv_med"], band_f))
    if len(rows) < 40:
        print("주의: %d편입니다. 40편 미만이면 한 편이 들고 날 때마다 대역이"
              " 출렁입니다. 더 모으세요." % len(rows))
        print("      얼마나 흔들리는지는 --stability 로 봅니다.")


def scan(path, txt_dir, band_f, allow_f):
    src = open(path, encoding="utf-8").read()
    raw = prose_only(src)                       # 겹침 검사용 (표·캡션 뺀다)
    rhythm_src = prose_only(src, drop_floats=False)   # 리듬용 (게재작과 같게)
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

    where = {}          # 5-gram -> 그것이 나온 문헌 이름들
    files = sorted(glob.glob(txt_dir + "/*.txt"))
    if not files:
        print("(문헌 캐시가 없어 5-gram 대조를 건너뜁니다. --extract 먼저)")
    for f in files:
        # 문헌 쪽도 **산문만** 본다. 참고문헌까지 세면 같은 논문을 인용한
        # 두 글이 제목·저널명을 공유해 겹침이 열 배로 부푼다
        cw = norm_words(prose_only(
            open(f, encoding="utf-8", errors="replace").read(),
            drop_floats=False))
        cg = set(" ".join(cw[i:i + N]) for i in range(len(cw) - N + 1))
        for g in grams:
            if g in cg:
                where.setdefault(g, []).append(os.path.basename(f)[:48])
    if where:
        common = {g: v for g, v in where.items() if len(v) >= 3}
        rare = {g: v for g, v in where.items() if len(v) <= 2}
        print("## 문헌 본문과 겹치는 5-gram %d종" % len(where))
        print("")
        print("- **세 편 이상에 나오는 것 %d종**: 그 분야가 같이 쓰는 말이다."
              " 여러 논문이 함께 쓰면 베낀 것이 아니라 그 분야의 어휘다"
              % len(common))
        print("- **한두 편에만 나오는 것 %d종**: 읽어야 하는 것" % len(rare))
        print("")
        if common:
            print("### 분야 관용구 후보 (세 편 이상)")
            for g, v in sorted(common.items(), key=lambda x: -len(x[1]))[:10]:
                print('  - "%s"  (%d편)' % (g, len(v)))
            print("")
        if rare:
            print("### 읽어야 하는 것 (한두 편에만)")
            for g, v in sorted(rare.items())[:25]:
                print('  - "%s"  <- %s' % (g, v[0]))
            if len(rare) > 25:
                print("  - (외 %d종. 전수 판정은 문장 층에서 문장과 함께 한다)"
                      % (len(rare) - 25))
        print("  → 귀속 인용이 아니면 문장을 재구성할 것."
              " 관용구면 %s에 등재." % allow_f)
    elif files:
        print("## 5-gram 겹침 없음")

    # 원래의 문단 거르기를 그대로 쓴다. 한 글자짜리 토막(참고문헌의 이니셜
    # 등)이 많은 문단은 산문이 아니다
    rh_parts = []
    for para in rhythm_src.split(chr(10) + chr(10)):
        w = norm_words(para)
        if w and sum(1 for x in w if len(x) > 1) / max(1, len(w)) > 0.6                 and not re.search(r"[가-힣]", para):
            rh_parts.append(para)
    lens = sentences_en(" ".join(rh_parts))
    if len(lens) >= 5:
        cv = statistics.stdev(lens) / statistics.mean(lens)
        line = "\n## 문장 리듬: 평균 %.1f단어, 길이 편차/평균 %.2f" % (statistics.mean(lens), cv)
        if os.path.exists(band_f):
            b = json.load(open(band_f))
            if b.get("method") != METHOD:
                print("")
                print("**대역을 다시 재야 한다.** 이 대역 파일은 옛 방식으로"
                      " 잰 것이고(참고문헌·표를 빼지 않았다), 지금 원고는 새"
                      "  방식으로 쟀다.")
                print("잣대와 재는 법이 다르면 판정이 뒤집힌다."
                      " `--calibrate`를 다시 돌린 뒤에 이 검사를 한다.")
                return
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
