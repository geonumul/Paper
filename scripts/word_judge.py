# -*- coding: utf-8 -*-
"""낱말 대장의 한 구간을 판정한다. 갈래로 갈리는 것은 갈래로, 나머지는 사람이.

쓰임:
  python word_judge.py 대장.md 61 120 --md 원고.md --txt <코퍼스>
      그 구간을 갈래로 갈라 보여 준다 (대장은 안 건드린다)
  python word_judge.py 대장.md 61 120 --md 원고.md --txt <코퍼스> --apply
      갈래로 갈린 행에 판정과 근거를 적는다. **남은 것은 안 적는다**
  python word_judge.py 대장.md 61 120 --md 원고.md --txt <코퍼스> --verify
      **이미 적힌 근거가 사실인지 되짚는다.** 근거가 댄 논문에 그 낱말이
      실제로 있는지, 인용한 문장이 그 논문에 있는지 확인한다

왜 필요한가
  낱말이 1,500개면 한 턴 60행으로도 스물다섯 턴이다. 행마다 손으로 근거를
  쓰면 스물다섯 턴이 타자로 지나가거나, 더 흔하게는 **한 줄짜리 이유를
  전부에 붙여 넣는 것으로 무너진다.** 둘 다 판정이 아니다.

  그래서 **근거로 갈리는 것은 근거로 가르고**, 안 갈리는 것만 남긴다.
  자동화의 목적은 대신 답하는 것이 아니라, 사람이 실제로 읽을 만큼
  남는 것을 줄이는 데 있다.

갈래
  대상 아님   수식·코드 안에만 있다 (LaTeX 명령이 낱말로 올라온 것)
  유지        참고문헌에만 있다 (인용한 논문의 저자명·제목 조각)
  유지        그림·표 캡션에만 있다 (우리 그림을 설명하는 말)
  유지        게재작 8% 이상이 쓴다 (**어느 논문 어느 문장인지 함께 적는다**)
  유지        그 꼴만 없고 어간이 게재작에 흔하다
  ★ 다른 꼴   우리 꼴은 게재작에 **아예 없고** 낱말이 통째로 다른 꼴로 굳어
              있다 (overfit / overfitting). **단수·복수·시제·부사형은
              알리지 않는다.** 그건 문장 자리가 정하는 문법이다
  유지        조사표 항목 코드(Q14) 옆이거나 표 안에만 있다 (원자료 표기)
  손으로 볼 것 위 어디에도 안 걸리는 것

**★ 다른 꼴은 지적이 아니라 후보다.** 바꿀지는 저자가 정한다.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _norm import mask_currency, norm_text   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MATH = re.compile(r"\$\$[^$]{0,800}\$\$|\$[^$]{0,300}\$", re.S)
CAPTION = re.compile(r"(?m)^\**(?:Table|Fig(?:\.|ure)?|Note|Source)\b[^\n]*")
REFHEAD = re.compile(r"(?im)^#{0,4}\s*\**(references|bibliography|참고문헌)\**\s*$")


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def has(text, w):
    return re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])",
                     text, re.I) is not None


def stem_of(w):
    w = w.split("-")[-1] if "-" in w else w
    for suf in ("ities", "ies", "ing", "ed", "es", "ly", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w


def papers_with(docs, pat, exact_case=False):
    """그 표현이 나오는 게재작 이름들.

    exact_case=True면 **소문자 그대로만** 찾는다. 고유명을 굴절형으로
    오인하는 것을 막는다. `bullet`이 저널 이름 *Bulletin*으로, `rose`가
    저자 성 *Rosen*으로 잡힌 적이 있다.
    """
    rx = re.compile(pat) if exact_case else re.compile(pat, re.I)
    return [n for n, t in docs if rx.search(t)]


def content_words(s):
    return {w.lower() for w in re.findall(r"[A-Za-z]{4,}", s or "")}


def sentence_in(docs, pat, like=None):
    """그 표현이 쓰인 게재작 문장 하나. **우리 문장과 가까운 것을 고른다.**

    첫 문장을 그냥 집으면 **다른 뜻의 문장**이 근거로 붙는다. 실제로
    `contributions`의 근거로 "연구의 학술적 기여"를 말하는 문장이 붙었는데
    우리 쓰임은 변수가 예측에 기여한 양이었다. 같은 낱말, 다른 뜻이다.

    그래서 우리 문장과 **내용어가 겹치는** 문장을 고른다.
    """
    rx = re.compile(r"[^.]{0,60}" + pat + r"[^.]{0,60}", re.I)
    want = content_words(like)
    best = None
    for n, t in docs:
        for m in list(rx.finditer(t))[:4]:
            cand = re.sub(r"\s+", " ", m.group(0)).strip()[:110]
            score = len(want & content_words(cand)) if want else 0
            if best is None or score > best[0]:
                best = (score, n, cand)
        if best and best[0] >= 3:
            break
    return (best[1], best[2]) if best else (None, None)



def load_docs(txt_dir):
    out = []
    for f in sorted(os.listdir(txt_dir)):
        if f.endswith(".txt"):
            out.append((f[:-4], io.open(os.path.join(txt_dir, f),
                                        encoding="utf-8",
                                        errors="replace").read()))
    return out


def split_manuscript(md):
    """본문 산문 / 표 / 캡션 / 수식 / 참고문헌으로 가른다.

    **통화의 달러를 먼저 가린다.** `US$ 4 million`의 달러가 다음 달러와
    짝지으면 그 사이 본문이 통째로 수식이 된다. 실제로 7,876자가 삼켜져
    그 구간 낱말이 전부 "LaTeX 명령"으로 판정된 적이 있다.
    """
    md = mask_currency(md)
    m = REFHEAD.search(md)
    body, refs = (md[:m.start()], md[m.start():]) if m else (md, "")
    math = " ".join(MATH.findall(body))
    caps = " ".join(CAPTION.findall(body))
    tables = " ".join(l for l in body.split("\n") if l.strip().startswith("|"))
    prose = MATH.sub(" ", body)
    prose = CAPTION.sub(" ", prose)
    prose = re.sub(r"(?m)^\s*\|.*$", " ", prose)
    return prose, tables, caps, math, refs


def rows_of(path):
    """대장 행: 번호, 낱말, 원고 빈도, 코퍼스 편수, 1차 판정.

    1차 판정 칸에 대조표가 잰 어간 측정이 들어 있다. 여기서 다시 재지 않고
    그대로 쓴다. 같은 것을 두 번 재면 두 값이 갈린다.
    """
    rows = []
    for ln in io.open(path, encoding="utf-8"):
        cells = [c.strip() for c in ln.rstrip().strip("|").split("|")]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        try:
            rows.append((int(cells[0]), cells[1], int(cells[2]),
                         int(cells[3]), cells[5]))
        except ValueError:
            continue
    return rows


def judge(w, cnt, n_docs, docs, parts, note=''):
    """한 낱말의 판정과 근거. 못 정하면 None."""
    prose, tables, caps, math, refs = parts
    in_prose = has(prose, w) or has(tables, w)
    if not in_prose and has(math, w):
        return ("대상 아님", "낱말이 아니라 수식 안의 LaTeX 명령이다."
                          " 대조표가 수식을 다 걷어내지 못해 행으로 올라왔다")
    if not in_prose and has(refs, w):
        return ("유지", "본문에 없고 참고문헌에만 있다. 인용한 논문의 저자명이나"
                      " 제목의 일부다")
    if not in_prose and has(caps, w):
        return ("유지", "그림·표 캡션에만 있다. 우리 그림을 설명하는 말이라"
                      " 게재작과 달라도 정상이다")
    # 조사표 항목 코드(Q14, SQ2) 옆에 있으면 원자료를 가리키는 말이다.
    # 바꾸면 조사표와 어긋나므로 게재작에 없다고 고칠 일이 아니다
    win = r"[^.]{0,70}(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])[^.]{0,70}"
    near = re.search(win, prose + " " + tables, re.I)
    # 코드처럼 보이는 것을 다 문항 코드로 보면 안 된다. `F1`, `R2`, `H1`이
    # 걸려서 **결과표의 지표 이름**(precision, recall, F1)이 원자료 용어로
    # 판정된 적이 있다. 문항 코드는 Q로 시작하는 것만 인정한다
    if near and re.search(r"(?<![A-Za-z])(?:S?Q\d{1,3}|item\s+\d{1,3})"
                          r"(?![A-Za-z0-9])", near.group(0)):
        return ("유지", "조사표 항목 코드 옆에서 원자료를 가리킨다: %s"
                % re.sub(r"\s+", " ", near.group(0)).strip()[:90])
    if not has(prose, w) and has(tables, w):
        return ("유지", "본문이 아니라 표 안에만 있다. 표의 항목 이름이라"
                      " 원자료·조사표 표기를 따른다")
    # 우리가 그 낱말을 쓴 문장. 근거를 고를 때 이것과 가까운 것을 고른다
    om = re.search(r"[^.]{0,90}(?<![A-Za-z])" + re.escape(w) +
                   r"(?![A-Za-z])[^.]{0,90}", prose, re.I)
    ours_sent = om.group(0) if om else None
    pct = 100.0 * cnt / max(1, n_docs)
    if pct >= 8:
        p, s = sentence_in(docs, r"(?<![A-Za-z])" + re.escape(w) +
                           r"(?![A-Za-z])", ours_sent)
        return ("유지", "게재작 %d편(%.0f%%)이 쓴다. [%s] %s" % (cnt, pct, p, s)
                if p else "게재작 %d편(%.0f%%)이 쓴다" % (cnt, pct))
    if "형태만 없음" in note:
        # 대조표가 이미 어간을 쟀다. 그 측정을 그대로 쓴다
        return ("유지", "그 꼴만 없고 어간은 게재작에 있다. 대조표 측정: %s"
                % note)
    # 그 꼴만 없는 것인가, 아니면 게재작이 다른 꼴을 쓰는가
    st = stem_of(w.lower())
    if st != w.lower():
        sp = papers_with(docs, r"(?<![A-Za-z])" + re.escape(st) +
                         r"[a-z]{0,5}(?![A-Za-z])")
        if 100.0 * len(sp) / max(1, n_docs) >= 8:
            p, s = sentence_in(docs, r"(?<![A-Za-z])" + re.escape(st) +
                               r"[a-z]{0,5}(?![A-Za-z])")
            return ("유지", "그 꼴만 없고 어간 '%s'가 게재작 %d편에 있다. [%s] %s"
                    % (st, len(sp), p, s))
    # 낱말을 앞머리로 하는 **굴절형**을 게재작이 쓰는가
    # (overfit -> overfitting). 아무 글자나 붙은 것을 같은 말로 보면
    # 안 된다. bullet에 in이 붙은 Bulletin은 다른 낱말이다
    # **문법이 정하는 어미는 알리지 않는다.** 단수와 복수, 시제, 부사형은
    # 문장 자리가 정하는 것이지 그 저널의 어휘 선택이 아니다.
    #   was slight는 was slightly가 될 수 없고, 열거 안의 sanction은
    #   sanctions가 될 수 없다. 이런 것을 알리면 문법을 문체 지적으로
    #   바꿔 놓는다 (실제로 일곱 건이 그렇게 잘못 걸렸다)
    # 알리는 것은 **낱말이 통째로 다른 꼴로 굳은 경우**뿐이다
    #   (overfit / overfitting)
    SUF = "(?:ing|ment|ments|ation|ations)"
    # overfit + ing 은 overfitting 이다. 끝 자음이 겹치는 것을 봐 준다
    DBL = "[bdgklmnprt]?"
    longer = papers_with(docs, r"(?<![A-Za-z])" + re.escape(w.lower())
                         + DBL + SUF + r"(?![A-Za-z])",
                         exact_case=True)
    # 이 갈래는 "흔한가"가 아니라 "우리 꼴보다 그쪽이 더 자주 쓰이는가"를
    # 묻는다. 그래서 8% 문턱을 쓰지 않는다. 두 편 이상이고 우리 꼴보다
    # 많으면 저자에게 알린다 (판정이 아니라 후보다)
    # **우리 꼴이 게재작에 아예 없을 때만** 알린다. 단수와 복수가 갈리는
    # 정도로는 알리지 않는다. 그건 문체가 아니라 문법 선택이다
    if cnt == 0 and len(longer) >= 2:
        p, s = sentence_in(docs, r"(?<![A-Za-z])" + re.escape(w.lower())
                           + DBL + SUF + r"(?![A-Za-z])")
        return ("★ 다른 꼴", "이 꼴은 게재작 %d편, **같은 말의 다른 꼴은"
                          " %d편.** [%s] %s → 문장 자리가 그 꼴을 요구하는지"
                          " 먼저 보고, 아니면 저자가 정한다"
                % (cnt, len(longer), p, s))
    return None


def in_body_independent(md_raw, w):
    """그 낱말이 본문에 있는가를 **판정과 다른 방법으로** 다시 본다.

    되짚기가 판정과 같은 계산을 쓰면 같은 버그에 같이 눈이 먼다. 실제로
    달러 짝짓기 버그 하나가 판정과 자가검사를 동시에 통과시킨 적이 있다.

    그래서 여기서는 달러를 아예 안 본다. 낱말이 나온 **줄의 생김새**로
    가른다. 보통 낱말이 다섯 개 이상이고 LaTeX 명령이 없고 표 줄이
    아니면 산문이다.
    """
    m = REFHEAD.search(md_raw)
    body = md_raw[:m.start()] if m else md_raw
    rx = re.compile(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", re.I)
    for line in body.split(chr(10)):
        if not rx.search(line):
            continue
        st = line.strip()
        if st.startswith("|") or st.startswith("$$"):
            continue
        if len(re.findall(chr(92) * 2 + r"[a-zA-Z]{2,}", st)) >= 2:
            continue                      # LaTeX 명령이 여럿이면 수식 줄이다
        if len(re.findall(r"[A-Za-z]{3,}", st)) >= 5:
            return True
    return False


def verify(led, a, b, docs, parts, md_raw):
    """이미 적힌 근거가 사실인지 되짚는다. **판정과 다른 경로로 계산한다.**

    네 가지를 본다.

      1 근거가 이름 댄 논문이 코퍼스에 있는가 (줄여 적었으면 알려 준다)
      2 인용한 문장이 그 논문에 실제로 있는가 (따옴표·굽은 부호는 맞춰 본다)
      3 "참고문헌에만" "수식 안"이라 적힌 낱말이 정말 본문에 없는가
      4 판정 칸이 비어 있지 않은가

    **한 줄이라도 안 맞으면 그 배치의 판정을 다시 본다.**
    """
    byname = dict(docs)
    bad, checked, short_key = [], 0, 0
    rows_seen = []
    lines = list(io.open(led, encoding="utf-8"))
    for line in lines:
        m0 = re.match(r"\|\s*(\d+)\s*\|", line)
        if not m0:
            continue
        n = int(m0.group(1))
        if not (a <= n <= b):
            continue
        cells = [c.strip() for c in line.rstrip().strip("|").split("|")]
        if len(cells) < 8 or not cells[-1]:
            continue
        w, ev = cells[1], cells[-1]
        checked += 1
        rows_seen.append((n, w, int(cells[2]) if cells[2].isdigit() else 0))
        m = re.search(r"\[([^\]]+)\]([^\[]*)", ev)
        if m:
            name, quote = m.group(1), m.group(2)
            t = byname.get(name)
            if t is None:
                cand = [k for k in byname if k.startswith(name)]
                if len(cand) == 1:
                    t = byname[cand[0]]
                    short_key += 1
                else:
                    bad.append((n, w, "근거가 댄 논문이 코퍼스에 없다: %s"
                                % name))
                    continue
            # 따옴표·굽은 부호·조사를 걷어내고 앞머리를 맞춰 본다
            # 인용을 대조할 때 **양쪽에서 같은 것을 걷어낸다.** 굽은
            # 아포스트로피, 별표, 세로줄 때문에 근거가 맞는데도 "그 논문에
            # 없다"로 걸린 적이 세 번 있다
            def flat(x):
                x = norm_text(x, fold_accents=True)
                x = re.sub(r"[*|`_~]", "", x)
                return re.sub(r"\s+", " ", x).strip()

            q = re.sub(r"^[^A-Za-z]+", "", flat(quote))[:40]
            if q and flat(t).find(q) < 0:
                bad.append((n, w, "인용한 문장이 그 논문에 없다: %s…" % q))
        if ("참고문헌에만" in ev or "수식 안" in ev) and                 in_body_independent(md_raw, w):
            bad.append((n, w, "본문에 있는데 '%s'이라고 적혔다"
                        % ("참고문헌에만" if "참고문헌에만" in ev else "수식")))
    print("# 근거 되짚기 · %d-%d행" % (a, b))
    print("")
    print("- 근거가 적힌 행 **%d개** 중 어긋난 것 **%d개**" % (checked, len(bad)))
    for n, w, why in bad[:25]:
        print("    - #%d %s: %s" % (n, w, why))
    if short_key:
        print("- 논문 키를 줄여 적은 근거 %d개. **전체 키로 적는다.**"
              " 기계가 되짚을 수 없는 근거는 근거가 아니다" % short_key)
    if not bad and checked:
        print("- 전부 확인됐다. 근거가 댄 논문에 그 낱말과 문장이 실제로 있다")
    if not checked:
        print("- 그 구간에 아직 근거가 적힌 행이 없다")
        return
    # **되짚기는 사실만 본다. 뜻이 같은지는 못 본다.**
    # 논문 이름이 맞고 문장이 그 논문에 있어도, 그 문장이 우리 문장과 같은
    # 뜻으로 그 낱말을 쓰는지는 사람이 읽어야 안다. 그래서 매 몫마다 몇 행을
    # 지목해 눈으로 보게 한다
    # **원고에서 많이 쓰는 낱말부터 본다.** 서른세 번 쓰는 낱말은 주장을
    # 떠받치고, 한 번 쓰는 낱말은 안 그렇다. 같은 한 행을 읽어도 앞엣것을
    # 읽는 편이 낫다. 거기에 구간 앞뒤를 하나씩 더해 치우침을 막는다
    top = sorted(rows_seen, key=lambda r: -r[2])[:2]
    picks, seen_n = [], set()
    for r in top + [rows_seen[0], rows_seen[-1]]:
        if r[0] not in seen_n:
            seen_n.add(r[0])
            picks.append(r)
        if len(picks) >= 3:
            break
    print("")
    print("## 뜻은 기계가 못 본다. 아래 %d행은 눈으로 본다" % len(picks))
    for n, w, freq in picks:
        print("    - #%d %s (원고 %d회): 게재작 문장과 우리 문장이 **같은"
              " 뜻·같은 문법 자리**로 그 낱말을 쓰는가" % (n, w, freq))
    print("      많이 쓰는 낱말이 주장을 떠받친다. 그 낱말의 뜻이 어긋나면"
          " 그 위에 선 문단이 전부 어긋난다")



def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        print(__doc__)
        return
    led, a, b = args[0], int(args[1]), int(args[2])
    md_path = opt("--md")
    txt_dir = opt("--txt", "literature/_txt")
    if not md_path or not os.path.exists(md_path):
        print("`--md 원고.md`가 필요하다. 낱말이 본문인지 참고문헌인지"
              " 캡션인지 갈라야 판정할 수 있다.")
        return
    docs = load_docs(txt_dir)
    if not docs:
        print("코퍼스가 없다: %s" % txt_dir)
        return
    parts = split_manuscript(io.open(md_path, encoding="utf-8",
                                     errors="replace").read())
    if "--verify" in sys.argv:
        verify(led, a, b, docs, parts,
               io.open(md_path, encoding="utf-8", errors="replace").read())
        return
    rows = [r for r in rows_of(led) if a <= r[0] <= b]
    if not rows:
        print("그 구간에 행이 없다: %d-%d" % (a, b))
        return

    got, left = {}, []
    for n, w, freq, cnt, note in rows:
        v = judge(w, cnt, len(docs), docs, parts, note)
        if v:
            got[n] = (w, v)
        else:
            left.append((n, w, freq, cnt, note))

    print("# 낱말 판정 · %d-%d행" % (a, b))
    print("")
    print("- 갈래로 갈린 것 **%d개** / 손으로 볼 것 **%d개** (코퍼스 %d편)"
          % (len(got), len(left), len(docs)))
    kinds = {}
    for _, (_, (v, _)) in got.items():
        kinds[v] = kinds.get(v, 0) + 1
    for k, c in sorted(kinds.items(), key=lambda x: -x[1]):
        print("    - %s %d개" % (k, c))
    print("")
    print("## 손으로 볼 것")
    if not left:
        print("- 없음")
    for n, w, freq, cnt, _note in left:
        print("")
        print("**#%d %s** (원고 %d회 · 게재작 %d편)" % (n, w, freq, cnt))
        m = re.search(r"[^.\n]{0,90}(?<![A-Za-z])" + re.escape(w) +
                      r"(?![A-Za-z])[^.\n]{0,90}", parts[0], re.I)
        if m:
            print("- 우리: %s" % re.sub(r"\s+", " ", m.group(0)).strip()[:150])

    if "--apply" not in sys.argv:
        print("")
        print("**대장에 적으려면 `--apply`.** 손으로 볼 것은 비워 둔다.")
        return

    out, n_w = [], 0
    for ln in io.open(led, encoding="utf-8"):
        m = re.match(r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|(.*)\|\s*\|\s*\|\s*$",
                     ln.rstrip("\n"))
        if m and int(m.group(1)) in got:
            w, (v, e) = got[int(m.group(1))]
            out.append("| %s | %s |%s| %s | %s |\n"
                       % (m.group(1), m.group(2), m.group(3), v, e))
            n_w += 1
        else:
            out.append(ln)
    io.open(led, "w", encoding="utf-8").write("".join(out))
    print("")
    print("대장에 %d행을 적었다. 남은 %d행은 사람이 판정한다." % (n_w, len(left)))


if __name__ == "__main__":
    main()
