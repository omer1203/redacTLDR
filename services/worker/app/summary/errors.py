"""Failures the summary stage reports to the user. The message never contains document text."""

from __future__ import annotations


class SummaryError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
