# -*- coding: utf-8 -*-
"""문장 대장의 한 구간을 판정한다. **`15` §4의 절차를 그대로 돌린다.**

쓰임:

  python sent_judge.py 문장_대장.md 1 25 --md 원고.md --txt <코퍼스>

      그 구간을 판정해 보여 준다 (대장은 안 건드린다)

  python sent_judge.py 문장_대장.md 1 25 --md 원고.md --txt <코퍼스> --apply

      **비어 있는** 기능·근거만 적는다. 판정 칸과 사람이 적어
      둔 칸은 건드리지 않는다

  python sent_judge.py 문장_대장.md 1 25 --md 원고.md --txt <코퍼스> --verify

      이미 적힌 근거가 사실인지 되짚는다

왜 이 도구가 있나

  `15` §4는 절차를 글로 적어 두었는데 **그 절차를 돌리는 도구가 없었다.**
  그래서 검수하는 쪽이 임시 스크립트를 따로 만들었고, 기능 갈래를 §4-1의
  열 가지 대신 제 나름대로 여섯 개 지어 썼다. 근거도 같은 기능의 문장이
  아니라 **낱말이 겹치는 문장**을 붙였다. `coefficient`가 겹쳐서 표준화를
  말하는 우리 문장에 상관계수를 말하는 문장이 근거로 붙었다.

  **절차만 적어 두면 절차가 지켜지지 않는다.** 낱말 층은 도구와 되짚기와
  관문이 있어서 어긋나면 걸렸고, 문장 층은 셋 다 없어서 안 걸렸다.

무엇을 하나 (`15` §4-1 - §4-4)

  1 문장의 **기능**을 §4-1의 열 갈래 중 하나로 정한다. 못 정하면 비워 둔다
  2 **같은 기능**의 게재작 문장을 찾아 앞뒤 한 문장과 함께 붙인다
  3 문법·논리·흐름을 기계가 볼 수 있는 만큼만 본다
  4 기능을 못 정했거나 같은 기능의 선례를 못 찾은 행은 **판정을 안 적는다**

**기계는 후보만 낸다.** 몫마다 세 행을 지목하니 그 세 행은 눈으로 읽는다.
"""
import io
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _norm import norm_text                                    # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

