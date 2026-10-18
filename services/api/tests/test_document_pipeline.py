"""Upload → OCR → detect pipeline, review toggles, retry, delete, stale-upload cleanup, and export."""

from datetime import datetime, timedelta

import boto3
import pymupdf
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from services.api.app.config import get_settings
from services.api.app.db import Base, engine, ensure_database_exists
from services.api.app.main import app
from services.worker.app import ocr as ocr_module
from services.worker.app.celery_app import celery
from services.worker.app.detection.models import Candidate
from services.worker.app.ocr import PageInspection, merge_ocr_payload
from services.worker.app.tasks import cleanup_stale_uploads, export_job, process_document
from services.worker.app.tasks import engine as worker_engine

BUCKET = "redactldr-originals-dev"
DOWNLOADS = "redactldr-downloads-dev"
HEADERS = {"x-demo-user": "demo-user"}

# Synthetic resume text. None of it is real personal data.
RESUME_LINES = ("Jane Doe", "jane.doe@gmail.com | (212) 555-0199", "Class of 2019")
RAW_VALUES = ("Jane Doe", "jane.doe@gmail.com", "(212) 555-0199")


def _ocr_lines(lines: tuple[str, ...]) -> list[dict]:
    """OCR lines in the R2 JSON shape with simple per-word boxes."""
    out = []
    for index, line in enumerate(lines):
        y = 0.1 + index * 0.03
        words, column = [], 0
        for token in line.split(" "):
            words.append({"text": token, "bbox": {"x": 0.1 + column * 0.01, "y": y, "width": len(token) * 0.01, "height": 0.02}})
            column += len(token) + 1
        out.append({"text": line, "bbox": {"x": 0.1, "y": y, "width": len(line) * 0.01, "height": 0.02}, "words": words})
    return out


class FakeComprehend:
    """Finds the synthetic name and email the way Comprehend would."""

    def detect(self, page_text: str) -> list[Candidate]:
        hits = []
        for value, kind in (("Jane Doe", "NAME"), ("jane.doe@gmail.com", "EMAIL")):
            start = page_text.find(value)
            if start >= 0:
                hits.append(Candidate(start, start + len(value), kind, 0.99, "comprehend"))
        return hits


def _postgres_ready() -> bool:
    try:
        ensure_database_exists(get_settings().get_runtime_database_url())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (OperationalError, OSError):
        return False


@pytest.fixture(scope="session")
def test_schema():
    """Rebuild the ORM schema once per run.

    The test database is created from the models, not Alembic, and `create_all`
    never adds columns to an existing table. Without the drop, a local test
    database from an older revision drifts from the models.
    """
    if not _postgres_ready():
        pytest.skip("local Postgres is not available for pipeline tests")
    if not (engine.url.database or "").endswith("_test"):
        pytest.fail(f"refusing to reset non-test database {engine.url.database!r}")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def pipeline(monkeypatch, test_schema):
    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = False

    def _fake_ocr(document_id: str, **_kwargs: object) -> dict:
        # Store real OCR JSON (in moto S3) and page rows, without Textract or a real PDF.
        row = ocr_module._load_document(document_id)
        payload = merge_ocr_payload(
            [PageInspection(page_number=1, width=612, height=792, has_text_layer=True)],
            [{"pageNumber": 1, "lines": _ocr_lines(RESUME_LINES)}],
        )
        ocr_module._store_ocr(document_id, row["user_id"], payload, boto3.client("s3", region_name="us-east-1"))
        return {"ok": True, "skipped": False, "pageCount": 1}

    # The pipeline fixture uploads a one-line stand-in, not a real PDF.
    # OCR itself is covered in services/worker/tests/test_ocr.py.
    monkeypatch.setattr("services.worker.app.tasks.run_ocr_for_document", _fake_ocr)
    monkeypatch.setattr("services.worker.app.detect.default_pii_detector", FakeComprehend)

    def _run_process(task_name: str, *args: object) -> str:
        if task_name == "process_document":
            process_document.apply(args=list(args))
        if task_name == "export_job":
            export_job.apply(args=list(args))
        return "eager"

    monkeypatch.setattr("services.api.app.routes.documents.enqueue_task", _run_process)

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        s3.create_bucket(Bucket=DOWNLOADS)
        with TestClient(app) as client:
            yield client, s3


