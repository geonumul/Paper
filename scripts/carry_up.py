# -*- coding: utf-8 -*-
"""층에서 **기록**으로 넘긴 것을 한 대장에 모은다.

쓰임:

  python carry_up.py --dir outputs                 # 모아서 보여 준다
  python carry_up.py --dir outputs --apply         # 기록_대장.md에 적는다

왜 이 대장이 있나

  **낱말 하나가 걸렸다고 그 자리에서 정하면 틀린다.** 문장에서 걸린 것이
  문단에서 풀리고, 문단에서 걸린 것이 소절에서 풀리고, 소절에서 걸린 것이
  전체를 보고 나서야 풀린다. 그 반대도 있다. 한 문장에서는 사소해 보이던
  것이 전체를 놓고 보면 같은 병이 열두 군데다.

  그래서 **조금이라도 논란이 될 만한 것은 그 층에서 정하지 않고 기록한다.**
  판정 칸에 `기록`이라 적으면 이 도구가 그 행을 모아 온다. 정하는 것은
  층을 다 지나고 나서다.

  기록은 유보와 다르다. 유보는 **선례를 못 찾아서** 저자에게 넘기는 것이고,
  기록은 **아직 정할 때가 아니라서** 위층으로 넘기는 것이다.

무엇을 모으나

  - 판정 칸이 `기록`으로 시작하는 행 (`기록`, `유지 (기록)`, `★ 기록` 모두)
  - 어느 층 어느 번호에서 왔는지, 무엇이 걸렸는지

닫는 법

  모인 행마다 **처리** 칸을 채워야 이 단계가 닫힌다. 처리는 셋 중 하나다.
  **고침 / 그대로 둠 / 저자 판단**. 그리고 왜 그렇게 정했는지를 적는다.
  같은 병이 여러 층에 걸쳐 나왔으면 **한 줄로 묶어서** 정한다.
"""
import io
import os
import re
import sys
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

OUT = "기록_대장.md"
# 어느 대장이 어느 층인가
LAYERS = [
    ("낱말_대장.md", "낱말"),
    ("문장_대장.md", "문장"),
    ("문단_대장.md", "문단"),
    ("소절_대장.md", "소절·장·전체"),
    ("회차_대장.md", "각도별 읽기"),
    ("인용_대장.md", "인용"),
    ("번역_대장.md", "번역"),
    ("그림표_사양서.md", "그림·표"),
]


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def marked_rows(path, layer):
    """그 대장에서 `기록`으로 넘긴 행."""
    rows = []
    if not os.path.exists(path):
        return rows
    in_body, header, col = False, None, None
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        ln = ln.rstrip()
        if not ln.startswith("|"):
            in_body, header, col = False, None, None
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if set(ln) <= set("|-: "):
            in_body = True
            if header:
                vi = [i for i, h in enumerate(header) if "판정" in h]
                ei = [i for i, h in enumerate(header)
                      if "근거" in h or "흐름" in h]
                col = (vi[0] if vi else len(cells) - 1,
                       ei[-1] if ei else None)
            continue
        if not in_body:
            header = cells
            continue
        if not col:
            continue
        vi, ei = col
        if vi >= len(cells):
            continue
        verd = cells[vi]
        if "기록" not in verd:
            continue
        why = cells[ei] if ei is not None and ei < len(cells) else ""
        rows.append((layer, cells[0], cells[1] if len(cells) > 1 else "",
                     verd, re.sub(r"\s+", " ", why)[:220]))
    return rows


def existing(path):
    """이미 적어 둔 처리. 다시 모을 때 덮어쓰지 않는다."""
    done = {}
    if not os.path.exists(path):
        return done
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        cells = [c.strip() for c in ln.rstrip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0] not in ("층", "--"):
            done[(cells[0], cells[1])] = (cells[4], cells[5])
    return done


def main():
    d = opt("--dir", "outputs")
    rows = []
    for fn, layer in LAYERS:
        rows += marked_rows(os.path.join(d, fn), layer)

    path = os.path.join(d, OUT)
    keep = existing(path)

    print("# 기록 대장 · 층에서 넘어온 것 %d개" % len(rows))
    print("")
    if not rows:
        print("- 넘어온 것이 없다. 층의 판정 칸에 `기록`이 적힌 행이 없다.")
        print("- **조금이라도 논란이 될 만한 것은 그 층에서 정하지 말고"
              " 판정 칸에 `기록`이라 적는다.** 정하는 것은 층을 다 지나고"
              " 나서다")
        return

    by = {}
    for layer, no, what, verd, why in rows:
        by.setdefault(layer, []).append((no, what, verd, why))
    for layer in by:
        print("- %s 층 **%d개**" % (layer, len(by[layer])))
    print("")

    lines = ["| 층 | 번호 | 무엇 | 판정 | 처리 | 왜 그렇게 정했나 |",
             "|--|--|--|--|--|--|"]
    for layer, no, what, verd, why in rows:
        p, r = keep.get((layer, no), ("", ""))
        lines.append("| %s | %s | %s | %s | %s | %s |"
                     % (layer, no, (what or why)[:110], verd, p, r))

    if "--apply" not in sys.argv:
        print("\n".join(lines[:2] + lines[2:14]))
        if len(lines) > 14:
            print("| ... | | | | | |")
        print("")
        print("**적으려면 `--apply`.**")
        return

    head = [
        "# 기록 대장",
        "",
        "층에서 **그 자리에서 정하지 않고 넘긴 것**을 모았다. 문장에서 걸린",
        "것이 문단에서 풀리고, 문단에서 걸린 것이 전체를 보고 나서야 풀린다.",
        "그 반대도 있다. 한 자리에서는 사소하던 것이 전체로는 같은 병이 열두",
        "군데다.",
        "",
        "**처리 칸을 다 채우기 전에는 이 단계가 닫히지 않는다.** 처리는 셋 중",
        "하나다: **고침 / 그대로 둠 / 저자 판단**. 같은 병이 여러 층에 걸쳐",
        "나왔으면 한 줄로 묶어서 정한다.",
        "",
    ]
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        "\n".join(head + lines) + "\n")
    kept = sum(1 for layer, no, _, _, _ in rows if (layer, no) in keep)
    print("`%s`에 %d행을 적었다. 이미 처리를 적어 둔 %d행은 그대로 두었다."
          % (OUT, len(rows), kept))


if __name__ == "__main__":
    main()
