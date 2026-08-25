# -*- coding: utf-8 -*-
"""검사 도구 자체를 검사한다. **도구를 고쳤으면 이것부터 돌린다.**

쓰임:
  python selfcheck.py              # 스킬 폴더 전체
  python selfcheck.py --dir <경로>  # 다른 폴더

무엇을 보나
  1 보이지 않는 문자  정규식의 `\\b`가 **백스페이스 문자로 깨지는 사고**가
                     반복해서 났다. 그러면 검사기가 아무것도 못 잡으면서
                     조용히 통과한다
  2 문법             컴파일이 되는가
  3 빈 파일          내용이 사라진 파일이 없는가
  4 표시 문자열      깨진 글자(replacement character)가 섞이지 않았는가

왜 필요한가
  **검사기가 조용히 통과하는 것이 가장 위험하다.** 78건이 그대로 통과한 적,
  게재작 51편 중 11편만 세고도 표를 낸 적, 문서의 `\\bibliography`가 글자
  하나로 깨져 있던 적이 있다. 전부 눈으로는 안 보였다.
"""
import io
import os
import re
import sys
import glob
import ast

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
BAD_CHAR = chr(0xFFFD)   # 글자가 깨졌을 때 나오는 문자 (여기에 직접 적으면 이 파일이 걸린다)


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def main():
    root = opt("--dir", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = (sorted(glob.glob(os.path.join(root, "scripts", "*.py")))
             + sorted(glob.glob(os.path.join(root, "references", "*.md")))
             + sorted(glob.glob(os.path.join(root, "templates", "*.md")))
             + [os.path.join(root, "SKILL.md"), os.path.join(root, "README.md")])
    files = [f for f in files if os.path.exists(f)]

    print("# 도구 자가 점검 · %s" % root)
    print("")
    print("- 검사한 파일 %d개" % len(files))

    ctrl, syntax, empty, junk = [], [], [], []
    for f in files:
        raw = io.open(f, encoding="utf-8", errors="replace").read()
        for i, ln in enumerate(raw.split(chr(10)), 1):
            if CTRL.search(ln):
                ctrl.append((f, i, repr(ln.strip())[:90]))
        if BAD_CHAR in raw:
            junk.append(f)
        if len(raw.strip()) < 80:
            empty.append(f)
        if f.endswith(".py"):
            try:
                ast.parse(raw)
            except SyntaxError as e:
                syntax.append((f, e.lineno, str(e)[:60]))

    print("")
    print("## 1. 보이지 않는 문자")
    if ctrl:
        print("- **%d곳.** 정규식이 깨져 검사기가 조용히 통과할 수 있다"
              % len(ctrl))
        for f, i, ln in ctrl[:12]:
            print("    - %s:%d  %s" % (os.path.basename(f), i, ln))
    else:
        print("- 없음")

    print("")
    print("## 2. 문법")
    if syntax:
        print("- **%d개 파일이 컴파일 안 된다**" % len(syntax))
        for f, i, e in syntax:
            print("    - %s:%s  %s" % (os.path.basename(f), i, e))
    else:
        print("- 전부 통과")

    print("")
    print("## 3. 빈 파일 / 깨진 글자")
    print("- 빈 파일: %s" % (", ".join(os.path.basename(f) for f in empty)
                            or "없음"))
    print("- 깨진 글자: %s" % (", ".join(os.path.basename(f) for f in junk)
                             or "없음"))

    bad = len(ctrl) + len(syntax) + len(empty) + len(junk)
    print("")
    print("---")
    if bad:
        print("**걸린 것 %d건. 고치기 전에는 검사 결과를 믿지 않는다.**" % bad)
        sys.exit(1)
    print("**깨끗하다.**")


if __name__ == "__main__":
    main()