def _create_and_upload(client: TestClient, s3, filename: str, body: bytes = b"%PDF-1.4\n") -> str:
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
    created_body = created.json()
    s3.put_object(Bucket=BUCKET, Key=created_body["s3Key"], Body=body, ContentType="application/pdf")
    return created_body["id"]


def test_ingest_runs_detect_to_detected(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "resume.pdf")
    done = client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "READY_FOR_REVIEW"

    jobs = client.get(f"/v1/documents/{document_id}/jobs", headers=HEADERS)
    assert jobs.status_code == 200, jobs.text
    process_jobs = [row for row in jobs.json() if row["jobType"] == "process"]
    assert process_jobs
    assert process_jobs[0]["status"] == "COMPLETED"

    with worker_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM detections WHERE document_id = CAST(:document_id AS UUID)"),
            {"document_id": document_id},
        ).scalar()
    assert count and count >= 1

    again = process_document.apply(args=[document_id, "demo-user"]).get()
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

    monkeypatch.setattr("services.worker.app.tasks.run_detection_for_document", _boom)
    document_id = _create_and_upload(client, s3, "bad.pdf")
    done = client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "FAILED"

    jobs = client.get(f"/v1/documents/{document_id}/jobs", headers=HEADERS)
    process_job_row = next(row for row in jobs.json() if row["jobType"] == "process")
    assert process_job_row["status"] == "FAILED"
    assert "boom" in (process_job_row["lastError"] or "")
    assert process_job_row["attemptCount"] >= 2


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
    assert retried.json()["status"] == "READY_FOR_REVIEW"
    document = client.get(f"/v1/documents/{document_id}", headers=HEADERS)
    assert document.status_code == 200
    assert document.json()["error_message"] is None
    noop = client.post(f"/v1/documents/{document_id}/process", headers=HEADERS)
    assert noop.status_code == 200
    assert noop.json()["status"] == "READY_FOR_REVIEW"


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


def test_detections_are_stored_masked_with_boxes(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "resume.pdf")
    done = client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    assert done.json()["status"] == "READY_FOR_REVIEW"

    listed = client.get(f"/v1/documents/{document_id}/detections", headers=HEADERS)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    by_type = {item["entity_type"]: item for item in body["items"]}
    assert {"NAME", "EMAIL", "PHONE"} <= set(by_type)
    assert by_type["EMAIL"]["masked_text"] == "j***@g***.com"
    assert by_type["EMAIL"]["detected_text"] == "j***@g***.com"
    assert by_type["EMAIL"]["policy_action"] == "auto"
    assert by_type["EMAIL"]["accepted"] is True
    assert by_type["EMAIL"]["rects"] and by_type["EMAIL"]["char_end"] > by_type["EMAIL"]["char_start"]
    assert by_type["PHONE"]["source"] == "rule" and by_type["PHONE"]["rule_id"] == "us_phone"
    # `_create_and_upload` turns safe mode on, which promotes resume suggestions to auto.
    assert body["safe_mode"] is True
    assert by_type["GRADUATION_YEAR"]["accepted"] is True
    assert by_type["GRADUATION_YEAR"]["policy_action"] == "auto"
    groups = {group["entity_type"]: group for group in body["groups"]}
    assert groups["EMAIL"]["label"] == "Email" and groups["EMAIL"]["count"] == 1

    with worker_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT detected_text, masked_text, block_ref
                FROM detections WHERE document_id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).all()
    stored = " ".join(" ".join(str(value) for value in row) for row in rows)
    for raw in RAW_VALUES:
        assert raw not in stored

    jobs = client.get(f"/v1/documents/{document_id}/jobs", headers=HEADERS).json()
    assert jobs[0]["status"] == "COMPLETED"

    empty_page = client.get(f"/v1/documents/{document_id}/detections?page=2", headers=HEADERS).json()
    assert empty_page["items"] == [] and empty_page["groups"] == body["groups"]


