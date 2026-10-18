import type { LucideIcon } from "lucide-react";
import { Briefcase, FileText, HeartPulse, Scale, ScrollText } from "lucide-react";

import type { DocumentMode } from "@/lib/types";

export interface ModeMeta {
  id: DocumentMode;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const DOCUMENT_MODES: ModeMeta[] = [
  {
    id: "resume_anonymization",
    label: "Resume",
    description: "Hide contact details and keep skills and experience.",
    icon: FileText,
  },
  {
    id: "employment_paperwork_review",
    label: "Employment",
    description: "Find pay, deadlines, and restrictions in offer paperwork.",
    icon: Briefcase,
  },
  {
    id: "medical_paperwork_safe_sharing",
    label: "Medical",
    description: "Share instructions without exposing patient identifiers.",
    icon: HeartPulse,
  },
  {
    id: "legal_contract_review",
    label: "Legal contract",
    description: "Surface obligations, fees, and risky clauses.",
    icon: Scale,
  },
  {
    id: "terms_and_conditions_summarization",
    label: "Terms & conditions",
    description: "Pull out cancellation, refunds, and data use.",
    icon: ScrollText,
  },
];

export function modeMeta(mode: string): ModeMeta {
  return DOCUMENT_MODES.find((item) => item.id === mode) ?? DOCUMENT_MODES[0];
}
