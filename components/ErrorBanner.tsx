import styles from "./ErrorBanner.module.css";

/** The run struck out: what failed, and what the server says to do about it. */
export function ErrorBanner({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className={styles.banner} role="alert" aria-live="assertive">
      <p className={styles.line}>
        <span className={styles.tag}>error</span>
        <span className={styles.text}>{message}</span>
      </p>
      {hint ? (
        <p className={styles.line}>
          <span className={`${styles.tag} ${styles.tagHint}`}>hint</span>
          <span className={styles.text}>{hint}</span>
        </p>
      ) : null}
    </div>
  );
}
