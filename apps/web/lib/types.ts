export type DocumentMode =
  | "resume_anonymization"
  | "employment_paperwork_review"
  | "medical_paperwork_safe_sharing"
  | "legal_contract_review"
  | "terms_and_conditions_summarization";

export type DocumentStatus =
  | "CREATED"
  | "UPLOADED"
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
  mode: DocumentMode;
  status: DocumentStatus;
  createdAt: string;
}
