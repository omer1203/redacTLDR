"""OCR parser, Textract polling, and PDF inspection. No live AWS calls."""

import json
from pathlib import Path

import pytest

from services.worker.app.ocr import (
    OcrError,
    PageInspection,
    collect_textract_blocks,
    inspect_pdf,
    merge_ocr_payload,
    normalize_textract_blocks,
    start_or_resume_textract,
)

FIXTURE = Path(__file__).parent / "fixtures" / "textract_two_page.json"


def _blocks() -> list[dict]:
    return json.loads(FIXTURE.read_text())["Blocks"]


def test_normalize_two_pages_keeps_word_boxes() -> None:
    pages = normalize_textract_blocks(_blocks())
    assert [page["pageNumber"] for page in pages] == [1, 2]
    assert pages[0]["lines"][0]["text"] == "Ada Lovelace"
    assert pages[0]["lines"][0]["words"][0]["bbox"] == {"x": 0.1, "y": 0.2, "width": 0.08, "height": 0.02}
    assert pages[1]["lines"][0]["words"][0]["text"] == "Second"


def test_collect_follows_next_token() -> None:
    blocks = _blocks()
    split = 4  # page 1 blocks, then page 2 blocks

    class FakeTextract:
        def __init__(self) -> None:
            self.calls = 0

        def get_document_text_detection(self, **kwargs):
            self.calls += 1
            if kwargs.get("NextToken"):
                return {"JobStatus": "SUCCEEDED", "Blocks": blocks[split:]}
            return {"JobStatus": "SUCCEEDED", "Blocks": blocks[:split], "NextToken": "page-2"}

    client = FakeTextract()
    collected = collect_textract_blocks(client, "job-1", sleep=lambda _seconds: None, clock=lambda: 0.0)
    assert client.calls == 2
    assert len(normalize_textract_blocks(collected)) == 2


def test_collect_times_out_while_textract_is_in_progress() -> None:
    now = {"t": 0.0}

    def clock() -> float:
        return now["t"]

    def sleep(seconds: float) -> None:
        now["t"] += seconds

    class FakeTextract:
        def get_document_text_detection(self, **kwargs):
            return {"JobStatus": "IN_PROGRESS"}

    with pytest.raises(OcrError) as caught:
        collect_textract_blocks(FakeTextract(), "job-1", sleep=sleep, clock=clock, deadline_s=5)
    assert caught.value.code == "TEXTRACT_TIMEOUT"
    assert caught.value.retryable is True


def test_start_or_resume_does_not_call_textract_twice() -> None:
    calls = {"start": 0}

    class FakeTextract:
        def start_document_text_detection(self, **kwargs):
            calls["start"] += 1
            assert kwargs["DocumentLocation"]["S3Object"]["Name"] == "originals/a.pdf"
            return {"JobId": "job-1"}

    job_id, started = start_or_resume_textract(FakeTextract(), None, "bucket", "originals/a.pdf")
    assert started is True
    assert job_id == "job-1"
    resumed, started_again = start_or_resume_textract(FakeTextract(), job_id, "bucket", "originals/a.pdf")
    assert resumed == "job-1"
    assert started_again is False
    assert calls["start"] == 1


def test_merge_uses_pdf_page_size_and_word_count() -> None:
    pages = normalize_textract_blocks(_blocks())
    inspections = [
        PageInspection(page_number=1, width=612, height=792, has_text_layer=True),
        PageInspection(page_number=2, width=612, height=792, has_text_layer=False),
    ]
    payload = merge_ocr_payload(inspections, pages)
    assert payload["pageCount"] == 2
    assert payload["pages"][0]["width"] == 612
    assert payload["pages"][0]["wordCount"] == 2
    assert payload["pages"][1]["hasTextLayer"] is False


def test_inspect_pdf_reads_size_and_text_layer() -> None:
    import pymupdf

    document = pymupdf.open()
    first = document.new_page(width=200, height=100)
    first.insert_text((10, 40), "Ada")
    document.new_page(width=200, height=100)
    pdf_bytes = document.tobytes()
    document.close()

    pages = inspect_pdf(pdf_bytes)
    assert len(pages) == 2
    assert pages[0].width == 200
    assert pages[0].has_text_layer is True
    assert pages[1].has_text_layer is False


def test_inspect_pdf_rejects_corrupt_bytes() -> None:
    with pytest.raises(OcrError) as caught:
        inspect_pdf(b"this is not a pdf")
    assert caught.value.code == "UNSUPPORTED_PDF"
    assert caught.value.retryable is False
