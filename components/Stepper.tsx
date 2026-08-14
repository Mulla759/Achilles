"use client";

import { useId } from "react";
import styles from "./Stepper.module.css";

interface StepperProps {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}

export function Stepper({ label, value, min, max, onChange }: StepperProps) {
  const id = useId();
  const atMin = value <= min;
  const atMax = value >= max;

  return (
    <div className={styles.field}>
      <span className={styles.label} id={id}>
        {label.toLowerCase()}
      </span>
      {/*
        The group's own name carries the current value, so entering it announces
        "max passes, currently 3" instead of "max passes, group" with the figure
        never spoken.
      */}
      <div
        className={styles.control}
        role="group"
        aria-label={`${label.toLowerCase()}, currently ${value}`}
      >
        {/*
          aria-disabled, not disabled. The browser removes focus from an element
          that becomes disabled, so stepping up to the maximum threw the user's
          focus to <body> and they had to Tab in from the top of the page to
          reach the run button — at the exact moment they had finished setting
          the value. The handlers already clamp with Math.min/Math.max, so a
          click at the bound is a no-op either way; this keeps the button
          focusable and still announces it as unavailable.
        */}
        <button
          type="button"
          className={styles.btn}
          onClick={() => onChange(Math.max(min, value - 1))}
          aria-disabled={atMin}
          aria-label={`Decrease ${label}`}
        >
          −
        </button>
        <span className={`${styles.value} tabular`} aria-live="polite">
          {value}
        </span>
        <button
          type="button"
          className={styles.btn}
          onClick={() => onChange(Math.min(max, value + 1))}
          aria-disabled={atMax}
          aria-label={`Increase ${label}`}
        >
          +
        </button>
      </div>
    </div>
  );
}
