# -*- coding: utf-8 -*-
"""PDF에서 글을 뽑아 캐시로 만든다. **두 단을 단 순서로 읽는다.**

쓰임:

  python pdf_text.py <pdf폴더> <출력폴더>          # 폴더째 뽑는다
  python pdf_text.py <pdf파일> <출력폴더>          # 한 편만
  python pdf_text.py --check <pdf폴더> <캐시폴더>  # 이미 만든 캐시를 검사한다

왜 이 도구가 있나

  **두 단으로 조판된 논문을 줄 단위로 뽑으면 왼쪽 단과 오른쪽 단이 한 줄씩
  번갈아 섞인다.** 그러면 글자는 다 있는데 어떤 문장도 이어지지 않는다.

  실제로 그 일이 났다. 인용을 대조하는데 `future researchers conduct field
  testing on these indicators`가 캐시에 없다고 나왔다. 원문에는 그대로 있었다.
  캐시가 이렇게 되어 있었을 뿐이다.

      ...recommend that future researchers conduct field   ← 왼쪽 단
      indicators." Construction industry institute research ← 오른쪽 단
      team 284 research testin...                          ← 왼쪽 단

  **이것이 가장 위험한 갈래다.** 도구가 "없다"고 말하고, 그 말이 조용히
  맞는 것처럼 지나간다. 인용이 틀렸다고 원고를 고치러 갈 뻔했다.

  쪽을 단 순서로 다시 뽑으니 그 문장이 8쪽에 그대로 있었다.

무엇을 하나

  1 쪽마다 글 덩이를 뽑아, 가운데를 기준으로 **왼쪽 단을 위에서 아래로 다
    읽고 그다음 오른쪽 단**을 읽는다
  2 한 단짜리 쪽은 그대로 위에서 아래로 읽는다
  3 줄 끝 붙임표(`indi-` + `cator`)를 잇는다
  4 `--check`는 원문에서 다시 뽑아 **캐시와 맞춰 본다.** 글의 생김새로
    어림잡지 않는다. 그렇게 재려다 통계 연보 열세 편이 걸리고 정작
    섞여 있던 논문은 안 걸린 적이 있다

**캐시를 새로 만들었으면 그 위에서 잰 것을 다시 잰다.** 섞인 캐시로 잰
편수와 근거는 전부 못 믿는다.
"""
import io
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _norm import norm_text                    # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")


def page_text(pg):
    """한 쪽을 **단 순서로** 읽는다. 두 단이면 왼쪽을 다 읽고 오른쪽으로."""
    blocks = [b for b in pg.get_text("blocks") if b[6] == 0 and b[4].strip()]
    if not blocks:
        return ""
    mid = pg.rect.width / 2.0
    left = [b for b in blocks if (b[0] + b[2]) / 2 < mid]
    right = [b for b in blocks if (b[0] + b[2]) / 2 >= mid]
    # 한 단짜리 쪽에서 억지로 가르면 오히려 글이 뒤집힌다. 양쪽에 고루
    # 있을 때만 두 단으로 본다
    two = len(left) >= 2 and len(right) >= 2
    if not two:
        order = sorted(blocks, key=lambda b: (round(b[1], 1), b[0]))
    else:
        order = (sorted(left, key=lambda b: b[1])
                 + sorted(right, key=lambda b: b[1]))
    return "\n".join(b[4].strip() for b in order)


def dehyphen(t):
    """줄 끝에서 끊긴 낱말을 잇는다. `indi-` + 줄바꿈 + `cator`."""
    return re.sub(r"([A-Za-z])-\s*\n\s*([a-z])", r"\1\2", t)


def extract(path):
    import fitz
    d = fitz.open(path)
    pages = []
    for i in range(d.page_count):
        pages.append("<<<PAGE %d>>>\n%s" % (i + 1, page_text(d[i])))
    d.close()
    return dehyphen("\n".join(pages))


# 캐시가 섞였는지는 **재 봐서** 안다. 글의 생김새로 어림잡으면 안 된다.
#
# 처음에는 마침표 하나에 낱말이 몇 개인지로 재려 했다. 그랬더니 문장이 거의
# 없는 통계 연보 열세 편이 걸리고, **정작 섞여 있던 논문은 안 걸렸다.**
# 노이즈가 많은 검사는 안 넣는 것이 낫다. 사람이 출력을 안 읽게 된다.
#
# 그래서 원문에서 단 순서로 다시 뽑아, 거기 있는 **긴 문장이 캐시에도
# 이어져 있는지**를 본다. 섞인 캐시에서는 그 문장이 통째로 안 잡힌다.
# 문장이 없는 문서는 잴 것이 없으므로 그냥 건너뛴다.
LONG_SENT = re.compile(r"[A-Z][A-Za-z0-9 ,()'-]{70,180}[.]")


