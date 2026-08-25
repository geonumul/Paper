# 9단계. 제출: Elsevier 규격, CAS LaTeX, 그림 파일, 서약

> **이 문서의 숫자를 그대로 쓰지 마세요.**
> 절차와 규칙은 분야·저널과 무관하게 쓰지만, 숫자와 사례는 **특허·건설 분야
> 논문 한 편(목표 저널 TFSC)에서 실제로 잰 값**입니다. 〔사례〕 표시가 붙은
> 것은 전부 그 논문 이야기입니다. **자기 저널에서 같은 방식으로 다시 재서
> 바꿔 넣으세요.** 무엇을 재는지가 이 문서의 내용이고, 얼마가 나오는지는
> 저널마다 다릅니다.


markdown 원고를 Elsevier CAS 이중단 양식으로 옮겨 컴파일하고 투고 파일을
만드는 전 과정이다. 여기서 실제로 시간을 가장 많이 잡아먹은 것은 **조판이
아니라 조판 때문에 생긴 원고-파일 불일치**였다.

---

## 1. 투고 규정을 먼저 표로 만든다

Guide for authors PDF를 받아 직접 읽고, 우리 값과 나란히 놓는다.

| 항목 | 규정 | 우리 |
|--|--|--|
| 초록 | 250낱말 이하 | 227낱말 (안전 여유를 두고 220낱말대로 관리) |
| 하이라이트 | 3-5개, 각 85자 | 5개, 최대 82자 |
| 키워드 | 1-7개, `and`/`of` 회피 | 6개 |
| 분량 | 별도 상한 없음 | 23쪽 |

- 초록에는 **인용을 넣지 않고, 정의되지 않은 약어를 쓰지 않는다**
- 하이라이트의 글자 수는 **공백 포함으로 센다.** 낱말 하나를 고쳐 88자가 되어
  상한을 넘긴 적이 있다. 하이라이트를 고치면 반드시 다시 센다
- 약어 규정은 보통 **키워드와 초록에만** 걸린다. 하이라이트의 `AUC`는 85자
  안에 풀어 쓸 수 없어 그대로 두었고, 그 판단 근거를 기록에 남겼다

## 2. 제출 폴더는 하나로

`제출/` 폴더만 그대로 올리면 되도록 만든다. **낡은 사본은 지운다.**

| 파일 | 내용 | 익명 |
|--|--|--|
| `00_읽어보기.md` | 무엇을 어디에 올리는지 (내부용) | - |
| `01_manuscript.pdf` / `.tex` | 본문·참고문헌·표·부록 | 예 |
| `02_title_page.md` | 저자·소속·교신저자·연구비 | 아니오 |
| `03_highlights.md` | 하이라이트 5개 | 예 |
| `04_declarations.md` | 서약·CRediT (올리는 파일이 아니라 **입력할 내용**) | - |
| `figures/figN_이름.pdf` `.png` | 그림 (PDF·PNG 각각) | 예 |

`00_읽어보기.md`에는 **어느 파일을 시스템의 어느 항목에 올리는지**를 표로
적는다. 투고는 대개 며칠 뒤에 하게 되고, 그때는 이 구조를 잊는다.

## 3. 이중 익명 심사

- 본문에 저자·소속·ORCID·사사·펀딩이 없어야 하고 **자기 인용도 없어야 한다**
- **PDF 메타데이터의 저자 항목도 비운다**(`08_AI티제거.md` §4)
- 본문·각주·감사의 말·파일 이름·저장소 주소에 실명이나 소속이 남아 있는지
  **직접 검색해서** 확인한다. 도구가 다 잡아 주지 않는다
- cas-common 일부 판본은 저자를 선언하지 않아도 빈 "ORCID(s):" 각주를 찍는다.
  `doubleblind` 옵션으로 항상 억제되지 않으므로 아래처럼 막는다

```latex
\makeatletter
\let\printorcid\relax
\makeatother
```

## 4. CAS LaTeX 조판

### 4-1. markdown에서 tex로

원고 정본은 markdown으로 두고 **변환 스크립트로 tex를 생성**한다. 손으로
tex를 고치기 시작하면 정본이 둘이 되어 반드시 어긋난다.

