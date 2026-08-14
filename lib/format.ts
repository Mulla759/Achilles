import type { RubricGateName } from "./types";

/** Stable gate name -> human label, per docs/API.md's rubric gate table. */
export const GATE_LABELS: Record<RubricGateName | string, string> = {
  graduation: "graduation date",
  semantics: "word choice",
  metrics: "metrics",
  storyline: "storyline",
  one_page: "one page",
  mac: "mac (metric/action/context)",
  ats_parseable: "ats parseable",
};

export function gateLabel(name: string): string {
  return GATE_LABELS[name] ?? name;
}

function slugify(input: string): string {
  return (
    input
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "resume"
  );
}

/** `<lastname>-<role-slug>` used as the base for both download filenames. */
export function downloadBasename(fullName: string, targetRole: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  const last = parts.length ? parts[parts.length - 1] : "resume";
  return `${slugify(last ?? "resume")}-${slugify(targetRole)}`;
}

export function base64ToBlob(b64: string, mime: string): Blob {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mime });
}

/** Renders an ASCII bar meter like `[██████████████░░░░░░]`. */
export function asciiMeter(pct: number, width = 20): string {
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  const filled = Math.round((clamped / 100) * width);
  return `[${"█".repeat(filled)}${"░".repeat(Math.max(0, width - filled))}]`;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Give the browser a tick to pick up the download before revoking.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
