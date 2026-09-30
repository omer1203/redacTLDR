#!/usr/bin/env python3
"""
Create one document + queued detect job for manual pipeline checks.

Use this after migrations when you want a row in `documents` and `jobs` without
going through the API or S3. Re-running is a no-op if the stable `s3_key` is
already present.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.app.enums import DocumentMode, DocumentStatus
from services.api.app.models import Document, Job
from services.api.app.db import SessionLocal


def main() -> None:
    demo_owner = "demo-user"
    demo_key = "originals/demo-user/demo-doc-seed/resume.pdf"

    db = SessionLocal()
    try:
        existing = db.query(Document).filter(Document.s3_key == demo_key).first()
        if existing:
            print(f"Seed already present: document_id={existing.id}")
            return

        doc = Document(
            owner_user_id=demo_owner,
            user_id=demo_owner,
            workspace_id=None,
            filename="m3-demo-resume.pdf",
            content_type="application/pdf",
            mode=DocumentMode.RESUME_ANONYMIZATION.value,
            document_type=DocumentMode.RESUME_ANONYMIZATION.value,
            safe_mode=True,
            s3_key=demo_key,
            s3_key_original=demo_key,
            status=DocumentStatus.CREATED.value,
        )
        db.add(doc)
        db.flush()

        job = Job(
            document_id=doc.id,
            owner_user_id=demo_owner,
            workspace_id=None,
            job_type="detect",
            status="QUEUED",
            payload={"documentId": str(doc.id), "seeded": True},
        )
        db.add(job)
        db.commit()
        print(f"Seed created: document_id={doc.id} job_id={job.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