변환기는 **프로젝트마다 새로 쓴다**(원고 구조와 참고문헌 키가 프로젝트마다
다르므로 스킬에 넣지 않았다). 실제로 쓴 판은 프로젝트 저장소의
`scripts/md_to_cas_tex.py`에 있다. 하는 일은 이렇다.

- 앞머리: 제목·초록·하이라이트·키워드만. **저자 없음**
- `##`/`###` → `\section`/`\subsection`
- markdown 표 → booktabs `tabular`. **넓은 표는 `table*`(양단 통짜)**
- 본문 인용 표시 → `\citep`/`\citet` (참고문헌 목록에서 키를 만든다)
- 참고문헌 → `thebibliography` 블록(기존 문자열 유지)
- 그림 → `\includegraphics[width=...\textwidth]{figs/...}`
- 부록 → `\appendix` 뒤에 번호 체계를 재정의

```latex
\appendix
\renewcommand{\thesection}{Appendix \Alph{section}}
\renewcommand{\thetable}{\Alph{section}.\arabic{table}}
\renewcommand{\thefigure}{\Alph{section}.\arabic{figure}}
```

참고문헌 앞에는 `\clearpage`를 넣어 **부록의 부동체가 참고문헌 사이로 끼어
들어가지 않게** 한다.

### 4-2. 실제로 쓴 preamble과 그 이유

각 줄이 특정 사고를 막으려고 들어갔다. 그대로 재사용할 수 있다.

```latex
\documentclass[a4paper,fleqn,doubleblind]{cas-dc}
\usepackage[authoryear,longnamesfirst]{natbib}
\usepackage{array}

%% 부동체 배치. 한 쪽의 92%까지 허용하되 본문이 따라오게 하고,
%% 표·그림만으로 쪽을 차지하는 것은 85%를 채울 때만 허용한다.
\renewcommand{\topfraction}{0.92}
\renewcommand{\bottomfraction}{0.6}
\renewcommand{\textfraction}{0.08}
\renewcommand{\floatpagefraction}{0.85}
\setcounter{topnumber}{3}
\setcounter{totalnumber}{5}
\setcounter{dbltopnumber}{3}
\renewcommand{\dbltopfraction}{0.92}
\renewcommand{\dblfloatpagefraction}{0.85}

%% 클래스가 표 부동체 안에서 \centering을 유지해, 표 아래 주석이 줄마다
%% 가운데 정렬된다. 부동체 폭짜리 \parbox로 보통의 양끝맞춤을 되돌린다.
\newcommand{\tabnote}[1]{\par\vspace{2pt}\parbox{\tblwidth}{\footnotesize #1}}

%% 부동체 쪽의 여백. 부동체를 본문 틀 끝까지 늘리고 남는 공간은
%% 부동체 사이에 둔다(위아래에 몰리지 않게).
\makeatletter
\setlength{\@fptop}{0pt}    \setlength{\@fpsep}{10pt plus 1fil}
\setlength{\@fpbot}{0pt}    \setlength{\@dblfptop}{0pt}
\setlength{\@dblfpsep}{10pt plus 1fil}  \setlength{\@dblfpbot}{0pt}
\makeatother

%% 본문이 "Fig. 1"로 부르므로 캡션 라벨도 맞춘다.
\renewcommand{\figurename}{Fig.}

%% 두 단은 폭이 좁다. 어려운 줄에 여유를 주고 하이픈 뒤에서 끊기게 한다.
\emergencystretch=3em
\hyphenation{Patent-SBERTa BER-Topic}
```

`\maketitle` **뒤**에 `\flushbottom`을 둔다. cas-dc는 `twocolumn`을 클래스
옵션으로 넘기지 않아 `\raggedbottom`이 살아 있고, 그러면 단마다 끝 깊이가
달라진다. `\maketitle` 앞에 두면 클래스가 그 안에서 찍는 **하이라이트 쪽이
늘어난다.**

캡션 구분자가 콜론인 것이 저널 실물과 다르면 클래스 매크로를 재정의해
마침표로 바꾼다. 다른 것은 건드리지 않는다.

### 4-3. `\hspace{0pt}` 함정

두 단 조판에서 `co-occurrence`, `supplier-dominated` 같은 긴 낱말이 단 밖으로
넘친다. 하이픈 뒤에 분철점을 넣어 막는다.

