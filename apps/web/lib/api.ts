export { ApiError, uploadWithProgress } from "@/lib/api/client";
export { listAuditEvents, type AuditEvent } from "@/lib/api/audit";
export {
  completeIngest,
  createDocument,
  deleteDocument,
  getDetections,
  getDocument,
  listDetections,
  listDocuments,
  listJobs,
  reprocessDocument,
  type CreateDocumentInput,
  type CreateDocumentOutput,
  type DetectionGroup,
  type DetectionList,
  type DetectionRecord,
  type JobRecord,
} from "@/lib/api/documents";
export {
  getExport,
  isExportActive,
  listExports,
  queueExport,
  type ExportOptions,
  type ExportRecord,
  type ExportStatus,
} from "@/lib/api/exports";
export { getLatestSummary, isSummaryActive, queueSummary, type SummaryRecord } from "@/lib/api/summaries";
