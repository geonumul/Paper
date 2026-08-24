# Submission statements

투고 시스템의 해당 칸에 붙여 넣는 내용이다. **익명 원고 파일에는 아무것도
들어가지 않는다.**

---

## 1. Data statement

> The data analysed in this study are publicly available from [출처 기관과
> 주소]. [무엇을 어디서 받았는지 한 문장.] The screening rules, hyperparameter
> grid, and feature definitions needed to rebuild the sample are stated in full
> in Sections [번호] and Appendix [문자].

코드를 공개하면 한 문장을 더한다.

> The analysis code is available at [저장소 주소].

## 2. CRediT author statement

역할 이름은 Elsevier 표준 목록에서만 고른다. 해당이 없는 역할은 쓰지 않는다.

> **저자 A:** Conceptualization, Methodology, Software, Formal analysis, Data
> curation, Investigation, Validation, Visualization, Writing - original draft.
> **저자 B:** Conceptualization, Project administration, Supervision, Writing -
> review and editing.

- **초고 작성(Writing - original draft)은 실제로 쓴 사람이 가져간다**
- 연구비를 받지 않았고 공개 자료를 개인 컴퓨터로 분석했으면 Funding
  acquisition과 Resources는 **존재하지 않으므로 뺀다.** 왜 뺐는지 내부 기록에
  한 줄 남긴다

## 3. Declaration of competing interests

신고할 것이 없으면 시스템에서 **"I have nothing to declare"**를 고른다.
별도 파일도 서명도 필요 없다.

## 4. Funding

> This research did not receive any specific grant from funding agencies in the
> public, commercial, or not-for-profit sectors.

## 5. Declaration of generative AI use

**저자만 무엇을 실제로 썼는지 말할 수 있다. 저자가 고른다.**

썼다면:

> During the preparation of this work the authors used [도구] in order to
> [목적]. After using this tool, the authors reviewed and edited the content as
> needed and take full responsibility for the content of the publication.

안 썼다면:

> The authors did not use generative AI or AI-assisted technologies in the
> preparation of this manuscript.

이 신고는 **원고 작성**에 대한 것이지 분석 자체가 아니다. 측정 도구로 쓴
모형은 방법 절에 보고하는 것이고 이 신고의 대상이 아니다.

## 6. Author biographies (Vitae)

요구하되 필수가 아니면 내지 않는다. (근거: 최근 게재작 N편 중 M편이 없음)

---

## 업로드 파일 목록

| 파일 | 내용 | 익명 |
|--|--|--|
| title_page | 저자·소속·교신저자·연구비 | 아니오 |
| manuscript (.tex와 컴파일된 PDF) | 본문·참고문헌·표·부록 | **예** |
| highlights | 항목 3-5개, 각 85자 이내 | 예 |
| fig1_이름 | Figure 1, 설명 | 예 |
| fig2_이름 | Figure 2, 설명 | 예 |

**파일 이름의 번호와 인쇄되는 그림 번호가 같아야 한다.** 위 순서대로 올린다.

원고 원본에는 저자·소속·ORCID가 없으므로, 컴파일된 PDF가 그대로 익명 본문이
된다.

그림 재현: `code/figN.py`. 옛 사본은 현재 문안과 어긋나므로 쓰지 않는다.
