# -*- coding: utf-8 -*-
"""게재작들이 어느 저널을 몇 퍼센트씩 인용하는지 센다.

쓰임:
  python cite_sources.py --txt literature/_txt --journal TFSC
  python cite_sources.py --txt literature/_txt --journal TFSC --top 30
  python cite_sources.py --txt literature/_txt --journal TFSC --out outputs/인용출처.md
  python cite_sources.py --txt literature/_txt --self "저널 이름"   # 자기 저널 인용 비율
  python cite_sources.py --txt literature/_txt --journal TFSC --ours 원고.md
      우리 참고문헌의 저널 분포를 게재작 분포와 나란히 놓고,
      **모자란 저널(더 받아 올 것)** 과 **과한 저널**을 낸다.

무엇을 보나
  목표 저널에 실린 논문들의 참고문헌에서 **저널 이름**을 뽑아 분포를 낸다.
  - 그 저널이 자기 저널을 몇 % 인용하는가
  - **한 편이 각 저널을 몇 %씩 인용하는가**(편별 중앙값·사분위. 우리 원고가 맞출 대역은 이쪽이다)
  - 어느 저널을 주로 인용하는가 (상위 목록)
  - 우리 원고의 인용 분포와 견줄 기준이 된다

읽는 법
  참고문헌은 형식이 제각각이라 **완전히 뽑히지 않는다.** 뽑힌 것의 분포를
  보는 것이지 절대 개수를 믿는 것이 아니다. 상위 저널 이름과 대략의 비율만
  쓴다. 이상한 항목이 섞이면 눈으로 걸러 낸다.
"""
import io
import os
import re
import sys
import glob
import statistics
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REF_HEAD = re.compile(r"^\s*#{0,4}\s*\**(References|REFERENCES|Bibliography|참고문헌)\**\s*$",
                      re.M)
# "... . Journal Name, 45(2), 123-145." 또는 "... . Journal Name 45, 123."
JOURNAL = re.compile(
    r"\.\s*([A-Z][A-Za-z&\-\'\s\.]{4,70}?)[,\s]+\d{1,4}\s*[\(,:]")
STOP_WORDS = re.compile(
    r"^(In|Proceedings|Proc|Paper|Working|Technical|Doctoral|PhD|Master|"
    r"Retrieved|Available|Accessed|Vol|No|pp|Springer|Elsevier|Wiley|Routledge|"
    r"Cambridge|Oxford|MIT|University|Press)\b", re.I)


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def normalize(j):
    j = re.sub(r"\s+", " ", j).strip(" .,&-")
    j = re.sub(r"^(and|the)\s+", "", j, flags=re.I)
    # 흔한 약어를 펴서 같은 저널로 묶는다
    for a, b in (("Technol Forecast Soc Change",
                  "Technological Forecasting and Social Change"),
                 ("Res Policy", "Research Policy"),
                 ("Technovation", "Technovation"),
                 ("J. ", "Journal of "), ("Int. ", "International ")):
        if j.startswith(a):
            j = j.replace(a, b, 1)
    return j


# 같은 저널의 약어 변형을 하나로 묶는다 (Technol. Forecast. Soc. Chang.
# / Technological Forecasting & Social Change 가 같은 것으로 세지도록)
LABEL = defaultdict(set)


def key_of(j):
    words = [w for w in re.split(r"[^A-Za-z]+", j.lower())
             if w and w not in ("and", "the", "of", "for", "in", "on")]
    return "|".join(w[:3] for w in words)


# 참고문헌 항목처럼 보이는 연도. 두 꼴을 다 센다.
#   Zhao, X. (2026). ...        괄호형
#   Ilkay, M.S., Aslan, E., 2012. ...   괄호 없는 꼴 (Elsevier 계열에 흔하다)
REF_YEAR = re.compile(r"\((?:19|20)[0-9][0-9][a-z]?\)"
                      r"|,\s*(?:19|20)[0-9][0-9][a-z]?\.")


