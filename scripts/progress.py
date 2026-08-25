# -*- coding: utf-8 -*-
"""검수 진행을 파일에 적어 두고, 한 턴에 한 단계만 하도록 막는다.

쓰임:
  python progress.py --init 원고.md --journal TFSC     # 처음 한 번
  python progress.py --status                          # 지금 할 일 하나만 알려 준다
  python progress.py --check 7                         # 그 단계 관문을 통과했나
  python progress.py --done 7                          # 통과했으면 완료로 적는다
  python progress.py --note "7-2 3회차: 흐름, 새 지적 4건"

왜 필요한가
  절차를 글로만 적어 두면 **한 번에 다 훑고 "끝냈습니다"가 된다.** 실제로
  며칠 걸릴 검수가 10분에 끝난 적이 있다. 그래서 진행 상태를 파일에 두고,
  **관문을 통과해야만 다음 단계로 넘어가게** 한다.

관문이란
  그 단계의 산출물이 실제로 있고, 대장이라면 **판정이 빈 행이 0**이어야
  통과다. 파일이 없거나 빈 행이 남아 있으면 `--done`이 거부한다.

한 턴에 얼마나
  전수 층은 한 번에 다 못 한다. 층마다 **한 턴 몫**이 정해져 있고,
  `--status`가 이번 턴에 볼 행 번호 범위를 찍어 준다.
"""
import io
import os
import re
import sys
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

STATE = "검수_진행상태.json"

# 단계: (번호, 이름, 산출물, 관문 종류)
#   file   = 그 파일이 있으면 통과
#   ledger = 대장이고, 판정이 빈 행이 0이어야 통과
#   ask    = 저자에게 물어 답을 받아야 통과 (기록에 남긴다)
STEPS = [
    ("0",   "원고·논문 폴더·목표 저널 확인", "",                    "ask"),
    ("1",   "저널 정하기",                  "저널_결정.md",         "ask"),
    ("2",   "모으기와 폴더 진단",           "폴더진단.md",          "file"),
    ("3",   "대역 실측",                    "_burstiness_band.json", "file"),
    ("4",   "인용 출처 분포",               "인용출처.md",          "file"),
    ("5",   "기준 뽑기(통독·구조 지도)",     "구조지도.md",          "file"),
    ("6",   "기계 검사",                    "기계검사.md",          "file"),
    ("7a",  "전수 대조: 낱말",              "낱말_대장.md",         "ledger"),
    ("7b",  "전수 대조: 문장",              "문장_대장.md",         "ledger"),
    ("7c",  "전수 대조: 문단",              "문단_대장.md",         "ledger"),
    ("7d",  "전수 대조: 소절·장·전체",      "소절_대장.md",         "ledger"),
    ("7-2", "각도별 읽기",                  "회차_대장.md",         "ledger"),
    ("7e",  "기록 정리: 층에서 넘어온 것",   "기록_대장.md",         "ledger"),
    ("8",   "인용 검증",                    "인용_대장.md",         "ledger"),
    ("9",   "번역 대조",                    "번역_대장.md",         "ledger"),
    ("10",  "그림·표",                      "그림표_사양서.md",     "ledger"),
    ("11",  "AI 티·파일 위생",              "위생점검.md",          "file"),
    ("12",  "투고 점검",                    "제출점검.md",          "file"),
]

# 한 턴 몫 (전수 층에서 한 번에 볼 행 수)
# 한 줄마다 게재작 근거를 대야 하므로 몫이 작다. 늘리면 근거를 안 대게 된다
QUOTA = {"7a": 60, "7b": 25, "7c": 10, "7d": 4, "7-2": 1,
         "7e": 10,
         "8": 8, "9": 10, "10": 2}


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def state_path(d):
    return os.path.join(d, STATE)