# ── 기능 열 갈래. `15` §4-1의 표 그대로다. **여기에 없는 이름은 안 쓴다** ──
# 지어낸 갈래를 쓰면 게재작에서 같은 기능을 찾을 수가 없다. 실제로 "서술",
# "결과 수치" 같은 이름을 쓰다가 근거가 전부 어긋났다
FUNCS = [
    ("표·그림 지시", [
        r"^\**(Table|Fig(?:\.|ure)?)\s*\d",
        r"(?:Table|Fig(?:\.|ure)?)\s*\d[^.]{0,60}"
        r"(shows|reports|presents|summari[sz]es|lists|gives|holds|displays)",
        r"\b(shown|reported|presented|given)\s+in\s+"
        r"(Table|Fig(?:\.|ure)?)\s*\d",
    ]),
    ("한계", [
        r"\blimitations?\b",
        r"\bthis\s+study\s+(is\s+limited|cannot)",
        r"\b(we|the\s+study|the\s+data)\s+(could\s+not|cannot|"
        r"do(es)?\s+not\s+allow|was\s+not\s+able\s+to)\b",
        r"\bfuture\s+(research|work|studies)\s+(should|could|might)\b",
    ]),
    ("경계", [
        r"\bdo(es)?\s+not,\s+however\b",
        r"\b(cannot|should\s+not|must\s+not)\s+be\s+"
        r"(read|interpreted|taken|understood)\s+as\b",
        r"\bno\s+caus(al|ation)\b|\bcausal(ity)?\s+cannot\b",
        r"\b(these|those)\s+(figures|results|estimates|findings)\s+do\s+not\b",
        r"\bis\s+not\s+established\b|\bno\s+\w+\s+is\s+established\b",
        r"\bdescribe\s+associations?\b|\bnot\s+causal\b",
    ]),
    ("갭 진술", [
        r"\b(harder|hard)\s+to\s+find\b",
        r"\b(less|little)\s+is\s+known\b",
        r"\bfew\s+studies\b|\bhas\s+(not|rarely|seldom)\s+been\s+"
        r"(examined|studied|tested|addressed)",
        r"\bremains?\s+(unclear|unexamined|open|unanswered)\b",
        r"\bno\s+study\s+(has|to\s+our\s+knowledge)\b",
        r"\bgaps?\s+in\s+the\s+literature\b",
    ]),
    ("선택 정당화", [
        r"\b(we|this\s+study)\s+(use[sd]?|chose|adopt(ed)?|select(ed)?|"
        r"follow(ed)?|treat(ed)?)\b[^.]{0,90}"
        r"\b(because|since|as\s+it\s+is|in\s+order\s+to|so\s+that|"
        r"to\s+avoid|following)\b",
        r"\b(was|were)\s+(chosen|selected|preferred|adopted|used)\b"
        r"[^.]{0,70}\b(because|since|as|so\s+that|to\s+avoid|in\s+order)\b",
        r"\bfor\s+(this|that)\s+reason\b",
    ]),
    ("절차 서술", [
        r"\bwe\s+(constructed|computed|estimated|fitted|coded|scored|"
        r"assembled|removed|merged|split|trained|entered|tested|measured|"
        r"compared|drew|report|examine|model(ed)?)\b",
        r"\b(was|were)\s+(fitted|estimated|computed|coded|constructed|"
        r"removed|trained|standardi[sz]ed|imputed|entered|tested|measured|"
        r"compared|obtained|drawn|modeled|modelled|recoded|excluded|"
        r"interpreted|weighted|sampled)\b",
        r"\bthe\s+(data|sample|survey|models?|analysis)\s+"
        r"(are|is|was|were|draws?|comes?)\b",
    ]),
    ("결과 보고", [
        r"\b(the\s+)?results?\s+(indicate|show|suggest|report|reveal)\b",
        r"\bwe\s+(find|found|observe[d]?)\b",
        r"\b(odds\s+ratio|AUC|p\s*[<=]\s*0?\.\d|95%\s*CI|F1|recall|"
        r"precision)\b",
        r"\b(was|were)\s+(significant|not\s+significant|higher|lower)\b",
        r"\bnone\s+survived\b|\bdid\s+not\s+differ\b",
        r"\bin\s+the\s+\w+\s+ranking\b|\bthe\s+best\s+performing\b",
    ]),
    ("해석", [
        r"\b(is|are)\s+consistent\s+with\b",
        r"\bthis\s+(result|finding|pattern|difference)\b",
        r"\b(suggests?|implies|indicates?|means)\s+that\b",
        r"\b(can|may|might)\s+be\s+read\s+as\b",
        r"\bin\s+line\s+with\b|\bin\s+keeping\s+with\b",
    ]),
    ("선행 관행 규정", [
        r"\b(prior|previous|earlier|most)\s+(studies|work|research)\b",
        r"\b(studies|research|the\s+literature)\s+(has|have)\s+"
        r"(often|typically|generally|largely|mostly)\b",
        r"\bwhile\s+(prior|previous|most)\s+(studies|work)\b",
        # 인용된 저자가 주어인 문장. 선행연구를 정리하는 자리다
        r"^[A-Z][A-Za-z'-]+(\s+(?:et\s+al\.|and|&)\s*[A-Za-z'-]*)?\s*"
        r"\(\d{4}[a-z]?\)\s+[a-z]",
        r"\b(review|reviewed|examined|compared|followed|report)\b[^.]{0,60}"
        r"\(\d{4}[a-z]?\)",
    ]),
    ("현상 제시", [
        r"^[A-Z][^.]{0,80}\b(has|have)\s+"
        r"(grown|increased|risen|declined|expanded|fallen)\b",
        r"\b(remains?|continues?\s+to)\s+(be\s+)?(a|one\s+of|high|the)\b",
        r"^[A-Z][^.]{0,60}\b(is|are)\s+(one\s+of\s+the|among\s+the)\b",
        r"\b(accident|injury|fatality)\s+(rate|rates)\b[^.]{0,60}"
        r"\b(high|higher|rose|rising)\b",
    ]),
]
FUNC_NAMES = [f[0] for f in FUNCS]
CITE = re.compile(r"\([A-Z][A-Za-z'’-]+(?:\s+(?:et\s+al\.|and|&)[^)]{0,40})?,"
                  r"\s*\d{4}[a-z]?\)|\b[A-Z][A-Za-z'’-]+\s+et\s+al\.\s*\(\d{4}\)")

