"use client";

import { useId, useState, type RefObject } from "react";
import styles from "./AdvancedSection.module.css";
import { Stepper } from "./Stepper";

interface AdvancedSectionProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  keyRequired: boolean;
  maxPasses: number;
  onMaxPassesChange: (value: number) => void;
  apiKeyRef?: RefObject<HTMLInputElement | null>;
  /** Validation message for the key field. Before this existed the page set
   *  the error and nothing ever rendered it, so a run just silently refused
   *  to start. */
  error?: string;
}

/** Rotated by CSS off the trigger's own aria-expanded, so the glyph can never
 *  disagree with the state a screen reader is told. */
function Chevron() {
  return (
    <svg
      className={styles.chevron}
      viewBox="0 0 12 12"
      width="12"
      height="12"
      aria-hidden="true"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4.25 2.5 L8 6 L4.25 9.5" />
    </svg>
  );
}

export function AdvancedSection({
  open,
  onOpenChange,
  apiKey,
  onApiKeyChange,
  keyRequired,
  maxPasses,
  onMaxPassesChange,
  apiKeyRef,
  error,
}: AdvancedSectionProps) {
  const keyId = useId();
  const bodyId = useId();
  const errorId = `${keyId}-error`;
  const [reveal, setReveal] = useState(false);

  return (
    <section className={styles.section}>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => onOpenChange(!open)}
        aria-expanded={open}
        aria-controls={bodyId}
      >
        <Chevron />
        <span className={styles.triggerLabel}>advanced</span>
        {keyRequired ? <span className={styles.requiredBadge}>key required</span> : null}
      </button>
      {/*
        Mounted whether or not it is open, and collapsed with
        grid-template-rows 0fr -> 1fr like every other disclosure in the app.
        Two reasons it cannot be conditional: the trigger's aria-controls has to
        resolve to a real element (a screen-reader user asking to jump to the
        controlled region got nothing), and Ctrl+K opens this panel and focuses
        the key field in the next frame, which needs the input to exist.
        `inert` keeps the collapsed field out of the tab order — and it is
        removed in the same commit that opens the panel, so the Ctrl+K focus
        still lands.
      */}
      <div
        className={`${styles.panel} ${open ? styles.panelOpen : ""}`}
        id={bodyId}
        inert={!open}
      >
        <div className={styles.panelClip}>
          <div className={styles.body}>
            <div className={styles.keyRow}>
              <label htmlFor={keyId} className={styles.keyLabel}>
                anthropic api key{keyRequired ? " *" : ""}
              </label>
              <div className={styles.keyInputRow}>
                <input
                  id={keyId}
                  ref={apiKeyRef}
                  type={reveal ? "text" : "password"}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="sk-ant-..."
                  value={apiKey}
                  required={keyRequired}
                  onChange={(e) => onApiKeyChange(e.target.value)}
                  className={`${styles.keyInput} ${error ? styles.keyInvalid : ""}`}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? errorId : undefined}
                />
                <button
                  type="button"
                  className={styles.showBtn}
                  onClick={() => setReveal((v) => !v)}
                  aria-pressed={reveal}
                >
                  {reveal ? "hide" : "show"}
                </button>
              </div>
              {error ? (
                <p id={errorId} className={styles.error} role="alert">
                  {error}
                </p>
              ) : null}
              {/* This copy is a privacy promise. Do not reword it. */}
              <p className={styles.note}>
                sent only to this app&apos;s own /api/tailor, held in memory for this page only —
                never written to disk or browser storage. reloading the page clears it.
              </p>
            </div>
            <Stepper
              label="max passes"
              value={maxPasses}
              min={1}
              max={5}
              onChange={onMaxPassesChange}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
