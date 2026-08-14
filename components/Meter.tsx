import styles from "./Meter.module.css";

interface MeterProps {
  label: string;
  /** 0-100. */
  value: number;
  /** Where the bar has to reach to count as passing; drawn as a hairline tick. */
  target?: number;
  /** Mono small print under the rule — the count behind the percentage. */
  note?: string;
}

/**
 * A figure with a rule under it. The number is the content; the rule is just
 * the number drawn again so the eye can compare two of them at a glance —
 * which is why the fill is ink rather than a colour that would rank them.
 */
export function Meter({ label, value, target, note }: MeterProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const clampedTarget =
    typeof target === "number" ? Math.max(0, Math.min(100, Math.round(target))) : null;

  return (
    <div className={styles.meter}>
      <div className={styles.head}>
        <span className={styles.label}>{label}</span>
        <span className={`${styles.value} tabular`}>
          {clamped}
          <span className={styles.unit}>%</span>
        </span>
      </div>

      {/* Decorative: the figure above and the note below already say it all. */}
      <div className={styles.track} aria-hidden="true">
        <span className={styles.fill} style={{ width: `${clamped}%` }} />
        {clampedTarget !== null ? (
          <span className={styles.tick} style={{ left: `${clampedTarget}%` }} />
        ) : null}
      </div>

      <p className={`${styles.note} tabular`}>
        {note ? <span>{note}</span> : <span />}
        {clampedTarget !== null ? <span>target {clampedTarget}</span> : null}
      </p>
    </div>
  );
}