# 문장을 끊을 때 마침표가 문장 끝이 아닌 자리. 이걸 안 지키면 `et al.`에서
# 문장이 잘려 "괄호가 안 닫혔다"가 무더기로 나온다 (실제로 났다)
ABBR = (r"(?<!et al)(?<!e\.g)(?<!i\.e)(?<!cf)(?<!vs)(?<!Fig)"
        r"(?<!Tab)(?<!No)(?<!approx)(?<!Dr)(?<!St)(?<![A-Z])")
SENT_END = re.compile(ABBR + r"[.!?](?=\s+[\"'(“]?[A-Z0-9])")

BAD_MARKS = '?"‘’“”–—*|'
CLEAN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 ,]+")
_FLAT = {}


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def flat_text(x):
    """대조용으로 다듬은 글. **적는 쪽과 되짚는 쪽이 같은 것을 쓴다.**"""
    x = norm_text(x, fold_accents=True)
    x = re.sub(r"[*|`_~]", "", x)
    return re.sub(r"\s+", " ", x).strip()


def flat_doc(name, t):
    if name not in _FLAT:
        _FLAT[name] = flat_text(t)
    return _FLAT[name]


def round_trips(name, t, quote):
    """되짚기와 **똑같은 방식으로** 그 문장이 그 논문에 있는지 본다."""
    q = re.sub(r"^[^A-Za-z]+", "", flat_text(quote))[:40]
    return bool(q) and flat_doc(name, t).find(q) >= 0


def split_sents(t):
    t = re.sub(r"\s+", " ", t)
    out, last = [], 0
    for m in SENT_END.finditer(t):
        s = t[last:m.end()].strip()
        if s:
            out.append(s)
        last = m.end()
    tail = t[last:].strip()
    if tail:
        out.append(tail)
    return out


def corpus_prose(t):
    cands = [m.start() for m in
             re.finditer("References|REFERENCES|Bibliography", t)
             if m.start() > len(t) * 0.5]
    return re.sub(r"\s+", " ", t[:cands[0]] if cands else t)


def load_docs(txt_dir):
    docs = []
    for f in sorted(glob.glob(os.path.join(txt_dir, "*.txt"))):
        raw = io.open(f, encoding="utf-8", errors="replace").read()
        docs.append((os.path.basename(f)[:-4],
                     corpus_prose(norm_text(raw))))
    return docs


def function_of(s):
    """§4-1의 열 갈래 중 하나. **못 정하면 None을 낸다.**

    억지로 하나 붙이면 그 기능의 게재작 문장이 근거로 붙는데, 기능이 틀렸
    으므로 근거도 틀린다. **모른다고 말하는 편이 낫다.**
    """
    hit = []
    for name, pats in FUNCS:
        for p in pats:
            if re.search(p, s, re.I):
                hit.append(name)
                break
    if len(hit) == 1:
        return hit[0]
    if len(hit) > 1:
        # 여럿이 걸리면 앞의 것이 좁은 갈래다. 표·그림 지시와 한계는
        # 다른 것과 겹쳐도 그것이 그 문장의 일이다
        for name in ("표·그림 지시", "한계", "경계", "갭 진술"):
            if name in hit:
                return name
        return hit[0]
    return None


