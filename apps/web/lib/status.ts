import type { LucideIcon } from "lucide-react";
import { AlertCircle, CheckCircle2, Clock3, FileSearch, Loader2, ScanText, ShieldCheck } from "lucide-react";

import type { ExportStatus } from "@/lib/api/exports";
import type { DocumentStatus } from "@/lib/types";

export interface StatusMeta {
  label: string;
  description: string;
  badgeClass: string;
  icon: LucideIcon;
  inProgress: boolean;
}

export const STATUS_META: Record<DocumentStatus, StatusMeta> = {
  CREATED: {
    label: "Created",
    description: "Waiting for the file upload to finish.",
    badgeClass: "bg-muted text-muted-foreground",
    icon: Clock3,
    inProgress: true,
  },
  UPLOADED: {
    label: "Uploaded",
    description: "The file is stored and waiting to be read.",
    badgeClass: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
    icon: Clock3,
    inProgress: true,
  },
  PROCESSING: {
    label: "Reading document (OCR)",
    description: "Reading the PDF, then checking it for sensitive information.",
    badgeClass: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
    icon: ScanText,
    inProgress: true,
  },
  READY_FOR_REVIEW: {
    label: "Ready for review",
    description: "The document has been read and is ready to review.",
    badgeClass: "bg-primary/15 text-primary",
    icon: FileSearch,
    inProgress: false,
  },
  DETECT_QUEUED: {
    label: "Detecting",
    description: "Looking for sensitive information.",
    badgeClass: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
    icon: Loader2,
    inProgress: true,
  },
  DETECTED: {
    label: "Ready for review",
    description: "Sensitive items are ready to review.",
    badgeClass: "bg-primary/15 text-primary",
    icon: FileSearch,
    inProgress: false,
  },
  EXPORT_QUEUED: {
    label: "Exporting",
    description: "Building the redacted PDF.",
    badgeClass: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
    icon: Loader2,
    inProgress: true,
  },
  EXPORTED: {
    label: "Exported",
    description: "A redacted PDF is ready to download.",
    badgeClass: "bg-primary/15 text-primary",
    icon: ShieldCheck,
    inProgress: false,
  },
  SUMMARY_QUEUED: {
    label: "Summarizing",
    description: "Writing the mode-specific summary.",
    badgeClass: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
    icon: Loader2,
    inProgress: true,
  },
  SUMMARIZED: {
    label: "Summarized",
    description: "A summary is ready.",
    badgeClass: "bg-primary/15 text-primary",
    icon: CheckCircle2,
    inProgress: false,
  },
  FAILED: {
    label: "Failed",
    description: "Processing stopped. You can retry.",
    badgeClass: "bg-destructive/15 text-destructive",
    icon: AlertCircle,
    inProgress: false,
  },
};

export function statusMeta(status: string, stage?: string | null): StatusMeta {
  if (status === "PROCESSING" && stage === "detect") {
    return {
      ...STATUS_META.PROCESSING,
      label: "Detecting",
      description: "Looking for sensitive information.",
      icon: Loader2,
    };
  }
  if (status in STATUS_META) {
    return STATUS_META[status as DocumentStatus];
  }
  return {
    label: status,
    description: "Unknown status.",
    badgeClass: "bg-muted text-muted-foreground",
    icon: ScanText,
    inProgress: false,
  };
}

export const EXPORT_STATUS_META: Record<ExportStatus, StatusMeta> = {
  QUEUED: {
    label: "Queued",
    description: "Waiting for a worker.",
    badgeClass: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
    icon: Clock3,
    inProgress: true,
  },
  PROCESSING: {
    label: "Building",
    description: "Removing the selected content and checking the result.",
    badgeClass: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
    icon: Loader2,
    inProgress: true,
  },
  EXPORTED: {
    label: "Ready",
    description: "Verified: none of the selected text is left in the file.",
    badgeClass: "bg-primary/15 text-primary",
    icon: ShieldCheck,
    inProgress: false,
  },
  FAILED: {
    label: "Failed",
    description: "No file was saved.",
    badgeClass: "bg-destructive/15 text-destructive",
    icon: AlertCircle,
    inProgress: false,
  },
};

export type TimelineStep = "uploaded" | "reading" | "detecting" | "ready";

export function timelineState(
  status: DocumentStatus,
  stage?: string | null,
): Record<TimelineStep, "done" | "current" | "upcoming" | "failed"> {
  if (status === "FAILED") {
    if (stage === "detect") {
      return { uploaded: "done", reading: "done", detecting: "failed", ready: "upcoming" };
    }
    return { uploaded: "done", reading: "failed", detecting: "upcoming", ready: "upcoming" };
  }
  if (status === "CREATED") {
    return { uploaded: "current", reading: "upcoming", detecting: "upcoming", ready: "upcoming" };
  }
  if (status === "UPLOADED") {
    return { uploaded: "done", reading: "current", detecting: "upcoming", ready: "upcoming" };
  }
  if (status === "PROCESSING" && stage !== "detect") {
    return { uploaded: "done", reading: "current", detecting: "upcoming", ready: "upcoming" };
  }
  if (status === "PROCESSING" || status === "DETECT_QUEUED") {
    return { uploaded: "done", reading: "done", detecting: "current", ready: "upcoming" };
  }
  return { uploaded: "done", reading: "done", detecting: "done", ready: "current" };
}
