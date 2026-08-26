# -*- coding: utf-8 -*-
"""**"원문이 없다"고 말하기 전에 돌린다.** 그 논문이 어디 있는지 찾는다.

쓰임:

  python find_source.py "O'Brien" 2007

  python find_source.py --title "caution regarding rules of thumb"

  python find_source.py "Fernandez-Muniz" 2009 --root <프로젝트 뿌리>

왜 이 도구가 있나

  한 원고를 검수하면서 **"원문이 없어 대조 못 한다"를 네 번 말했고 네 번 다
  뒤집혔다.**

  | 말한 것 | 실제 |
  |--|--|
  | 고용노동부 자료 5건이 없다 | `ARCHIVE/산재관련`에 있었다. 캐시에도 있었다 |
  | Chawla 2002의 SMOTE-NC 절차를 못 본다 | 스캔본이라 글자 층이 74낱말뿐이었다. 쪽을 이미지로 읽으니 349쪽에 그대로 있었다 |
  | O'Brien 2007이 없다 | 처음부터 있었다. 파일 이름이 DOI였다 |
  | 인용 네 종의 원문이 없다 | 이름 맞추기가 악센트와 성 길이에서 실패한 것이었다 |

  **"대조 불가"는 증거에 대한 주장이지 사실이 아니다.** 글자 캐시에 없다는
  것과 원문이 없다는 것은 다르고, 스캔본은 이미지로 읽을 수 있고, 파일
  이름은 저자 이름이 아닐 수 있다.

무엇을 하나

  1 프로젝트 안의 **모든 PDF와 글자 파일**을 훑는다
  2 파일 **이름**으로 찾는다 (악센트를 접고, 성 네 글자 이상으로 맞춘다)
  3 못 찾으면 파일 **속**을 찾는다 (제목 조각이나 저자+연도)
  4 PDF에 글자 층이 없으면 **스캔본이라고 말하고 읽는 법을 알려 준다**

**여기서도 못 찾아야 없는 것이다.** 그때 비로소 "없다"고 적는다.
"""
import io
import os
import re
import sys
import unicodedata

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

SKIP = {".git", "__pycache__", "node_modules", ".venv"}


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def fold(s):
    """악센트를 접고 글자만 남긴다. `Fernández-Muñiz` -> `fernandezmuniz`."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def walk(root):
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for f in files:
            if f.lower().endswith((".pdf", ".txt")):
                yield os.path.join(dirpath, f)


def has_text(path):
    """PDF에 글자 층이 있는가. 없으면 스캔본이다."""
    try:
        import fitz
    except ImportError:
        return None
    try:
        d = fitz.open(path)
        n = sum(len(d[i].get_text().split()) for i in range(min(4, d.page_count)))
        d.close()
        return n
    except Exception:                                         # noqa: BLE001
        return None


def read_head(path, cap=400000):
    if path.lower().endswith(".txt"):
        return io.open(path, encoding="utf-8", errors="replace").read(cap)
    try:
        import fitz
    except ImportError:
        return ""
    try:
        d = fitz.open(path)
        t = " ".join(d[i].get_text() for i in range(min(6, d.page_count)))
        d.close()
        return t
    except Exception:                                         # noqa: BLE001
        return ""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    title = opt("--title")
    root = opt("--root", ".")
    if not args and not title:
        print(__doc__)
        return
    surname = args[0] if args else ""
    year = args[1] if len(args) > 1 else ""
    key = fold(surname)

    files = list(walk(root))
    print("# 원문 찾기")
    print("")
    if surname:
        print("- 찾는 것: **%s %s**" % (surname, year))
    if title:
        print("- 제목 조각: **%s**" % title)
    print("- 뒤진 파일 %s개 (%s 아래)" % ("{:,}".format(len(files)), root))
    print("")

    # ① 파일 이름으로
    by_name = []
    for p in files:
        stem = fold(os.path.splitext(os.path.basename(p))[0])
        if key and len(key) >= 4 and key[:8] in stem:
            if not year or year in os.path.basename(p):
                by_name.append(p)
    if by_name:
        print("## 파일 이름으로 찾음 **%d개**" % len(by_name))
        for p in sorted(set(by_name)):
            say = ""
            if p.lower().endswith(".pdf"):
                n = has_text(p)
                if n is not None and n < 120:
                    say = "  ← **스캔본이다.** 글자 층이 %d낱말뿐" % n
            print("    - %s%s" % (p, say))
        print("")

    # ② 파일 속으로
    # **이름으로 찾았으면 속은 안 뒤진다.** 저자 이름은 남의 논문
    # 참고문헌에도 나오므로, 속을 뒤지면 그 저자를 인용한 논문이 전부
    # 걸려 찾은 것처럼 보인다
    probe = title or ("%s" % surname)
    pk = fold(probe)
    inside = []
    if not by_name and pk and len(pk) >= 6:
        for p in files:
            if p in by_name:
                continue
            t = fold(read_head(p))
            if not t:
                continue
            if pk[:40] in t and (not year or year in t or year in p):
                inside.append(p)
            if len(inside) >= 12:
                break
    if inside:
        print("## 파일 이름으로는 못 찾았고, **속에 그 말이 있는 파일** %d개" % len(inside))
        print("")
        print("    참고문헌에 그 이름이 나오는 것일 수 있다. 열어서 그 논문 자체인지 본다")
        print("")
        for p in inside:
            print("    - %s" % p)
        print("")

    if not by_name and not inside:
        print("## 못 찾았다")
        print("")
        print("**여기까지 왔으면 이제 없다고 적어도 된다.** 다만 그 전에 셋을"
              " 더 본다.")
        print("")
        print("1. **이름이 저자가 아닐 수 있다.** DOI(`s11135-006-9018-6`)나"
              " 출판사 번호(`1-s2.0-...`)로 저장된 파일이 있다."
              " `--title`로 제목 조각을 넣어 다시 찾는다")
        print("2. **다른 폴더에 있을 수 있다.** `--root`를 프로젝트 뿌리로"
              " 올려 다시 찾는다. 실제로 `ARCHIVE` 아래에 있던 것을 없다고"
              " 한 적이 있다")
        print("3. **스캔본이면 글자로 안 잡힌다.** 그 논문의 PDF가 있는데도"
              " 안 걸리면 `pdf_render.py`로 쪽을 이미지로 만들어 눈으로 읽는다")
        sys.exit(1)

    print("---")
    print("**스캔본이면 글자로 대조하지 말고 이미지로 읽는다.**")
    print("")
    print("    python pdf_render.py <그 pdf> <시작쪽> <끝쪽> 2.0")
    print("")
    print("한 원고에서 스캔본을 \"대조 불가\"로 적었다가, 쪽을 이미지로 읽어")
    print("우리 서술이 원문 그대로임을 확인한 적이 있다.")


if __name__ == "__main__":
    main()
