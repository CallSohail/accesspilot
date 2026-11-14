/**
 * TypeScript interfaces mirroring the AccessPilot backend API contract.
 * Field names must match the backend exactly.
 */

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  ai_configured: boolean;
  ai_model: string | null;
}

export interface DocumentInfo {
  filename: string;
  kind: 'pdf' | 'docx' | 'pptx';
  size_bytes: number;
  num_blocks: number;
}

export interface Block {
  index: number;
  kind: 'heading' | 'paragraph' | 'image' | 'link' | 'table' | 'list' | 'other';
  text: string;
  heading_level: number | null;
  has_alt_text: boolean | null;
  link_label: string | null;
  page: number | null;
  slide: number | null;
}

export type Severity = 'error' | 'warning' | 'info';
export type FindingSource = 'deterministic' | 'ai' | 'human';

export interface Finding {
  id: string;
  rule: string;
  severity: Severity;
  source: FindingSource;
  location: string;
  description: string;
  detail: string;
  remediation: string;
  wcag_ref: string;
  block_index: number | null;
  suggestion: string | null;
}

export interface Suggestion {
  finding_id: string;
  location: string;
  before: string;
  after: string;
  rationale: string;
  source: FindingSource;
}

export interface Summary {
  errors: number;
  warnings: number;
  info: number;
  total_blocks: number;
}

export interface Report {
  report_id: string;
  created_at: string;
  document: DocumentInfo;
  blocks: Block[];
  findings: Finding[];
  suggestions: Suggestion[];
  summary: Summary;
  ai_available: boolean;
  ai_model: string | null;
  notes: string[];
}

export interface AssistantResponse {
  ok: boolean;
  answer: string;
  model: string | null;
  provider_configured: boolean;
  error: string | null;
}
