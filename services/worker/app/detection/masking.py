"""Masked display values such as `j***@g***.com`.

The masked value is what Postgres stores by default. It is enough for a
reviewer to tell items apart, and short masks hide the real length of words.
"""

from __future__ import annotations

MASK = "*"
MAX_MASKED_LENGTH = 128
_KEEP_TRAILING_DIGITS = 2
# Generic path segments that are not personal, kept so a profile link stays recognizable.
_PUBLIC_PATH_SEGMENTS = {"in", "pub", "u", "user", "users", "profile"}


def _mask_token(token: str) -> str:
    if not token:
        return token
    # Only a leading letter is kept; a leading digit would reveal a day, year, or house number.
    if len(token) == 1 or not token[0].isalpha():
        return MASK * min(len(token), 3)
    return token[0] + MASK * 3


def _mask_domain(domain: str) -> str:
    labels = domain.split(".")
    if len(labels) < 2:
        return _mask_token(domain)
    return ".".join([_mask_token(label) for label in labels[:-1]] + [labels[-1]])


def _mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    return f"{_mask_token(local)}@{_mask_domain(domain)}"


def _mask_url(value: str, *, keep_host: bool) -> str:
    scheme, separator, rest = value.partition("://")
    prefix = f"{scheme}://" if separator else ""
    if not separator:
        rest = value
    host, slash, path = rest.partition("/")
    masked_host = host if keep_host else _mask_domain(host)
    if not slash:
        return prefix + masked_host
    segments = [
        segment if not segment or segment.lower() in _PUBLIC_PATH_SEGMENTS else _mask_token(segment)
        for segment in path.split("/")
    ]
    return f"{prefix}{masked_host}/{'/'.join(segments)}"


def _mask_digits(value: str) -> str:
    """Keep separators and the last two digits: `(212) 555-0199` → `(***) ***-**99`."""
    kept = 0
    out: list[str] = []
    for char in reversed(value):
        if char.isdigit():
            out.append(char if kept < _KEEP_TRAILING_DIGITS else MASK)
            kept += 1
        elif char.isalpha():
            out.append(MASK)
        else:
            out.append(char)
    return "".join(reversed(out))


def mask_value(entity_type: str, raw: str) -> str:
    value = " ".join(raw.split())
    if not value:
        return ""
    if entity_type == "EMAIL" and value.count("@") == 1:
        masked = _mask_email(value)
    elif entity_type in {"URL", "SOCIAL_PROFILE_URL"}:
        # A personal site's host can be the person's name; a LinkedIn/GitHub host is not.
        masked = _mask_url(value, keep_host=entity_type == "SOCIAL_PROFILE_URL")
    else:
        digits = sum(char.isdigit() for char in value)
        letters = sum(char.isalpha() for char in value)
        if digits >= 4 and digits >= letters:
            masked = _mask_digits(value)
        else:
            masked = " ".join(_mask_token(token) for token in value.split(" "))
    return masked[:MAX_MASKED_LENGTH]