def test_review_toggles_persist(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "toggle.pdf")
    client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    items = client.get(f"/v1/documents/{document_id}/detections", headers=HEADERS).json()["items"]
    email = next(item for item in items if item["entity_type"] == "EMAIL")

    patched = client.patch(
        f"/v1/documents/{document_id}/detections/{email['id']}", headers=HEADERS, json={"accepted": False}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["accepted"] is False

    bulk = client.post(
        f"/v1/documents/{document_id}/detections/bulk",
        headers=HEADERS,
        json={"entityType": "GRADUATION_YEAR", "accepted": False},
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["updated"] == 1

    after = {item["entity_type"]: item for item in client.get(f"/v1/documents/{document_id}/detections", headers=HEADERS).json()["items"]}
    assert after["EMAIL"]["accepted"] is False
    assert after["GRADUATION_YEAR"]["accepted"] is False
    assert after["NAME"]["accepted"] is True

    missing = client.patch(
        f"/v1/documents/{document_id}/detections/00000000-0000-0000-0000-000000000000",
        headers=HEADERS,
        json={"accepted": True},
    )
    assert missing.status_code == 404
    other_user = client.patch(
        f"/v1/documents/{document_id}/detections/{email['id']}",
        headers={"x-demo-user": "someone-else"},
        json={"accepted": True},
    )
    assert other_user.status_code == 404


def test_toggles_are_rejected_while_processing(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "busy.pdf")
    bulk = client.post(
        f"/v1/documents/{document_id}/detections/bulk",
        headers=HEADERS,
        json={"entityType": "EMAIL", "accepted": False},
    )
    assert bulk.status_code == 409


def _ready_document(client: TestClient, s3, filename: str, body: bytes = b"%PDF-1.4\n") -> str:
    document_id = _create_and_upload(client, s3, filename, body)
    done = client.post(f"/v1/documents/{document_id}/ingest-complete", headers=HEADERS)
    assert done.json()["status"] == "READY_FOR_REVIEW", done.text
    return document_id


def _audit_events(document_id: str) -> list[str]:
    with worker_engine.connect() as conn:
        return list(
            conn.execute(
                text("SELECT event_type FROM audit_logs WHERE document_id = CAST(:document_id AS UUID) ORDER BY created_at"),
                {"document_id": document_id},
            ).scalars()
        )


def test_review_state_has_everything_the_viewer_needs(pipeline) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "review.pdf")
    response = client.get(f"/v1/documents/{document_id}/review-state", headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["documentId"] == document_id
    assert body["filename"] == "review.pdf"
    assert body["status"] == "READY_FOR_REVIEW" and body["reviewable"] is True
    assert body["mode"] == "resume_anonymization" and body["safeMode"] is True
    assert body["pageCount"] == 1
    assert body["pages"] == [{"pageNumber": 1, "width": 612, "height": 792, "wordCount": 9, "hasTextLayer": True}]
    assert body["manualRedactions"] == [] and body["activity"] == []

    email = next(item for item in body["detections"] if item["entityType"] == "EMAIL")
    assert email["maskedText"] == "j***@g***.com"
    assert email["policyAction"] == "auto" and email["accepted"] is True
    assert email["rects"] and set(email["rects"][0]) == {"x", "y", "width", "height"}
    groups = {group["entityType"]: group for group in body["groups"]}
    assert groups["EMAIL"] == {"entityType": "EMAIL", "label": "Email", "color": groups["EMAIL"]["color"], "count": 1, "acceptedCount": 1}

    # The payload never carries raw values.
    for raw in RAW_VALUES:
        assert raw not in response.text


def test_review_state_reports_not_reviewable_while_processing(pipeline) -> None:
    client, s3 = pipeline
    document_id = _create_and_upload(client, s3, "pending.pdf")
    body = client.get(f"/v1/documents/{document_id}/review-state", headers=HEADERS).json()
    assert body["status"] == "CREATED" and body["reviewable"] is False
    assert body["pages"] == [] and body["detections"] == []


def test_manual_redaction_lifecycle(pipeline) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "manual.pdf")
    base = f"/v1/documents/{document_id}/redactions"
    client_id = "5b0d6a52-6a43-4d8e-9d1b-3f2a7f1c9e01"
    box = {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05}

    created = client.post(base, headers=HEADERS, json={"id": client_id, "pageNumber": 1, "bbox": box})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] == client_id
    assert body["entityType"] == "CUSTOM" and body["label"] == "Manual redaction"
    assert body["bbox"] == box and body["status"] == "ACTIVE" and body["kind"] == "bbox"

    # A retried save with the same id does not create a second box.
    replay = client.post(base, headers=HEADERS, json={"id": client_id, "pageNumber": 1, "bbox": box})
    assert replay.status_code == 201 and replay.json()["id"] == client_id
    state = client.get(f"/v1/documents/{document_id}/review-state", headers=HEADERS).json()
    assert [item["id"] for item in state["manualRedactions"]] == [client_id]

    moved = {"x": 0.5, "y": 0.5, "width": 0.25, "height": 0.1}
    patched = client.patch(f"{base}/{client_id}", headers=HEADERS, json={"bbox": moved})
    assert patched.status_code == 200, patched.text
    assert patched.json()["bbox"] == moved
    state = client.get(f"/v1/documents/{document_id}/review-state", headers=HEADERS).json()
    assert state["manualRedactions"][0]["bbox"] == moved

    deleted = client.delete(f"{base}/{client_id}", headers=HEADERS)
    assert deleted.status_code == 204
    state = client.get(f"/v1/documents/{document_id}/review-state", headers=HEADERS).json()
    assert state["manualRedactions"] == []
    assert client.delete(f"{base}/{client_id}", headers=HEADERS).status_code == 404
    assert client.patch(f"{base}/{client_id}", headers=HEADERS, json={"bbox": box}).status_code == 404
    # A deleted id cannot be revived by replaying the create.
    assert client.post(base, headers=HEADERS, json={"id": client_id, "pageNumber": 1, "bbox": box}).status_code == 409

    events = _audit_events(document_id)
    assert events.count("document.redaction.saved") == 1
    assert "document.redaction.updated" in events and "document.redaction.deleted" in events


