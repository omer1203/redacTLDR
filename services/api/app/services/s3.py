"""
S3 helper utilities for object key naming and presigned URL generation.

The API currently uses presigned URLs so clients/workers can move files directly
to/from S3 without proxying file bytes through the API process.
"""

import time
import uuid
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from services.api.app.config import get_settings

_ALLOWED_UPLOAD_CONTENT_TYPES = {"application/pdf"}


def _client():
    """Create a short-lived S3 client configured for presigned URL signing."""
    settings = get_settings()
    region = settings.aws_region
    # Regional endpoint avoids global `s3.amazonaws.com` quirks (redirect chains, wrong region)
    # that can invalidate browser PUTs against presigned URLs.
    endpoint = f"https://s3.{region}.amazonaws.com"
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        config=Config(signature_version="s3v4"),
    )


def _bucket_originals() -> str:
    """Source-upload bucket used for original user documents."""
    return get_settings().s3_bucket_originals


def _bucket_downloads() -> str:
    """Output bucket used for generated/redacted exports."""
    return get_settings().s3_bucket_downloads


def redact_presigned_url_for_logging(url: str) -> str:
    """Strip query parameters (signatures and temporary credentials) before logging or support snippets."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def make_originals_key(user_id: str, document_id: uuid.UUID, filename: str) -> str:
    """
    Build a deterministic-ish, namespaced key for original uploads.

    - User-scoped prefix prevents cross-user key collisions.
    - Timestamp helps uniqueness for repeated filename uploads.
    - Filename is sanitized to avoid unsafe/path characters.
    """
    safe = "".join(c for c in filename if c.isalnum() or c in ".-_") or "doc.pdf"
    return f"originals/{user_id}/{document_id}/{int(time.time())}-{safe}"


def make_export_key(user_id: str, document_id: str, export_id: str | None = None) -> str:
    """Build output key for exported PDFs.

    With `export_id` (R5) every export gets its own object, so a re-export never
    overwrites a file someone may still be downloading. The short form is the
    pre-R5 layout, kept for rows that already point at it.
    """
    if export_id:
        return f"exports/{user_id}/{document_id}/{export_id}.pdf"
    return f"exports/{user_id}/{document_id}.pdf"


def redacted_download_name(filename: str) -> str:
    """`resume.pdf` → `resume-redacted.pdf`, ASCII-only so it is safe inside a Content-Disposition header."""
    stem = filename.rsplit(".", 1)[0] if filename.lower().endswith(".pdf") else filename
    safe = "".join(c if c.isascii() and (c.isalnum() or c in "-_") else "-" for c in stem).strip("-")
    return f"{(safe or 'document')[:100]}-redacted.pdf"


def _validate_upload_request(content_type: str, size_bytes: int | None) -> None:
    if content_type not in _ALLOWED_UPLOAD_CONTENT_TYPES:
        raise ValueError("unsupported content type")
    settings = get_settings()
    if size_bytes is not None and size_bytes > settings.max_upload_size_bytes:
        raise ValueError("file exceeds max upload size")


def presign_put(key: str, content_type: str, size_bytes: int | None = None, expires: int | None = None) -> str:
    """Presign PUT without binding Content-Type (avoids fragile browser MIME/SigV4 coupling). PUT raw bytes, no Content-Type header."""
    _validate_upload_request(content_type, size_bytes)
    settings = get_settings()
    requested_expiry = expires if expires is not None else settings.upload_presign_ttl_seconds
    expires_in = max(60, min(requested_expiry, 3600))
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket_originals(), "Key": key},
        ExpiresIn=expires_in,
    )


def presign_original_get(key: str, expires: int = 300) -> str:
    """Short-lived GET for the original PDF. The viewer uses this; exports stay on the downloads bucket."""
    expires_in = max(60, min(expires, 900))
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket_originals(), "Key": key},
        ExpiresIn=expires_in,
    )


def presign_download(key: str, expires: int | None = None, filename: str | None = None) -> str:
    """Generate temporary URL for downloading generated exports.

    `filename` makes the browser save the file under that name instead of the S3 key.
    """
    settings = get_settings()
    requested_expiry = expires if expires is not None else settings.upload_presign_ttl_seconds
    expires_in = max(60, min(requested_expiry, 3600))
    params = {"Bucket": _bucket_downloads(), "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return _client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )


def delete_stored_object(bucket: str, key: str) -> None:
    """Delete one object. A missing key is a no-op so retries stay safe."""
    if not bucket or not key:
        return
    try:
        _client().delete_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return
        raise


def get_original_object_metadata(key: str) -> dict[str, int | str] | None:
    """
    Return metadata for an uploaded original object.

    Returns None when the object is not found.
    """
    try:
        response = _client().head_object(Bucket=_bucket_originals(), Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    return {
        "content_length": int(response.get("ContentLength", 0)),
        "content_type": str(response.get("ContentType", "")),
    }