def load(d):
    p = state_path(d)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def save(d, st):
    json.dump(st, open(state_path(d), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


EMPTY = ("", "-", "미판정", "TBD", "?", "…")


def ledger_rows(path):
    """대장의 전체 행 수와 **아직 안 끝난 행** 수를 센다.

    끝난 행이란 **판정과 근거가 둘 다 채워진 행**이다. 머리글에 '판정'이나
    '근거'가 들어간 칸을 찾아 그 칸들을 본다. 못 찾으면 마지막 칸을 본다.

    판정만 보면 "게재작 어느 문장을 근거로 썼는가"를 비워 둔 채 넘어간다.
    실제로 그렇게 넘어간 적이 있어서 근거 칸까지 보게 했다.
    """
    if not os.path.exists(path):
        return 0, 0
    total = blank = 0
    in_body = False           # 구분선(|--|--|) 아래부터가 본문 행이다
    need = None               # 채워져야 하는 칸 번호
    header = None
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        ln = ln.rstrip()
        if not ln.startswith("|"):
            in_body, need, header = False, None, None
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if set(ln) <= set("|-: "):
            in_body = True
            if header:
                need = [i for i, h in enumerate(header)
                        if "판정" in h or "근거" in h]
            continue
        if not in_body:
            header = cells    # 머리글 행
            continue
        total += 1
        idx = need if need else [len(cells) - 1]
        if any(i >= len(cells) or cells[i] in EMPTY for i in idx):
            blank += 1
    return total, blank


# `15` §4-1의 기능 열 갈래와 §4-4의 판정 셋. **여기 없는 이름은 안 쓴다.**
# 갈래를 지어 쓰면 게재작에서 같은 기능을 찾을 수가 없고, 근거가 자리도
# 기능도 다른 문장이 된다. 실제로 "서술", "결과 수치" 같은 이름을 지어
# 쓰다가 한 층의 근거가 통째로 어긋났다
FUNCS10 = ("현상 제시", "선행 관행 규정", "갭 진술", "선택 정당화",
           "절차 서술", "표·그림 지시", "결과 보고", "해석", "경계", "한계")
# 판정 넷. **기록**은 그 층에서 정하지 않고 위층으로 넘긴다는 뜻이다.
# 유보는 선례를 못 찾아 저자에게 넘기는 것이고, 기록은 아직 정할 때가
# 아니라서 넘기는 것이다. 문장에서 걸린 것이 문단에서 풀리고, 문단에서
# 걸린 것이 전체를 보고 나서야 풀린다
VERDICT3 = ("유지", "대체", "유보", "기록")


def ledger_terms(path):
    """대장이 **정해진 이름만** 쓰는가. (기능이 틀린 행, 판정이 틀린 행)

    관문이 빈칸만 보면, 채워져 있기만 하면 무엇이 적혀 있든 통과한다.
    그래서 지어낸 갈래로 채운 층이 그대로 닫힐 뻔했다.
    """
    bad_fn, bad_vd = [], []
    if not os.path.exists(path):
        return bad_fn, bad_vd
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
                fi = [i for i, h in enumerate(header) if h.strip() == "기능"]
                vi = [i for i, h in enumerate(header) if "판정" in h]
                col = (fi[0] if fi else None, vi[0] if vi else None)
            continue
        if not in_body:
            header = cells
            continue
        if not col or col[0] is None:
            continue
        fi, vi = col
        if fi < len(cells) and cells[fi] and cells[fi] not in FUNCS10:
            bad_fn.append((cells[0], cells[fi]))
        # 판정 칸은 "유지 (기록)"처럼 적힐 수 있다. 앞머리로 본다
        if vi is not None and vi < len(cells) and cells[vi]:
            v = cells[vi].lstrip("★ ").strip()
            if not any(v.startswith(x) for x in VERDICT3):
                bad_vd.append((cells[0], cells[vi]))
    return bad_fn, bad_vd


def gate(step, d, st):
    """그 단계가 실제로 끝났는가. (통과여부, 설명)"""
    info = dict((s[0], s) for s in STEPS)[step]
    _, name, out, kind = info
    if kind == "ask":
        ans = st.get("answers", {}).get(step)
        if ans:
            return True, "저자 답을 받았다: %s" % ans[:60]
        return False, "저자에게 묻고 답을 받아 `--note`로 적어야 한다"
    path = os.path.join(d, out) if out else ""
    if not os.path.exists(path):
        return False, "산출물이 없다: %s" % path
    if kind == "ledger":
        total, blank = ledger_rows(path)
        if total == 0:
            return False, "대장에 행이 없다: %s" % path
        if blank:
            return False, ("판정 안 한 행 **%d개** 남았다 (전체 %d행). "
                           "**이 단계는 아직 안 끝났다**" % (blank, total))
        # 채워진 것만 보지 않고 **무엇으로 채웠는지**를 본다
        bad_fn, bad_vd = ledger_terms(path)
        if bad_fn:
            ex = ", ".join("%s(%s)" % (n, v) for n, v in bad_fn[:4])
            return False, ("기능이 `15` §4-1의 열 갈래 밖인 행 **%d개**: %s. "
                           "**갈래를 지어 쓰면 게재작에서 같은 기능을 찾을 수"
                           " 없다**" % (len(bad_fn), ex))
        if bad_vd:
            ex = ", ".join("%s(%s)" % (n, v) for n, v in bad_vd[:4])
            return False, ("판정이 `15` §4-4의 넷(유지·대체·유보·기록)"
                           " 밖인 행 "
                           "**%d개**: %s" % (len(bad_vd), ex))
        return True, "%d행 전부 판정" % total
    return True, "산출물 있음: %s" % os.path.basename(path)


def bar(st, d):
    done = [s[0] for s in STEPS if st["steps"].get(s[0], {}).get("done")]
    cur = next((s for s in STEPS if not st["steps"].get(s[0], {}).get("done")),
               None)
    line = "[진행 %d/%d단계" % (len(done), len(STEPS))
    if cur:
        out = os.path.join(d, cur[2]) if cur[2] else ""
        if cur[3] == "ledger" and os.path.exists(out):
            total, blank = ledger_rows(out)
            pct = 100.0 * (total - blank) / total if total else 0
            line += (" · %s %d/%d (%.0f%%) · 남음 %d"
                     % (cur[1], total - blank, total, pct, blank))
        else:
            line += " · %s 진행 중" % cur[1]
    else:
        line += " · 전 단계 완료"
    return line + "]"


def status(d, st):
    print("# 검수 진행 상태")
    print("")
    print("- 원고: %s" % st.get("manuscript", "(안 적힘)"))
    print("- 목표 저널: %s" % st.get("journal", "(안 적힘)"))
    print("")
    print("| 단계 | 이름 | 상태 |")
    print("|--|--|--|")
    cur = None
    for num, name, out, kind in STEPS:
        rec = st["steps"].get(num, {})
        if rec.get("done"):
            mark = "완료"
        elif rec.get("skip"):
            mark = "건너뜀(%s)" % rec.get("skip")
        else:
            mark = "**여기**" if cur is None else "-"
            if cur is None:
                cur = (num, name, out, kind)
        print("| %s | %s | %s |" % (num, name, mark))
    print("")
    if not cur:
        print("**전 단계 완료.**")
        print(bar(st, d))
        return
    num, name, out, kind = cur
    ok, why = gate(num, d, st)
    print("## 이번 턴에 할 일 하나")
    print("")
    print("**%s단계: %s**" % (num, name))
    print("")
    if kind == "ledger":
        path = os.path.join(d, out)
        total, blank = ledger_rows(path)
        q = QUOTA.get(num, 20)
        if total == 0:
            print("- 아직 대장이 없다. **대장부터 만든다** (`%s`)" % path)
            print("- 만들 때 판정 칸을 비워 둔다. 그 빈 칸이 곧 남은 일이다")
        else:
            first = total - blank + 1
            last = min(total, first + q - 1)
            print("- 대장: `%s` (전체 %d행, 판정 안 한 행 %d개)"
                  % (path, total, blank))
            print("- **이번 턴 몫: %d-%d행 (%d행)**" % (first, last, q))
            print("- 그 행만 판정하고 **멈춘다.** 다음 턴에 이어서 한다")
    else:
        print("- 산출물: `%s`" % (os.path.join(d, out) if out else "(파일 없음)"))
    print("- 관문: %s" % ("통과" if ok else why))
    print("")
    print("끝나면 `python progress.py --done %s` 를 돌린다."
          " **통과 못 하면 거부된다.**" % num)
    print("")
    print(bar(st, d))


def main():
    d = opt("--dir", "outputs")
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

    if "--init" in sys.argv:
        st = {"manuscript": opt("--init"), "journal": opt("--journal", ""),
              "steps": {}, "answers": {}, "notes": []}
        save(d, st)
        print("진행 상태를 만들었다: %s" % state_path(d))
        status(d, st)
        return

    st = load(d)
    if st is None:
        print("진행 상태가 없다. 먼저 `--init 원고.md` 로 시작한다.")
        return

    if "--note" in sys.argv:
        st["notes"].append(opt("--note"))
        m = re.match(r"\s*([0-9a-z\-]+)\s*[:：]", opt("--note") or "")
        if m:
            st.setdefault("answers", {})[m.group(1)] = opt("--note")
        save(d, st)
        print("적었다: %s" % opt("--note"))
        return

    if "--skip" in sys.argv:
        num = opt("--skip")
        why = opt("--why", "저자가 건너뛰기로 함")
        st["steps"].setdefault(num, {})["skip"] = why
        save(d, st)
        print("%s단계를 건너뜀으로 적었다. **보고서에도 적는다.** (%s)"
              % (num, why))
        return

    if "--check" in sys.argv or "--done" in sys.argv:
        num = opt("--check") or opt("--done")
        if num not in dict((s[0], s) for s in STEPS):
            print("그런 단계가 없다: %s" % num)
            return
        ok, why = gate(num, d, st)
        print("%s단계 관문: %s" % (num, "통과" if ok else "**막힘**"))
        print("- %s" % why)
        if "--done" in sys.argv:
            if ok:
                st["steps"].setdefault(num, {})["done"] = True
                save(d, st)
                print("완료로 적었다.")
                print("")
                print(bar(st, d))
            else:
                print("")
                print("**완료로 적지 않았다.** 위를 채운 뒤 다시 돌린다.")
        return

    status(d, st)


if __name__ == "__main__":
    main()
