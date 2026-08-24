# -*- coding: utf-8 -*-
"""PDF의 쪽을 PNG로 렌더링한다 (원문 대조·그림 양식 관찰용).

쓰임:  python pdf_render.py <pdf> <시작쪽> <끝쪽> [배율] [출력폴더]
예:    python pdf_render.py "literature/5_journal/Zamani 2022.pdf" 6 8 2.0

쓰는 때
  - OCR·스캔본에서 인용을 대조할 때. 텍스트 추출이 의심스러우면 눈으로 본다
  - 게재작의 그림 양식을 재려 할 때. 그림은 텍스트로 못 잰다
  - 우리 원고를 컴파일한 뒤 부동체가 어디에 떨어졌는지 볼 때

쪽 번호는 PDF의 물리적 쪽이다. 인쇄된 쪽 번호와 다를 수 있으니, 면주를 보고
차이를 확인한 뒤 인용에 쓴다.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return
    path, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    zoom = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
    out_dir = sys.argv[5] if len(sys.argv) > 5 else "."
    try:
        import fitz
    except ImportError:
        print("PyMuPDF가 필요합니다:  pip install pymupdf")
        return

    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(path)
    stem = os.path.splitext(os.path.basename(path))[0][:40]
    made = []
    for p in range(a, min(b, doc.page_count) + 1):
        page = doc.load_page(p - 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        out = os.path.join(out_dir, "%s_p%03d.png" % (stem, p))
        pix.save(out)
        made.append(out)
    doc.close()
    for m in made:
        print(m)
    print("%d쪽 렌더링. 확인이 끝나면 지운다." % len(made))


if __name__ == "__main__":
    main()