```python
BREAK_AFTER_HYPHEN = ("co-occurrence", "supplier-dominated", "out-of-sample", ...)
t = t.replace(w, w.replace('-', '-\\hspace{0pt}'))
```

**이 처리를 하면 그 낱말은 문자열 검색·치환에 안 걸린다.** 원고를 고칠 때
`supplier-dominated`로 찾으면 tex에서는 안 나온다. 이 함정에 여러 번 걸렸다.

- 검색·치환은 **markdown 정본을 대상으로** 한다
- tex를 직접 봐야 하면 `supplier-` 처럼 **하이픈까지만** 넣고 찾는다
- 실제로 `\hspace{0pt}`가 72개 들어가 있었고, 개수를 세어 기록에 남겼다

## 5. Overleaf에서 조판하기

로컬에 LaTeX를 깔지 않고 **Overleaf에서 컴파일하는 것이 기본 경로**다.
클래스 파일이 갖춰져 있어 가장 덜 막힌다.

### 5-1. 올릴 것

```
manuscript.tex          변환기가 만든 것 (손으로 안 고친다)
figs/
  fig1_이름.pdf
  fig2_이름.pdf
  ...
cas-dc.cls              Overleaf에 없을 때만
cas-common.sty          Overleaf에 없을 때만
references.bib          thebibliography를 쓰면 필요 없다
```

- 그림은 **PDF로** 넣는다(벡터라 확대해도 안 깨진다). 파일 이름은 본문의
  `\includegraphics{figs/...}` 와 글자까지 같아야 한다
- 참고문헌을 `thebibliography` 블록으로 넣었으면 `.bib` 파일도 BibTeX 실행도
  필요 없다

### 5-2. 프로젝트 만들기 (둘 중 하나)

**방법 A: 통째로 올리기 (권장)**

1. 위 파일들을 한 폴더에 모아 **zip으로 압축**한다(폴더 구조를 그대로)
2. Overleaf에서 `New Project` → `Upload Project` → zip 선택
3. 올라간 뒤 `figs/` 폴더가 그대로 있는지 확인한다

**방법 B: 템플릿에서 시작**

1. `New Project` → `Templates` → Elsevier 계열 CAS 템플릿을 연다
2. 템플릿의 `main.tex`를 지우고 우리 `manuscript.tex`를 올린다
3. `figs/` 폴더를 만들어 그림을 올린다

템플릿에는 클래스 파일이 이미 들어 있어 "class not found"가 안 난다.

### 5-3. 설정 세 가지

Overleaf 왼쪽 위 `Menu`에서 확인한다.

| 설정 | 값 |
|--|--|
| **Compiler** | **pdfLaTeX** |
| **Main document** | `manuscript.tex` |
| **TeX Live version** | 최신(문제가 나면 한 판 낮춰 본다) |

### 5-4. 컴파일하고 확인할 것

`Recompile`을 누른 뒤 **로그(Logs and output files)를 연다.**

1. **오류 0건**
2. **Undefined citation / undefined reference 0건**
   (한 번에 안 잡히면 다시 컴파일한다. 참조는 두세 번 돌아야 자리를 잡는다)
3. **쪽수**를 확인한다(그림 하나 때문에 한 쪽이 늘어난 적이 있다)
4. 남는 경고가 **내가 건드린 자리인지** 가른다. `\maketitle` 근처나 부록 표
   번호 재설정에서 나는 Overfull hbox는 원래 있던 것일 수 있다
5. **부동체가 어디에 떨어졌는지 눈으로 본다.** 표만 있는 쪽, 빈 쪽, 참고문헌
   중간에 끼어든 표를 찾는다

### 5-4-2. 조판이 무너진 실제 사례 셋 〔사례〕

세 가지가 별개의 문제였는데 증상이 비슷해 한 문제로 착각했다.

**① 본문에 `??`가 깔렸다 - 조용한 실패**

서지를 **파일 참조**로 실어 보냈다. `ibliography{references_xai}`는 "`.bib`과
`.bst`를 찾아 bibtex을 돌려라"라는 뜻인데, 그 프로젝트에는 템플릿이 딸려 준
다른 이름의 파일만 있었다. **그리고 `.bst`를 못 찾은 bibtex은 오류를 내지
않고 조용히 실패한다.** 화면에는 "성공"이 뜨고 본문에는 `??`가 깔렸다.

