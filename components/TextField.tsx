"use client";

import { useId, type InputHTMLAttributes } from "react";
import styles from "./TextField.module.css";

interface TextFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "value" | "onChange"> {
  label: string;
  value: string;
  onChange: (value: string) => void;
  optional?: boolean;
  error?: string;
  hint?: string;
}

export function TextField({
  label,
  value,
  onChange,
  optional,
  error,
  hint,
  required,
  ...rest
}: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <div className={styles.field}>
      <div className={styles.labelRow}>
        <label htmlFor={id} className={styles.label}>
          {label.toLowerCase()}
          {required ? <span aria-hidden="true"> *</span> : null}
        </label>
        {optional ? <span className={styles.optional}>optional</span> : null}
      </div>
      <input
        id={id}
        className={`${styles.input} ${error ? styles.invalid : ""}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        required={required}
        {...rest}
      />
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}
