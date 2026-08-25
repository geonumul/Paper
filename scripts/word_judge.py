# -*- coding: utf-8 -*-


"""낱말 대장의 한 구간을 판정한다. 갈래로 갈리는 것은 갈래로, 나머지는 사람이.


쓰임:


  python word_judge.py 대장.md 61 120 --md 원고.md --txt <코퍼스>


      그 구간을 갈래로 갈라 보여 준다 (대장은 안 건드린다)


  python word_judge.py 대장.md 61 120 --md 원고.md --txt <코퍼스> --apply


      갈래로 갈린 행에 판정과 근거를 적는다. **남은 것은 안 적는다**

  python word_judge.py 대장.md 1 1769 --md 원고.md --txt <코퍼스> --apply --refresh

      **도구를 고친 뒤, 근거가 부실한 행만 다시 적는다.** 인용이 없거나,

      적힌 인용이 그 논문에 되짚어지지 않는 행이다. ★가 붙은 행과,

      코퍼스에 문장이 있을 수 없는 갈래(참고문헌에만 나오는 말, 고유명,

      조사표 항목)는 건드리지 않는다


  python word_judge.py 대장.md 1 1200 --md 원고.md --txt <코퍼스> --diff


      **도구가 바뀐 뒤** 새 판이 다르게 말하는 행만 뽑는다. 층을 처음부터


      다시 판정하지 않고 갈라지는 행만 본다


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


_HIT_CACHE = {}


def papers_with(docs, pat, exact_case=False):

    """그 표현이 나오는 게재작 이름들.


    **값싼 걸러내기를 붙이려다 사고를 냈다.** 정규식 문자열에서 글자만

    뽑아 열쇠로 썼더니 `(?<![A-Za-z])institute`가 `azazin`이 되어 아무

    문서도 안 걸렸고, **답이 늘 0**이 되었다. 걸러내기를 빼고 그대로

    훑는다. 느린 것은 캐시로 감당한다.

    """

    """그 표현이 나오는 게재작 이름들.


    exact_case=True면 **소문자 그대로만** 찾는다. 고유명을 굴절형으로


    오인하는 것을 막는다. `bullet`이 저널 이름 *Bulletin*으로, `rose`가


    저자 성 *Rosen*으로 잡힌 적이 있다.


    """

    # **같은 패턴을 행마다 다시 훑지 않는다.** 코퍼스가 51편이면 한 번

    # 훑는 데 2MB가 넘고, 1,700행이면 그것을 수천 번 되풀이하게 된다

    key = (pat, exact_case)

    if key in _HIT_CACHE:

        return _HIT_CACHE[key]

    rx = re.compile(pat) if exact_case else re.compile(pat, re.I)

    out = []

    for item in docs:

        n, t, tl = item[0], item[1], item[2]

        if rx.search(t):

            out.append(n)

    _HIT_CACHE[key] = out

    return out


def content_words(s):

    return {w.lower() for w in re.findall(r"[A-Za-z]{4,}", s or "")}


# 되짚을 수 없는 문장은 근거로 쓰지 않는다. 물음표·따옴표·대시가 든


# 문장은 대조가 막힌다(오늘만 일곱 번). 그런 부호는 대개 참고문헌


# 제목에 있으므로, 거르면 제목도 함께 걸러진다


BAD_MARKS = '?"‘’“”–—*|'


_SENT_CACHE = {}


# **편수만 적힌 근거는 근거가 아니다.** "게재작 34편이 쓴다"는 그렇게


# 적힌 글자를 서른네 편이 담고 있다는 말일 뿐, 그 낱말이 우리와 같은 일을


# 한다는 말이 아니다. 편수는 맞는데 뜻이 다른 낱말이 오늘만 네 번 있었다.


# 그러니 문장을 못 찾았으면 **못 찾았다고 적는다.** 그래야 되짚기가 센다


NOQUOTE = ("  **인용할 문장을 못 찾았다. 편수만으로는 뜻이 같은지"

           " 알 수 없다. 사람이 확인할 것**")


CLEAN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 ,]+")


_FLAT_CACHE = {}


def flat_text(x):
    """대조용으로 다듬은 글. **적는 쪽과 되짚는 쪽이 같은 것을 쓴다.**

    굽은 아포스트로피, 별표, 세로줄 때문에 근거가 맞는데도 "그 논문에
    없다"로 걸린 적이 세 번 있다. 둘이 서로 다른 다듬기를 쓰면 또 갈린다.
    """
    x = norm_text(x, fold_accents=True)
    x = re.sub(r"[*|`_~]", "", x)
    return re.sub(r"\s+", " ", x).strip()


def _flat_doc(name, t):
    if name not in _FLAT_CACHE:
        _FLAT_CACHE[name] = flat_text(t)
    return _FLAT_CACHE[name]


def round_trips(name, t, cand):
    """되짚기와 **똑같은 방식으로** 그 문장이 그 논문에 있는지 본다.

    오늘 열한 번, 도구가 적은 인용을 되짚기가 "그 논문에 없다"로 걸렀고
    그때마다 사람이 손으로 고쳤다. 적는 쪽과 되짚는 쪽이 같은 글을 서로
    다르게 다듬었기 때문이다. **적기 전에 맞춰 보면 그 일이 없어진다.**
    """
    q = re.sub(r"^[^A-Za-z]+", "", flat_text(cand))[:40]
    return bool(q) and _flat_doc(name, t).find(q) >= 0


def _clean_quote(win, rx):

    """창에서 **되짚을 수 있는 토막** 하나를 고른다. 없으면 None.


    인용은 글자·숫자·쉼표·빈칸만으로 이루어진 구간에서만 고른다. PDF에서

    뽑은 글에는 수식 부스러기(`PrYi 14 1 14 ^pi`)와 하이픈·괄호가 섞여

    있는데, 그런 토막을 근거로 적으면 되짚기가 "그 논문에 없다"로 막힌다.

    **부호를 지워 맞추는 대신 부호가 없는 구간만 쓴다.**

    """

    win = norm_text(win, fold_accents=True)

    win = "".join(c if ord(c) < 128 else " " for c in win)

    best = None

    for m in CLEAN_RUN.finditer(win):

        run = m.group(0)

        if m.start() == 0:

            # 창이 낱말 한가운데서 시작했을 수 있다(grating <- integrating).

            # 토막이 창 첫머리면 앞 낱말을 버린다. 첫머리가 아니면 앞이

            # 부호이므로 이미 낱말 경계다

            sp = run.find(" ")

            run = run[sp + 1:] if sp > 0 else ""

        run = re.sub(r"\s+", " ", run).strip(" ,")

        if len(run) < 45 or not rx.search(run):

            continue

        toks = run.split()

        # 수식·표에서 뽑힌 부스러기는 숫자 토막이 몰려 있다

        if sum(1 for t in toks if t.strip(",").isdigit()) > len(toks) * 0.25:

            continue

        if re.search(r"Manual for|www\.|doi|pp\.|ISBN|Proceedings", run, re.I):

            continue

        if best is None or len(run) > len(best):

            best = run

    return best[:110] if best else None


def _candidates(docs, pat):

    """그 표현이 나온 문장 후보들. **패턴마다 한 번만 훑는다.**


    이 훑기가 가장 비싸다. 51편이면 한 번에 2MB가 넘는데, 행마다 다시

    훑으면 1,700행에서 몇 분이 걸린다.

    """

    if pat in _SENT_CACHE:

        return _SENT_CACHE[pat]

    rx = re.compile(r"[^.]{0,90}" + pat + r"[^.]{0,90}", re.I)

    inner = re.compile(pat, re.I)

    out = []

    for n, t, tl in docs:

        for m in list(rx.finditer(t))[:6]:

            cand = _clean_quote(m.group(0), inner)

            # **적기 전에 되짚어 본다.** 안 맞는 문장은 근거가 아니라 일거리다
            if cand and round_trips(n, t, cand):

                out.append((n, cand))

        if len(out) >= 40:

            break

    _SENT_CACHE[pat] = out

    return out


def sentence_in(docs, pat, like=None, w_low=""):

    """그 표현이 쓰인 게재작 문장 하나. **우리 문장과 가까운 것을 고른다.**


    첫 문장을 그냥 집으면 다른 뜻의 문장이 근거로 붙는다. 실제로


    `contributions`의 근거로 "연구의 학술적 기여"를 말하는 문장이 붙었는데


    우리 쓰임은 변수가 예측에 기여한 양이었다.


    """

    want = content_words(like)

    best = None

    for n, cand in _candidates(docs, pat):

        score = len((want & content_words(cand)) - {w_low}) if want else 0

        if best is None or score > best[0]:

            best = (score, n, cand)

        if best[0] >= 3:

            break

    if not best:

        return None, None

    mark = ""

    if want and best[0] < 2:

        mark = ("  ※ 우리 문장과 겹치는 말이 없다."

                " **같은 뜻인지 사람이 확인할 것**")

    return best[1], best[2] + mark


def corpus_prose(t):

    """게재작에서 참고문헌을 잘라 낸다.


    안 자르면 서지의 **저널 이름과 저자명**이 본문 어휘로 잡힌다. `bullet`이


    Psychological *Bulletin* 때문에 "게재작은 다른 꼴을 쓴다"로 판정된 적이


    있다. 여덟 편이 그 저널을 인용했을 뿐이었다.


    """

    cands = [m.start() for m in

             re.finditer("References|REFERENCES|Bibliography", t)

             if m.start() > len(t) * 0.5]

    return t[:cands[0]] if cands else t


def load_docs(txt_dir):

    """게재작을 읽는다. 참고문헌은 잘라 내고, 소문자본을 함께 들고 다닌다.


    소문자본은 **정규식으로 훑기 전에 값싼 문자열 검사로 거르기 위한 것**


    이다. 안 그러면 대장 한 행마다 51편 전체를 훑어, 1,700행에서 몇 GB를


    훑게 되고 검사가 몇 분씩 걸린다.


    """

    out = []

    for f in sorted(os.listdir(txt_dir)):

        if f.endswith(".txt"):

            raw = io.open(os.path.join(txt_dir, f), encoding="utf-8",

                          errors="replace").read()

            t = corpus_prose(raw)

            out.append((f[:-4], t, t.lower()))

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

    # 창을 넓게 잡는다. `five controls for site characteristics. A logistic

    # regression ...` 처럼 뜻을 가르는 말이 문장 밖에 있는 일이 잦다

    om = re.search(r"[^.]{0,150}(?<![A-Za-z])" + re.escape(w) +

                   r"(?![A-Za-z])[^.]{0,150}", prose, re.I)

    ours_sent = om.group(0) if om else None

    pct = 100.0 * cnt / max(1, n_docs)

    if pct >= 8:

        p, s = sentence_in(docs, r"(?<![A-Za-z])" + re.escape(w) +

                           r"(?![A-Za-z])", ours_sent, w.lower())

        return ("유지", "게재작 %d편(%.0f%%)이 쓴다. [%s] %s" % (cnt, pct, p, s)

                if p else ("게재작 %d편(%.0f%%)이 쓴다." % (cnt, pct)) + NOQUOTE)

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

            return ("유지", "그 꼴만 없고 어간 '%s'가 게재작 %d편에 있다.%s"

                    % (st, len(sp), (" [%s] %s" % (p, s)) if p else NOQUOTE))

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

                          " %d편.**%s → 문장 자리가 그 꼴을 요구하는지"

                          " 먼저 보고, 아니면 저자가 정한다"

                % (cnt, len(longer), (" [%s] %s" % (p, s)) if p else NOQUOTE))

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

    byname = {d[0]: d[1] for d in docs}

    bad, checked, short_key, mute = [], 0, 0, []

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
        # 인용이 없는 근거는 되짚을 것이 없어 그냥 통과한다. 세어서 낸다
        if "[" not in ev and not re.search(
                r"참고문헌에만|수식|LaTeX|캡션에만|조사표|표 안에만"
                r"|어간|조각|대상 아님|고유명|저자 성", ev):
            mute.append((n, w, int(cells[2]) if cells[2].isdigit() else 0))

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

            flat = flat_text

            q = re.sub(r"^[^A-Za-z]+", "", flat(quote))[:40]

            if q and flat(t).find(q) < 0:

                bad.append((n, w, "인용한 문장이 그 논문에 없다: %s…" % q))

        # 본문 편수를 함께 적은 근거는 **견주는 말**이지 참고문헌
        # 전용을 주장하는 것이 아니다. 그것까지 잡으면 없는 잘못을 만든다
        refs_only = (("참고문헌에만" in ev or "수식 안" in ev)
                     and not re.search(r"본문에는", ev))
        if refs_only and in_body_independent(md_raw, w):

            bad.append((n, w, "본문에 있는데 '%s'이라고 적혔다"

                        % ("참고문헌에만" if "참고문헌에만" in ev else "수식")))

    print("# 근거 되짚기 · %d-%d행" % (a, b))

    print("")

    print("- 근거가 적힌 행 **%d개** 중 어긋난 것 **%d개**" % (checked, len(bad)))
    if mute:
        mute.sort(key=lambda r: -r[2])
        print("- **인용 없이 편수만 적힌 행 %d개.** 되짚을 것이 없어"
              " 그냥 통과한다. 그 낱말이 우리와 같은 일을 하는지"
              " 알 수 없다. `--refresh`로 다시 적는다" % len(mute))
        for n, w, freq in mute[:8]:
            print("    - #%d %s (원고 %d회)" % (n, w, freq))

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


def diff(led, a, b, docs, parts):

    """도구가 바뀐 뒤, **새 판이 다르게 말하는 행만** 뽑는다.


    도구를 고칠 때마다 층을 처음부터 다시 판정하면 끝나지 않는다. 그렇다고


    그냥 두면 옛 판이 잘못 적은 것이 남는다. 그래서 **이미 적힌 판정과 새


    판정을 견줘 갈라지는 행만** 낸다. 그 행만 다시 보면 된다.


    사람이 손으로 고친 행은 새 판이 뭐라 하든 건드리지 않는다. 다만 갈라진


    사실은 알려 준다.


    """

    rows = rows_of(led)

    lines = {}

    for ln in io.open(led, encoding="utf-8"):

        m0 = re.match(r"\|\s*(\d+)\s*\|", ln)

        if m0:

            lines[int(m0.group(1))] = ln

    changed, checked, n_hand = [], 0, 0

    for n, w, freq, cnt, note in rows:

        if not (a <= n <= b) or n not in lines:

            continue

        cells = [c.strip() for c in lines[n].rstrip().strip("|").split("|")]

        if len(cells) < 8 or not cells[-1]:

            continue

        checked += 1

        old_v, old_e = cells[-2], cells[-1]

        new = judge(w, cnt, len(docs), docs, parts, note)

        if new is None:

            # 새 판이 갈래를 못 정하는 행이다. 사람이 판정한 행이 대개

            # 여기 든다. **다시 볼 일이 아니므로 세지 않는다**

            n_hand += 1

            continue

        if new[0] != old_v:

            changed.append((n, w, old_v, new[0], new[1][:60]))

    print("# 새 판과 견주기 · %d-%d행" % (a, b))

    print("")

    print("- 판정이 적힌 행 **%d개** 중 새 판이 다르게 말하는 것 **%d개**"

          % (checked, len(changed)))

    print("- 새 판이 갈래를 못 정하는 행 %d개는 세지 않았다"

          " (사람이 판정한 자리다)" % n_hand)

    if not changed:

        print("- 갈라지는 행이 없다. **다시 판정할 것이 없다**")

        return

    print("")

    print("| 행 | 낱말 | 적힌 판정 | 새 판정 | 새 근거 |")

    print("|--|--|--|--|--|")

    for n, w, o, nv, e in changed[:40]:

        print("| %d | %s | %s | **%s** | %s |" % (n, w, o, nv, e))

    print("")

    print("**이 행만 다시 본다.** 손으로 고친 행이면 그대로 두고, 옛 판이"

          " 잘못 적은 것이면 새 판으로 바꾼다.")


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

    if "--diff" in sys.argv:

        diff(led, a, b, docs, parts)

        return

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

    print("")

    print("- **기술 용어는 분모가 다르다.** 게재작 51편 중 그 방법을 쓰는"

          " 논문만 그 말을 쓴다. 회귀를 돌리는 논문이 24편이면 통제변수의"

          " 분모는 24이지 51이 아니다")

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

    # `--refresh`면 **근거가 부실한 행을 다시 적는다.** 인용이 없거나,
    # 적힌 인용이 그 논문에 되짚어지지 않는 행이다. ★가 붙은 행은
    # 사람이 판정한 자리이므로 건드리지 않는다
    refresh = "--refresh" in sys.argv
    byname = {d[0]: d[1] for d in docs}

    def weak(verd, ev):
        # 코퍼스에 문장이 있을 수 없는 갈래는 부실한 것이 아니다.
        # 참고문헌에만 나오는 말, 고유명, 조사표 항목, 수식 안의 기호가
        # 그렇다. **사람이 손으로 적어 둔 판정도 여기 든다**
        if re.search(r"참고문헌에만|본문에는|수식|LaTeX|캡션에만|조사표"
                     r"|표 안에만|어간|조각|대상 아님|고유명|저자 성", ev):
            return False
        if "★" in verd:
            return False
        m2 = re.search(r"\[([^\]]+)\]([^\[]*)", ev)
        if not m2:
            return True
        t2 = byname.get(m2.group(1))
        return t2 is None or not round_trips(m2.group(1), t2, m2.group(2))

    out, n_w, kept = [], 0, 0

    for ln in io.open(led, encoding="utf-8"):

        pat_row = (r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|(.*)"
                   r"\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$"
                   if refresh else
                   r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|(.*)\|\s*\|\s*\|\s*$")
        m = re.match(pat_row, ln.rstrip(chr(10)))
        if m and refresh and not weak(m.group(4), m.group(5)):
            kept += 1 if a <= int(m.group(1)) <= b else 0
            out.append(ln)
            continue

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
    if refresh:
        print("- `--refresh`: 근거가 튼튼한 행 %d개는 그대로 두었다."
              " ★가 붙은 행도 건드리지 않는다" % kept)


if __name__ == "__main__":

    main()