def clean_quote(s):
    """되짚을 수 있는 토막 하나. 부호가 없는 구간에서만 고른다."""
    s = norm_text(s, fold_accents=True)
    for ch in BAD_MARKS:
        s = s.replace(ch, " ")
    s = "".join(c if ord(c) < 128 else " " for c in s)
    best = None
    for m in CLEAN_RUN.finditer(s):
        run = m.group(0)
        if m.start() == 0:
            sp = run.find(" ")
            run = run[sp + 1:] if sp > 0 else ""
        run = re.sub(r"\s+", " ", run).strip(" ,")
        if len(run) < 45:
            continue
        toks = run.split()
        if sum(1 for x in toks if x.strip(",").isdigit()) > len(toks) * 0.25:
            continue
        if best is None or len(run) > len(best):
            best = run
    return best[:120] if best else None


STOP = set("""the a an of to in on at and or for with by is are was were be
been it its this that these those not no than then so such can could may will
would have has had do does did which who what when where while also more most
each every both all any some one two three four five our we us their""".split())


def content(s):
    return {w for w in re.findall(r"[a-z]{4,}", (s or "").lower())
            if w not in STOP}


def build_corpus_index(docs):
    """게재작 문장을 **기능별로** 갈라 둔다. 근거는 같은 갈래에서만 고른다.

    낱말이 겹치는 문장을 근거로 붙이면 자리도 기능도 다른 문장이 붙는다.
    `threshold`가 겹쳐서 SHAP 값을 순위로 읽는다는 우리 문장에 임계값
    신뢰도를 말하는 문장이 붙은 적이 있다.
    """
    idx = dict((n, []) for n in FUNC_NAMES)
    lens = []
    for name, t in docs:
        ss = split_sents(t)
        for i, s in enumerate(ss):
            w = len(s.split())
            if 4 <= w <= 90:
                lens.append(w)
            if not (6 <= w <= 70):
                continue
            fn = function_of(s)
            if not fn:
                continue
            q = clean_quote(s)
            if not q or not round_trips(name, t, q):
                continue
            before = ss[i - 1] if i else ""
            after = ss[i + 1] if i + 1 < len(ss) else ""
            idx[fn].append((name, t, q, content(s), before, after))
    lens.sort()
    return idx, lens


def pick_evidence(idx, fn, ours):
    """같은 기능의 게재작 문장 하나. 앞뒤 한 문장을 함께 붙인다(§4-2)."""
    want = content(ours)
    best = None
    for name, t, q, cw, before, after in idx.get(fn, []):
        score = len(want & cw)
        if best is None or score > best[0]:
            best = (score, name, q, before, after)
        if best[0] >= 4:
            break
    if not best:
        return None
    score, name, q, before, after = best
    ctx = ""
    if before or after:
        ctx = (" (앞: %s / 뒤: %s)"
               % (re.sub(r"\s+", " ", before)[:50] or "없음",
                  re.sub(r"\s+", " ", after)[:50] or "없음"))
    tail = (" 겹치는 말 %d개" % score if score
            else " ※ 우리 문장과 겹치는 말이 없다. 같은 자리인지"
                 " 사람이 확인할 것")
    return "[%s] %s%s -%s" % (name, q, ctx, tail)


LINKS = ("however|moreover|furthermore|therefore|thus|in addition|"
         "consequently|nevertheless|accordingly")


