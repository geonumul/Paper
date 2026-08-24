# -*- coding: utf-8 -*-
"""게재작 코퍼스에서 용어가 몇 편에 나오는지 센다 (용어 합격선 8% 판정용).

쓰임:
  python corpus_freq.py "technology cluster" "technology field" granularity
  python corpus_freq.py --txt literature/_txt --journal TFSC "link prediction"
  python corpus_freq.py --context "residual"      # 쓰인 문장을 함께 본다

판정: 코퍼스에서 8% 미만이면 걷어내거나 풀어 쓴다. 8% 이상이면 그대로 쓴다.

다만 빈도만으로 정하지 않는다. **맥락을 함께 본다.** 같은 낱말이라도 쓰인
자리가 다르면 근거가 되지 않는다(예: residual이 대부분 신경망의 잔차 연결을
뜻하면 범주 이름으로는 못 쓴다). --context 로 실제 문장을 확인할 것.
"""
import io
import os
import re
import sys
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEF_TXT = "literature/_txt"


def opt(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def main():
    txt_dir = opt("--txt", DEF_TXT)
    mark = opt("--journal", "")
    show_ctx = "--context" in sys.argv

    skip = {txt_dir, mark, "--txt", "--journal", "--context"}
    terms = [a for a in sys.argv[1:] if a not in skip and not a.startswith("--")]
    if not terms:
        print(__doc__)
        return

    files = [f for f in sorted(glob.glob(txt_dir + "/*.txt"))
             if not mark or mark.lower() in os.path.basename(f).lower()]
    if not files:
        print("코퍼스가 없습니다: %s (check_ngram.py --extract 먼저)" % txt_dir)
        return

    texts = []
    for f in files:
        texts.append((os.path.basename(f),
                      open(f, encoding="utf-8", errors="replace").read()))

    print("코퍼스 %d편 (%s%s)\n" % (len(texts), txt_dir,
                                  ", 표식 '%s'" % mark if mark else ""))
    print("|용어|등장 논문 수|비율|판정|")
    print("|--|--|--|--|")
    ctx_bank = []
    for t in terms:
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])",
                         re.I)
        n = 0
        for name, body in texts:
            if pat.search(body):
                n += 1
                if show_ctx and len(ctx_bank) < 12:
                    m = pat.search(body)
                    s = max(0, m.start() - 90)
                    ctx = " ".join(body[s:m.end() + 90].split())
                    ctx_bank.append((t, name[:40], ctx))
        pct = 100.0 * n / len(texts)
        verdict = "채택 가능" if pct >= 8 else "8% 미만 - 걷어내거나 풀어 쓴다"
        print("|%s|%d|%.1f%%|%s|" % (t, n, pct, verdict))

    if ctx_bank:
        print("\n## 쓰인 자리 (맥락 확인)")
        for t, name, ctx in ctx_bank:
            print("- **%s** (%s)\n  …%s…" % (t, name, ctx))


if __name__ == "__main__":
    main()
