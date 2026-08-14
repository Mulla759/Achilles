"use client";

import { Fragment, useId, useState } from "react";
import styles from "./GateTable.module.css";
import { gateLabel } from "../lib/format";
import type { GateResult } from "../lib/types";

function PassMark() {
  return (
    <svg
      viewBox="0 0 12 12"
      width="12"
      height="12"
      aria-hidden="true"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 6.4 L4.7 9 L10 3" />
    </svg>
  );
}

function FailMark() {
  return (
    <svg
      viewBox="0 0 12 12"
      width="12"
      height="12"
      aria-hidden="true"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <path d="M6 1.8 V7" />
      <path d="M6 9.9 V10" />
    </svg>
  );
}

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

/**
 * The seven rubric gates as a real table: mark, gate, and the grader's own
 * one-line detail. A failing gate that named offenders can be opened to show
 * them; the mark is a glyph shape plus the word "pass"/"fail", so the colour
 * on it is only ever confirming what is already written.
 */
export function GateTable({ gates }: { gates: GateResult[] }) {
  const [openGate, setOpenGate] = useState<string | null>(null);
  const baseId = useId();

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className="sr-only">
          The seven rubric gates, with the grader&apos;s detail for each.
        </caption>
        <thead>
          <tr>
            <th scope="col" className={styles.markHead}>
              mark
            </th>
            <th scope="col">gate</th>
            <th scope="col">detail</th>
            {/*
              The cell stays in flow and only its TEXT is visually hidden.
              `.sr-only` is position:absolute, and on a <th> that takes the cell
              out of the table box entirely: the header row then laid out three
              cells against four body columns, so the --paper-2 header band and
              its rule stopped short and left a visible notch above every
              expand button.
            */}
            <th scope="col" className={styles.expandHead}>
              <span className="sr-only">offenders</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {gates.map((gate) => {
            const expandable = !gate.passed && gate.offenders.length > 0;
            const isOpen = openGate === gate.name;
            const rowId = `${baseId}-${gate.name}`;
            const label = gateLabel(gate.name);
            return (
              <Fragment key={gate.name}>
                <tr className={gate.passed ? undefined : styles.rowFailed}>
                  <td className={styles.markCell}>
                    <span className={gate.passed ? styles.pass : styles.fail}>
                      {gate.passed ? <PassMark /> : <FailMark />}
                      {gate.passed ? "pass" : "fail"}
                    </span>
                  </td>
                  <th scope="row" className={styles.labelCell}>
                    {label}
                  </th>
                  <td className={styles.detailCell}>{gate.detail}</td>
                  <td className={styles.expandCell}>
                    {expandable ? (
                      <button
                        type="button"
                        className={styles.expandBtn}
                        aria-expanded={isOpen}
                        aria-controls={rowId}
                        onClick={() => setOpenGate(isOpen ? null : gate.name)}
                      >
                        <span className={styles.expandCount}>{gate.offenders.length}</span>
                        <span className="sr-only"> offending bullets in {label}</span>
                        <Chevron />
                      </button>
                    ) : null}
                  </td>
                </tr>
                {/*
                  Rendered whenever the gate HAS offenders and hidden with the
                  `hidden` attribute, rather than mounted only while open. The
                  button's aria-controls has to resolve to a real element: with
                  a conditional row, a screen-reader user on the collapsed
                  trigger who asks to jump to the controlled region was pointed
                  at an IDREF that matched nothing.
                */}
                {expandable ? (
                  <tr className={styles.offendersRow} id={rowId} hidden={!isOpen}>
                    <td colSpan={4}>
                      <ul className={styles.offenders}>
                        {gate.offenders.map((offender, i) => (
                          <li key={i} className={styles.offender}>
                            {offender}
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
