"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./LoadingState.module.css";

export type LoadingVariant = "grid" | "dots" | "orbit";

export interface LoadingStateProps {
  /** What the machine is doing right now, lower case: "churning", "grading". */
  label: string;
  /** Cell choreography. "grid"/"dots" drive a chevron right; "orbit" laps. */
  variant?: LoadingVariant;
  /** ms epoch the work began. Omitted → the timer counts from mount. */
  startedAt?: number;
}

/* --------------------------------------------------------------------------
   Cell choreography
   --------------------------------------------------------------------------
   Nine cells, index 0..8, row-major:

       0 1 2
       3 4 5
       6 7 8

   Delays are computed here rather than in CSS because they are arithmetic on
   the cell's position, and nine hand-written :nth-child() rules per variant
   would be three copies of the same sum. Each cell carries its delay as a
   custom property; the module reads it in one rule.
   -------------------------------------------------------------------------- */

/** Chevron wavefront driving right: front is delayed by column, and by
 *  distance from the middle row, so the leading edge is a ">" not a bar. */
function chevronDelay(index: number): number {
  const row = Math.floor(index / 3);
  const col = index % 3;
  return (col + Math.abs(row - 1)) * 90;
}

/** Perimeter, clockwise from the top-left. The centre (4) is absent on
 *  purpose — it stays permanently dim so the comet has something to lap. */
const ORBIT_ORDER = [0, 1, 2, 5, 8, 7, 6, 3] as const;

function orbitDelay(index: number): number | null {
  const step = ORBIT_ORDER.indexOf(index as (typeof ORBIT_ORDER)[number]);
  return step === -1 ? null : step * 110;
}

const CYCLE_CHEVRON = 650;
const CYCLE_ORBIT = 950;

/* --------------------------------------------------------------------------
   Elapsed time
   -------------------------------------------------------------------------- */

/**
 * Tenths under a minute, minutes + zero-padded tenths above it:
 *   940ms   → "0.9s"
 *   4200ms  → "4.2s"
 *   64200ms → "1m 04.2s"
 *
 * Truncates rather than rounds, so 59.97s reads "59.9s" and never the
 * impossible "60.0s".
 */
export function formatElapsed(ms: number): string {
  const tenths = Math.max(0, Math.floor(ms / 100));
  const minutes = Math.floor(tenths / 600);
  const seconds = ((tenths - minutes * 600) / 10).toFixed(1);
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds.padStart(4, "0")}s`;
}

const TICK_MS = 100;

/**
 * Inline loader for long-running work: a 3x3 pixel grid, a shimmering label,
 * and a live elapsed timer in tabular figures. One row, no card, no border —
 * it is meant to sit in a line of running text or beside a button.
 *
 * Under prefers-reduced-motion the grid freezes to its dim floor and the label
 * stops pulsing, but the timer keeps ticking: it is information, not
 * decoration, and it is the only thing telling the reader that a slow job is
 * still alive.
 */
export default function LoadingState({
  label,
  variant = "grid",
  startedAt,
}: LoadingStateProps) {
  const [elapsed, setElapsed] = useState(0);

  /* Mount time, captured on the client only. Not derived during render: the
     server and the browser would stamp different values and the first paint
     would be a hydration mismatch. */
  const mountedAt = useRef<number | null>(null);

  useEffect(() => {
    /* Elapsed is always recomputed from a fixed origin, never accumulated by
       adding TICK_MS to a counter. A background tab throttles timers to about
       once a second, so a counter would silently run slow and under-report a
       job that is actually taking a minute. */
    if (mountedAt.current === null) mountedAt.current = Date.now();
    const origin = startedAt ?? mountedAt.current;

    const tick = () => setElapsed(Math.max(0, Date.now() - origin));
    tick();

    const id = window.setInterval(tick, TICK_MS);
    return () => window.clearInterval(id);
  }, [startedAt]);

  const isOrbit = variant === "orbit";
  const cycle = isOrbit ? CYCLE_ORBIT : CYCLE_CHEVRON;

  const variantClass = isOrbit
    ? styles.orbit
    : variant === "dots"
      ? styles.dots
      : styles.gridVariant;

  return (
    /*
     * Deliberately NOT role="status". This mounts with its text already inside
     * it, and a live region only announces MUTATIONS to a region that was
     * already present — so the role never bought an announcement. What it did
     * buy was another region competing with the pipeline's during a run, and a
     * timer ticking ten times a second inside it. The label is ordinary visible
     * text; the run's progress is announced once, by TaskRows.
     */
    <span className={styles.root} style={{ ["--cycle" as string]: `${cycle}ms` }}>
      {/* Decorative: the label and the timer already say everything. */}
      <span className={`${styles.grid} ${variantClass}`} aria-hidden="true">
        {Array.from({ length: 9 }, (_, i) => {
          const delay = isOrbit ? orbitDelay(i) : chevronDelay(i);
          return (
            <span
              key={i}
              className={delay === null ? `${styles.cell} ${styles.dim}` : styles.cell}
              style={delay === null ? undefined : { ["--delay" as string]: `${delay}ms` }}
            />
          );
        })}
      </span>

      <span className={styles.label}>{label}</span>

      {/* aria-hidden: a figure that changes ten times a second is for eyes
          only. The label beside it is the readable message. */}
      <span className={`${styles.timer} tabular`} aria-hidden="true">
        {formatElapsed(elapsed)}
      </span>
    </span>
  );
}

export { LoadingState };
