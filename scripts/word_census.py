# -*- coding: utf-8 -*-
"""원고의 낱말을 하나도 빠짐없이 뽑아 코퍼스 대조표를 만든다 (전수 판정용).

쓰임:
  python word_census.py 원고.md --txt literature/_txt --journal TFSC
  python word_census.py 원고.md --ngram 2          # 두 낱말 결합형까지
  python word_census.py 원고.md --abbr            # 약어만 전수 검사
  python word_census.py 원고_국문.md --ko --txt <국문코퍼스폴더>   # 국문 원고
  python word_census.py 원고.md --min-freq 1       # 한 번 나온 낱말도 전부
  python word_census.py 원고.md --out 대조표.md    # 파일로

왜 쓰나
  낱말 층 검수는 **전수**여야 한다. "몇 개를 확인했다"로 끝내면 반드시 놓친다.
  이 표는 행 개수가 정해져 있으므로, 모든 행에 판정이 붙어야 끝난다.

출력
  낱말 | 원고 빈도 | 코퍼스 편수 | 비율 | 1차 판정
  비율이 낮은 것부터 나온다(위험한 것 먼저).

  **1차 판정은 기계의 후보일 뿐이다.** 8% 이상이어도 맥락 다섯(뜻·대상·
  문법 자리·강도·정의)을 문장으로 확인해야 판정이 끝난다.
  `find_usage.py`로 그 낱말이 쓰인 문장을 읽는다.
"""
import io
import os
import re
import sys
import glob
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 판정 대상이 아닌 것: 기능어
STOP = set("""a an the and or but if while of in on at to for from by with without
into onto over under between among through during before after above below up down
out off again further then once here there when where why how all any both each few
more most other some such no nor not only own same so than too very can will just
should now is are was were be been being have has had do does did doing this that
these those it its itself they them their we our us i you your he she his her as
about against because until also however therefore moreover furthermore thus
whether which who whom whose what within across per via due upon toward towards
than may might must would could shall let there's cannot""".split())

# 코드·매개변수 이름은 대조 대상이 아니다 (번역·교체하지 않는다).
# 프로젝트마다 다르므로 style_config.json의 "code_names"로 바꿔 쓴다.
CODE_DEFAULT = ["random_state", "n_estimators", "learning_rate", "batch_size",
                "n_components", "python", "github", "auc", "rmse"]


def load_code_names(path="style_config.json"):
    import json
    if os.path.exists(path):
        try:
            cfg = json.load(open(path, encoding="utf-8"))
            return set(CODE_DEFAULT) | set(cfg.get("code_names", []))
        except Exception:
            pass
    return set(CODE_DEFAULT)


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


# 국문 조사·어미 (뒤에서 떼어 낸다. 긴 것부터)
JOSA = ["에서는", "으로써", "으로서", "이라는", "라는", "에서", "에게", "으로",
        "까지", "부터", "처럼", "보다", "만큼", "과의", "와의", "의", "은", "는",
        "이", "가", "을", "를", "에", "도", "만", "과", "와", "로", "며", "고"]


def ko_tokens(text):
    text = re.sub(r"`[^`]*`", " ", text)
    out = []
    for w in re.findall(r"[가-힣]{2,}", text):
        for j in JOSA:
            if w.endswith(j) and len(w) - len(j) >= 2:
                w = w[:-len(j)]
                break
        if len(w) >= 2:
            out.append(w)
    return out


def tokens(text):
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"`[^`]*`", " ", text)              # 코드 조각 제거
    text = re.sub(r"\((?:[^()]*\d{4}[^()]*)\)", " ", text)   # 인용 괄호 제거
    text = re.sub(r"[^A-Za-z\- ]+", " ", text)
    out = []
    for w in text.split():
        w = w.strip("-").lower()
        if len(w) < 3:
            continue
        out.append(w)
    return out


def load_corpus(txt_dir, mark, n, ko=False):
    files = [f for f in sorted(glob.glob(txt_dir + "/*.txt"))
             if not mark or mark.lower() in os.path.basename(f).lower()]
    docs = []
    for f in files:
        raw = open(f, encoding="utf-8", errors="replace").read()
        t = ko_tokens(raw) if ko else tokens(raw)
        s = set(t)
        if n > 1:
            s |= set(" ".join(t[i:i + n]) for i in range(len(t) - n + 1))
        docs.append(s)
    return docs, len(files)