def test_server_generates_redaction_id_when_client_omits_it(pipeline) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "noid.pdf")
    box = {"x": 0, "y": 0, "width": 1, "height": 1}
    first = client.post(f"/v1/documents/{document_id}/redactions", headers=HEADERS, json={"page_number": 1, "bbox": box})
    second = client.post(f"/v1/documents/{document_id}/redactions", headers=HEADERS, json={"pageNumber": 1, "bbox": box})
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


@pytest.mark.parametrize(
    "payload",
    [
        {"pageNumber": 1, "bbox": {"x": 0.9, "y": 0.1, "width": 0.2, "height": 0.1}},  # past the right edge
        {"pageNumber": 1, "bbox": {"x": 0.1, "y": 0.95, "width": 0.1, "height": 0.1}},  # past the bottom
        {"pageNumber": 1, "bbox": {"x": -0.1, "y": 0.1, "width": 0.1, "height": 0.1}},
        {"pageNumber": 1, "bbox": {"x": 0.1, "y": 0.1, "width": 0.0005, "height": 0.1}},  # accidental click
        {"pageNumber": 1, "bbox": {"x": 0.1, "y": 0.1, "width": 0.1}},
        {"pageNumber": 1, "bbox": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1, "z": 1}},
        {"pageNumber": 0, "bbox": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}},
        {"pageNumber": 1, "bbox": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}, "entityType": "lower case"},
    ],
)
def test_invalid_manual_boxes_are_rejected(pipeline, payload) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "invalid.pdf")
    response = client.post(f"/v1/documents/{document_id}/redactions", headers=HEADERS, json=payload)
    assert response.status_code == 422, response.text


