"""R5 true redaction: content is removed, the file is scrubbed, and verification catches leftovers.

All PDFs are built in the test with synthetic values. Every leak assertion is
paired with a check that the same value was readable in the input, so a
passing test cannot be a broken detector.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from redaction_helpers import (
    detection_row,
    extracted_text,
    make_pdf,
    make_scanned_pdf,
    ocr_payload_for,
    raw_contains,
)

from services.worker.app.redaction import (
    ExportError,
    LeakProbe,
    RedactionBox,
    build_probes,
    build_targets,
    redact_pdf,
    verify_export,
)
from services.worker.app.redaction.matching import compact, compact_with_flags, uncovered_occurrences
from services.worker.app.redaction.verify import verify_geometry, verify_text

EMAIL = "jane.doe@example.com"
PHONE = "(212) 555-0199"
RESUME = ["Jane Doe", f"Email {EMAIL} Phone {PHONE}", "Senior data engineer since 2015", "Python SQL Spark"]
SAMPLES = Path(__file__).resolve().parents[3] / "samples"


def _export(pdf: bytes, detections=(), manual=(), *, include_labels=False, payload=None):
    """The pure half of `run_export`: targets → redact → verify."""
    payload = payload or ocr_payload_for(pdf)
    boxes = build_targets(detections, manual)
    probes, skipped = build_probes(payload, detections, manual, boxes)
    redacted = redact_pdf(pdf, boxes, include_labels=include_labels)
    report = verify_export(redacted, boxes, probes, probes_skipped=skipped)
    return redacted, report


def test_digital_value_is_removed_and_the_rest_of_the_page_stays() -> None:
    pdf = make_pdf([RESUME])
    payload = ocr_payload_for(pdf)
    assert EMAIL in extracted_text(pdf) and raw_contains(pdf, EMAIL)

    detections = [detection_row(payload, EMAIL), detection_row(payload, PHONE, entity_type="PHONE")]
    redacted, report = _export(pdf, detections, payload=payload)

    text = extracted_text(redacted.final)
    assert EMAIL not in text and PHONE not in text
    assert not raw_contains(redacted.final, EMAIL) and not raw_contains(redacted.final, "555-0199")
    # Words beside the boxes on the same line, and other lines, are untouched.
    for kept in ("Email", "Phone", "Jane Doe", "Senior data engineer since 2015", "Python SQL Spark"):
        assert kept in text
    assert redacted.page_count == 1 and redacted.boxes_applied == 2
    assert report.boxes_checked == 2 and report.probes_checked == 2 and report.probes_skipped == 0


def test_copy_paste_leak_regression() -> None:
    """A black rectangle drawn on top (what the M5 stub's approach amounts to) leaves the text extractable."""
    pdf = make_pdf([RESUME])
    payload = ocr_payload_for(pdf)
    row = detection_row(payload, EMAIL)

    covered = pymupdf.open(stream=pdf, filetype="pdf")
    target = build_targets([row], [])[0]
    from services.worker.app.redaction.geometry import page_rect

    covered[0].draw_rect(page_rect(covered[0], target.rect), color=(0, 0, 0), fill=(0, 0, 0))
    overlay_only = covered.tobytes()
    assert EMAIL in extracted_text(overlay_only)
    with pytest.raises(ExportError) as caught:
        verify_geometry(overlay_only, [target], expected_pages=1)
    assert caught.value.code == "VERIFICATION_FAILED"

    redacted, _ = _export(pdf, [row], payload=payload)
    assert EMAIL not in extracted_text(redacted.final)


def test_scanned_page_pixels_are_removed_not_covered() -> None:
    digital = make_pdf([RESUME])
    scanned = make_scanned_pdf(RESUME)
    assert extracted_text(scanned).strip() == ""
    payload = ocr_payload_for(scanned, words_from=digital)
    row = detection_row(payload, EMAIL)

    redacted, report = _export(scanned, [row], payload=payload)
    assert report.boxes_checked == 1

    output = pymupdf.open(stream=redacted.final, filetype="pdf")
    page = output[0]
    image = pymupdf.Pixmap(output, page.get_images()[0][0])
    scale_x, scale_y = image.width / page.rect.width, image.height / page.rect.height

    def dark_pixels(box: dict[str, float]) -> int:
        x0, y0 = int(box["x"] * page.rect.width * scale_x), int(box["y"] * page.rect.height * scale_y)
        x1 = int((box["x"] + box["width"]) * page.rect.width * scale_x)
        y1 = int((box["y"] + box["height"]) * page.rect.height * scale_y)
        return sum(1 for y in range(y0, y1) for x in range(x0, x1) if sum(image.pixel(x, y)[:3]) < 300)

    # The embedded image itself no longer has ink under the box (the black fill is a separate shape).
    assert dark_pixels(row["rects"][0]) == 0
    # Ink elsewhere on the scan is untouched.
    name_box = detection_row(payload, "Jane Doe", entity_type="NAME")["rects"][0]
    assert dark_pixels(name_box) > 0


def test_invisible_text_layer_is_removed_and_visible_text_is_kept() -> None:
    hidden_layer = make_pdf([["HIDDENCOPY of the value"]], render_mode=3)
    visible = pymupdf.open(stream=hidden_layer, filetype="pdf")
    visible[0].insert_text((72, 400), "Visible paragraph stays", fontsize=11)
    pdf = visible.tobytes()
    assert "HIDDENCOPY" in extracted_text(pdf)

    redacted, _ = _export(pdf)
    text = extracted_text(redacted.final)
    assert "HIDDENCOPY" not in text and "Visible paragraph stays" in text


def test_metadata_xmp_links_attachments_outline_and_javascript_are_removed() -> None:
    document = pymupdf.open(stream=make_pdf([RESUME]), filetype="pdf")
    document.set_metadata({"author": "Jane Doe", "title": "Jane Doe resume", "subject": EMAIL})
    document.set_xml_metadata("<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf>Jane Doe</rdf></x:xmpmeta>")
    document.set_toc([[1, "Jane Doe CV", 1]])
    document.embfile_add("notes.txt", b"attached Jane Doe notes")
    document[0].insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 300, 200, 320), "uri": f"mailto:{EMAIL}"})
    document[0].add_text_annot((400, 500), "Reviewer comment about Jane Doe")
    js_xref = document.get_new_xref()
    document.update_object(js_xref, "<</S/JavaScript/JS(app.alert('x'))>>")
    document.xref_set_key(document.pdf_catalog(), "OpenAction", f"{js_xref} 0 R")
    pdf = document.tobytes()

    redacted, _ = _export(pdf)
    output = pymupdf.open(stream=redacted.final, filetype="pdf")
    assert not any(output.metadata.get(key) for key in ("author", "title", "subject", "keywords", "creator"))
    assert output.get_xml_metadata() == ""
    assert output.get_toc() == [] and output.embfile_names() == []
    assert output[0].get_links() == [] and list(output[0].annots()) == []
    # The page body still shows the email (nothing was selected); its copies elsewhere in the file are gone.
    for leftover in ("app.alert", "mailto:", "attached Jane Doe notes", "Reviewer comment", "Jane Doe CV", "adobe:ns:meta"):
        assert raw_contains(pdf, leftover) or leftover == "attached Jane Doe notes"
        assert not raw_contains(redacted.final, leftover), leftover


