/**
 * Shared TS types mirroring docs/API.md and achilles/models.py 1:1.
 * If you change a shape here, it has drifted from the contract — check both
 * files before editing.
 */

// --------------------------------------------------------------------------
// Resume
// --------------------------------------------------------------------------

export type SectionName = "experience" | "projects" | "leadership";

export interface Contact {
  name: string;
  phone: string;
  email: string;
  linkedin: string;
  github: string;
  website: string;
}

export interface SkillGroup {
  label: string;
  items: string;
}

export interface Entry {
  role: string;
  org: string;
  date: string;
  location: string;
  stack: string;
  bullets: string[];
}

export interface Resume {
  contact: Contact;
  target_role: string;
  availability: string;
  education: Entry[];
  skills: SkillGroup[];
  experience: Entry[];
  projects: Entry[];
  leadership: Entry[];
}

// --------------------------------------------------------------------------
// Job description
// --------------------------------------------------------------------------

export interface Keyword {
  label: string;
  forms: string[];
  required: boolean;
  group: string;
}

export interface JobDescription {
  company: string;
  title: string;
  raw: string;
  keywords: Keyword[];
}

// --------------------------------------------------------------------------
// Grading
// --------------------------------------------------------------------------

export interface KeywordHit {
  label: string;
  group: string;
  required: boolean;
  hit: boolean;
  matched_form: string;
}

export interface ScanReport {
  hits: KeywordHit[];
  word_count: number;
  total: number;
  matched: number;
  score: number; // 0-100, overall coverage
  required_score: number; // 0-100, coverage of required quals only
  gaps: string[];
}

export const RUBRIC_GATE_NAMES = [
  "graduation",
  "semantics",
  "metrics",
  "storyline",
  "one_page",
  "mac",
  "ats_parseable",
] as const;

export type RubricGateName = (typeof RUBRIC_GATE_NAMES)[number];

export interface GateResult {
  name: string;
  passed: boolean;
  score: number; // 0-100
  detail: string;
  offenders: string[];
}

export interface RubricReport {
  gates: GateResult[];
  passed: boolean;
  score: number;
  failures: GateResult[];
}

export interface BuildResult {
  resume: Resume;
  typst_source: string;
  pdf_b64: string;
  text: string;
  pages: number;
  scan: ScanReport;
  rubric: RubricReport;
  passes: number;
  notes: string[];
  ready: boolean;
}

// --------------------------------------------------------------------------
// Endpoint payloads
// --------------------------------------------------------------------------

export interface ProviderInfo {
  id: string;
  label: string;
  model: string;
}

export interface HealthResponse {
  ok: boolean;
  version: string;
  /** The server key's provider. "" on a bring-your-own-key deployment. */
  provider?: string;
  /** The server key's default model. "" on a bring-your-own-key deployment. */
  model: string;
  /** Every provider this deployment can call. Absent on an older backend. */
  providers?: ProviderInfo[];
  renderer?: string;
  byo_key_only: boolean;
  server_key: boolean;
}

export interface ScanRequest {
  resume?: Resume;
  resume_text?: string;
  jd_text: string;
  target_role: string;
}

export interface ScanResponse {
  scan: ScanReport;
  rubric: RubricReport;
  pages: number;
}

export interface TailorRequest {
  resume_text?: string;
  resume?: Resume;
  jd_text: string;
  target_role: string;
  availability?: string;
  company_url?: string;
  api_key?: string;
  /** Only needed for a key whose shape matches no known provider. */
  provider?: string;
  /** Only honoured alongside `api_key`; sending it without one is a 400. */
  model?: string;
  max_passes?: number;
}

// --------------------------------------------------------------------------
// Errors
// --------------------------------------------------------------------------

export type ApiErrorCode =
  | "bad_input"
  | "missing_api_key"
  | "ungrounded_claim"
  | "render_failed"
  | "upstream_error";

export interface ErrorEnvelope {
  error: ApiErrorCode | string;
  message: string;
  hint: string;
}

/** Thrown by lib/api.ts for any non-2xx response. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly hint: string;

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.message);
    this.name = "ApiError";
    this.status = status;
    this.code = envelope.error;
    this.hint = envelope.hint;
  }
}