def abbr_report(src, txt_dir, mark):
    """원고의 약어를 전부 뽑아 ①원고에서 정의했는가 ②게재작이 실제로 쓰는가."""
    raw = open(src, encoding="utf-8", errors="replace").read()
    body = "\n".join(ln for ln in raw.split("\n")
                     if not ln.lstrip().startswith((">", "#")))
    found = Counter(re.findall(r"(?<![A-Za-z])([A-Z]{2,6})(?![A-Za-z])", body))
    if not found:
        print("약어를 못 찾았다.")
        return
    files = [f for f in sorted(glob.glob(txt_dir + "/*.txt"))
             if not mark or mark.lower() in os.path.basename(f).lower()]
    docs = []
    for f in files:
        t = open(f, encoding="utf-8", errors="replace").read()
        docs.append(set(re.findall(r"(?<![A-Za-z])([A-Z]{2,6})(?![A-Za-z])", t)))
    n_files = len(files) or 1

    print("# 약어 전수 검사 · %s" % os.path.basename(src))
    print("")
    print("- 원고의 약어 **%d종** / 코퍼스 %d편" % (len(found), n_files))
    print("- **대화에서 익숙해진 약어를 원고에 쓰지 않는다.** 게재작이 실제로"
          " 그 약어를 쓰는지, 원고에서 정의했는지 둘 다 본다")
    print("")
    print("| 약어 | 원고 빈도 | 원고에서 정의 | 코퍼스 편수 | 비율 | 1차 판정 |")
    print("|--|--|--|--|--|--|")
    rows = []
    for a_, n in found.items():
        first = body.find(a_)
        window = body[max(0, first - 140):first + 140]
        defined = bool(re.search(r"\([^)]*%s[^)]*\)" % re.escape(a_), window)
                       or re.search(r"%s\s*\(" % re.escape(a_), window))
        c = sum(1 for d in docs if a_ in d)
        pct = 100.0 * c / n_files
        if c == 0:
            v = "**코퍼스에 없음. 풀어 쓸 것**"
        elif not defined:
            v = "**정의 없음**"
        elif pct < 8:
            v = "드묾(8% 미만). 풀어 쓸지 판단"
        else:
            v = "맥락 확인"
        rows.append((c, -n, a_, n, "○" if defined else "**✗**", c, pct, v))
    rows.sort()
    for _, _, a_, n, d, c, pct, v in rows:
        print("| %s | %d | %s | %d | %.1f%% | %s |" % (a_, n, d, c, pct, v))
    print("")
    print("판정: 유지 / 풀어 쓰기 / 정의 추가 중 하나를 모든 행에 적는다.")
    print("**새 약어를 만들지 않는다.** 게재작이 안 쓰는 줄임말은 풀어 쓴다"
          "(예: CV라 쓰지 말고 cross-validation).")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return
    if "--abbr" in sys.argv:
        abbr_report(args[0], opt("--txt", "literature/_txt"), opt("--journal", ""))
        return
    src = args[0]
    txt_dir = opt("--txt", "literature/_txt")
    mark = opt("--journal", "")
    n = int(opt("--ngram", 1))
    min_freq = int(opt("--min-freq", 1))
    out = opt("--out")

    body = open(src, encoding="utf-8", errors="replace").read()
    # 기록 블록과 헤더는 본문이 아니다
    body = "\n".join(ln for ln in body.split("\n")
                     if not ln.lstrip().startswith((">", "#")))
    ko = "--ko" in sys.argv
    toks = ko_tokens(body) if ko else tokens(body)
    if n > 1:
        units = Counter(" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1))
        units = Counter({k: v for k, v in units.items()
                         if not any(w in STOP for w in k.split())})
    else:
        units = Counter(w for w in toks if w not in STOP)
    code = load_code_names(opt("--config", "style_config.json"))
    units = Counter({k: v for k, v in units.items()
                     if v >= min_freq and k not in code})

    docs, n_files = load_corpus(txt_dir, mark, n, ko)
    if not docs:
        print("코퍼스가 없습니다: %s (check_ngram.py --extract 먼저)" % txt_dir)
        return

    def stems(w):
        """굴절형 오탐을 줄이려고 어간 후보를 만든다."""
        out = []
        for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ed", ""),
                         ("ed", "e"), ("ing", ""), ("ing", "e")):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                out.append(w[:-len(suf)] + rep)
        return out

    rows = []
    for w, f in units.items():
        c = sum(1 for d in docs if w in d)
        pct = 100.0 * c / n_files
        note = ""
        if c == 0 and n == 1 and not ko:
            best = 0
            for st in stems(w):
                sc = sum(1 for d in docs if st in d)
                if sc > best:
                    best, best_st = sc, st
            if best:
                note = " (어간 `%s` %.0f%%)" % (best_st, 100.0 * best / n_files)
        verdict = "확인 필요 (8% 미만)" if pct < 8 else "맥락 확인"
        if c == 0:
            verdict = ("**코퍼스에 없음**" + note) if not note else                       ("형태만 없음" + note)
        rows.append((pct, -f, w, f, c, verdict))
    rows.sort()

    L = []
    L.append("# 낱말 전수 대조표 · %s" % os.path.basename(src))
    L.append("")
    L.append("- 코퍼스 %d편%s" % (n_files, (", 표식 '%s'" % mark) if mark else ""))
    L.append("- 대조 대상 %d개 (%d낱말 단위, %s)"
             % (len(rows), n,
                "국문: 조사 제거" if ko else "기능어·코드 이름 제외"))
    if n_files < 5:
        L.append("- **주의: 코퍼스가 %d편뿐이다.** 비율(%%)은 의미가 약하니"
                 " '있다/없다'로만 읽는다" % n_files)
    zero = sum(1 for r in rows if r[4] == 0 and "어간" not in r[5])
    low = sum(1 for r in rows if r[0] < 8)
    L.append("- **코퍼스에 아예 없음 %d개 / 8%% 미만 %d개**" % (zero, low))
    L.append("- 굴절형이라 형태만 없는 것은 어간 비율을 괄호에 적었다"
             "(그 낱말은 대개 문제가 아니다)")
    if rows and zero / float(len(rows)) > 0.5:
        L.append("")
        L.append("> **경고: 대조 대상의 %.0f%%가 코퍼스에 없다.**"
                 " 이 정도면 우리 낱말이 문제인 것이 아니라"
                 " **코퍼스가 이 원고와 안 맞거나 텍스트가 깨진 것**이다."
                 " (국문 PDF 추출본은 띄어쓰기가 깨져 아무것도 안 맞는다.)"
                 " 코퍼스를 먼저 확인하고 다시 돌린다."
                 % (100.0 * zero / len(rows)))
    L.append("")
    L.append("**전수 판정이다.** 아래 %d행에 전부 판정을 적기 전에는 낱말 층을"
             " 닫지 않는다. 표본으로 몇 개만 보지 않는다." % len(rows))
    L.append("")
    L.append("| # | 낱말 | 원고 빈도 | 코퍼스 편수 | 비율 | 1차 판정 | 사람 판정 | 근거 |")
    L.append("|--|--|--|--|--|--|--|--|")
    for i, (pct, negf, w, f, c, verdict) in enumerate(rows, 1):
        L.append("| %d | %s | %d | %d | %.1f%% | %s |  |  |"
                 % (i, w, f, c, pct, verdict))
    L.append("")
    L.append("판정은 유지 / 대체 / 유보 중 하나로 적고, 근거 칸에 게재작 문장을"
             " 확인한 결과를 적는다(`find_usage.py`).")
    L.append("8% 이상이어도 끝이 아니다. **맥락 다섯**(뜻·가리키는 대상·문법"
             " 자리와 연어·강도·정의를 붙이는가)을 문장으로 확인한다.")
    text = "\n".join(L)

    if out:
        open(out, "w", encoding="utf-8").write(text)
        print("저장: %s (행 %d개)" % (out, len(rows)))
        print("코퍼스에 없음 %d개, 8%% 미만 %d개부터 본다." % (zero, low))
    else:
        print(text)


if __name__ == "__main__":
    main()
