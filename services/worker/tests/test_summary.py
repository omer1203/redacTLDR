"""R6 summary: safe-mode prompts, per-mode schemas, chunking, and the leak check. No Bedrock calls."""

from services.shared.summary_contract import MODE_SUMMARY_FIELDS, empty_summary
from services.worker.app.detection.page_text import build_page_text
from services.worker.app.summary.engine import ModelResult, generate_summary
from services.worker.app.summary.errors import SummaryError
from services.worker.app.summary.markdown import render_markdown
from services.worker.app.summary.schemas import MODELS, assert_models_match_contract
from services.worker.app.summary.source import build_source


class RecordingModel:
    def __init__(self, data: dict | None = None, *, leak: str = "") -> None:
        self.prompts: list[str] = []
        self.data = data
        self.leak = leak
        self.model_id = "fake"

    def complete(self, mode: str, system: str, user: str) -> ModelResult:
        self.prompts.append(user)
        body = dict(self.data or empty_summary(mode))
        if self.leak:
            body["experienceSummary"] = self.leak
        return ModelResult(data=body, input_tokens=5, output_tokens=3)


def _page(line: str, number: int = 1) -> dict:
    words = []
    column = 0
    for token in line.split(" "):
        words.append(
            {"text": token, "bbox": {"x": 0.05 + column * 0.01, "y": 0.1, "width": max(len(token), 1) * 0.01, "height": 0.02}}
        )
        column += len(token) + 1
    return {"pageNumber": number, "lines": [{"words": words}]}


def _span(page: dict, value: str) -> tuple[int, int]:
    text = build_page_text(page).text
    start = text.index(value)
    return start, start + len(value)


def test_models_match_the_shared_contract() -> None:
    assert_models_match_contract()
    assert set(MODELS) == set(MODE_SUMMARY_FIELDS)


def test_safe_mode_replaces_the_value_and_the_prompt_cannot_contain_it() -> None:
    page = _page("Jane Doe jane.doe@gmail.com engineer")
    start, end = _span(page, "jane.doe@gmail.com")
    source = build_source(
        {"pages": [page]},
        [{"entity_type": "EMAIL", "page_number": 1, "char_start": start, "char_end": end}],
        [],
        safe_mode=True,
    )
    assert "jane.doe@gmail.com" not in source.pages[0].text
    assert "[EMAIL]" in source.pages[0].text
    assert "engineer" in source.pages[0].text
    assert "jane.doe@gmail.com" in source.forbidden

    model = RecordingModel()
    generated = generate_summary(mode="resume_anonymization", pages=source.pages, forbidden=source.forbidden, model=model, max_pages=30)
    assert "jane.doe@gmail.com" not in model.prompts[0]
    assert generated.payload["skills"] == []
    rendered = render_markdown("Resume", generated.payload, safe_mode=True, truncated=False)
    assert "Generated from redacted text." in rendered
    assert "jane.doe@gmail.com" not in rendered


def test_safe_mode_off_sends_the_raw_text() -> None:
    page = _page("Jane Doe jane.doe@gmail.com")
    start, end = _span(page, "jane.doe@gmail.com")
    source = build_source(
        {"pages": [page]},
        [{"entity_type": "EMAIL", "page_number": 1, "char_start": start, "char_end": end}],
        [],
        safe_mode=False,
    )
    assert "jane.doe@gmail.com" in source.pages[0].text
    assert source.forbidden == ()


def test_a_repeated_redacted_value_fails_the_summary() -> None:
    page = _page("Contact jane.doe@gmail.com today")
    start, end = _span(page, "jane.doe@gmail.com")
    source = build_source(
        {"pages": [page]},
        [{"entity_type": "EMAIL", "page_number": 1, "char_start": start, "char_end": end}],
        [],
        safe_mode=True,
    )
    model = RecordingModel(leak="jane.doe@gmail.com")
    try:
        generate_summary(mode="resume_anonymization", pages=source.pages, forbidden=source.forbidden, model=model, max_pages=30)
    except SummaryError as exc:
        assert exc.code == "OUTPUT_LEAK" and exc.retryable is False
    else:
        raise AssertionError("expected OUTPUT_LEAK")


def test_an_unlocated_selection_is_not_sent() -> None:
    page = _page("Nothing sensitive here")
    try:
        build_source(
            {"pages": [page]},
            [{"entity_type": "EMAIL", "page_number": 1, "char_start": None, "char_end": None, "bbox": {"x": 0.9, "y": 0.9, "width": 0.05, "height": 0.02}}],
            [],
            safe_mode=True,
        )
    except SummaryError as exc:
        assert exc.code == "REDACTION_UNLOCATED"
    else:
        raise AssertionError("expected REDACTION_UNLOCATED")


def test_each_mode_accepts_its_own_shape() -> None:
    page = _page("A short document")
    source = build_source({"pages": [page]}, [], [], safe_mode=True)
    for mode in MODELS:
        model = RecordingModel()
        generated = generate_summary(mode=mode, pages=source.pages, forbidden=(), model=model, max_pages=30)
        assert set(generated.payload) == set(MODE_SUMMARY_FIELDS[mode])


def test_long_documents_are_chunked_then_merged() -> None:
    pages = [_page(f"Section {number} stays", number) for number in range(1, 8)]
    source = build_source({"pages": pages}, [], [], safe_mode=False)
    model = RecordingModel()
    generated = generate_summary(mode="legal_contract_review", pages=source.pages, forbidden=(), model=model, max_pages=30)
    # 7 pages, 6 per call: two partials and one merge.
    assert len(model.prompts) == 3
    assert "part 1 of 2" in model.prompts[0]
    assert "Merge these partial summaries" in model.prompts[2]
    assert generated.calls == 3 and generated.truncated is False


def test_pages_past_the_cap_are_left_out() -> None:
    pages = [_page(f"Section {number}", number) for number in range(1, 5)]
    source = build_source({"pages": pages}, [], [], safe_mode=False)
    model = RecordingModel()
    generated = generate_summary(mode="resume_anonymization", pages=source.pages, forbidden=(), model=model, max_pages=2)
    assert generated.truncated is True and generated.pages_used == 2
    assert "page 3" not in model.prompts[0]


def test_manual_box_words_are_tokenized() -> None:
    page = _page("Meet Jane Doe tomorrow")
    text = build_page_text(page)
    jane = next(word for word in text.words if text.text[word.start : word.end] == "Jane")
    source = build_source(
        {"pages": [page]},
        [],
        [{"entity_type": "CUSTOM", "page_number": 1, "bbox": jane.bbox}],
        safe_mode=True,
    )
    assert "Jane" not in source.pages[0].text.split("[CUSTOM]")[0]
    assert "[CUSTOM]" in source.pages[0].text
    assert "tomorrow" in source.pages[0].text
