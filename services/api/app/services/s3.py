import os
import time

import boto3
from botocore.config import Config


def _client():
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))


def _bucket_originals() -> str:
    return os.environ.get("S3_BUCKET_ORIGINALS", "redactldr-originals-dev")


def _bucket_downloads() -> str:
    return os.environ.get("S3_BUCKET_DOWNLOADS", "redactldr-downloads-dev")


def make_originals_key(user_id: str, filename: str) -> str:
    safe = "".join(c for c in filename if c.isalnum() or c in ".-_") or "doc.pdf"
    return f"originals/{user_id}/{int(time.time())}-{safe}"


def make_export_key(user_id: str, document_id: str) -> str:
    return f"exports/{user_id}/{document_id}.pdf"


def presign_put(key: str, content_type: str, expires: int = 600) -> str:
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket_originals(), "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def presign_download(key: str, expires: int = 600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket_downloads(), "Key": key},
        ExpiresIn=expires,
    )