> **시끄럽게 실패했으면 첫날 잡혔다.** 조용히 실패하는 도구를 찾아 두는 것이
> 이 단계의 핵심이다. 로그에 오류가 없다고 성공한 것이 아니다.

**해결한 방법**: 작동하는 게재작 tex를 구해 **한 줄씩 diff**했다. 차이는 한
곳이었다. 그쪽은 `ibitem` 75개를 **tex 안에** 갖고 있었다.

> 그때까지는 템플릿 문서를 읽으며 "이렇게 하라고 되어 있다"로 작업했다.
> 문서도 맞고 우리 파일도 문서대로였는데, **문서가 전제하는 환경이 그
> 프로젝트에 없었다.** 배운 것은 조판 지식이 아니라 방법이다.
> **되는 실물이 있으면 스펙을 읽지 말고 diff한다.**

**② 고쳐 놨는데 다음 빌드에서 미정의 87건 - 일회성 수선**

인라인 서지를 손으로 넣어 고쳤더니 다음 빌드에서 다시 무너졌다. 변환기가
**매번 tex를 새로 쓰기** 때문이다.

> **일회성 수선은 재생성 파이프라인에서 죽는다.** 고침은 손이 아니라
> **변환 단계에 넣는다.** 이 규칙은 §5-7과 같은 말이다.

**③ 그림 크기가 제각각 - 잘라내기 설정**

그림을 저장할 때 잉크에 맞춰 여백을 잘라내는 설정(`savefig`의 `bbox=tight`)을
쓰면 **파일 폭이 그림마다 달라진다.** 그 상태로 본문 폭에 맞추라고 하면
LaTeX이 각각 다른 배율로 늘리거나 줄인다. 그 결과 **같은 8pt로 그렸는데
인쇄면에서는 한 그림이 9.9pt, 다른 그림이 7.4pt**가 되었다(배율 1.16배와
0.97배).

> **그림은 목표 폭을 정해 두고 그 폭으로 저장한다.** 자동 잘라내기를 쓰면
> 폭이 흔들린다. 자세한 것은 `09_그림과표.md` §10-3.

### 5-5. 자주 나는 오류와 처방

| 오류 | 뜻 | 처방 |
|--|--|--|
| `File 'cas-dc.cls' not found` | 클래스 파일이 없다 | 출판사 템플릿에서 `cas-dc.cls`와 `cas-common.sty`를 받아 프로젝트에 올린다 |
| `File 'stfloats.sty' not found` | 부동체 꾸러미 | Overleaf에는 대개 있다. 없으면 `sttools`의 해당 파일을 올린다 |
| `File 'figs/fig1.pdf' not found` | 경로·확장자 불일치 | 폴더 이름, 파일 이름, 대소문자를 본문과 맞춘다 |
| `Undefined control sequence 	abnote` | preamble이 빠졌다 | 변환기가 만든 preamble이 통째로 들어갔는지 본다 |
| 인용이 `[?]`로 나온다 | 참조가 안 잡혔다 | 다시 컴파일. `thebibliography`면 키 철자를 본다 |
| 한글 주석에서 오류 | 인코딩 | 파일을 **UTF-8**로 저장해 다시 올린다 |
| 표가 판면을 넘는다 | 열이 넓다 | `table*`로 바꾸거나 열을 줄인다(§8) |

### 5-6. 내려받고 마무리

1. `Download PDF`로 받는다. tex도 `Download source`로 함께 받아 둔다
2. **PDF 속성을 확인한다.** 작성자 항목이 비어 있어야 한다(익명 심사)
3. 필요하면 파일 위생 절차를 돌린다(`08_AI티제거.md` §6)
4. 받은 tex와 PDF를 **제출 폴더에 넣는다**(§2)
5. **인쇄된 PDF에서 글자를 뽑아** 최근 수정이 실제로 들어갔는지 본다

### 5-7. Overleaf에서 직접 고치지 않는다

**정본은 markdown이고 tex는 그것에서 생성된 파생물이다**(`11_기록운영.md` §5-2).
Overleaf 화면에서 문장을 고치면 정본과 갈라지고, 다음에 변환기를 돌리는 순간
그 수정이 사라진다.

