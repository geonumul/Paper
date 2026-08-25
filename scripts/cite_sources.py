# -*- coding: utf-8 -*-
"""게재작들이 어느 저널을 몇 퍼센트씩 인용하는지 센다.

쓰임:
  python cite_sources.py --txt literature/_txt --journal TFSC
  python cite_sources.py --txt literature/_txt --journal TFSC --top 30
  python cite_sources.py --txt literature/_txt --journal TFSC --out outputs/인용출처.md

무엇을 보나
  목표 저널에 실린 논문들의 참고문헌에서 **저널 이름**을 뽑아 분포를 낸다.
  - 그 저널이 자기 저널을 몇 % 인용하는가
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
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REF_HEAD = re.compile(r"^\s*(References|REFERENCES|Bibliography|참고문헌)\s*$",
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


def refs_of(text):
    m = list(REF_HEAD.finditer(text))
    if not m:
        return ""
    return text[m[-1].end():]


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
