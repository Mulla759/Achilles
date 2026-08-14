"use client";

/**
 * ThinkingTrace — the model's margin notes.
 *
 * Reads like an editor's annotation in the margin of a proof: a single line of
 * running prose while work is happening, an indented trace of what was actually
 * done hanging off a hairline, and a settled one-line summary once it is over.
 * It is deliberately NOT a card — it sits inline on the paper, so it never
 * competes with the real document panels around it.
 *
 * Props-driven: there is no internal timeline, no fake progress, no timers.
 * The only local state is whether the trace is expanded, which stays available
 * after the run finishes so you can go back and read what happened.
 */

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { CSSProperties } from "react";
import styles from "./ThinkingTrace.module.css";

export interface TraceStep {
  /** What was done, in prose: "matched 14 of 19 required keywords". */
  primary: string;
  /** Mono meta pinned to the right: a file, a count, a source. */
  secondary?: string;
  /** Render `primary` in mono — for tool names, file paths, identifiers. */
  mono?: boolean;
}

export interface ThinkingTraceProps {
  /** Present tense, shown while `running`: "reading the job description". */
  title: string;
  /** Past tense, shown once finished: "read the job description". */
  doneTitle: string;
  steps: TraceStep[];
  running: boolean;
  /**
   * Seeds the open/closed state on mount. Left undefined, the trace opens
   * while running and settles closed when the run ends — until the reader
   * touches the header, after which their choice is respected for good.
   */
  defaultExpanded?: boolean;
}

/** `useLayoutEffect` warns when React renders this on the server, so fall back
 *  to `useEffect` there. The measurement it guards only exists in a browser. */
const useIsomorphicLayoutEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

/** Steps stagger in at 120ms (--dur-1) each, but the ramp is capped so a long
 *  trace does not spend two seconds assembling itself. */
const STAGGER_MS = 120;
const STAGGER_CAP = 6;

/** Vertical offset from a step's top edge to the centre of its mark, in px.
 *  Only used as the fallback if a mark has not laid out yet. */
const MARK_CENTRE_FALLBACK = 10;

