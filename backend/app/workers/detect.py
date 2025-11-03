from .celery_app import celery


#this will run the OCR detection and PII

@celery.task(name = "detect_job")
def detect_job(document_id: str):
    print(f"[detect_job] Starting detection for document {document_id}")
    return {"ok": True, "document_id": document_id}