def checks(s, prev, cut99, sec_no):
    """기계가 볼 수 있는 만큼만 본다. **못 보는 것은 안 본다고 말한다.**"""
    gram, logic, flow = [], [], []
    if s.count("(") != s.count(")"):
        gram.append("괄호 안 닫힘")
    m = re.search(r"\b(\w{5,})\b[^.]{0,25}\b\1\b", s, re.I)
    if m:
        gram.append("같은 말 겹침(%s)" % m.group(1))
    if len(re.findall(r"\b(?:%s)\b" % LINKS, s, re.I)) >= 2:
        gram.append("이음말 둘 이상")
    w = len(s.split())
    if w > cut99:
        flow.append("긴 문장 %d낱말" % w)
    if prev:
        a = re.findall(r"[A-Za-z]{4,}", prev)
        b = re.findall(r"[A-Za-z]{4,}", s)
        if a and b and a[-1].lower() == b[0].lower():
            flow.append("앞 문장 끝말로 시작")
    # 숫자에 출처가 없다. **우리 자료를 말하는 절은 뺀다.** 방법·결과 절의
    # 숫자는 우리가 잰 것이라 인용이 없는 것이 정상이다
    own = re.match(r"\s*[34]\b|\s*(Materials|Methods|Results|Abstract)",
                   sec_no or "")
    if (re.search(r"\b\d[\d,.]*\b", s) and not CITE.search(s) and not own
            and not re.search(r"\b(p|AUC|CI|SD|n)\s*[<=]", s)):
        logic.append("숫자가 있는데 출처도 통계도 없다")
    return (" / ".join(gram) or "이상 없음",
            " / ".join(logic) or "이상 없음",
            " / ".join(flow) or "이상 없음")