- 문장을 고칠 일이 생기면 **markdown을 고치고 다시 변환해 올린다**
- 조판만의 문제(부동체 위치, 줄 넘침)는 **preamble이나 변환기에서** 고친다
- 급해서 Overleaf에서 직접 고쳤으면 **그날 안에 markdown에 되옮긴다.**
  안 옮기면 다음 판에서 되돌아간다

**협업할 때**: Overleaf 공유 링크에는 편집 이력(History)에 이름이 남는다.
익명 심사용 파일을 만들 때는 그 점을 염두에 둔다.

## 5-0. 컴파일 환경 (참고)

- **Overleaf**: cas-dc.cls와 cas-common.sty가 갖춰져 있어 가장 간단하다.
  로컬에 LaTeX가 없으면 여기서 컴파일한다. 컴파일 없이 확인할 수 있는 것은
  올리기 전에 전부 확인해 둔다(§6)
- **로컬(Windows)**: MiKTeX를 winget으로 설치하면 cas-dc 클래스는 자동으로
  받아 온다. 다만 **`stfloats.sty`(sttools 꾸러미)는 수동 설치**가 필요했다
- **`pdflatex`를 3회 돌린다.** 참조·인용·목차가 안정되려면 그렇다

## 6. 컴파일 없이 미리 확인할 것

Overleaf에 올리기 전에 tex 문법을 눈으로 검산한다. 실제로 이 목록으로 잡았다.

- **중괄호 개수가 짝이 맞는가**(867 대 867로 확인)
- 본문에 곧은 따옴표(`"`)가 없는가. 여닫이(``` `` ``` / `''`)가 깊이 어긋남 없이
  짝지어지는가
- `\citep[p.~356]{key}` 같은 natbib 선택인자 형식이 정상인가, 묶음빈칸(`~`)이
  들어갔는가
- 새 따옴표가 명령어 인자 안으로 들어가지 않았는가
- `\hspace{0pt}` 개수가 그대로인가, em dash 0건인가
- 참고문헌의 `pp. 785-794` 같은 쪽 범위는 정상이다(물결표 금지 규칙의 예외가
  아니라 하이픈이므로 그대로 둔다)

## 7. 컴파일 뒤 검증

1. **오류 0건, 미해결 참조(undefined citation/reference) 0건**을 로그에서 확인
2. **쪽수**를 확인한다(그림 하나 때문에 한 쪽이 늘어난 적이 있다)
3. **인쇄된 PDF에서 글자를 뽑아** 고친 내용이 실제로 들어갔는지 본다
4. 남는 경고는 **내가 건드린 영역인지** 가른다. `\maketitle` 근처와 부록 표
   번호 재설정 구조의 Overfull hbox·중복 앵커 경고는 원래 있던 것이었다
5. 합자(`fi`, `ff`) 추출 차이는 조판기마다 다르므로 **내용 차이와 구분한다**
6. 부동체가 실제로 어디에 떨어졌는지 **쪽을 렌더링해 눈으로 본다**

> **혼동 사례**: `\ref{fig3}`가 PDF에서 "Fig. 6"으로 렌더링되어 오류인 줄 알았다.
> 확인해 보니 본문의 참조도 똑같이 "Fig. 6"으로 나오고, 그 그림이 문서 등장
> 순서상 여섯 번째라서 그런 것이었다. `\label{fig3}`은 옛 편집 순서의 흔적일
> 뿐 독자에게 보이는 번호에는 영향이 없다. **결함이 아니었다.**
> 다만 이런 혼동을 피하려면 label 이름을 인쇄 번호와 맞춰 두는 편이 낫다.

**정리**: 검증에 쓴 `page-*.png`, `manuscript_check.txt`, `aux`/`out`/`log`는
지운다. PDF는 남긴다.

## 8. 표·그림을 옮기다 생기는 일

- 표를 본문에서 부록으로 옮기면 `table*` → `table`, `tabular` →
  `tabular*{\tblwidth}`로 함께 바꿔야 한다. 옮긴 뒤 ①행·열 개수가 같은지
  ②환경 짝과 컬럼 스펙이 맞는지 ③재컴파일에 새 오류가 없는지 셋을 확인한다
