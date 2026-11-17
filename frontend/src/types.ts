export interface DocumentInfo {
  id: number;
  family: string;
  title: string;
  version_label: string;
  effective_date: string | null;
  is_current: boolean;
  source_filename: string;
  page_count: number;
  chunk_count: number;
  uploaded_at: string;
}

export interface Source {
  ref: string;
  chunk_id: number;
  document_id: number;
  title: string;
  family: string;
  version_label: string;
  is_current: boolean;
  section: string | null;
  page_start: number;
  page_end: number;
  excerpt: string;
  similarity: number;
  cited: boolean;
}

export interface Contradiction {
  kind: "numeric" | "llm" | "version_change";
  ref_a: string;
  ref_b: string;
  explanation: string;
  confidence: "low" | "medium" | "high";
}

export interface Answer {
  status: "answered" | "refused";
  answer: string | null;
  refusal_reason: string | null;
  refusal_message: string | null;
  sources: Source[];
  contradictions: Contradiction[];
  warnings: string[];
  citation_coverage: number | null;
  top_similarity: number | null;
  llm_provider: string;
  latency_ms: number;
}

export interface Family {
  family: string;
  versions: DocumentInfo[];
}

export interface SectionDiff {
  section: string;
  change: "added" | "removed" | "modified";
  page_from: number | null;
  page_to: number | null;
  diff: string[];
}

export interface VersionDiff {
  family: string;
  from_document: DocumentInfo;
  to_document: DocumentInfo;
  unchanged_sections: number;
  changes: SectionDiff[];
}
