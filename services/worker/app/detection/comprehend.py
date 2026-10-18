"""Amazon Comprehend `DetectPiiEntities` for one page of text.

Comprehend accepts at most 100 KB of UTF-8 per request. Long pages are split
at line breaks (or spaces, or a hard cut as a last resort) and each result is
shifted back to page offsets. An entity that straddles a split is cut in two;
splits land on line breaks, so this only affects text near a 90 KB boundary.
"""

from __future__ import annotations

from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from services.worker.app.detection.models import Candidate, DetectionError

MAX_REQUEST_BYTES = 90_000
LANGUAGE_CODE = "en"

_RETRYABLE_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "InternalServerException",
    "ServiceUnavailableException",
}
_NOT_PERMITTED_CODES = {"AccessDeniedException", "UnrecognizedClientException"}


class PiiDetector(Protocol):
    def detect(self, text: str) -> list[Candidate]: ...


class ComprehendClient(Protocol):
    def detect_pii_entities(self, **kwargs: Any) -> dict[str, Any]: ...


def _byte_len(char: str) -> int:
    return len(char.encode("utf-8", "replace"))


def chunk_text(text: str, max_bytes: int = MAX_REQUEST_BYTES) -> list[tuple[int, str]]:
    """Split `text` into `(offset, chunk)` pairs, each at most `max_bytes` of UTF-8."""
    if max_bytes < 4:
        raise ValueError("max_bytes must fit at least one UTF-8 character")
    chunks: list[tuple[int, str]] = []
    start = 0
    length = len(text)
    while start < length:
        size = 0
        end = start
        while end < length and size + _byte_len(text[end]) <= max_bytes:
            size += _byte_len(text[end])
            end += 1
        if end >= length:
            cut = length
        else:
            window = text[start:end]
            newline = window.rfind("\n")
            space = window.rfind(" ")
            if newline > 0:
                cut = start + newline
            elif space > 0:
                cut = start + space
            else:
                cut = end
        piece = text[start:cut]
        if piece.strip():
            chunks.append((start, piece))
        start = cut
        while start < length and text[start] in "\n ":
            start += 1
    return chunks


def map_client_error(exc: ClientError) -> DetectionError:
    code = exc.response.get("Error", {}).get("Code") or ""
    if code in _NOT_PERMITTED_CODES:
        return DetectionError(
            "DETECTION_NOT_PERMITTED",
            "This AWS account is not allowed to call Comprehend.",
            retryable=False,
        )
    if code == "UnsupportedLanguageException":
        return DetectionError(
            "DETECTION_UNSUPPORTED_LANGUAGE",
            "Sensitive-data detection supports English documents only.",
            retryable=False,
        )
    if code == "TextSizeLimitExceededException":
        return DetectionError("DETECTION_FAILED", "A page was too large to check.", retryable=False)
    return DetectionError(
        "DETECTION_FAILED",
        "Sensitive-data detection failed. You can retry.",
        retryable=code in _RETRYABLE_CODES or not code,
    )


class ComprehendPiiDetector:
    def __init__(
        self,
        client: ComprehendClient | None = None,
        *,
        region_name: str = "us-east-1",
        language_code: str = LANGUAGE_CODE,
        max_bytes: int = MAX_REQUEST_BYTES,
    ) -> None:
        # Adaptive retries absorb short throttling bursts before the task-level retry kicks in.
        self._client = client or boto3.client(
            "comprehend",
            region_name=region_name,
            config=Config(retries={"max_attempts": 6, "mode": "adaptive"}),
        )
        self._language_code = language_code
        self._max_bytes = max_bytes

    def detect(self, text: str) -> list[Candidate]:
        candidates: list[Candidate] = []
        for offset, chunk in chunk_text(text, self._max_bytes):
            try:
                response = self._client.detect_pii_entities(Text=chunk, LanguageCode=self._language_code)
            except ClientError as exc:
                raise map_client_error(exc) from exc
            except NoCredentialsError as exc:
                raise DetectionError(
                    "DETECTION_NOT_PERMITTED", "AWS credentials are missing for detection.", retryable=False
                ) from exc
            except BotoCoreError as exc:
                raise DetectionError(
                    "DETECTION_FAILED", "Could not reach Comprehend. You can retry.", retryable=True
                ) from exc
            for entity in response.get("Entities") or []:
                begin = int(entity.get("BeginOffset", -1))
                end = int(entity.get("EndOffset", -1))
                if begin < 0 or end <= begin or end > len(chunk):
                    continue
                candidates.append(
                    Candidate(
                        start=offset + begin,
                        end=offset + end,
                        entity_type=str(entity.get("Type") or "UNKNOWN"),
                        confidence=float(entity.get("Score") or 0.0),
                        source="comprehend",
                    )
                )
        return candidates