def test_manual_box_past_last_page_is_rejected(pipeline) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "onepage.pdf")
    response = client.post(
        f"/v1/documents/{document_id}/redactions",
        headers=HEADERS,
        json={"pageNumber": 2, "bbox": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "page number is past the end of the document"


def test_manual_redactions_are_guarded(pipeline) -> None:
    client, s3 = pipeline
    box = {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}
    pending = _create_and_upload(client, s3, "early.pdf")
    early = client.post(f"/v1/documents/{pending}/redactions", headers=HEADERS, json={"pageNumber": 1, "bbox": box})
    assert early.status_code == 409

    document_id = _ready_document(client, s3, "owned.pdf")
    created = client.post(f"/v1/documents/{document_id}/redactions", headers=HEADERS, json={"pageNumber": 1, "bbox": box})
    redaction_id = created.json()["id"]
    stranger = {"x-demo-user": "someone-else"}
    assert client.post(f"/v1/documents/{document_id}/redactions", headers=stranger, json={"pageNumber": 1, "bbox": box}).status_code == 404
    assert client.patch(f"/v1/documents/{document_id}/redactions/{redaction_id}", headers=stranger, json={"bbox": box}).status_code == 404
    assert client.delete(f"/v1/documents/{document_id}/redactions/{redaction_id}", headers=stranger).status_code == 404

    # An id from one document cannot be edited through another.
    other_id = _ready_document(client, s3, "other.pdf")
    assert client.patch(f"/v1/documents/{other_id}/redactions/{redaction_id}", headers=HEADERS, json={"bbox": box}).status_code == 404
    reused = client.post(
        f"/v1/documents/{other_id}/redactions", headers=HEADERS, json={"id": redaction_id, "pageNumber": 1, "bbox": box}
    )
    assert reused.status_code == 409
    assert client.patch(f"/v1/documents/{document_id}/redactions/{redaction_id}", headers=HEADERS, json={}).status_code == 422


def test_policies_endpoint_lists_every_mode(pipeline) -> None:
    client, _s3 = pipeline
    response = client.get("/v1/policies/modes")
    assert response.status_code == 200
    modes = {mode["id"] for mode in response.json()["modes"]}
    assert "resume_anonymization" in modes and len(modes) == 5


# --- R5 export -------------------------------------------------------------


def _resume_pdf() -> bytes:
    """A real PDF whose text sits under the boxes `_ocr_lines` reports.

    Courier advances 0.6 em per character, so 10.2 pt gives 6.12 pt = 0.01 of
    the page width, the per-character step `_ocr_lines` uses.
    """
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    for index, line in enumerate(RESUME_LINES):
        top = (0.1 + index * 0.03) * 792
        page.insert_text((0.1 * 612, top + 12), line, fontname="cour", fontsize=10.2)
    return document.tobytes()


def _export_text(s3, key: str) -> str:
    body = s3.get_object(Bucket=DOWNLOADS, Key=key)["Body"].read()
    return "\n".join(page.get_text() for page in pymupdf.open(stream=body, filetype="pdf"))


def _object_exists(s3, key: str) -> bool:
    return s3.list_objects_v2(Bucket=DOWNLOADS, Prefix=key).get("KeyCount", 0) == 1


def test_export_removes_selected_values_and_is_downloadable(pipeline) -> None:
    client, s3 = pipeline
    original = _resume_pdf()
    assert all(raw in "\n".join(p.get_text() for p in pymupdf.open(stream=original, filetype="pdf")) for raw in RAW_VALUES)
    document_id = _ready_document(client, s3, "resume.pdf", original)

    response = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "EXPORTED", body
    assert body["documentId"] == document_id and body["includeLabels"] is False
    assert body["pageCount"] == 1 and body["redactionCount"] >= 3 and body["sizeBytes"] > 0
    assert body["errorCode"] is None and body["completedAt"]
    assert "resume-redacted.pdf" in body["downloadUrl"]

    key = f"exports/demo-user/{document_id}/{body['id']}.pdf"
    exported = _export_text(s3, key)
    for raw in RAW_VALUES:
        assert raw not in exported
    assert "|" in exported  # the separator between email and phone was not selected
    with worker_engine.connect() as conn:
        verification = conn.execute(
            text("SELECT verification FROM exports WHERE id = CAST(:id AS UUID)"), {"id": body["id"]}
        ).scalar_one()
    assert verification["boxesChecked"] == body["redactionCount"] and verification["probesChecked"] >= 3

    document = client.get(f"/v1/documents/{document_id}", headers=HEADERS).json()
    assert document["status"] == "EXPORTED"
    assert client.get(f"/v1/documents/{document_id}/review-state", headers=HEADERS).json()["reviewable"] is True
    export_jobs = [job for job in client.get(f"/v1/documents/{document_id}/jobs", headers=HEADERS).json() if job["jobType"] == "export"]
    assert [job["status"] for job in export_jobs] == ["COMPLETED"]
    events = _audit_events(document_id)
    assert "document.export.queued" in events and "document.export.completed" in events

    listed = client.get(f"/v1/documents/{document_id}/exports", headers=HEADERS).json()
    assert [item["id"] for item in listed] == [body["id"]]
    one = client.get(f"/v1/documents/{document_id}/exports/{body['id']}", headers=HEADERS).json()
    latest = client.get(f"/v1/documents/{document_id}/export", headers=HEADERS).json()
    assert one["id"] == latest["id"] == body["id"] and one["downloadUrl"]

    # Deleting the document removes the exported file too.
    assert client.delete(f"/v1/documents/{document_id}", headers=HEADERS).status_code == 204
    assert not _object_exists(s3, key)


def test_reexport_reads_the_current_review_and_keeps_the_earlier_file(pipeline) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "again.pdf", _resume_pdf())
    first = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={}).json()

    items = client.get(f"/v1/documents/{document_id}/detections", headers=HEADERS).json()["items"]
    email = next(item for item in items if item["entity_type"] == "EMAIL")
    client.patch(f"/v1/documents/{document_id}/detections/{email['id']}", headers=HEADERS, json={"accepted": False})
    second = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={"includeLabels": True}).json()

    assert second["status"] == "EXPORTED" and second["id"] != first["id"] and second["includeLabels"] is True
    second_text = _export_text(s3, f"exports/demo-user/{document_id}/{second['id']}.pdf")
    assert "jane.doe@gmail.com" in second_text and "Jane Doe" not in second_text
    # Labels name the type, never the value.
    assert "Name" in second_text
    first_text = _export_text(s3, f"exports/demo-user/{document_id}/{first['id']}.pdf")
    assert "jane.doe@gmail.com" not in first_text

    history = client.get(f"/v1/documents/{document_id}/exports", headers=HEADERS).json()
    assert [item["id"] for item in history] == [second["id"], first["id"]]


