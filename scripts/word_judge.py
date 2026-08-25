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
  ★ 다른 꼴   게재작은 같은 말의 **다른 꼴**을 쓴다 (overfit / overfitting)
  유지        조사표 항목 코드(Q14) 옆이거나 표 안에만 있다 (원자료 표기)
  손으로 볼 것 위 어디에도 안 걸리는 것

**★ 다른 꼴은 지적이 아니라 후보다.** 바꿀지는 저자가 정한다.
"""
import io
import os
import re
import sys

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


def papers_with(docs, pat):
    rx = re.compile(pat, re.I)
    return [n for n, t in docs if rx.search(t)]


def sentence_in(docs, pat):
    rx = re.compile(r"[^.\n]{0,60}" + pat + r"[^.\n]{0,60}", re.I)
    for n, t in docs:
        m = rx.search(t)
        if m:
            return n, re.sub(r"\s+", " ", m.group(0)).strip()[:110]
    return None, None


def load_docs(txt_dir):
    out = []
    for f in sorted(os.listdir(txt_dir)):
        if f.endswith(".txt"):
            out.append((f[:-4], io.open(os.path.join(txt_dir, f),
                                        encoding="utf-8",
                                        errors="replace").read()))
    return out


def split_manuscript(md):
    """본문 산문 / 표 / 캡션 / 수식 / 참고문헌으로 가른다."""
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
    if near and re.search(r"(?<![A-Za-z])[A-Z]{1,3}\d{1,3}(?![A-Za-z0-9])",
                          near.group(0)):
        return ("유지", "조사표 항목 코드 옆에서 원자료를 가리킨다: %s"
                % re.sub(r"\s+", " ", near.group(0)).strip()[:90])
    if not has(prose, w) and has(tables, w):
        return ("유지", "본문이 아니라 표 안에만 있다. 표의 항목 이름이라"
                      " 원자료·조사표 표기를 따른다")
    pct = 100.0 * cnt / max(1, n_docs)
    if pct >= 8:
        p, s = sentence_in(docs, r"(?<![A-Za-z])" + re.escape(w) +
                           r"(?![A-Za-z])")
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
    # 낱말을 앞머리로 하는 다른 꼴을 게재작이 쓰는가 (overfit -> overfitting)
    longer = papers_with(docs, r"(?<![A-Za-z])" + re.escape(w.lower()) +
                         r"[a-z]{1,6}(?![A-Za-z])")
    if 100.0 * len(longer) / max(1, n_docs) >= 8:
        p, s = sentence_in(docs, r"(?<![A-Za-z])" + re.escape(w.lower()) +
                           r"[a-z]{1,6}(?![A-Za-z])")
        return ("★ 다른 꼴", "이 꼴은 게재작 %d편, 그러나 **같은 말의 다른 꼴을"
                          " %d편이 쓴다.** [%s] %s → 저자가 정한다"
                % (cnt, len(longer), p, s))
    return None


def verify(led, a, b, docs, parts):
    """이미 적힌 근거가 사실인지 되짚는다.

    대장의 근거는 기계가 쓴 것이다. 아무도 되짚지 않으면 그대로 굳는다.
    세 가지를 본다.

      1 근거가 이름 댄 논문에 그 낱말이 실제로 있는가
      2 인용한 문장이 그 논문에 실제로 있는가
      3 "참고문헌에만 있다"고 적힌 낱말이 정말 본문에 없는가

    **한 줄이라도 안 맞으면 그 배치의 판정을 다시 본다.**
    """
    prose, tables, caps, math, refs = parts
    byname = dict(docs)
    rows, bad, checked = rows_of(led), [], 0
    for n, w, freq, cnt, note in rows:
        if not (a <= n <= b):
            continue
        line = None
        for ln in io.open(led, encoding="utf-8"):
            if re.match(r"\|\s*%d\s*\|" % n, ln):
                line = ln
                break
        if not line:
            continue
        cells = [c.strip() for c in line.rstrip().strip("|").split("|")]
        if len(cells) < 8 or not cells[-1]:
            continue
        ev = cells[-1]
        checked += 1
        m = re.search(r"\[([^\]]+)\]\s*(.*)$", ev)
        if m:
            name, quote = m.group(1), m.group(2).strip()
            t = byname.get(name)
            if t is None:
                bad.append((n, w, "근거가 댄 논문이 코퍼스에 없다: %s" % name))
                continue
            head = re.sub(r"\s+", " ", quote)[:40]
            if head and re.sub(r"\s+", " ", t).find(head) < 0:
                bad.append((n, w, "인용한 문장이 그 논문에 없다: %s…" % head))
        if "참고문헌에만" in ev and (has(prose, w) or has(tables, w)):
            bad.append((n, w, "본문에도 있는데 참고문헌에만 있다고 적혔다"))
        if "수식 안" in ev and (has(prose, w) or has(tables, w)):
            bad.append((n, w, "본문에도 있는데 수식이라고 적혔다"))
    print("# 근거 되짚기 · %d-%d행" % (a, b))
    print("")
    print("- 근거가 적힌 행 **%d개** 중 어긋난 것 **%d개**" % (checked, len(bad)))
    for n, w, why in bad[:20]:
        print("    - #%d %s: %s" % (n, w, why))
    if not bad and checked:
        print("- 전부 확인됐다. 근거가 댄 논문에 그 낱말과 문장이 실제로 있다")
    if not checked:
        print("- 그 구간에 아직 근거가 적힌 행이 없다")


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
        verify(led, a, b, docs, parts)
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
