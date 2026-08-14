"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import styles from "./HelpOverlay.module.css";

const BINDINGS: [string, string][] = [
  ["Ctrl+Enter", "run tailor"],
  ["Ctrl+S", "just score"],
  ["Ctrl+K", "focus api key field"],
  ["Tab / Shift+Tab", "move between fields"],
  ["?", "toggle this help"],
  ["Esc", "close overlay / blur field"],
];

interface HelpOverlayProps {
  open: boolean;
  onClose: () => void;
}

/** Everything inside the dialog that Tab may land on. The dialog element
 *  itself is `tabIndex={-1}` — programmatically focusable, deliberately not
 *  part of the cycle — so it is excluded by the `:not([tabindex="-1"])` tail. */
const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function CloseMark() {
  return (
    <svg
      viewBox="0 0 12 12"
      width="12"
      height="12"
      aria-hidden="true"
      focusable="false"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <path d="M3 3 L9 9 M9 3 L3 9" />
    </svg>
  );
}

export function HelpOverlay({ open, onClose }: HelpOverlayProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  /**
   * Take focus on open and give it back on close. Without the restore, closing
   * unmounts the focused node, focus falls to <body>, and a keyboard user has
   * to Tab in from the top of the document to get back to the field they were
   * in when they pressed `?`.
   */
  useEffect(() => {
    if (!open) return;
    const previous =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => {
      previous?.focus();
    };
  }, [open]);

  if (!open) return null;

  /**
   * `aria-modal="true"` asserts the rest of the page is unavailable, so Tab has
   * to actually stay inside. Without this, the second Tab walks into the input
   * rail behind the scrim, where the caret is invisible.
   */
  function trapTab(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "Tab") return;
    const root = dialogRef.current;
    if (!root) return;

    const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = items[0];
    const last = items[items.length - 1];
    if (!first || !last) {
      // Nothing to move to; hold focus on the dialog rather than leaking it.
      e.preventDefault();
      root.focus();
      return;
    }

    const active = document.activeElement;
    if (e.shiftKey) {
      if (active === first || active === root) {
        e.preventDefault();
        last.focus();
      }
    } else if (active === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <div className={styles.overlay}>
      {/*
        A real <button>, not a <div onClick>. Click-outside used to be the only
        pointer dismissal in the app and it had no role, no accessible name and
        no keyboard equivalent — a voice-control or switch user had to guess
        that Esc worked. As a button it is named and actionable. It stays out
        of the Tab cycle (tabIndex -1) because a viewport-sized focus ring is
        not a useful stop; the close button below and Esc are the keyboard
        paths, and both are spelled out in the dialog.
      */}
      <button
        type="button"
        className={styles.scrim}
        aria-label="close keyboard help"
        tabIndex={-1}
        onClick={onClose}
      />

      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
        tabIndex={-1}
        onKeyDown={trapTab}
      >
        <header className={styles.head}>
          <h2 className={styles.title} id="help-title">
            keyboard
          </h2>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label="close keyboard help"
          >
            <CloseMark />
          </button>
        </header>
        <ul className={styles.list}>
          {BINDINGS.map(([key, desc]) => (
            <li key={key}>
              <kbd>{key}</kbd>
              <span className={styles.desc}>{desc}</span>
            </li>
          ))}
        </ul>
        <p className={styles.hint}>press Esc, or click outside, to close.</p>
      </div>
    </div>
  );
}
