/**
 * Fetch layer for the Achilles API (docs/API.md). Every function throws
 * ApiError on a non-2xx response, with `message`/`hint` lifted straight from
 * the server's error envelope so the UI never has to guess.
 */

import {
  ApiError,
  type BuildResult,
  type ErrorEnvelope,
  type HealthResponse,
  type ScanRequest,
  type ScanResponse,
  type TailorRequest,
} from "./types";

const DEGRADED_HEALTH: HealthResponse = {
  ok: false,
  version: "",
  model: "",
  byo_key_only: false,
  server_key: true,
};

async function parseErrorEnvelope(res: Response): Promise<ErrorEnvelope> {
  try {
    const body: unknown = await res.json();
    if (
      body &&
      typeof body === "object" &&
      "message" in body &&
      typeof (body as Record<string, unknown>).message === "string"
    ) {
      const b = body as Record<string, unknown>;
      return {
        error: typeof b.error === "string" ? b.error : "unknown_error",
        message: b.message as string,
        hint: typeof b.hint === "string" ? b.hint : "",
      };
    }
  } catch {
    // fall through to generic envelope below
  }
  return {
    error: "unknown_error",
    message: `Request failed with status ${res.status}.`,
    hint: "Try again in a moment. If this keeps happening, check your connection.",
  };
}

async function postJson<TResponse>(url: string, payload: unknown): Promise<TResponse> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError(0, {
      error: "network_error",
      message: "Could not reach the server.",
      hint: "Check your internet connection and try again.",
    });
  }

  if (!res.ok) {
    const envelope = await parseErrorEnvelope(res);
    throw new ApiError(res.status, envelope);
  }

  return (await res.json()) as TResponse;
}

/**
 * GET /api/health. Degrades gracefully: if the endpoint is unreachable (e.g.
 * during `next dev`, where /api/* 404s), assume server_key=true and
 * byo_key_only=false so the app stays usable.
 */
export async function getHealth(): Promise<HealthResponse> {
  try {
    const res = await fetch("/api/health", { method: "GET" });
    if (!res.ok) return DEGRADED_HEALTH;
    const body = (await res.json()) as HealthResponse;
    if (typeof body?.ok !== "boolean") return DEGRADED_HEALTH;
    return body;
  } catch {
    return DEGRADED_HEALTH;
  }
}

/** POST /api/scan — deterministic grading only, no LLM, no API key required. */
export function scanResume(payload: ScanRequest): Promise<ScanResponse> {
  return postJson<ScanResponse>("/api/scan", payload);
}

/** POST /api/tailor — the full rewrite -> render -> grade loop. */
export function tailorResume(payload: TailorRequest): Promise<BuildResult> {
  return postJson<BuildResult>("/api/tailor", payload);
}