def refs_of(text):
    """참고문헌 덩어리를 돌려준다.

    **줄 단위로만 찾으면 안 된다.** PDF에서 뽑은 글은 줄바꿈이 없거나
    머리글이 줄 안에 묻혀 있다. 실제로 51편 중 11편만 잡혀 분포가 5분의 1로
    만들어질 뻔했다.

    머리글 줄이 없으면 글의 40%를 지난 뒤의 "References"를 후보로 두고,
    **그 뒤가 실제로 서지 목록인지**(연도가 열다섯 개 이상 나오는지) 보고
    고른다. 본문에서 "references to the standard"처럼 쓰인 자리를 참고문헌
    시작으로 삼지 않기 위해서다.
    """
    m = list(REF_HEAD.finditer(text))
    if m:
        return text[m[-1].end():]
    best = None
    for m2 in re.finditer("References|REFERENCES|Bibliography|참고문헌", text):
        if m2.start() < len(text) * 0.4:
            continue
        tail = text[m2.end():m2.end() + 12000]
        if len(REF_YEAR.findall(tail)) >= 15:
            best = m2          # 마지막으로 조건을 만족한 자리
    return text[best.end():] if best else ""


def journals_of(body):
    """참고문헌 덩어리에서 저널 이름을 뽑아 센다."""
    c = Counter()
    for m in JOURNAL.finditer(body):
        j = normalize(m.group(1))
        if len(j) < 5 or STOP_WORDS.match(j) or len(j.split()) > 9:
            continue
        c[key_of(j)] += 1
        LABEL[key_of(j)].add(j)
    return c


def per_paper_stats(per_paper, keys):
    """저널마다 편별 점유율의 중앙값·사분위를 낸다."""
    out = {}
    for k in keys:
        shares = []
        for _, c in per_paper:
            tot = sum(c.values())
            shares.append(100.0 * c.get(k, 0) / tot if tot else 0.0)
        shares.sort()
        if len(shares) >= 4:
            q = statistics.quantiles(shares, n=4)
            q1, q3 = q[0], q[2]
        else:
            q1, q3 = shares[0], shares[-1]
        out[k] = (statistics.median(shares), q1, q3,
                  sum(1 for x in shares if x > 0), len(shares))
    return out


def per_paper_report(per_paper, total, top, mine=None, n_mine=0):
    """한 편이 각 저널을 몇 %씩 인용하는지 (편별 분포).

    전체를 한 통에 넣고 세면 참고문헌이 많은 한두 편이 값을 끈다.
    편마다 따로 세서 중앙값과 범위를 내야 "한 편의 정상 범위"가 된다.
    """
    L = ["", "## 한 편이 몇 %씩 인용하나 (편별 분포)", ""]
    L.append("- 게재작 %d편을 **한 편씩 따로** 세서 낸 분포다. 앞의 표(전체를"
             " 한 통에 넣고 센 값)와 다를 수 있다" % len(per_paper))
    L.append("- **우리 원고 한 편이 맞춰야 할 대역은 이쪽이다**")
    L.append("")
    head = "| 저널 | 중앙값 | 사분위(25-75%) | 최소-최대 | 인용하는 편수 |"
    if mine is not None:
        head = head + " 우리 | 판정 |"
    L.append(head)
    L.append("|--|--|--|--|--|" + ("--|--|" if mine is not None else ""))
    for k, _ in total.most_common(top):
        shares = []
        for _, c in per_paper:
            tot = sum(c.values())
            shares.append(100.0 * c.get(k, 0) / tot if tot else 0.0)
        used_n = sum(1 for x in shares if x > 0)
        shares.sort()
        med = statistics.median(shares)
        if len(shares) >= 4:
            q = statistics.quantiles(shares, n=4)
            q1, q3 = q[0], q[2]
        else:
            q1, q3 = shares[0], shares[-1]
        label = max(LABEL[k], key=len) if LABEL[k] else k
        row = ("| %s | %.1f%% | %.1f-%.1f%% | %.1f-%.1f%% | %d/%d편 |"
               % (label, med, q1, q3, shares[0], shares[-1],
                  used_n, len(per_paper)))
        if mine is not None:
            ours = 100.0 * mine.get(k, 0) / n_mine if n_mine else 0.0
            if ours < q1:
                v = "**대역 아래**"
            elif ours > q3:
                v = "대역 위"
            else:
                v = "대역 안"
            row = row + " %.1f%% | %s |" % (ours, v)
        L.append(row)
    L.append("")
    L.append("**사분위 25-75%가 실질 대역이다.** 우리 값이 그 밖이면 왜 그런지"
             " 답할 수 있어야 한다. 대역 아래면 그 학계가 읽는 것을 안 읽은")
    L.append("것이고, 대역 위면 한쪽에 치우친 것이다. **다만 맞추려고 인용을"
             " 끼우지 않는다**(1-2항-2).")
    return L