def test_manual_box_is_removed_from_the_export(pipeline) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "manual-export.pdf", _resume_pdf())
    # "Class of 2019" is the third line: y = 0.1 + 2 * 0.03.
    box = {"x": 0.09, "y": 0.155, "width": 0.16, "height": 0.03}
    created = client.post(f"/v1/documents/{document_id}/redactions", headers=HEADERS, json={"pageNumber": 1, "bbox": box})
    assert created.status_code == 201, created.text
    body = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={}).json()
    assert body["status"] == "EXPORTED", body
    assert "Class" not in _export_text(s3, f"exports/demo-user/{document_id}/{body['id']}.pdf")


def test_export_failure_keeps_the_document_reviewable(pipeline) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "broken.pdf")  # the stand-in bytes are not a real PDF
    body = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={}).json()
    assert body["status"] == "FAILED" and body["errorCode"] == "UNSUPPORTED_PDF"
    assert body["errorMessage"] and body["downloadUrl"] is None
    assert not _object_exists(s3, f"exports/demo-user/{document_id}/{body['id']}.pdf")

    document = client.get(f"/v1/documents/{document_id}", headers=HEADERS).json()
    assert document["status"] == "READY_FOR_REVIEW"
    export_job_row = next(job for job in client.get(f"/v1/documents/{document_id}/jobs", headers=HEADERS).json() if job["jobType"] == "export")
    assert export_job_row["status"] == "FAILED" and "UNSUPPORTED_PDF" in export_job_row["lastError"]
    assert "document.export.failed" in _audit_events(document_id)
    # Review edits still work after a failed export.
    items = client.get(f"/v1/documents/{document_id}/detections", headers=HEADERS).json()["items"]
    assert client.patch(f"/v1/documents/{document_id}/detections/{items[0]['id']}", headers=HEADERS, json={"accepted": False}).status_code == 200


def test_export_in_flight_is_returned_instead_of_queued_twice(pipeline, monkeypatch) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "twice.pdf", _resume_pdf())
    queued: list[tuple] = []
    monkeypatch.setattr("services.api.app.routes.documents.enqueue_task", lambda *args: queued.append(args))

    first = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={}).json()
    second = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={"includeLabels": True}).json()
    assert first["status"] == "QUEUED" and first["downloadUrl"] is None
    assert second["id"] == first["id"] and len(queued) == 1
    assert queued[0] == ("export_job", document_id, "demo-user", first["id"])


def test_export_queue_failure_is_recorded(pipeline, monkeypatch) -> None:
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "noqueue.pdf", _resume_pdf())

    def _down(*_args):
        raise RuntimeError("broker down")

    monkeypatch.setattr("services.api.app.routes.documents.enqueue_task", _down)
    response = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={})
    assert response.status_code == 503
    latest = client.get(f"/v1/documents/{document_id}/export", headers=HEADERS).json()
    assert latest["status"] == "FAILED" and latest["errorCode"] == "QUEUE_FAILED"
    assert client.get(f"/v1/documents/{document_id}", headers=HEADERS).json()["status"] == "READY_FOR_REVIEW"


