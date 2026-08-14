import styles from "./KeywordGaps.module.css";
import type { KeywordHit } from "../lib/types";

/**
 * Terms the job description asks for that the resume never says. Required and
 * preferred are separated into two labelled groups — the grouping and the
 * label are what distinguish them; the mark ink on the required tags is only
 * a reminder of a distinction the heading has already made.
 */
export function KeywordGaps({ hits }: { hits: KeywordHit[] }) {
  const gaps = hits.filter((h) => !h.hit);
  const required = gaps.filter((h) => h.required);
  const preferred = gaps.filter((h) => !h.required);

  if (gaps.length === 0) {
    return (
      <p className={styles.empty}>
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
        no gaps — every term the posting asks for appears in the resume.
      </p>
    );
  }

  return (
    <div className={styles.wrap}>
      {required.length > 0 ? (
        <div className={styles.group}>
          <p className={styles.groupLabel}>
            required, missing <span className={styles.count}>{required.length}</span>
          </p>
          <ul className={styles.list}>
            {required.map((hit) => (
              <li key={`${hit.group}:${hit.label}`} className={styles.required}>
                {hit.label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {preferred.length > 0 ? (
        <div className={styles.group}>
          <p className={styles.groupLabel}>
            preferred, missing <span className={styles.count}>{preferred.length}</span>
          </p>
          <ul className={styles.list}>
            {preferred.map((hit) => (
              <li key={`${hit.group}:${hit.label}`} className={styles.preferred}>
                {hit.label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
