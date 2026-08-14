"use client";

import { useId, useState } from "react";
import styles from "./TaskRows.module.css";

/* ==========================================================================
   TaskRows — the tailoring pipeline as a list of expandable status rows.
   --------------------------------------------------------------------------
   A tailor run takes 30-90s. A spinner for that long is a lie: it says
   "something is happening" without saying what. This says what.

   The component is PURELY driven by props. It owns no timers, no fake
   sequence, and never mutates a task — the parent advances `state` as the
   server reports progress. The only local state is which rows the reader has
   opened, which is a reading preference, not pipeline data.
   ========================================================================== */

export type TaskState = "pending" | "running" | "done" | "failed";

export interface TaskDetail {
  label: string;
  meta?: string;
}

export interface Task {
  id: string;
  /** Human phrase, lowercase, present participle: "rewriting bullets". */
  label: string;
  /** Right-aligned figure or count: "18 bullets", "2 passes", "612 words". */
  meta?: string;
  state: TaskState;
  /** Sub-steps. A row is only expandable when this is non-empty. */
  details?: TaskDetail[];
}

export interface TaskRowsProps {
  tasks: Task[];
  /** Spoken name of the list. Defaults to "Tailoring pipeline". */
  label?: string;
}

/** Spoken + printed name of each state. Colour is never the only signal
 *  (rule 2): every row carries this word in its pill as well as a distinct
 *  glyph SHAPE, so the row survives greyscale print and colour blindness. */
const STATE_WORD: Record<TaskState, string> = {
  pending: "pending",
  running: "running",
  done: "done",
  failed: "failed",
};

/** Explicit map rather than `styles[state]` — a CSS Module is typed as an
 *  index signature, so a renamed class would fail silently at runtime instead
 *  of at typecheck. */
const PILL_CLASS: Record<TaskState, string | undefined> = {
  pending: styles.pillPending,
  running: styles.pillRunning,
  done: styles.pillDone,
  failed: styles.pillFailed,
};

/* --------------------------------------------------------------------------
   Status glyph — 24px, inline SVG only (rule 5).
   pending  hollow ring carrying the step number
   running  the same ring plus a rotating arc, number still legible
   done     a bare check, like a marker tick in the margin
   failed   a bare cross
   The ring/check/cross are different SHAPES, so the state reads with no
   colour at all; --ins / --del only reinforce what the shape already says.
   -------------------------------------------------------------------------- */

function StatusGlyph({ state, step }: { state: TaskState; step: number }) {
  if (state === "done") {
    return (
      <span className={`${styles.glyph} ${styles.glyphDone}`} aria-hidden="true">
        <svg viewBox="0 0 24 24" width="24" height="24" focusable="false">
          <path
            d="M6 12.5 L10 16.5 L18 7.5"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    );
  }

  if (state === "failed") {
    return (
      <span
        className={`${styles.glyph} ${styles.glyphFailed}`}
        aria-hidden="true"
      >
        <svg viewBox="0 0 24 24" width="24" height="24" focusable="false">
          <path
            d="M7 7 L17 17 M17 7 L7 17"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </span>
    );
  }

  const running = state === "running";

  return (
    <span
      className={`${styles.glyph} ${running ? styles.glyphRunning : styles.glyphPending}`}
      aria-hidden="true"
    >
      <svg
        className={styles.ring}
        viewBox="0 0 24 24"
        width="24"
        height="24"
        focusable="false"
      >
        <circle cx="12" cy="12" r="9" strokeWidth="1.25" />
      </svg>
      {running ? (
        <svg
          className={styles.arc}
          viewBox="0 0 24 24"
          width="24"
          height="24"
          focusable="false"
        >
          <path
            d="M12 3 A 9 9 0 0 1 20.86 10.44"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
        </svg>
      ) : null}
      <span className={`${styles.step} tabular`}>{step}</span>
    </span>
  );
}