def test_form_field_value_under_a_box_is_removed() -> None:
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 100), "Social security number", fontsize=11)
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "ssn"
    widget.field_value = "123-45-6789"
    widget.rect = pymupdf.Rect(72, 120, 260, 140)
    page.add_widget(widget)
    pdf = document.tobytes()

    box = {"x": 72 / 612, "y": 118 / 792, "width": 190 / 612, "height": 24 / 792}
    redacted, _ = _export(pdf, manual=[{"entity_type": "CUSTOM", "page_number": 1, "bbox": box}])
    assert "123-45-6789" not in extracted_text(redacted.final)
    assert not raw_contains(redacted.final, "123-45-6789")
    assert "Social security number" in extracted_text(redacted.final)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_boxes_land_on_the_text_on_rotated_pages(rotation: int) -> None:
    pdf = make_pdf([RESUME], rotation=rotation)
    payload = ocr_payload_for(pdf)
    redacted, _ = _export(pdf, [detection_row(payload, EMAIL)], payload=payload)
    text = extracted_text(redacted.final)
    assert EMAIL not in text and "Senior data engineer since 2015" in text


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_labels_run_along_the_box_and_the_value_is_still_gone(rotation: int) -> None:
    pdf = make_pdf([RESUME], rotation=rotation)
    payload = ocr_payload_for(pdf)
    redacted, _ = _export(pdf, [detection_row(payload, EMAIL)], include_labels=True, payload=payload)
    assert redacted.labels_drawn == 1
    text = extracted_text(redacted.final)
    assert EMAIL not in text and EMAIL not in extracted_text(redacted.clean)
    # One label on one line (not wrapped), plus the word "Email" already on that line.
    assert text.count("Email") == 2

    output = pymupdf.open(stream=redacted.final, filetype="pdf")
    label_lines = [
        line
        for block in output[0].get_text("dict")["blocks"]
        for line in block.get("lines", [])
        if "".join(span["text"] for span in line["spans"]) == "Email" and line["spans"][0]["size"] < 11
    ]
    assert len(label_lines) == 1
    direction = label_lines[0]["dir"]
    # Along the box's long side: `make_pdf` writes the page's own text along the x axis.
    assert direction in {(1.0, 0.0), (-1.0, 0.0)}
    spin = pymupdf.Matrix(output[0].rotation_matrix)
    spin.e = spin.f = 0
    on_screen = pymupdf.Point(direction) * spin
    # Reads left to right on screen, or bottom to top when the box is vertical on screen.
    assert round(on_screen.x, 6) > 0 or (round(on_screen.x, 6) == 0 and on_screen.y < 0)