def rows_of(path):
    rows = []
    for ln in io.open(path, encoding="utf-8"):
        cells = [c.strip() for c in ln.rstrip().strip("|").split("|")]
        if len(cells) < 9 or cells[0].startswith("-") or cells[0] == "번호":
            continue
        rows.append(cells)
    return rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        print(__doc__)
        return
    led, a, b = args[0], int(args[1]), int(args[2])
    md_path = opt("--md")
    txt_dir = opt("--txt", "literature/_txt")
    if not md_path or not os.path.exists(md_path):
        print("`--md 원고.md`가 필요하다.")
        return
    docs = load_docs(txt_dir)
    if not docs:
        print("코퍼스가 없다: %s" % txt_dir)
        return

    rows = rows_of(led)
    if not rows:
        print("대장에 행이 없다: %s" % led)
        return

    if "--verify" in sys.argv:
        verify(rows, a, b, docs)
        return

    idx, lens = build_corpus_index(docs)
    cut99 = lens[int(len(lens) * .99)] if lens else 60
    print("# 문장 판정 · %d-%d행" % (a, b))
    print("")
    print("- 게재작 문장 %s개 · 99%% 지점 **%d낱말**"
          % ("{:,}".format(len(lens)), cut99))
    print("- 기능별 선례: %s"
          % ", ".join("%s %d" % (n, len(idx[n])) for n in FUNC_NAMES
                      if idx[n]))
    print("")

    # **대장의 문장 칸은 잘려 있다.** 그 토막으로 기능을 정하고 길이를 재면
    # 둘 다 틀린다. 잘린 토막을 열쇠로 원고에서 문장 전체를 찾아 쓴다
    md_body = re.sub(r"\s+", " ",
                     io.open(md_path, encoding="utf-8",
                             errors="replace").read())

    def whole(frag):
        key = re.sub(r"\s+", " ", frag).strip()
        if len(key) < 20:
            return key
        p = md_body.find(key)
        if p < 0:
            return key
        m = SENT_END.search(md_body, p)
        return md_body[p:m.end()].strip() if m else key

    got, left, read = {}, [], []
    prev = ""
    for i, c in enumerate(rows, 1):
        if not (a <= i <= b):
            prev = whole(c[2])
            continue
        no, sec, s = c[0], c[1], whole(c[2])
        fn = function_of(s)
        ev = pick_evidence(idx, fn, s) if fn else None
        gram, logic, flow = checks(s, prev, cut99, no)
        prev = s
        if not fn:
            left.append((i, no, s, "기능을 못 정했다"))
            continue
        if not ev:
            left.append((i, no, s, "같은 기능(%s)의 선례를 못 찾았다" % fn))
            continue
        bad = [x for x in (gram, logic, flow) if x != "이상 없음"]
        # **판정은 안 적는다.** 기계가 채울 수 있는 것은 기능 후보와 같은
        # 기능의 선례와 기계 검사뿐이다. `15` §4-3이 요구하는 여섯 항목 중
        # 논리("주장 강도가 근거 크기와 맞는가")와 기능("이 문장이 문단
        # 메시지에 복무하는가")은 사람이 읽어야 답이 나온다. 기계가 "유지"를
        # 적어 버리면 그 두 항목이 안 본 채로 닫힌다
        got[i] = (fn, ev, gram, logic, flow, "")
        read.append((i, no, s, fn, ev, " / ".join(bad) or "기계 검사 이상 없음"))

    print("## 이 몫의 %d행. **한 행씩 읽고 판정한다**" % len(read))
    print("")
    print("- 판정은 `15` §4-4의 넷 중 하나다:"
          " **유지 / 대체 / 유보 / 기록**")
    print("- **조금이라도 논란이 될 만하면 `기록`이다.** 이 층에서 정하지"
          " 않고 위층으로 넘긴다. 문장에서 걸린 것이 문단에서 풀리고,"
          " 문단에서 걸린 것이 전체를 보고 나서야 풀린다."
          " `carry_up.py`가 모아 온다")
    print("- 보는 것은 §4-3의 여섯 항목이다. 그중 **논리와 기능은 기계가"
          " 못 본다.** 아래 근거를 앞뒤와 함께 읽고 사람이 적는다")
    print("")
    for i, no, s, fn, ev, note in read:
        print("### [%d행 %s] 기능: %s" % (i, no, fn))
        print("")
        print("- 우리: %s" % re.sub(r"\s+", " ", s)[:240])
        print("- 게재작 같은 기능: %s" % ev[:260])
        print("- 기계 검사: %s" % note)
        print("")

    if left:
        print("## 기계가 못 정한 행 %d개. **판정을 안 적었다**" % len(left))
        print("")
        print("- 사람이 §4-1의 열 갈래 중 하나로 기능을 정하고, 그 기능의"
              " 게재작 문장을 `find_usage.py`로 찾아 적는다")
        for i, no, s, why in left[:10]:
            print("    - [%d행 %s] %s" % (i, no, why))
            print("      %s" % re.sub(r"\s+", " ", s)[:120])
        print("")

    # **기계는 사실만 본다. 자리가 같은지는 사람이 읽어야 안다.**
    # 그래서 몫마다 세 행을 지목한다. 가장 긴 문장, 절의 첫 문장, 구간 끝
    inrange = [(i, c) for i, c in enumerate(rows, 1) if a <= i <= b]
    if inrange:
        picks, seen = [], set()
        longest = max(inrange, key=lambda x: len(x[1][2].split()))
        first = next((x for x in inrange if x[1][0].endswith("-P1-S1")),
                     inrange[0])
        for x in (longest, first, inrange[-1]):
            if x[0] not in seen:
                seen.add(x[0])
                picks.append(x)
            if len(picks) >= 3:
                break
        print("## 자리는 기계가 못 본다. 아래 %d행은 눈으로 본다" % len(picks))
        for i, c in picks:
            print("    - [%d행 %s] 게재작의 **같은 자리**가 이 기능을 어떻게"
                  " 쓰는지 앞뒤와 함께 읽는다" % (i, c[0]))
        print("")

    if "--apply" not in sys.argv:
        print("**대장에 적으려면 `--apply`.** 못 정한 행은 비워 둔다.")
        return

    out, n_w, left_alone = [], 0, 0
    seen_row = 0
    for ln in io.open(led, encoding="utf-8"):
        cells = [c.strip() for c in ln.rstrip().strip("|").split("|")]
        if len(cells) < 9 or cells[0].startswith("-") or cells[0] == "번호":
            out.append(ln)
            continue
        seen_row += 1
        if seen_row in got:
            fn, ev, gram, logic, flow, verd = got[seen_row]
            # **사람이 적어 둔 칸을 기계가 덮지 않는다.**
            # 이 자리에서 사고가 났다. 빈 판정을 그대로 써 넣는 바람에 이미
            # 적혀 있던 판정 82행이 지워졌고 그중 ★가 셋이었다. 백업이
            # 없었으면 되돌릴 수 없었다.
            # 기계가 채우는 것은 **비어 있는 칸뿐이다.**
            def keep(old, new):
                return old if old and old != "-" else new
            row = [cells[0], cells[1], cells[2],
                   keep(cells[3], fn), keep(cells[4], ev),
                   keep(cells[5], gram), keep(cells[6], logic),
                   keep(cells[7], flow), cells[8]]
            if row == cells:
                left_alone += 1
            else:
                n_w += 1
            out.append("| %s |\n" % " | ".join(row))
        else:
            out.append(ln)
    io.open(led, "w", encoding="utf-8", newline="\n").write("".join(out))
    print("대장 %d행에 **비어 있던 기능·근거만** 적었다. 못 정한 %d행은"
          " 그것도 비어 있다." % (n_w, len(left)))
    if left_alone:
        print("- 이미 채워져 있어 **그대로 둔 행 %d개.** 사람이 적어 둔 칸은"
              " 기계가 안 덮는다" % left_alone)
    print("")
    print("**판정 칸은 비워 두었다.** 위의 행을 한 행씩 읽고 유지·대체·유보를"
          " 사람이 적는다. 관문은 판정 칸이 다 차기 전에는 이 단계를 안 닫는다.")
    # **대화창에 적은 판정은 판정이 아니다.** 대장에 안 적고 답변에만 적어
    # 넘어간 적이 있다. 그래서 매 몫 끝에 대장의 남은 행을 세어 보여 준다
    done = sum(1 for c in rows if len(c) > 8 and c[8])
    print("")
    print("- 대장 %d행 중 **판정이 적힌 행 %d개, 남은 행 %d개**"
          % (len(rows), done, len(rows) - done))
    print("- 판정은 **대장에 적어야 적은 것이다.** 답변에만 적고 넘어가면"
          " 그 행은 안 한 행이다")


