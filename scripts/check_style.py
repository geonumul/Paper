# -*- coding: utf-8 -*-
"""원고 기계 검수기 (저널 무관 일반판).

쓰임:
  python check_style.py 원고.md --txt <게재작 코퍼스 폴더>
      **--txt를 주면 이음말 밀도와 쉼표 부담을 게재작에서 재서 판정한다.**
      안 주면 기본 대역을 쓰는데, 그 값은 **어느 저널에서도 잰 적이 없다.**
  python check_style.py <원고.md> [--config style_config.json]

검사 ①금지어·폐기 수치 ②이음말 밀도 ③약어 미정의 ④소수점 자리
     ⑤쉼표 4+ 문장 ⑥번호 나열 연속성 ⑦군말 반복 ⑧예고 시제 잔존
     ⑨영문 문법(기계 검사 가능분)

국문·영문 초안 모두 지원. 결과는 화면 + <원고>._style_report.md

프로젝트별 금지어·폐기 수치는 설정 파일에 둔다. 설정이 없으면 저널 무관
기본 규칙만 검사한다. 설정 파일 틀은 style_config.example.json 참고.
"""
import io
import json
import os
import re
import glob
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 저널 무관 기본 금지어 ────────────────────────────────────────
# (정규식, 왜 금지인가)
BANNED_DEFAULT = [
    # 최상급·처음 주장
    (r"\bnovel\b", "novel 남발은 게재작에서도 병리로 관찰됨"),
    (r"state[- ]of[- ]the[- ]art", "최상급 주장"),
    (r"for the first time|the first to", "'처음' 주장 금지"),
    (r"\bunveil", "과장 어휘"),
    (r"\bdisruptive\b", "판정 불가 어휘"),
    (r"\boutperform(s|ing|ed)? (all|the current|existing)", "과장. 비교표가 말하게"),
    (r"prove[sd]? that", "단정 회피. show/indicate로"),
    (r"우리가 처음|최초로|가장 먼저", "최상급·처음 금지"),
    (r"입증하였다|증명하였다", "단정 회피. '보였다/확인하였다'로"),
    # AI 티 상투구
    (r"delve", "AI향 금지어"),
    (r"landscape of", "AI향 비유"),
    (r"pivotal", "AI향 금지어"),
    (r"In today's", "AI향 상투구"),
    (r"rapidly evolving", "AI향 상투구"),
    (r"It is worth noting", "AI향 군말"),
    (r"It is important to note", "AI향 군말"),
    (r"plays? an? (crucial|vital|pivotal|key|important)? ?role", "AI향 상투구"),
    (r"underscore[sd]?", "AI향 금지어"),
    (r"foster(s|ing|ed)?", "AI향 금지어"),
    (r"not only", "남발 주의 (문서당 1회 이하 권장)"),
    # 국문 상투구
    (r"십여 년간|십수 년간", "모호한 기간 - 연도 명시로"),
    (r"널리 도입된|널리 활용되고", "구체 서술로"),
    (r"는지 규명하기 위해", "번역투 틀 - '~를 검토한다/확인한다'로"),
]

CONN_EN = ["However", "Therefore", "Moreover", "Furthermore", "Specifically",
           "Thus", "In addition", "Nevertheless", "In contrast", "Consequently",
           "Nonetheless", "Accordingly", "Likewise", "In turn", "Instead",
           "By contrast", "In short"]
CONN_KR = ["그러나", "따라서", "다만", "또한", "한편", "반면", "그러므로",
           "이에 비해", "요컨대", "아울러"]

HEDGE = [
    (r"we believe", 1, "반복 금지"),
    (r"is likely attributable|The likely reason", 1, "해석 문단 병리"),
    (r"\blikely\b", 4, "과다하면 해석 문단 병리"),
    (r"to the best of our knowledge", 1, "전체 1회 이하"),
    (r"it (should|must) be noted", 2, "군말"),
    (r"인 것으로 보인다", 4, "국문 군말 반복"),
    (r"할 수 있을 것이다", 3, "국문 군말 반복"),
]

