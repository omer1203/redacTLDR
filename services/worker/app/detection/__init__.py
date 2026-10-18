"""R3 sensitive-data detection: page text, Comprehend, custom rules, merge, boxes, masking.

`engine.detect_document` is the entry point. `services/worker/app/detect.py`
wraps it with S3 and Postgres I/O for the pipeline.
"""

from services.worker.app.detection.engine import DetectionResult, detect_document
from services.worker.app.detection.models import DetectionError, Finding

__all__ = ["DetectionError", "DetectionResult", "Finding", "detect_document"]