def compare_ours(path, total, n_ref_total, top, stats=None):
    """우리 참고문헌 분포를 게재작 분포와 나란히 놓는다."""
    L = ["", "## 우리 원고와 나란히 보기"]
    if not os.path.exists(path):
        return L + ["", "- 원고를 못 찾았다: %s" % path], None, 0
    raw = re.sub(r"-\s*\n\s*", "", open(path, encoding="utf-8",
                                        errors="replace").read())
    body = refs_of(raw)
    if not body:
        return L + ["", "- 원고에서 참고문헌 절을 못 찾았다."
                        " 제목이 `References`인지 확인하라"], None, 0
    # 원고가 markdown이면 저널 이름이 *기울임*으로 싸여 있다. 걷어낸다
    body = body.replace("*", "").replace("_", " ")
    mine = journals_of(body)
    n_mine = sum(mine.values())
    if n_mine < 5:
        return L + ["", "- 원고 참고문헌에서 저널 이름을 %d개밖에 못 뽑았다."
                        " 형식을 확인하라" % n_mine], None, 0
    L.append("")
    L.append("- 우리 참고문헌에서 뽑힌 항목 **%d개** (게재작 쪽은 %d개)"
             % (n_mine, n_ref_total))
    L.append("")
    L.append("| 저널 | 게재작 | 우리 | 차이 | 판정 |")
    L.append("|--|--|--|--|--|")
    short = []
    for k, n in total.most_common(top):
        p_them = 100.0 * n / n_ref_total
        p_us = 100.0 * mine.get(k, 0) / n_mine
        gap = p_us - p_them
        med = stats.get(k, (None,))[0] if stats else None
        if med is not None and med == 0 and p_us == 0:
            # 게재작도 **한 편이 보통 0%**인 저널이다. 우리가 0인 것이 정상.
            # 전체를 한 통에 넣고 센 값으로 "한 편도 없음"이라 하면 오판이다
            v = "정상(게재작도 편별 중앙값 0%)"
        elif mine.get(k, 0) == 0 and p_them >= 1.0:
            v = "**한 편도 없음**"
            short.append((max(LABEL[k], key=len) if LABEL[k] else k, p_them))
        elif gap < -0.5 * p_them and p_them >= 1.0:
            v = "**모자람**"
            short.append((max(LABEL[k], key=len) if LABEL[k] else k, p_them))
        elif gap > max(5.0, p_them):
            v = "과함"
        else:
            v = "비슷"
        L.append("| %s | %.1f%% | %.1f%% | %+.1f%%p | %s |"
                 % (max(LABEL[k], key=len) if LABEL[k] else k,
                    p_them, p_us, gap, v))
    L.append("")
    if short:
        L.append("**더 받아 올 저널 %d곳** (게재작은 읽는데 우리는 거의 안"
                 " 읽은 것):" % len(short))
        for nm, p in short:
            L.append("- %s (게재작 인용의 %.1f%%)" % (nm, p))
        L.append("")
    L.append("**주의: 비율을 맞추려고 인용하지 않는다.** 이 표는 *받아 올*"
             " 목록을 정하는 데 쓴다. 받아 온 뒤에는 한 편씩 읽고,")
    L.append("우리 문장이 하는 말을 그 논문이 실제로 하는지 확인한 것만"
             " 인용한다(`17_인용검증.md`). 맥락이 안 맞으면 인용하지 않고,")
    L.append("그 자리는 비율이 모자란 채로 둔다.")
    return L, mine, n_mine


