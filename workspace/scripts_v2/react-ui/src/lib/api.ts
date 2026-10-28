export const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export type RunMode = "dry_run" | "baseline_only" | "report_only" | "full_run";
export type SampleKey = "full_300" | "pilot_60" | "remaining_240" | "custom";
export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "unknown";

export interface SampleInfo {
  key: SampleKey | string;
  label: string;
  path: string;
  exists: boolean;
  rows: number;
  repos: number;
  selected_type_counts: Record<string, number>;
  stratum_counts: Record<string, number>;
  duplicate_class_rows?: number | null;
  missing_focal_files?: number | null;
  missing_test_files?: number | null;
  status: "ok" | "warn" | "error" | "missing" | string;
  error?: string;
}

export interface SamplesPayload {
  active_manifest: string;
  tree_may_be_mutating?: boolean;
  samples: SampleInfo[];
}

export interface ArtifactInfo {
  name: string;
  path: string;
  size_bytes: number;
  modified_at?: string;
}

export interface RunInfo {
  run_id: string;
  status: RunStatus;
  run_mode: RunMode | string;
  sample_csv: string;
  model: string;
  prompt: string;
  workers?: number | null;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  pid?: number;
  return_code?: number;
  source_sample_n?: number;
  buildable_run_n?: number;
  precheck_skipped_n?: number;
  baseline_pass_n?: number;
  baseline_failed_n?: number;
  generation_run_n?: number;
  error?: string;
  artifacts: ArtifactInfo[];
}

export interface RunEvent {
  event_id: number;
  timestamp_utc: string;
  phase: string;
  project: string;
  module: string;
  arm: string;
  focal_class: string;
  test_class: string;
  status: string;
  duration_sec: string | number;
  detail: string;
}

export interface GeneratedTestInfo {
  project: string;
  arm: string;
  file_name: string;
  source_path: string;
  stored_path: string;
  size_bytes: number;
  modified_at?: string;
}

export interface ApiCallInfo {
  timestamp_utc: string;
  model_requested: string;
  model_returned: string;
  duration_sec: string | number;
  prompt_tokens: string | number;
  completion_tokens: string | number;
  total_tokens: string | number;
  status: string;
  error_type: string;
  error_message: string;
}

export interface RunPayload {
  run: RunInfo;
  summary: Record<string, unknown>[];
  diagnostics: Record<string, unknown>[];
  generated_tests: GeneratedTestInfo[];
  api_calls: ApiCallInfo[];
  metrics_preview: Record<string, unknown>[];
  recent_events: RunEvent[];
}

export interface CreateRunInput {
  sample_key: SampleKey;
  custom_sample_csv?: string;
  run_mode: RunMode;
  model: string;
  prompt: string;
  workers: number;
  resume: boolean;
  clear_agone_output: boolean;
}

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listSamples: () => jsonRequest<SamplesPayload>("/api/samples"),
  listRuns: () => jsonRequest<RunInfo[]>("/api/runs"),
  getRun: (runId: string) => jsonRequest<RunPayload>(`/api/runs/${runId}`),
  createRun: (input: CreateRunInput) =>
    jsonRequest<RunInfo>("/api/runs", { method: "POST", body: JSON.stringify(input) }),
  cancelRun: (runId: string) => jsonRequest<RunInfo>(`/api/runs/${runId}/cancel`, { method: "POST" }),
  artifactUrl: (runId: string, artifactName: string) =>
    `${API_BASE}/api/runs/${runId}/artifacts/${encodeURIComponent(artifactName)}`
};
