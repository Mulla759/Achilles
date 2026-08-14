/**
 * No client-side persistence, by policy.
 *
 * A resume and a job description are personal data — full name, phone, email,
 * employment history. Students run this on shared machines (library, lab, a
 * friend's laptop), where anything in `localStorage` outlives the session and
 * is readable by any script later served from the same origin. An API key in
 * `sessionStorage` has the same exposure for the life of the tab.
 *
 * So nothing is written: the form lives in React state and dies with the page.
 * The cost is that a refresh loses a pasted JD, which is the correct trade for
 * not leaving someone's resume on a public computer.
 *
 * The module keeps its original shape (rather than deleting the calls at every
 * call site) so the no-persistence guarantee is enforced in exactly one place —
 * a future `saveForm` cannot quietly start writing again without editing this
 * file. `purgeStoredData` exists because removing the writes is not enough:
 * anyone who used an earlier build still has data on disk, and it needs
 * clearing on their next visit.
 */

/** Keys written by earlier builds. Kept only so they can be removed. */
const LEGACY_KEYS = ["achilles:form:v1", "achilles:api-key:v1"] as const;

export interface PersistedForm {
  jdText: string;
  resumeText: string;
  targetRole: string;
  availability: string;
  companyUrl: string;
  maxPasses: number;
  advancedOpen: boolean;
}

/** Delete anything a previous version of this app persisted. Safe to call often. */
export function purgeStoredData(): void {
  if (typeof window === "undefined") return;
  for (const store of [window.localStorage, window.sessionStorage]) {
    try {
      for (const key of LEGACY_KEYS) store.removeItem(key);
    } catch {
      // Storage access throws under some privacy settings; nothing to clean up
      // in that case anyway.
    }
  }
}

/** Always null: nothing is ever restored from the client. */
export function loadForm(): Partial<PersistedForm> | null {
  return null;
}

/** Intentionally a no-op. See the module comment. */
export function saveForm(_form: PersistedForm): void {
  // deliberately empty
}

/** Always empty: the key is held in memory only, for the life of the page. */
export function loadSessionApiKey(): string {
  return "";
}

/** Intentionally a no-op. */
export function saveSessionApiKey(_key: string): void {
  // deliberately empty
}

export function clearSessionApiKey(): void {
  purgeStoredData();
}