def main():
    txt_dir = opt("--txt", "literature/_txt")
    mark = opt("--journal", "")
    top = int(opt("--top", 25))
    out_path = opt("--out")

    files = [f for f in sorted(glob.glob(txt_dir + "/*.txt"))
             if not mark or mark.lower() in os.path.basename(f).lower()]
    if not files:
        print("대상 파일이 없다: %s (표식 '%s')" % (txt_dir, mark))
        return

    per_paper = []
    total = Counter()
    n_ref_total = 0
    used = 0
    for f in files:
        raw = open(f, encoding="utf-8", errors="replace").read()
        raw = re.sub(r"-\s*\n\s*", "", raw)
        body = refs_of(raw)
        if not body:
            continue
        c = Counter()
        for m in JOURNAL.finditer(body):
            j = normalize(m.group(1))
            if len(j) < 5 or STOP_WORDS.match(j):
                continue
            if len(j.split()) > 9:
                continue
            c[key_of(j)] += 1
            LABEL[key_of(j)].add(j)
        if sum(c.values()) < 5:
            continue
        used += 1
        n_ref_total += sum(c.values())
        total.update(c)
        per_paper.append((os.path.basename(f)[:44], c))

    if not per_paper:
        print("참고문헌을 못 뽑았다. 텍스트 캐시를 확인할 것"
              " (check_ngram.py --extract).")
        return

    L = []
    L.append("# 게재작이 인용하는 저널 분포")
    L.append("")
    L.append("- 대상 %d편 중 참고문헌을 뽑은 것 **%d편**, 뽑힌 항목 %d개"
             % (len(files), used, n_ref_total))
    if used < 0.6 * len(files):
        L.append("- **주의: 대상의 %.0f%%에서만 참고문헌을 뽑았다.**"
                 " 이 분포를 그대로 쓰면 안 된다. 캐시에서 참고문헌 머리글이"
                 " 사라졌는지 먼저 본다" % (100.0 * used / len(files)))
    L.append("- 형식이 제각각이라 **전부 뽑히지는 않는다.** 절대 개수가 아니라"
             " 분포로 읽는다")
    L.append("")
    L.append("| 순위 | 인용된 저널 | 건수 | 비율 | 몇 편이 인용하나 |")
    L.append("|--|--|--|--|--|")
    for i, (k, n) in enumerate(total.most_common(top), 1):
        papers = sum(1 for _, c in per_paper if k in c)
        label = max(LABEL[k], key=len) if LABEL[k] else k
        L.append("| %d | %s | %d | %.1f%% | %d/%d편 |"
                 % (i, label, n, 100.0 * n / n_ref_total, papers, used))

    # 자기 저널 인용
    self_name = opt("--self")
    if self_name:
        sk = key_of(self_name)
        n = total.get(sk, 0)
        L.append("")
        L.append("**자기 저널 인용**: %d건 (%.1f%%)" % (n, 100.0 * n / n_ref_total))
    elif total:
        k, n = total.most_common(1)[0]
        label = max(LABEL[k], key=len) if LABEL[k] else k
        L.append("")
        L.append("**가장 많이 인용된 저널**: %s (%.1f%%). 이것이 목표 저널이면"
                 " 곧 자기 저널 인용 비율이다. 다른 저널을 기준으로 세려면"
                 " `--self \"저널 이름\"`" % (label, 100.0 * n / n_ref_total))

    ours = opt("--ours")
    mine, n_mine = None, 0
    stats = per_paper_stats(per_paper, [k for k, _ in total.most_common(top)])
    if ours:
        block, mine, n_mine = compare_ours(ours, total, n_ref_total, top, stats)
        L.extend(block)
    L.extend(per_paper_report(per_paper, total, top, mine, n_mine))

    L.append("")
    L.append("## 어떻게 쓰나")
    L.append("")
    L.append("- **우리 원고의 인용 분포와 견준다.** 상위 저널이 우리 목록에"
             " 거의 없으면, 그 학계가 읽는 문헌을 안 읽은 것이다")
    L.append("- **자기 저널 인용 비율**을 우리 것과 견준다. 너무 낮으면 그"
             " 저널 독자가 아는 논문을 안 인용한 것이다")
    L.append("- 상위에 나오는데 우리가 안 읽은 저널이 있으면 **수집 목록에"
             " 추가**한다")
    L.append("- 이상한 항목(출판사 이름, 학회 이름)이 섞이면 눈으로 걸러 낸다")

    text = "\n".join(L)
    if out_path:
        open(out_path, "w", encoding="utf-8").write(text)
        print("저장: %s" % out_path)
        print("대상 %d편, 항목 %d개" % (used, n_ref_total))
    else:
        print(text)


if __name__ == "__main__":
    main()
