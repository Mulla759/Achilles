import styles from "./TopBar.module.css";
import type { HealthResponse } from "../lib/types";

/** Masthead: the paper's name on the left, the press it came off on the right. */
export function TopBar({ health }: { health: HealthResponse | null }) {
  return (
    <header className={styles.bar}>
      <span className={styles.brand}>
        <span className={styles.name}>achilles</span>
        <span className={styles.version}>v0.1.0</span>
      </span>
      <span className={styles.right} aria-live="polite">
        {health ? (
          <>
            <span className={styles.model}>model {health.model || "unknown"}</span>
            <span className={health.ok ? styles.online : styles.offline}>
              <span className={styles.dot} aria-hidden="true" />
              {health.ok ? "online" : "offline"}
            </span>
          </>
        ) : (
          <span className={styles.model}>connecting…</span>
        )}
      </span>
    </header>
  );
}
