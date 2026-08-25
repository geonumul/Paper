# -*- coding: utf-8 -*-
"""대조 전에 텍스트를 정규화한다.

**왜 필요한가**: 도구가 "없다"고 한 것의 상당수가 원고 문제가 아니라 추출
문제였다. 실제로 하루에 다섯 번 났고 다섯 다 원문을 열어서야 알았다.

| 도구가 "없다"고 한 것 | 진짜 원인 |
|--|--|
| `artificial`, `influence`, `specific` | 추출이 합자(ﬁ, ﬂ)를 떨어뜨림 |
| `indicator` | PDF가 `indi- cator`로 줄을 끊음 |
| `,` 뒤 줄바꿈 검사가 안 걸림 | 파일이 CRLF인데 정규식은 LF |
| 숫자 `1,566` | 원문이 "One thousand five hundred and sixty six"로 풀어 씀 |
| 낱말 자체 | PDF가 낱말 안에 공백을 넣음(`strati ed`) |

앞의 셋은 여기서 처리한다. **뒤의 둘은 기계로 못 고친다.** 그래서 도구가
0을 낼 때는 원고보다 도구를 먼저 의심하고, 원문을 열어 확인한다.
"""
import re
import unicodedata

LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
}

QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": " - ", "−": "-",
    " ": " ",
}

_HYPHEN_BREAK = re.compile(r"(\w)[-‐‑]\s*\n\s*(\w)")


def norm_text(t, fold_accents=False):
    """합자 복원, 줄바꿈 붙임표 잇기, CRLF 통일, 따옴표·붙임표 통일."""
    for a, b in LIGATURES.items():
        t = t.replace(a, b)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _HYPHEN_BREAK.sub(r"\1\2", t)
    for a, b in QUOTES.items():
        t = t.replace(a, b)
    if fold_accents:
        t = "".join(c for c in unicodedata.normalize("NFKD", t)
                    if not unicodedata.combining(c))
    return t


def suspicious_zero(hits, total, label=""):
    """0이거나 지나치게 균일한 답이면 도구를 먼저 의심하라고 알린다."""
    msgs = []
    if total and hits == 0:
        msgs.append("**0건이다. 원고보다 도구를 먼저 의심한다.** 합자·줄바꿈"
                    " 붙임표·CRLF·풀어쓴 숫자·낱말 안 공백을 확인하고, 원문을"
                    " 한 편 열어 눈으로 대조한다.")
    if total and hits == total:
        msgs.append("**%d개 중 %d개, 전부 걸렸다. 너무 균일한 답은 도구가"
                    " 틀렸다는 신호다.** 형식을 하나 열어 확인한다."
                    % (total, hits))
    return ("\n".join(msgs) + ("  (%s)" % label if label and msgs else ""))


# 통화의 달러는 수식 구분자가 아니다. 이것을 안 가리면 `US$ 4 million`의
# 달러가 다음 달러와 짝지어 그 사이 본문을 통째로 수식으로 삼킨다.
# 실제로 7,876자(3.1-3.2절 전체)가 삼켜져 그 구간의 낱말이 전부
# "LaTeX 명령"으로 판정된 적이 있다.
_CURRENCY = re.compile(r"(?:US|A|C|NZ|HK|S)?\$(?=\s?[\d.,])|(?<=[A-Z])\$")
_MASK = ""


def mask_currency(t):
    """통화 달러를 임시 문자로 가린다. 수식 짝짓기 전에 부른다."""
    return _CURRENCY.sub(lambda m: m.group(0).replace("$", _MASK), t)


def unmask_currency(t):
    return t.replace(_MASK, "$")