EN_GRAMMAR = [
    (r"\b(is|are|was|were|been)\s+(occurred|happened|appeared|disappeared|"
     r"originated|resulted|participated|arrived)\b", "자동사 수동태 금지"),
    (r"\bis consisted of|\bis comprised of", "consist of는 능동만, comprise 수동은 비표준"),
    (r"\bsucceeded to \w", "succeeded in ~ing"),
    (r"\b(can|could|may|might|will|would|should|must)\s+"
     r"(?!be\b|have\b|not\b|also\b|only\b|still\b|thus\b|then\b|further\b|"
     r"potentially\b|likely\b|instead\b|need\b|exceed\b|proceed\b|succeed\b|"
     r"speed\b|feed\b|indeed\b)([a-z]+ed)\b", "조동사 뒤 동사원형 - 확인 필요"),
    (r"\bSimilar with|\bRelated with|\breplaced? \w+ to\b", "전치사 세트"),
    (r"\bon Figure \d", "in Figure"),
    (r"\bthe below\b|shown in below|in the below", "below는 형용사가 아니다"),
    (r"\bthe (Figure|Table|Case|Scenario|Model) \d", "번호 붙은 것에 the 금지"),
    (r"\beach [a-z]+s\b|\bper [a-z]+s\b", "each/per 뒤 단수 - 확인"),
    (r"\bevidences\b|\ban evidence\b|\binformations\b", "불가산 명사"),
    (r"\b(i\.e\.|e\.g\.)(?!,)", "i.e./e.g. 뒤 콤마"),
    (r"\bet\.\s?al|\bet al\b(?!\.)", "et al. 표기"),
    (r"e\.g\.[^.]*etc\.", "e.g.와 etc. 병용 금지"),
    (r"[a-z], (however|therefore|moreover|furthermore|thus), [a-z]",
     "접속부사 콤마 접속 금지 - 마침표나 세미콜론으로"),
    (r"(?<!\d)\.\d+\b", "소수점 앞 0 누락"),
    (r"\d\s?x\s?10", "곱셈은 ×"),
    (r"\b(don't|can't|it's|we've|doesn't|isn't|won't|didn't)\b", "축약형 금지"),
    (r"\bmay possibly|\bcould perhaps|might be probable", "이중 완화 금지"),
    (r"\bIt is well known that", "인용 필요 또는 'A is known to'"),
    (r"^\d+ [A-Za-z]", "문두 아라비아 숫자 - 'A total of'로"),
    (r"\bIt indicates|\bIt suggests\b|\bThis is consistent",
     "지시 대상 명시: This result indicates"),
    (r"—", "em dash 전면 금지"),
    (r"~(?=\s?\d)", "물결표 금지 - approximately로"),
    (r"\bsignificant", "통계 검정이 있는 자리인지 확인. 아니면 substantial/marked"),
    (r"\brespectively\b", "앞 목록과 개수 일치 수동 확인"),
]

FUTURE_METHOD = [
    r"is (evaluated|determined|measured|conducted) using(?!.*\(|.*Table|.*Fig)",
    r"we (will|plan to)",
    r"평가할 것이다|측정할 예정|하고자 한다",
]

KNOWN_ABBR_DEFAULT = ["AI", "US", "RQ", "PDF", "DOI", "AUC", "SVM", "LR", "RF"]

CFG_DEFAULT = {
    "banned": [],                       # [[정규식, 왜], ...] 프로젝트 전용 (폐기 수치 등)
    "allow_file": "_style_allow.txt",   # 사람이 판정 통과시킨 문장 목록
    "connective_band": [1.5, 4.0],      # 쪽당 이음말 횟수 대역
    "words_per_page": 500,
    "decimals": 3,                      # 성능 수치 소수점 자리
    "known_abbr": [],
    "use_defaults": True,
}


