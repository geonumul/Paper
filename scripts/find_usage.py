# -*- coding: utf-8 -*-
"""게재작에서 그 표현이 실제로 쓰인 문장을 뽑아 온다 (직접 대조용).

쓰임:
  python find_usage.py "One limitation"
  python find_usage.py --txt literature/_txt --journal TFSC "Table \\d+ (shows|presents)"
  python find_usage.py --before 1 --after 1 "we constructed"   # 앞뒤 문장까지
  python find_usage.py --max 3 --per-file 1 "granularity"      # 편수·편당 개수 제한

왜 필요한가
  PDF에서 뽑은 텍스트는 문장 가운데에 줄바꿈이 들어간다. 그래서 보통의 한 줄
  검색으로는 문장이 통째로 안 잡힌다. 이 도구는 공백을 정규화한 뒤 문장 단위로
  잘라서 보여 준다.

이 도구는 판정하지 않는다. **문장을 눈으로 읽고 우리 자리와 같은 기능인지
사람이 판정한다.** 인용으로 쓸 문장은 반드시 원문 PDF에서 다시 확인한다
(줄바꿈 하이픈으로 낱말이 깨져 있을 수 있다).
"""
import io
import os
import re
import sys
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _norm import norm_text, suspicious_zero   # noqa: E402

DEF_TXT = "literature/_txt"


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default





def split_sentences(text):
    """공백을 정규화하고 문장으로 자른다. 약어 뒤 마침표는 최대한 피한다."""
    t = re.sub(r"-\s*\n\s*", "", text)        # 줄바꿈 하이픈 복원
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\b(et al|e\.g|i\.e|Fig|Eq|No|vs|cf|Dr|approx)\.", r"\1<DOT>", t)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", t)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


def main():
    txt_dir = opt("--txt", DEF_TXT)
    mark = opt("--journal", "")
    before = int(opt("--before", 0))
    after = int(opt("--after", 0))
    max_files = int(opt("--max", 12))
    per_file = int(opt("--per-file", 2))

    skip = {txt_dir, mark, str(before), str(after), str(max_files), str(per_file)}
    pats = [a for a in sys.argv[1:] if a not in skip and not a.startswith("--")]
    if not pats:
        print(__doc__)
        return
    pat = re.compile(pats[0], re.I)

    files = [f for f in sorted(glob.glob(txt_dir + "/*.txt"))
             if not mark or mark.lower() in os.path.basename(f).lower()]
    if not files:
        print("코퍼스가 없습니다: %s (check_ngram.py --extract 먼저)" % txt_dir)
        return

    shown_files = 0
    total = 0
    for f in files:
        if shown_files >= max_files:
            break
        sents = split_sentences(norm_text(
            open(f, encoding="utf-8", errors="replace").read()))
        hits = [i for i, s in enumerate(sents) if pat.search(s)]
        if not hits:
            continue
        shown_files += 1
        print("\n## %s" % os.path.basename(f)[:70])
        for i in hits[:per_file]:
            total += 1
            lo, hi = max(0, i - before), min(len(sents), i + after + 1)
            for j in range(lo, hi):
                mark_ = "  > " if j == i else "    "
                print(mark_ + sents[j][:400])
            if after or before:
                print()

    print("\n---")
    print("문헌 %d편에서 문장 %d개 (검색어: %s)" % (shown_files, total, pats[0]))
    print("판정은 사람이 한다. 우리 자리와 같은 기능의 문장인지 읽어서 정하고,")
    print("인용으로 쓸 것은 원문 PDF에서 다시 확인한다.")


if __name__ == "__main__":
    main()