function Chevron() {
  return (
    <svg
      className={styles.chevron}
      viewBox="0 0 14 14"
      width="14"
      height="14"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M3.5 5.25 L7 8.75 L10.5 5.25"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/* -------------------------------------------------------------------------- */

export default function TaskRows({ tasks, label }: TaskRowsProps) {
  /* Explicit reader choices only. A row with no entry here falls back to the
     prop-derived default below, so the list keeps following the pipeline
     until the reader takes over a particular row. */
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const baseId = useId();

  if (tasks.length === 0) return null;

  const toggle = (id: string, open: boolean) =>
    setOverrides((prev) => ({ ...prev, [id]: !open }));

  /* The one spoken summary of the pipeline. A single polite region that names
     the stage and its position, so a 60-second run is a handful of short
     announcements instead of five rows all talking at once. */
  const activeIndex = tasks.findIndex(
    (task) => task.state === "running" || task.state === "failed",
  );
  const active = activeIndex === -1 ? undefined : tasks[activeIndex];
  const progress = active
    ? `stage ${activeIndex + 1} of ${tasks.length}, ${active.label} — ${STATE_WORD[active.state]}`
    : tasks.every((task) => task.state === "done")
      ? `all ${tasks.length} stages done`
      : "";

  return (
    <div className={styles.card}>
      <ol className={styles.list} aria-label={label ?? "Tailoring pipeline"}>
        {tasks.map((task, i) => {
          const details = task.details ?? [];
          const expandable = details.length > 0;
          /* Default open for the step being worked on and for anything that
             broke — those are the only two rows a reader wants unfolded
             without asking. Everything else stays quiet. */
          const defaultOpen =
            task.state === "running" || task.state === "failed";
          const isOpen =
            expandable && (overrides[task.id] ?? defaultOpen);
          const panelId = `${baseId}-${i}-panel`;

          const rowBody = (
            <>
              <StatusGlyph state={task.state} step={i + 1} />
              <span
                className={`${styles.label} ${task.state === "running" ? styles.labelRunning : ""}`}
              >
                {task.label}
              </span>
              {/* Always rendered, even when empty, so the row keeps its five
                  grid tracks AND so the narrow-screen rule below can drop this
                  column by class. */}
              <span className={`${styles.meta} tabular`} aria-hidden={task.meta ? undefined : true}>
                {task.meta ?? ""}
              </span>
              {/* Not a live region. One stage tick re-renders every row, so five
                  live pills spoke "running… pending… done…" with no way to tell
                  which row had moved. The single region at the foot of this
                  component says which stage is in hand, once. */}
              <span className={`${styles.pill} ${PILL_CLASS[task.state]}`}>
                {STATE_WORD[task.state]}
              </span>
              {expandable ? <Chevron /> : <span aria-hidden="true" />}
            </>
          );

          return (
            <li key={task.id} className={styles.item}>
              {expandable ? (
                <button
                  type="button"
                  className={`${styles.row} ${styles.rowBtn} ${isOpen ? styles.rowOpen : ""}`}
                  aria-expanded={isOpen}
                  aria-controls={panelId}
                  onClick={() => toggle(task.id, isOpen)}
                >
                  {rowBody}
                </button>
              ) : (
                <div className={styles.row}>{rowBody}</div>
              )}

              {expandable ? (
                <div
                  id={panelId}
                  className={`${styles.panel} ${isOpen ? styles.panelOpen : ""}`}
                  aria-hidden={!isOpen}
                >
                  <div className={styles.panelInner}>
                    <ul className={styles.subList}>
                      {details.map((detail, j) => (
                        <li
                          key={`${detail.label}-${j}`}
                          className={styles.subRow}
                          /* 100ms stagger. Non-important inline value, so the
                             global reduced-motion `!important` overrides it. */
                          style={{ animationDelay: `${j * 100}ms` }}
                        >
                          <span className={styles.subLabel}>{detail.label}</span>
                          {detail.meta ? (
                            <span className={`${styles.subMeta} tabular`}>
                              {detail.meta}
                            </span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>

      <p className="sr-only" aria-live="polite">
        {progress}
      </p>
    </div>
  );
}

export { TaskRows };