- **부록에 표가 많으면 한 단으로 조판**하는 편이 낫다
- "Appendix A." 제목만 있고 내용이 다음 쪽에 나오거나, 참고문헌이 나오다가
  아래가 비고 오른쪽 단에서 다시 시작하는 것은 **부동체 배치 문제**다. §4-2의
  분수 값으로 조정한다

## 8-2. 참고문헌 목록 만들기

목록을 손으로 관리하면 반드시 어긋난다. **본문에서 뽑아서 만든다.**

### 절차

1. **본문 인용을 전수로 뽑는다**
   ```bash
   grep -ohE "\cite[a-z]*\{[^}]+\}" 원고.tex | sort | uniq -c | sort -rn
   grep -ohE "\([A-Z][A-Za-z'-]+( (and|&) [A-Z][A-Za-z'-]+| et al\.)?,? [12][0-9]{3}[a-z]?\)" 원고.md | sort | uniq -c
   ```
   실제로 이 방식으로 인용 49개를 뽑아 목록을 새로 만들었다

2. **양방향으로 대조한다**
   - 본문에 있는데 목록에 없는 것 (필수 수정)
   - 목록에 있는데 본문에 없는 것 (**미인용 항목. 뺀다**)
   - 인용을 하나 지우면 그 문헌이 유일 인용이었는지 반드시 확인한다

3. **항목마다 원문 표지와 대조한다**(`02_통독_기록형식.md` §12)
   - 저자·연도·저널·권·호·쪽수
   - **판본**: 워킹페이퍼인가 게재본인가
   - 파일명과 기억을 믿지 않는다. **"확인됨" 표시가 붙은 옛 자료에서도 오류가
     나왔다**
   - 소프트웨어 논문을 알고리즘 원전으로 인용하고 있지 않은지 훑는다

4. **제목을 소리 내 읽으며 방향을 검사한다**(`15_직접대조_검수.md` §6-2).
   제목에 `caution`, `myth`, `revisited`, `a note on`이 있으면 원문을 연다

5. **밀도를 대역과 맞춘다**
   - 개수(게재작 평균과 비교), **자기 저널 비율**(실측 14% 수준)
   - 연도 분포. 최신 연도가 너무 옛날이면 최근 문헌을 놓친 것이다

6. **서식을 저널 실물에 맞춘다**
   - `et al.`을 몇 명부터 쓰는가, 저자 이름 표기, 권·호·쪽 표기
   - DOI를 다는가, 다는 형식이 무엇인가
   - 게재작 서너 편의 참고문헌을 그대로 옆에 놓고 맞춘다

### 자주 나온 사고

- 인용을 지우면서 **목록의 항목을 안 지워 미인용 항목이 남았다**
- 파일명이 "(2021)"인데 실제 게재는 2020년이었다
- 저자가 아닌 사람이 저자로 들어가 있었다
- 워킹페이퍼를 게재본으로 적어 두었다(부록이 판본마다 다르다)

## 9. 서약과 CRediT

`04_declarations.md`에 시스템에 입력할 내용을 미리 적어 둔다. 틀은
`templates/서약_CRediT.md`에 있다.

**① 데이터 서약**: 자료의 출처와 접근 방법, 재현에 필요한 규칙이 본문 어디에
있는지 적는다. 코드를 공개하면 한 문장을 더한다.

**② CRediT**: 역할 이름은 Elsevier 표준 목록에서 고른다. 없는 역할은 쓰지
않는다. 실제로 쓴 예다.

> **저자 A:** Conceptualization, Methodology, Software, Formal analysis, Data
> curation, Investigation, Validation, Visualization, Writing - original draft.
> **저자 B:** Conceptualization, Project administration, Supervision, Writing -
> review and editing.

연구비와 자원 항목은 **해당이 없으면 빼고, 왜 뺐는지 내부 기록에 적는다**
(연구비를 받지 않았고 공개 자료를 개인 컴퓨터로 분석했으면 그 두 역할은
존재하지 않는다). **초고 작성(original draft)은 실제로 쓴 사람이 가져간다.**

**③ 이해충돌**: 신고할 것이 없으면 시스템에서 "I have nothing to declare"를
고른다. 별도 파일도 서명도 필요 없다.

