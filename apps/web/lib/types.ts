export type DocumentMode =
  | "resume_anonymization"
  | "employment_paperwork_review"
  | "medical_paperwork_safe_sharing"
  | "legal_contract_review"
  | "terms_and_conditions_summarization";

export type DocumentStatus =
  | "CREATED"
  | "UPLOADED"
  | "PROCESSING"
  | "READY_FOR_REVIEW"
  | "DETECT_QUEUED"
  | "DETECTED"
  | "EXPORT_QUEUED"
  | "EXPORTED"
  | "SUMMARY_QUEUED"
  | "SUMMARIZED"
  | "FAILED";

export interface DocumentRecord {
  id: string;
  filename: string;
  contentType: string;
  mode: DocumentMode;
  safeMode: boolean;
  status: DocumentStatus;
  pageCount: number | null;
  processingStage: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentApiDto {
  id: string;
  filename: string;
  content_type: string;
  mode: DocumentMode;
  safe_mode: boolean;
  status: DocumentStatus;
  page_count?: number | null;
  processing_stage?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export function toDocumentRecord(dto: DocumentApiDto): DocumentRecord {
  return {
    id: dto.id,
    filename: dto.filename,
    contentType: dto.content_type,
    mode: dto.mode,
    safeMode: dto.safe_mode,
    status: dto.status,
    pageCount: dto.page_count ?? null,
    processingStage: dto.processing_stage ?? null,
    errorMessage: dto.error_message ?? null,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}