def test_export_endpoints_are_guarded(pipeline) -> None:
    client, s3 = pipeline
    pending = _create_and_upload(client, s3, "notready.pdf")
    assert client.post(f"/v1/documents/{pending}/export", headers=HEADERS, json={}).status_code == 409
    assert client.get(f"/v1/documents/{pending}/export", headers=HEADERS).status_code == 404

    document_id = _ready_document(client, s3, "mine.pdf", _resume_pdf())
    export_id = client.post(f"/v1/documents/{document_id}/export", headers=HEADERS, json={}).json()["id"]
    stranger = {"x-demo-user": "someone-else"}
    assert client.post(f"/v1/documents/{document_id}/export", headers=stranger, json={}).status_code == 404
    assert client.get(f"/v1/documents/{document_id}/exports", headers=stranger).status_code == 404
    assert client.get(f"/v1/documents/{document_id}/exports/{export_id}", headers=stranger).status_code == 404
    assert client.get(f"/v1/documents/{document_id}/exports/not-a-uuid", headers=HEADERS).status_code == 404
    other = _ready_document(client, s3, "other-export.pdf", _resume_pdf())
    assert client.get(f"/v1/documents/{other}/exports/{export_id}", headers=HEADERS).status_code == 404


def test_summary_removes_selected_values_before_the_model_sees_them(pipeline) -> None:
    from services.shared.summary_contract import empty_summary
    from services.worker.app.summary.engine import ModelResult
    from services.worker.app.summary.run import run_summary

    class Recorder:
        def __init__(self) -> None:
            self.prompts: list[str] = []
            self.model_id = "fake"

        def complete(self, mode: str, system: str, user: str) -> ModelResult:
            self.prompts.append(user)
            data = empty_summary(mode)
            data["skills"] = ["Python"]
            data["experienceSummary"] = "Built services."
            data["confidence"] = 0.7
            data["citations"] = [{"page": 1, "quoteSnippet": "[EMAIL]"}]
            return ModelResult(data=data, input_tokens=4, output_tokens=2)

    client, s3 = pipeline
    document_id = _ready_document(client, s3, "summary.pdf")
    first = client.post(f"/v1/documents/{document_id}/summaries", headers=HEADERS, json={})
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "QUEUED"
    second = client.post(f"/v1/documents/{document_id}/summaries", headers=HEADERS, json={})
    assert second.json()["id"] == first.json()["id"]

    model = Recorder()
    run_summary(document_id, first.json()["id"], model=model)
    body = client.get(f"/v1/documents/{document_id}/summaries/latest", headers=HEADERS).json()
    assert body["status"] == "SUMMARIZED" and body["safeMode"] is True and body["schemaVersion"] == 1
    assert body["json"]["summary"]["skills"] == ["Python"]
    assert "jane.doe@gmail.com" not in model.prompts[0]
    assert "jane.doe@gmail.com" not in body["markdown"]
    assert client.get(f"/v1/documents/{document_id}", headers=HEADERS).json()["status"] == "SUMMARIZED"
    assert "document.summary.completed" in _audit_events(document_id)


def test_summary_leak_keeps_the_document_reviewable(pipeline, monkeypatch) -> None:
    from services.shared.summary_contract import empty_summary
    from services.worker.app.summary.engine import ModelResult
    from services.worker.app.tasks import summary_job

    class Leaky:
        model_id = "fake"

        def complete(self, mode: str, system: str, user: str) -> ModelResult:
            data = empty_summary(mode)
            data["experienceSummary"] = "jane.doe@gmail.com"
            return ModelResult(data=data, input_tokens=1, output_tokens=1)

    monkeypatch.setattr("services.worker.app.summary.run.BedrockSummarizer", lambda: Leaky())
    client, s3 = pipeline
    document_id = _ready_document(client, s3, "leak.pdf")
    queued = client.post(f"/v1/documents/{document_id}/summaries", headers=HEADERS, json={}).json()
    result = summary_job.apply(args=[document_id, "demo-user", True, queued["id"]]).get()
    assert result["ok"] is False and result["error"] == "OUTPUT_LEAK"
    body = client.get(f"/v1/documents/{document_id}/summaries/latest", headers=HEADERS).json()
    assert body["status"] == "FAILED" and body["errorCode"] == "OUTPUT_LEAK"
    assert "jane.doe@gmail.com" not in (body["markdown"] or "")
    assert client.get(f"/v1/documents/{document_id}", headers=HEADERS).json()["status"] == "READY_FOR_REVIEW"