**④ 연구비**: 없으면 표준 문구를 쓴다.

> This research did not receive any specific grant from funding agencies in the
> public, commercial, or not-for-profit sectors.

**⑤ 생성형 AI 사용 신고**: 대부분의 저널이 투고 시 요구한다. **무엇을 실제로
썼는지는 저자만 말할 수 있으므로 저자가 정한다.** 문구는 두 가지를 준비해 두고
고르게 한다.

> During the preparation of this work the authors used [도구] in order to
> [목적]. After using this tool, the authors reviewed and edited the content as
> needed and take full responsibility for the content of the publication.

> The authors did not use generative AI or AI-assisted technologies in the
> preparation of this manuscript.

이 신고는 **원고 작성**에 대한 것이지 분석 자체가 아니다. 측정 도구로 쓴
모형(예: 문서 임베딩 모형)은 방법 절에 보고하는 것이고 이 신고의 대상이 아니다.
그 구분을 서약 문서에 한 문장으로 적어 둔다.

**⑥ 저자 약력(Vitae)**: 요구하되 필수가 아니면 안 낸다. 최근 60편 중 26편이
아예 없다는 실측이 근거다.

## 10. 저장소 운영

- **AI 관련 흔적을 올리지 않는다.** 커밋 메시지에도 AI 서명을 넣지 않고,
  contributors에 아무것도 남기지 않는다
- **저널 대조 방법론을 저장소에 언급하지 않는다.** 용어와 말투는 그 기준으로
  하되 그 사실 자체는 적지 않는다
- 저작권물(출판사 PDF)은 사설 저장소라도 올리지 않는다. 재배포에 해당한다
- README는 국문·영문 두 벌, 간결하게. **정부과제 보고서라고 생각하고 쓴다.**
  말을 거는 문투, 친절한 척하는 군더더기, 제목 대신 쓰는 의문형을 쓰지 않는다
- 논문과 관련된 파일만 올린다. 주니어 개발자가 봐도 알아볼 수 있게

### 10-2. 자료와 코드를 공개할 때

**무엇을 담나**

| 담는 것 | 담지 않는 것 |
|--|--|
| 표·그림을 다시 만드는 스크립트 | 출판사 저작권이 있는 PDF |
| 표본을 다시 만드는 규칙(검색식·필터·하이퍼파라미터) | 재배포가 금지된 원자료 |
| 산출 결과 요약 파일 | 개인정보가 든 자료 |
| 국문·영문 README | 대화 기록·AI 관련 흔적 |

**언제 공개하나**

- **투고 시점**: 익명 심사면 저장소 주소가 저자를 드러낸다. 익명 저장소를 쓰거나,
  본문에는 "게재 시 공개"로 적고 심사자에게는 별도로 제공한다
- **게재 확정 후**: 주소를 본문에 넣고 공개로 돌린다

**공개 전에 확인**

- [ ] 스크립트를 **빈 폴더에서 받아 돌려** 실린 그림과 같은 것이 나오는가
- [ ] 원자료가 없어도 돌아가는지, 없으면 어디서 받는지 README에 적었는가
- [ ] 라이선스를 정했는가
- [ ] 저작권물·개인정보·AI 흔적이 없는가
- [ ] 데이터 서약(§9-1)이 저장소 주소와 맞는가

## 11. 마지막 점검 목록

```
□ 초록 낱말 수 / 하이라이트 개수·글자 수 / 키워드 개수가 규정 안
□ 본문에 저자·소속·ORCID·사사·자기인용 없음
□ PDF 메타데이터 저자 항목 비움
□ tex 컴파일 오류 0건, 미해결 참조 0건, 쪽수 확인
□ PDF에서 글자를 뽑아 최근 수정이 실제로 들어갔는지 확인
□ 그림 파일명 = \label = 인쇄 번호
□ 그림 PDF·PNG 둘 다, 재현 스크립트가 실제로 같은 그림을 만드는지 확인
□ 표 안의 셈 검산 (합계·차이·가중평균)
□ 제출 폴더에 낡은 사본 없음
□ CRediT·데이터·이해충돌·연구비·생성형 AI 문구 준비
□ 00_읽어보기.md에 업로드 순서 적힘
```