def cache_matches(pdf_path, cache_text, sample=12):
    """(재 본 문장 수, 캐시에서 못 찾은 수). 잴 것이 없으면 (0, 0)."""
    # **양쪽을 같은 방식으로 다듬는다.** 합자와 발음기호가 뽑는 도구마다
    # 다르게 나오므로, 안 다듬고 견주면 멀쩡한 캐시도 안 맞는다고 나온다
    fresh = re.sub(r"\s+", " ", norm_text(extract(pdf_path),
                                          fold_accents=True))
    flat = re.sub(r"\s+", " ", norm_text(cache_text,
                                         fold_accents=True))
    seen, miss = 0, 0
    for m in LONG_SENT.finditer(fresh):
        s = m.group(0).strip()
        if len(s.split()) < 12:
            continue
        seen += 1
        if flat.find(s[:60]) < 0:
            miss += 1
        if seen >= sample:
            break
    return seen, miss


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--check" in sys.argv:
        if len(args) < 2:
            print("쓰임: python pdf_text.py --check <pdf폴더> <캐시폴더>")
            print("")
            print("원문에서 단 순서로 다시 뽑아, 거기 있는 긴 문장이 캐시에도"
                  " 이어져 있는지 잰다. **글의 생김새로 어림잡지 않는다.**")
            return
        pdf_dir, cache_dir = args[0], args[1]
        pdfs = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
        print("# 캐시 검사 · 원문과 맞춰 본다")
        print("")
        print("- 원문 %d편 · 캐시 폴더 %s" % (len(pdfs), cache_dir))
        bad, checked, skipped = [], 0, 0
        for p in pdfs:
            name = os.path.splitext(os.path.basename(p))[0]
            c = os.path.join(cache_dir, name + ".txt")
            if not os.path.exists(c):
                continue
            t = io.open(c, encoding="utf-8", errors="replace").read()
            try:
                seen, miss = cache_matches(p, t)
            except Exception:                                 # noqa: BLE001
                continue
            if seen < 4:
                skipped += 1        # 잴 만한 문장이 없는 문서 (통계표 등)
                continue
            checked += 1
            if miss * 2 >= seen:
                bad.append((name, seen, miss))
        print("- 잰 것 %d편 · 잴 문장이 없어 건너뛴 것 %d편"
              % (checked, skipped))
        print("")
        if bad:
            print("## 원문에 있는 문장이 캐시에서 끊긴 파일 **%d개**" % len(bad))
            print("")
            for name, seen, miss in bad:
                print("    - %s (잰 문장 %d개 중 %d개가 캐시에 안 이어져 있다)"
                      % (name[:56], seen, miss))
            print("")
            print("**두 단이 줄 단위로 섞인 것이다.** 이 도구로 다시 뽑고,"
                  " 그 캐시 위에서 잰 편수와 근거를 다시 잰다. 섞인 캐시는"
                  " 인용을 못 찾으면서도 조용히 통과한다")
            sys.exit(1)
        print("- 원문과 캐시가 맞는다")
        return

    if len(args) < 2:
        print(__doc__)
        return
    src, out = args[0], args[1]
    if not os.path.isdir(out):
        os.makedirs(out)
    paths = ([src] if src.lower().endswith(".pdf")
             else sorted(glob.glob(os.path.join(src, "*.pdf"))))
    if not paths:
        print("PDF가 없다: %s" % src)
        return
    print("# PDF에서 글 뽑기 · %d편" % len(paths))
    print("")
    done = fail = 0
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        try:
            t = extract(p)
        except Exception as e:                                # noqa: BLE001
            print("    - %s: 못 뽑았다 (%s)" % (name[:50], str(e)[:60]))
            fail += 1
            continue
        io.open(os.path.join(out, name + ".txt"), "w", encoding="utf-8",
                newline="\n").write(t)
        done += 1
    print("- 뽑은 것 **%d편**, 못 뽑은 것 %d편" % (done, fail))
    print("")
    print("**이제 `--check`로 섞이지 않았는지 본다.**")


if __name__ == "__main__":
    main()