def corpus_band(txt_dir, conn_words):
    """게재작에서 이음말 밀도와 쉼표 부담을 재서 대역을 만든다.

    **기본 대역으로 판정하면 안 된다.** 이 도구의 기본값(쪽당 1.5-4.0회)은
    어느 저널에서도 잰 적이 없는 숫자다. 실제로 그 기본값으로 "대역 밖"이라
    보고했는데, 목표 저널 51편을 재 보니 사분위 한가운데였다.

    쪽 수는 조판에 달렸으므로 **1,000낱말당**으로 센다.
    """
    files = sorted(glob.glob(os.path.join(txt_dir, "*.txt")))
    dens, comma = [], []
    for f in files:
        t = io.open(f, encoding="utf-8", errors="replace").read()
        # 참고문헌은 뺀다. 서지에는 쉼표가 몰려 있다
        cands = [m.start() for m in re.finditer("References|Bibliography", t)
                 if m.start() > len(t) * 0.5]
        if cands:
            t = t[:cands[0]]
        nw = len(re.findall(r"[A-Za-z]+", t))
        if nw < 2000:
            continue
        n = 0
        for c in conn_words:
            n += len(re.findall(r"(?<![A-Za-z])" + re.escape(c) +
                                r"(?![A-Za-z])", t, re.I))
        dens.append(1000.0 * n / nw)
        sents = [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", t)
                 if len(x.split()) >= 5]
        if sents:
            comma.append(100.0 * sum(1 for x in sents if x.count(",") >= 4)
                         / len(sents))
    return dens, comma, len(dens)


def band_of(vals):
    v = sorted(vals)
    n = len(v)
    return (v[int(n * .25)], v[int(n * .5)], v[int(n * .75)], v[0], v[-1])


def opt_txt():
    """`--txt <게재작 코퍼스 폴더>`. 주면 대역을 거기서 잰다."""
    if "--txt" in sys.argv:
        i = sys.argv.index("--txt") + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return None


def load_cfg(path):
    cfg = dict(CFG_DEFAULT)
    if path and os.path.exists(path):
        cfg.update(json.load(open(path, encoding="utf-8")))
    return cfg


def load_allow(path):
    if path and os.path.exists(path):
        return [l.strip() for l in open(path, encoding="utf-8")
                if l.strip() and not l.startswith("#")]
    return []


def sentences(text):
    return re.split(r"(?<=[.!?다])\s+", text)