function RunningMark() {
  // An open arc, not a full ring: the gap is what makes the rotation legible
  // (and under reduced motion the arc still reads as "in progress" because it
  // is visibly unclosed, so the state never depends on the animation).
  return (
    <svg
      className={styles.spin}
      viewBox="0 0 16 16"
      width="14"
      height="14"
      aria-hidden="true"
    >
      <path d="M14 8a6 6 0 1 1-6-6" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function DoneMark() {
  // A proof-reader's tick in the margin.
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path
        d="M2.5 8.5 6 12l7.5-8"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Chevron() {
  return (
    <svg
      viewBox="0 0 16 16"
      width="12"
      height="12"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M3.5 6 8 10.5 12.5 6"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function StepMark({ active }: { active: boolean }) {
  // Active step: a hollow bullet — the note is still being written.
  // Finished step: the same tick as the header, smaller.
  return active ? (
    <svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">
      <circle cx="6" cy="6" r="3" strokeWidth="1.5" />
    </svg>
  ) : (
    <svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">
      <path
        d="M2 6.4 4.6 9 10 3"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ThinkingTrace({
  title,
  doneTitle,
  steps,
  running,
  defaultExpanded,
}: ThinkingTraceProps) {
  const panelId = useId();
  const hasSteps = steps.length > 0;

  const [expanded, setExpanded] = useState(defaultExpanded ?? running);
  // Once the reader has an opinion, `running` stops driving the disclosure.
  const [readerDecided, setReaderDecided] = useState(false);
  const wasRunning = useRef(running);

  useEffect(() => {
    if (wasRunning.current !== running && !readerDecided) {
      // Open when work starts, settle to the summary line when it ends.
      setExpanded(running);
    }
    wasRunning.current = running;
  }, [running, readerDecided]);

  const toggle = useCallback(() => {
    setReaderDecided(true);
    setExpanded((open) => !open);
  }, []);

  // --- the connecting hairline -------------------------------------------
  // Measured, never guessed. It runs from the centre of the first step's mark
  // to the centre of the last one, so it can neither overshoot the final step
  // nor fall short when a step wraps onto two or three lines.
  const listRef = useRef<HTMLOListElement | null>(null);
  const [rule, setRule] = useState<{ top: number; height: number } | null>(
    null,
  );

  useIsomorphicLayoutEffect(() => {
    const list = listRef.current;
    if (!list) {
      setRule(null);
      return;
    }

    const measure = () => {
      const marks = list.querySelectorAll<HTMLElement>("[data-trace-mark]");
      const first = marks[0];
      const last = marks[marks.length - 1];
      if (!first || !last) {
        setRule(null);
        return;
      }
      const centre = (el: HTMLElement) =>
        el.offsetTop + (el.offsetHeight || MARK_CENTRE_FALLBACK * 2) / 2;
      const top = centre(first);
      const height = Math.max(0, centre(last) - top);
      setRule((prev) =>
        prev && prev.top === top && prev.height === height
          ? prev
          : { top, height },
      );
    };

    measure();

    // Re-measure on reflow: the container narrowing rewraps step text, which
    // moves the last mark. Cheaper and more accurate than a resize listener.
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    for (const child of Array.from(list.children)) observer.observe(child);
    return () => observer.disconnect();
  }, [steps, expanded]);

  const heading = (
    <>
      <span className={styles.mark} aria-hidden="true">
        {running ? <RunningMark /> : <DoneMark />}
      </span>
      <span className={running ? styles.titleRunning : styles.titleDone}>
        {running ? title : doneTitle}
      </span>
    </>
  );

  return (
    <section className={styles.root} aria-label="reasoning trace">
      {hasSteps ? (
        <button
          type="button"
          className={styles.header}
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={toggle}
        >
          {heading}
          <span className={styles.count}>
            {steps.length}
            <span className="sr-only"> steps</span>
          </span>
          <span
            className={`${styles.chevron} ${expanded ? styles.chevronOpen : ""}`}
            aria-hidden="true"
          >
            <Chevron />
          </span>
        </button>
      ) : (
        // Nothing to disclose yet, so nothing pretends to be pressable.
        <p className={styles.headerStatic}>{heading}</p>
      )}

      {/*
        Stays mounted, opened with grid-template-rows 0fr -> 1fr — the same
        technique TaskRows and RecommendationCard use, and for the same two
        reasons: no height is ever hardcoded, and nothing clips when a step
        wraps. It replaced an AnimatePresence + motion.div animating
        height: 0 -> auto, which was the only JS animation in the app and the
        only one NOT using --ease: a component's own `transition` prop replaces
        MotionConfig's default rather than merging into it, so passing
        `{ duration: 0.3 }` silently discarded the shared easing curve.

        Keeping it mounted is also what makes the header's aria-controls
        resolve while collapsed, instead of pointing at an id that does not
        exist yet.
      */}
      <div
        id={panelId}
        className={`${styles.panel} ${hasSteps && expanded ? styles.panelOpen : ""}`}
        aria-hidden={!(hasSteps && expanded)}
      >
        <div className={styles.panelClip}>
          {/* The rule is a sibling of the list, not a child: an <ol> may only
              contain <li>, and the measurement origin has to be a positioned
              box shared by both. */}
          <div className={styles.body}>
            {rule ? (
              <span
                className={styles.rule}
                aria-hidden="true"
                style={{ top: rule.top, height: rule.height }}
              />
            ) : null}
            {/* No aria-live here. Appending step 4 to a live <ol> re-announces
                steps 1-4, and the pipeline already has exactly one polite
                region (TaskRows) reporting which stage is in hand. */}
            <ol className={styles.list} ref={listRef}>
              {steps.map((step, i) => {
                // While running, the newest step is the one in hand; every
                // earlier one is settled. Finished runs are all ticks.
                const active = running && i === steps.length - 1;
                return (
                  <li
                    key={`${i}-${step.primary}`}
                    className={styles.step}
                    style={
                      {
                        "--trace-delay": `${Math.min(i, STAGGER_CAP) * STAGGER_MS}ms`,
                      } as CSSProperties
                    }
                  >
                    <span
                      className={styles.stepMark}
                      data-trace-mark=""
                      data-active={active ? "" : undefined}
                    >
                      <StepMark active={active} />
                    </span>
                    <span
                      className={[
                        styles.primary,
                        step.mono ? styles.primaryMono : "",
                        active ? styles.primaryActive : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {step.primary}
                    </span>
                    {step.secondary ? (
                      <span className={styles.secondary}>{step.secondary}</span>
                    ) : null}
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
