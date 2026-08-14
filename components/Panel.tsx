import type { ReactNode } from "react";
import styles from "./Panel.module.css";

interface PanelProps {
  title: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  id?: string;
  /** Small print welded to the bottom edge of the card — counts, limits. */
  statusLine?: ReactNode;
  /** Sits on the header rule, right-aligned: a loader, a figure, a control. */
  aside?: ReactNode;
}

/**
 * A sheet of paper laid on the page: --surface ground, one hairline ring from
 * --shadow-card, and a title set as a mono eyebrow above a rule. This replaced
 * the box-drawing `┌─ TITLE ──┐` frame the terminal build used — the frame is
 * now drawn by the card's own edge, so the title can be real heading markup
 * instead of characters a screen reader has to skip.
 *
 * Focus is not styled here on purpose: the global 2px ink ring lands on the
 * control that actually has focus, which is more precise than lighting up the
 * whole card around it.
 */
export function Panel({
  title,
  children,
  className,
  bodyClassName,
  id,
  statusLine,
  aside,
}: PanelProps) {
  return (
    <section id={id} className={[styles.panel, className].filter(Boolean).join(" ")}>
      <header className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        {aside ? <div className={styles.aside}>{aside}</div> : null}
      </header>
      <div className={[styles.body, bodyClassName].filter(Boolean).join(" ")}>{children}</div>
      {statusLine ? <p className={styles.statusLine}>{statusLine}</p> : null}
    </section>
  );
}
