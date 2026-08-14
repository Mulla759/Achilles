import styles from "./StatusBar.module.css";

interface StatusBarProps {
  mode: string;
  ready: boolean | null;
}

/** The colophon: what mode the page is in, the shortcuts, and the verdict. */
export function StatusBar({ mode, ready }: StatusBarProps) {
  const readyClass = ready === null ? styles.readyIdle : ready ? styles.readyYes : styles.readyNo;
  return (
    <footer className={styles.bar}>
      <span className={styles.mode}>{mode.toLowerCase()}</span>
      <span className={styles.hints}>
        <span className={styles.hint}>
          <kbd>ctrl ↵</kbd>run
        </span>
        <span className={styles.hint}>
          <kbd>ctrl s</kbd>score
        </span>
        <span className={styles.hint}>
          <kbd>ctrl k</kbd>key
        </span>
        <span className={styles.hint}>
          <kbd>?</kbd>help
        </span>
        <span className={styles.hint}>
          <kbd>esc</kbd>close
        </span>
      </span>
      <span className={`${styles.ready} ${readyClass}`}>
        ready {ready === null ? "not graded" : ready ? "yes" : "no"}
      </span>
    </footer>
  );
}
