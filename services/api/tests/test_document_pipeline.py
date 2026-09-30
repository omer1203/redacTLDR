"""Upload → detect pipeline, retry, delete, and stale-upload cleanup."""

from datetime import datetime, timedelta

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from services.api.app.config import get_settings
from services.api.app.db import Base, engine, ensure_database_exists
from services.api.app.main import app
from services.worker.app.celery_app import celery
from services.worker.app.tasks import cleanup_stale_uploads, detect_job
from services.worker.app.tasks import engine as worker_engine

BUCKET = "redactldr-originals-dev"
HEADERS = {"x-demo-user": "demo-user"}


def _postgres_ready() -> bool:
    try:
        ensure_database_exists(get_settings().get_runtime_database_url())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (OperationalError, OSError):
        return False


@pytest.fixture
def pipeline(monkeypatch):
    if not _postgres_ready():
        pytest.skip("local Postgres is not available for pipeline tests")
    Base.metadata.create_all(bind=engine)
    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = False

    def _run_detect(task_name: str, *args: object) -> str:
        if task_name == "detect_job":
            detect_job.apply(args=list(args))
        return "eager"

    monkeypatch.setattr("services.api.app.routes.documents.enqueue_task", _run_detect)

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        s3.create_bucket(Bucket="redactldr-downloads-dev")
        with TestClient(app) as client:
            yield client, s3


def _create_and_upload(client: TestClient, s3, filename: str) -> str:
    created = client.post(
        "/v1/documents",
        headers=HEADERS,
        json={
            "filename": filename,
            "contentType": "application/pdf",
            "mode": "resume_anonymization",
            "safeMode": True,
            "sizeBytes": 64,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    s3.put_object(Bucket=BUCKET, Key=body["s3Key"], Body=b"%PDF-1.4\n", ContentType="application/pdf")
    return body["id"]


def test_ingest_runs_detect_to_detected(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "resume.pdf")
    done = client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "DETECTED"

    jobs = client.get(f"/v1/documents/{document_id}/jobs", headers=HEADERS)
    assert jobs.status_code == 200, jobs.text
    detect_jobs = [row for row in jobs.json() if row["jobType"] == "detect"]
    assert detect_jobs
    assert detect_jobs[0]["status"] == "COMPLETED"

    with worker_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM detections WHERE document_id = CAST(:document_id AS UUID)"),
            {"document_id": document_id},
        ).scalar()
    assert count and count >= 1

    again = detect_job.apply(args=[document_id, "demo-user"]).get()
    assert again["skipped"] is True
    with worker_engine.connect() as conn:
        count_after = conn.execute(
            text("SELECT COUNT(*) FROM detections WHERE document_id = CAST(:document_id AS UUID)"),
            {"document_id": document_id},
        ).scalar()
    assert count_after == count


def test_detect_failure_records_last_error(pipeline, monkeypatch) -> None:
    client, s3 = pipeline

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("services.worker.app.tasks._insert_detection", _boom)
    document_id = _create_and_upload(client, s3, "bad.pdf")
    done = client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "FAILED"

    jobs = client.get(f"/v1/documents/{document_id}/jobs", headers=HEADERS)
    detect_job_row = next(row for row in jobs.json() if row["jobType"] == "detect")
    assert detect_job_row["status"] == "FAILED"
    assert "boom" in (detect_job_row["lastError"] or "")
    assert detect_job_row["attemptCount"] >= 2


def test_process_retries_failed_document(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "retry.pdf")
    client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    with worker_engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE documents
                SET status = CAST('FAILED' AS VARCHAR)
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        )
    retried = client.post(f"/v1/documents/{document_id}/process", headers=HEADERS)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "DETECTED"
    noop = client.post(f"/v1/documents/{document_id}/process", headers=HEADERS)
    assert noop.status_code == 200
    assert noop.json()["status"] == "DETECTED"


def test_delete_hides_document_and_removes_object(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "gone.pdf")
    listed = s3.list_objects_v2(Bucket=BUCKET)
    assert listed.get("KeyCount", 0) >= 1
    deleted = client.delete(f"/v1/documents/{document_id}", headers=HEADERS)
    assert deleted.status_code == 204
    missing = client.get(f"/v1/documents/{document_id}", headers=HEADERS)
    assert missing.status_code == 404
    after = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"originals/demo-user/{document_id}/")
    assert after.get("KeyCount", 0) == 0


def test_stale_created_documents_are_soft_deleted(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "abandoned.pdf")
    old = datetime.utcnow() - timedelta(hours=25)
    with worker_engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE documents
                SET status = CAST('CREATED' AS VARCHAR),
                    created_at = CAST(:created_at AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id, "created_at": old},
        )
    result = cleanup_stale_uploads()
    assert result["softDeleted"] >= 1
    missing = client.get(f"/v1/documents/{document_id}", headers=HEADERS)
    assert missing.status_code == 404
