import styles from "./ReadyChip.module.css";

interface ReadyChipProps {
  ready: boolean;
  /** The sentence after the verdict — what is left to do, or why it passed. */
  detail?: string;
}

function PassMark() {
  return (
    <svg
      className={styles.mark}
      viewBox="0 0 14 14"
      width="14"
      height="14"
      aria-hidden="true"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2.5 7.6 L5.6 10.5 L11.5 3.5" />
    </svg>
  );
}

function QueryMark() {
  return (
    <svg
      className={styles.mark}
      viewBox="0 0 14 14"
      width="14"
      height="14"
      aria-hidden="true"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <path d="M7 2.5 V8.2" />
      <path d="M7 11.2 V11.3" />
    </svg>
  );
}

/**
 * The verdict, written out. Colour is the third signal here, behind the glyph
 * shape and the words themselves — print this in greyscale and nothing is lost.
 *
 * No role="status", and that is not an omission. ResultsPanel is remounted on
 * every run (`key={runSeq}`), so this element entered the DOM with its text
 * already inside it — and a live region only announces MUTATIONS to a region
 * that was already present. The role therefore never spoke the verdict once,
 * while claiming to. The verdict is announced by the page's own region, which
 * is mounted from first paint and carries "ready to send" / "not ready yet" in
 * its message.
 */
export function ReadyChip({ ready, detail }: ReadyChipProps) {
  return (
    <p className={`${styles.statement} ${ready ? styles.ready : styles.notReady}`}>
      {ready ? <PassMark /> : <QueryMark />}
      <span className={styles.text}>
        <strong className={styles.verdict}>{ready ? "ready to send" : "not ready yet"}</strong>
        {detail ? <span className={styles.detail}> — {detail}</span> : null}
      </span>
    </p>
  );
}