def verify(rows, a, b, docs):
    """적힌 근거가 사실인지, 기능이 열 갈래 안인지 되짚는다."""
    byname = dict((d[0], d[1]) for d in docs)
    bad, checked, mute, wrong_fn = [], 0, [], []
    for i, c in enumerate(rows, 1):
        if not (a <= i <= b) or not c[8]:
            continue
        checked += 1
        fn, ev = c[3], c[4]
        if fn and fn not in FUNC_NAMES:
            wrong_fn.append((i, c[0], fn))
        if "[" not in ev:
            mute.append((i, c[0]))
            continue
        m = re.search(r"\[([^\]]+)\]([^\[(]*)", ev)
        if not m:
            continue
        t = byname.get(m.group(1))
        if t is None:
            bad.append((i, c[0], "근거가 댄 논문이 코퍼스에 없다: %s"
                        % m.group(1)))
        elif not round_trips(m.group(1), t, m.group(2)):
            bad.append((i, c[0], "인용한 문장이 그 논문에 없다"))
    print("# 문장 근거 되짚기 · %d-%d행" % (a, b))
    print("")
    print("- 판정이 적힌 행 **%d개** 중 어긋난 것 **%d개**" % (checked, len(bad)))
    for i, no, why in bad[:20]:
        print("    - [%d행 %s] %s" % (i, no, why))
    if wrong_fn:
        print("- **기능이 §4-1의 열 갈래 밖인 행 %d개.** 지어낸 갈래를 쓰면"
              " 같은 기능의 선례를 찾을 수 없다" % len(wrong_fn))
        for i, no, fn in wrong_fn[:8]:
            print("    - [%d행 %s] %s" % (i, no, fn))
    if mute:
        print("- **근거가 없는데 판정이 적힌 행 %d개.** 되짚을 것이 없어"
              " 그냥 통과한다" % len(mute))
        for i, no in mute[:8]:
            print("    - [%d행 %s]" % (i, no))
    if not bad and not wrong_fn and not mute and checked:
        print("- 전부 확인됐다")
    if not checked:
        print("- 그 구간에 아직 판정이 적힌 행이 없다")


if __name__ == "__main__":
    main()
