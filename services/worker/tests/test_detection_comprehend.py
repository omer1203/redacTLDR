"""Comprehend chunking, offset mapping, and error handling. No live AWS calls."""

import pytest
from botocore.exceptions import ClientError

from services.worker.app.detection.comprehend import ComprehendPiiDetector, chunk_text
from services.worker.app.detection.models import DetectionError


class RecordingClient:
    """Returns one EMAIL entity at the position of every '@' word in each chunk."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def detect_pii_entities(self, **kwargs):
        text = kwargs["Text"]
        assert kwargs["LanguageCode"] == "en"
        self.calls.append(text)
        entities = []
        cursor = 0
        for token in text.replace("\n", " ").split(" "):
            if "@" in token:
                entities.append({"Type": "EMAIL", "Score": 0.99, "BeginOffset": cursor, "EndOffset": cursor + len(token)})
            cursor += len(token) + 1
        return {"Entities": entities}


def test_chunks_split_on_line_breaks_and_cover_the_text() -> None:
    text = "\n".join(f"line {index} a@b.co" for index in range(50))
    chunks = chunk_text(text, max_bytes=120)
    assert len(chunks) > 1
    for offset, chunk in chunks:
        assert len(chunk.encode("utf-8")) <= 120
        assert text[offset : offset + len(chunk)] == chunk
        assert not chunk.startswith("\n")
    # Every non-separator character lands in exactly one chunk.
    covered = sum(len(chunk) for _, chunk in chunks)
    assert covered == len(text) - (len(chunks) - 1)


def test_chunks_respect_multibyte_characters() -> None:
    text = "é" * 100
    chunks = chunk_text(text, max_bytes=50)
    assert all(len(chunk.encode("utf-8")) <= 50 for _, chunk in chunks)
    assert "".join(chunk for _, chunk in chunks) == text


def test_short_text_is_one_chunk() -> None:
    assert chunk_text("Jane Doe") == [(0, "Jane Doe")]
    assert chunk_text("   \n  ") == []


def test_offsets_are_mapped_back_to_the_page() -> None:
    text = "\n".join(f"row {index} person{index}@mail.com" for index in range(40))
    client = RecordingClient()
    hits = ComprehendPiiDetector(client, max_bytes=200).detect(text)
    assert len(client.calls) > 1
    assert len(hits) == 40
    for index, hit in enumerate(sorted(hits, key=lambda item: item.start)):
        assert text[hit.start : hit.end] == f"person{index}@mail.com"


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "DetectPiiEntities")


@pytest.mark.parametrize(
    ("code", "expected_code", "retryable"),
    [
        ("ThrottlingException", "DETECTION_FAILED", True),
        ("AccessDeniedException", "DETECTION_NOT_PERMITTED", False),
        ("UnsupportedLanguageException", "DETECTION_UNSUPPORTED_LANGUAGE", False),
        ("TextSizeLimitExceededException", "DETECTION_FAILED", False),
    ],
)
def test_client_errors_become_detection_errors(code: str, expected_code: str, retryable: bool) -> None:
    class FailingClient:
        def detect_pii_entities(self, **_kwargs):
            raise _client_error(code)

    with pytest.raises(DetectionError) as caught:
        ComprehendPiiDetector(FailingClient()).detect("Jane Doe")
    assert caught.value.code == expected_code
    assert caught.value.retryable is retryable
    assert "Jane" not in caught.value.message


def test_bad_offsets_from_the_service_are_dropped() -> None:
    class OddClient:
        def detect_pii_entities(self, **_kwargs):
            return {"Entities": [{"Type": "NAME", "Score": 0.9, "BeginOffset": 5, "EndOffset": 2}]}

    assert ComprehendPiiDetector(OddClient()).detect("Jane Doe") == []
