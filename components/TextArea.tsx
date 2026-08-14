"use client";

import {
  useId,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type TextareaHTMLAttributes,
} from "react";
import styles from "./TextArea.module.css";

interface TextAreaProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id" | "value" | "onChange"> {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  /** Minimum character count to consider the field satisfied; shown in the counter. */
  minLength?: number;
  /** Show a "Paste" convenience button next to the label (JD field is the hero action). */
  showPasteButton?: boolean;
  /** Accept a dropped .txt/.md file and read its contents into the field. */
  acceptFileDrop?: boolean;
}

/** Renders like an editor buffer: line-number gutter, block caret, no chrome. */
export function TextArea({
  label,
  value,
  onChange,
  error,
  minLength,
  showPasteButton,
  acceptFileDrop,
  required,
  rows = 10,
  ...rest
}: TextAreaProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const countId = `${id}-count`;
  const [isDragging, setIsDragging] = useState(false);
  const [pasteError, setPasteError] = useState("");
  const dragCounter = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);

  const count = value.length;
  const belowMin = typeof minLength === "number" && count > 0 && count < minLength;

  const lineCount = useMemo(() => {
    const n = value.length === 0 ? 1 : value.split("\n").length;
    return Math.max(n, rows);
  }, [value, rows]);

  const lineNumbers = useMemo(() => Array.from({ length: lineCount }, (_, i) => i + 1), [lineCount]);

  function syncGutterScroll() {
    if (textareaRef.current && gutterRef.current) {
      gutterRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }

  async function handlePasteClick() {
    setPasteError("");
    try {
      const text = await navigator.clipboard.readText();
      if (text) onChange(text);
    } catch {
      setPasteError("clipboard access denied — paste with Ctrl+V instead.");
    }
  }

  function readFile(file: File) {
    const okType = /\.(txt|md)$/i.test(file.name);
    if (!okType) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") onChange(reader.result);
    };
    reader.readAsText(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    if (!acceptFileDrop) return;
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) readFile(file);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    if (!acceptFileDrop) return;
    e.preventDefault();
  }

  function handleDragEnter(e: DragEvent<HTMLDivElement>) {
    if (!acceptFileDrop) return;
    e.preventDefault();
    dragCounter.current += 1;
    setIsDragging(true);
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    if (!acceptFileDrop) return;
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  }

  const wrapClass = [styles.wrap, error ? styles.wrapInvalid : "", isDragging ? styles.wrapDragging : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.field}>
      <div className={styles.labelRow}>
        <label htmlFor={id} className={styles.label}>
          {label.toLowerCase()}
          {required ? <span aria-hidden="true"> *</span> : null}
        </label>
        <div className={styles.labelActions}>
          {/* role="alert": pressing "paste" and being refused by the clipboard
              permission is a dead end unless the reader is told to use Ctrl+V,
              and in a bare <span> that message reached nobody. */}
          {pasteError ? (
            <span className={styles.error} role="alert">
              {pasteError}
            </span>
          ) : null}
          {showPasteButton ? (
            <button type="button" className={styles.pasteButton} onClick={handlePasteClick}>
              paste
            </button>
          ) : null}
        </div>
      </div>
      <div
        className={wrapClass}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
      >
        <div className={styles.editor}>
          <div className={styles.gutter} ref={gutterRef} aria-hidden="true">
            {lineNumbers.map((n) => (
              <div key={n} className={styles.gutterLine}>
                {n}
              </div>
            ))}
          </div>
          <textarea
            id={id}
            ref={textareaRef}
            className={styles.textarea}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onScroll={syncGutterScroll}
            rows={rows}
            spellCheck={false}
            aria-invalid={error ? true : undefined}
            /* The counter is described BY the field, not just drawn near it.
               Without this a blind user typing into the JD box never learned
               they were under the 40-character minimum — neither the counter
               nor its "· short" state was reachable — until they pressed run
               and validation fired. */
            aria-describedby={[error ? errorId : null, countId].filter(Boolean).join(" ")}
            required={required}
            {...rest}
          />
        </div>
        <div className={styles.footerRow}>
          {acceptFileDrop ? <span className={styles.dropHint}>drop a .txt or .md file</span> : <span />}
          <span
            id={countId}
            className={`${styles.count} tabular ${belowMin ? styles.countBad : ""}`}
          >
            {count.toLocaleString()}
            {typeof minLength === "number" ? ` / ${minLength} min` : " chars"}
            {/* The word, not the colour, is what says the field is short. */}
            {belowMin ? " · short" : ""}
          </span>
        </div>
      </div>
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