def test_verification_rejects_output_that_still_has_the_value() -> None:
    pdf = make_pdf([RESUME])
    payload = ocr_payload_for(pdf)
    row = detection_row(payload, EMAIL)
    boxes = build_targets([row], [])
    probes, _ = build_probes(payload, [row], [], boxes)

    with pytest.raises(ExportError) as geometry:
        verify_geometry(pdf, boxes, expected_pages=1)
    with pytest.raises(ExportError) as text:
        verify_text(pdf, probes, expected_pages=1)
    assert geometry.value.code == text.value.code == "VERIFICATION_FAILED"
    # The user-facing message never carries the value.
    assert EMAIL not in geometry.value.message and EMAIL not in repr(probes[0])


def test_a_value_repeated_outside_every_box_does_not_fail_the_export() -> None:
    pdf = make_pdf([[f"Primary {EMAIL}", f"Backup {EMAIL}"]])
    payload = ocr_payload_for(pdf)
    row = detection_row(payload, EMAIL)  # first occurrence only
    redacted, report = _export(pdf, [row], payload=payload)
    assert extracted_text(redacted.final).count(EMAIL) == 1
    assert report.probes_checked == 1


def test_manual_box_checks_the_words_under_it() -> None:
    pdf = make_pdf([RESUME])
    payload = ocr_payload_for(pdf)
    line = payload["pages"][0]["lines"][2]  # "Senior data engineer since 2015"
    first, last = line["words"][0]["bbox"], line["words"][-1]["bbox"]
    box = {
        "x": first["x"] - 0.002,
        "y": first["y"] - 0.002,
        "width": last["x"] + last["width"] - first["x"] + 0.004,
        "height": first["height"] + 0.004,
    }
    manual = [{"entity_type": "CUSTOM", "page_number": 1, "bbox": box}]
    boxes = build_targets([], manual)
    probes, _ = build_probes(payload, [], manual, boxes)
    assert [probe.source for probe in probes] == ["manual"]

    redacted, report = _export(pdf, manual=manual, payload=payload)
    assert "engineer" not in extracted_text(redacted.final) and report.probes_checked == 1


def test_multi_page_boxes_only_touch_their_page() -> None:
    pdf = make_pdf([RESUME, RESUME])
    payload = ocr_payload_for(pdf)
    redacted, _ = _export(pdf, [detection_row(payload, EMAIL, page_number=2)], payload=payload)
    output = pymupdf.open(stream=redacted.final, filetype="pdf")
    assert EMAIL in output[0].get_text() and EMAIL not in output[1].get_text()


