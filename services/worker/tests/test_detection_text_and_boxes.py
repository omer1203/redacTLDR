"""Page text offsets and span → rectangle mapping."""

import pytest

from services.worker.app.detection.boxes import rects_for_span, union_boxes
from services.worker.app.detection.page_text import build_page_text


def test_page_text_joins_words_and_lines(resume_page) -> None:
    page = build_page_text(resume_page)
    assert page.text.split("\n")[1] == "jane.doe@gmail.com | (212) 555-0199"
    for word in page.words:
        assert page.text[word.start : word.end].strip() == page.text[word.start : word.end]
        assert " " not in page.text[word.start : word.end]


def test_page_text_skips_empty_lines_and_words(make_ocr_page) -> None:
    raw = make_ocr_page(["Ada", "", "Lovelace"])
    raw["lines"][0]["words"].append({"text": "   ", "bbox": {}})
    page = build_page_text(raw)
    assert page.text == "Ada\nLovelace"
    # The OCR line index is kept even though line 1 was empty.
    assert [word.line_index for word in page.words] == [0, 2]


def test_single_word_span_maps_to_word_box(resume_page) -> None:
    page = build_page_text(resume_page)
    start = page.text.index("jane.doe@gmail.com")
    rects = rects_for_span(page, start, start + len("jane.doe@gmail.com"))
    assert rects == [pytest.approx({"x": 0.1, "y": 0.13, "width": 0.18, "height": 0.02})]


def test_multi_word_span_unions_words_on_one_line(resume_page) -> None:
    page = build_page_text(resume_page)
    start = page.text.index("(212) 555-0199")
    rects = rects_for_span(page, start, start + len("(212) 555-0199"))
    assert len(rects) == 1
    # "(212)" starts at column 21; "555-0199" ends at column 35.
    assert rects[0] == pytest.approx({"x": 0.31, "y": 0.13, "width": 0.14, "height": 0.02})


def test_multi_line_span_gets_one_rect_per_line(resume_page) -> None:
    page = build_page_text(resume_page)
    value = "123 Main Street\nSpringfield, IL 62704"
    start = page.text.index(value)
    rects = rects_for_span(page, start, start + len(value))
    assert len(rects) == 2
    assert rects[0]["y"] == pytest.approx(0.19)
    assert rects[1]["y"] == pytest.approx(0.22)
    assert rects[1]["width"] == pytest.approx(0.21)


def test_partial_word_span_covers_the_whole_word(make_ocr_page) -> None:
    page = build_page_text(make_ocr_page(["Email:jane@x.com"]))
    start = page.text.index("jane@x.com")
    rects = rects_for_span(page, start, start + len("jane@x.com"))
    assert rects == [pytest.approx({"x": 0.1, "y": 0.1, "width": 0.16, "height": 0.02})]


def test_span_in_whitespace_has_no_rects(make_ocr_page) -> None:
    page = build_page_text(make_ocr_page(["Ada Lovelace"]))
    assert rects_for_span(page, 3, 4) == []


def test_union_boxes_clamps_to_page() -> None:
    box = union_boxes([{"x": -0.1, "y": 0.5, "width": 0.3, "height": 0.7}])
    assert box == {"x": 0.0, "y": 0.5, "width": 0.2, "height": 0.5}
    assert union_boxes([]) is None
