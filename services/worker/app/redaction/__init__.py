"""True-redaction export (R5): review state + original PDF → redacted, scrubbed, verified PDF.

Pure: no database or S3 here. `services/worker/app/export.py` is the I/O shell.

- `targets`: rows → `RedactionBox` (what to remove) and `LeakProbe` (what to look for afterwards)
- `geometry`: normalized boxes → PDF points, rotation and cropbox included
- `engine`: apply, bake, scrub, label
- `verify`: re-open the output and prove nothing selected is still readable
"""

from services.worker.app.redaction.engine import redact_pdf
from services.worker.app.redaction.geometry import clamp_bbox
from services.worker.app.redaction.models import (
    ExportError,
    LeakProbe,
    RedactedPdf,
    RedactionBox,
    VerificationReport,
)
from services.worker.app.redaction.targets import build_probes, build_targets
from services.worker.app.redaction.verify import verify_export

__all__ = [
    "ExportError",
    "LeakProbe",
    "RedactedPdf",
    "RedactionBox",
    "VerificationReport",
    "build_probes",
    "build_targets",
    "clamp_bbox",
    "redact_pdf",
    "verify_export",
]