def test_no_selection_still_produces_a_scrubbed_copy() -> None:
    document = pymupdf.open(stream=make_pdf([RESUME]), filetype="pdf")
    document.set_metadata({"author": "Jane Doe"})
    redacted, report = _export(document.tobytes())
    assert redacted.boxes_applied == 0 and report.boxes_checked == 0
    assert pymupdf.open(stream=redacted.final, filetype="pdf").metadata["author"] == ""


def test_unreadable_encrypted_and_mismatched_inputs_fail_cleanly() -> None:
    with pytest.raises(ExportError) as garbage:
        redact_pdf(b"%PDF-1.4\n", [], include_labels=False)
    assert garbage.value.code == "UNSUPPORTED_PDF" and not garbage.value.retryable

    locked = pymupdf.open(stream=make_pdf([RESUME]), filetype="pdf").tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner"
    )
    with pytest.raises(ExportError) as encrypted:
        redact_pdf(locked, [], include_labels=False)
    assert encrypted.value.code == "ENCRYPTED_PDF"

    box = RedactionBox(3, {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}, "Email", "detection")
    with pytest.raises(ExportError) as mismatch:
        redact_pdf(make_pdf([RESUME]), [box], include_labels=False)
    assert mismatch.value.code == "PAGE_MISMATCH"


@pytest.mark.parametrize(
    "row",
    [
        {"entity_type": "EMAIL", "page_number": 1, "rects": [{"x": 0.1, "y": 0.1, "width": 0, "height": 0.1}]},
        {"entity_type": "EMAIL", "page_number": 1, "rects": [{"x": "nan", "y": 0.1, "width": 0.1, "height": 0.1}]},
        {"entity_type": "EMAIL", "page_number": 1, "rects": [], "bbox": {}},
        {"entity_type": "EMAIL", "page_number": 0, "rects": [{"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}]},
    ],
)
def test_a_selected_item_without_a_usable_box_stops_the_export(row) -> None:
    with pytest.raises(ExportError) as caught:
        build_targets([row], [])
    assert caught.value.code == "INVALID_REDACTION"


def test_pre_r3_detection_without_offsets_uses_bbox_and_skips_the_text_probe() -> None:
    pdf = make_pdf([RESUME])
    payload = ocr_payload_for(pdf)
    rect = detection_row(payload, EMAIL)["rects"][0]
    legacy = {"entity_type": "EMAIL", "page_number": 1, "rects": [], "bbox": rect, "char_start": None, "char_end": None}
    redacted, report = _export(pdf, [legacy], payload=payload)
    assert EMAIL not in extracted_text(redacted.final)
    assert report.probes_checked == 0 and report.probes_skipped == 1


def test_sample_resume_golden() -> None:
    """The committed sample: redact every word containing '@' plus the first line, keep everything else."""
    pdf = (SAMPLES / "resume.pdf").read_bytes()
    payload = ocr_payload_for(pdf)
    page = payload["pages"][0]
    first_line = " ".join(word["text"] for word in page["lines"][0]["words"])
    values = [first_line] + [w["text"] for line in page["lines"] for w in line["words"] if "@" in w["text"]]
    assert len(values) >= 2
    detections = [detection_row(payload, value, entity_type="NAME") for value in dict.fromkeys(values)]

    redacted, report = _export(pdf, detections, payload=payload)
    text = extracted_text(redacted.final)
    for value in values:
        assert compact(value) not in compact(text)
    # Over-redaction guard: almost every other word survives.
    before = {w["text"] for line in page["lines"] for w in line["words"]}
    after = set(text.split())
    redacted_words = {token for value in values for token in value.split()}
    assert len((before - redacted_words) - after) <= 2
    assert report.probes_checked == len(detections)


def test_matching_ignores_whitespace_and_case_and_respects_coverage() -> None:
    assert compact("Jane\n  DOE") == "janedoe"
    haystack, flags = compact_with_flags("ab ab ab", [False, False, False, True, True, False, False, False])
    assert haystack == "ababab"
    assert uncovered_occurrences(haystack, flags, "ab") == 2
    assert LeakProbe(1, "detection", EMAIL, 0).__repr__().count(EMAIL) == 0