def main(path, cfg_path=None):
    cfg = load_cfg(cfg_path)
    raw = open(path, encoding="utf-8").read()
    allow = load_allow(cfg.get("allow_file"))
    banned = [(p, w) for p, w in cfg.get("banned", [])]
    if cfg.get("use_defaults", True):
        banned = banned + BANNED_DEFAULT

    all_lines = raw.split("\n")
    # 기록 블록(>)과 헤더(#)는 본문이 아니므로 검사에서 뺀다
    lines = [ln if not ln.lstrip().startswith((">", "#")) else ""
             for ln in all_lines]
    body = "\n".join(lines)
    prose = re.sub(r"\|[^\n]*\|", " ", body)              # 표 제거
    prose = re.sub(r"```.*?```", " ", prose, flags=re.S)  # 코드 블록 제거

    R = ["# 기계 검수 보고 · %s" % os.path.basename(path), ""]
    n_issue = 0

    # ① 금지어·폐기 수치
    R.append("## ① 금지어·폐기 수치")
    hits = []
    for pat, why in banned:
        for i, ln in enumerate(lines, 1):
            for m in re.finditer(pat, ln, re.I):
                # 정정 문맥(옛 값을 명시적으로 폐기한다고 적은 줄)은 통과
                if re.search(r"폐기|금지|버린|옛|아니라|았?던|→", ln):
                    continue
                if any(a in ln for a in allow):
                    continue
                hits.append((i, m.group(0), why, ln.strip()[:60]))
    if hits:
        n_issue += len(hits)
        R += ["|줄|걸린 것|왜|문맥|", "|--|--|--|--|"]
        R += ["|%d|%s|%s|%s|" % h for h in hits[:40]]
        if len(hits) > 40:
            R.append("(외 %d건)" % (len(hits) - 40))
    else:
        R.append("통과.")

    # ② 이음말 밀도
    nw = len(re.findall(r"[A-Za-z가-힣]+", prose))
    pages = max(0.5, nw / float(cfg["words_per_page"]))
    cnt = collections.Counter()
    for c in CONN_EN:
        n = len(re.findall(r"(?<![A-Za-z])" + re.escape(c) + r"(?![A-Za-z])",
                           prose, re.I))
        if n:
            cnt[c.lower()] = n
    for c in CONN_KR:
        n = len(re.findall(r"(?<![가-힣])" + re.escape(c), prose))
        if n:
            cnt[c] = n
    lo, hi = cfg["connective_band"]
    dens = sum(cnt.values()) / pages
    ok = lo <= dens <= hi
    comma_judged = None      # 게재작 대역으로 판정했는가
    txt_dir = opt_txt()
    if txt_dir:
        # 게재작에서 재서 판정한다. 기본 대역은 어느 저널 것도 아니다
        cd_, cc_, n_ = corpus_band(txt_dir, CONN_EN)
        if n_ >= 5:
            q1, med, q3, mn, mx = band_of(cd_)
            per_k = 1000.0 * sum(cnt.values()) / max(1, nw)
            ok = q1 <= per_k <= q3
            wide = mn <= per_k <= mx
            R += ["", "## ② 이음말 밀도 (게재작 %d편 실측)" % n_,
                  "- 1,000낱말당: 게재작 Q1 %.2f · 중위 **%.2f** · Q3 %.2f"
                  " (최소 %.2f, 최대 %.2f)" % (q1, med, q3, mn, mx),
                  "- 우리 **%.2f** → %s" % (per_k, "대역 안(사분위)" if ok else
                                          ("대역 안(전체 범위)" if wide
                                           else "**대역 밖**")),
                  "- " + ", ".join("%s %d" % kv for kv in cnt.most_common(8))]
            if not ok and not wide:
                n_issue += 1
            # 쉼표 부담도 같은 대역으로
            sents_ = [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", prose)
                      if len(x.split()) >= 5]
            if sents_ and cc_:
                q1c, medc, q3c, mnc, mxc = band_of(cc_)
                ours_c = 100.0 * sum(1 for x in sents_ if x.count(",") >= 4)                     / len(sents_)
                okc = q1c <= ours_c <= q3c
                R += ["- 쉼표 4개 이상 문장 비율: 게재작 Q1 %.1f%% · 중위"
                      " **%.1f%%** · Q3 %.1f%% / 우리 **%.1f%%** → %s"
                      % (q1c, medc, q3c, ours_c,
                         "대역 안" if okc else "**대역 밖**")]
                comma_judged = okc
                if not okc:
                    n_issue += 1
            return_early = True
        else:
            return_early = False
    else:
        return_early = False
    if not return_early:
        R += ["", "## ② 이음말 밀도 (대역 %.1f-%.1f회/쪽. **저널에서 잰 값이"
              " 아니다.** `--txt <게재작 폴더>`를 주면 실측한다)" % (lo, hi),
              "- 단어 약 %s (약 %.1f쪽) / 이음말 %d회 = **쪽당 %.1f회** %s"
              % ("{:,}".format(nw), pages, sum(cnt.values()), dens,
                 "OK" if ok else "대역 밖(기본값 기준이므로 판정 아님)"),
              "- " + ", ".join("%s %d" % (k, v) for k, v in cnt.most_common(8))]

    # ③ 약어 첫 등장 정의
    R += ["", "## ③ 약어 (첫 등장 정의)"]
    abbrs = collections.Counter(
        re.findall(r"(?<![A-Za-z])([A-Z]{2,6})(?![A-Za-z])", prose))
    known = set(KNOWN_ABBR_DEFAULT) | set(cfg.get("known_abbr", []))
    bad = []
    for a, n in abbrs.items():
        if a in known or n < 2:
            continue
        first = prose.find(a)
        window = prose[max(0, first - 120):first + 120]
        if "(" not in window:
            bad.append("%s(%d회, 정의 미확인)" % (a, n))
    R.append(("- 정의 확인 필요: " + ", ".join(bad)) if bad else "통과.")
    n_issue += len(bad)

    # ④ 소수점 자리 - **갈래별로** 본다
    # 백분율이 1자리이고 오즈비가 3자리인 것은 다른 갈래라서지 불일치가
    # 아니다. 한 통에 넣고 세어 헛된 경고를 낸 적이 있다.
    d = int(cfg["decimals"])
    flat = re.sub(r"[$\{}*]", "", prose)
    KIND = [("p 값(측정)", r"(?<![A-Za-z])p\s*=\s*(\d*\.\d+)"),
            ("오즈비", r"(?:OR|odds ratio)\s*=?\s*(\d*\.\d+)"),
            ("신뢰구간", r"\[\s*(\d*\.\d+)\s*[-–]"),
            ("AUC", r"(?:AUC|area under the (?:ROC )?curve)[^\d]{0,30}"
                    r"(\d*\.\d+)"),
            ("백분율", r"(\d+\.\d+)\s*%"),
            ("F1·정확도", r"(?:F1|accuracy|precision|recall)[^\d]{0,26}"
                        r"(\d*\.\d+)")]
    # 관행으로 굳은 임계값은 자릿수 판정에서 뺀다
    CONVENTION = {"0.05", "0.01", "0.001", "0.10", "0.5", "0.95", "0.90"}
    R += ["", "## ④ 소수점 (갈래별)"]
    mixed = 0
    for name, pat in KIND:
        got = collections.Counter()
        for m in re.finditer(pat, flat, re.I):
            v = next((g for g in m.groups() if g), None)
            if not v or v in CONVENTION:
                continue
            got[len(v.split(".")[1])] += 1
        if not got:
            continue
        txt = ", ".join("%d자리 %d개" % (k, n) for k, n in sorted(got.items()))
        if len(got) > 1:
            mixed += 1
            R.append("- **%s: %s → 한 갈래 안에서 섞였다**" % (name, txt))
        else:
            R.append("- %s: %s" % (name, txt))
    if not mixed:
        R.append("- 갈래 안에서 섞인 것 없음. 통과")
    n_issue += mixed
    R.append("- (0.05·0.01·0.001 같은 관행 임계값과 정의상 상수는 셈에서 뺐다)")

    # ⑤ 쉼표 4개 이상 문장 (인용 괄호·짧은 괄호의 쉼표는 세지 않는다)
    prose_nc = re.sub(r"\((?:[^()]*\d{4}[^()]*)\)", " ", prose)
    prose_nc = re.sub(r"\([^()]{0,90}\)", " ", prose_nc)
    longs = [s.strip()[:80] for s in sentences(prose_nc)
             if s.count(",") >= 4 and len(s) > 60]
    R += ["", "## ⑤ 쉼표 4개 이상 문장"]
    if comma_judged is not None:
        # 비율은 ②에서 게재작 대역과 견줬다. 여기서 다시 세지 않는다.
        # 개수만으로 지적하면 긴 문장을 쓰는 저널에서 전부 걸린다
        R.append("- 비율 판정은 ②에 있다(게재작 대역 대비 %s)."
                 " 아래는 눈으로 볼 후보일 뿐 지적이 아니다"
                 % ("대역 안" if comma_judged else "**대역 밖**"))
        R += ["- %d개:" % len(longs)] + ["  - %s…" % x for x in longs[:8]]
    elif longs:
        n_issue += len(longs)
        R += ["- %d개 (**게재작에서 잰 대역이 아니다.** `--txt`를 주면"
              " 비율로 판정한다):" % len(longs)]
        R += ["  - %s…" % x for x in longs[:8]]
    else:
        R.append("통과.")

    # ⑥ 번호 나열 연속성
    R += ["", "## ⑥ 번호 나열 연속성"]
    probs = []
    order = ["First", "Second", "Third", "Fourth", "Fifth"]
    seq = re.findall(r"\b(First|Second|Third|Fourth|Fifth|Finally)\b", prose)
    for a, b in zip(seq, seq[1:]):
        if a == b:
            probs.append("'%s' 연속 중복" % a)
        elif a in order and b in order and order.index(b) - order.index(a) > 1:
            probs.append("%s 다음에 %s (건너뜀)" % (a, b))
    ka = ["첫째", "둘째", "셋째", "넷째", "다섯째"]
    kr = re.findall(r"(첫째|둘째|셋째|넷째|다섯째)", prose)
    for a, b in zip(kr, kr[1:]):
        if a == b:
            probs.append("'%s' 연속 중복" % a)
        elif ka.index(b) - ka.index(a) > 1:
            probs.append("%s 다음에 %s (건너뜀)" % (a, b))
    R.append(("주의: " + "; ".join(probs)) if probs else "통과.")
    n_issue += len(probs)

    # ⑦ 군말 반복
    R += ["", "## ⑦ 군말 반복"]
    hh = []
    for pat, cap, why in HEDGE:
        n = len(re.findall(pat, prose, re.I))
        if n > cap:
            hh.append("'%s' %d회 (허용 %d) - %s" % (pat, n, cap, why))
    R += (["- " + h for h in hh] if hh else ["통과."])
    n_issue += len(hh)

    # ⑧ 예고 시제 잔존
    R += ["", "## ⑧ 예고 시제 잔존 ('평가한다'고 쓰고 값이 없는 병리)"]
    ff = []
    for pat in FUTURE_METHOD:
        for m in re.finditer(pat, prose, re.I):
            ff.append(m.group(0)[:60])
    R += (["- " + f for f in ff[:8]] if ff else ["통과."])
    n_issue += len(ff)

    # ⑨ 영문 문법
    R += ["", "## ⑨ 영문 문법 (기계 검사 가능분)"]
    eg = []
    for pat, why in EN_GRAMMAR:
        for i, ln in enumerate(lines, 1):
            for m in re.finditer(pat, ln, re.M):
                if any(a in ln for a in allow):
                    continue
                # 문두 숫자 검사는 앞 줄에서 문장이 이어진 경우 제외
                if pat.startswith("^") and i >= 2 and \
                        not re.search(r"[.!?]\s*$", all_lines[i - 2]):
                    continue
                eg.append((i, m.group(0)[:30], why))
    if eg:
        n_issue += len(eg)
        R += ["|줄|걸린 것|규칙|", "|--|--|--|"]
        R += ["|%d|%s|%s|" % e for e in eg[:30]]
        if len(eg) > 30:
            R.append("(외 %d건)" % (len(eg) - 30))
    else:
        R.append("통과.")

    R += ["", "---",
          "**문제 합계: %d** %s" % (n_issue, "→ 다음 겹(문단 카드)으로."
                                   if n_issue == 0 else "→ 고치고 재검."),
          "",
          "기계는 후보만 낸다. 판정은 사람이 한다. 통과시킨 문장은 예외 목록"
          "(%s)에 등재한다." % cfg.get("allow_file")]
    rep = "\n".join(R)
    out = os.path.splitext(path)[0] + "._style_report.md"
    open(out, "w", encoding="utf-8").write(rep)
    print(rep)
    return n_issue


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cfg = None
    if "--config" in sys.argv:
        cfg = sys.argv[sys.argv.index("--config") + 1]
    elif os.path.exists("style_config.json"):
        cfg = "style_config.json"
    if not args:
        print(__doc__)
        sys.exit(1)
    main(args[0], cfg)
