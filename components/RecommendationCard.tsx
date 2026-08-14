"use client";

import { useId, useState, type ReactNode } from "react";
import styles from "./RecommendationCard.module.css";
import { Button } from "./Button";

/**
 * One editorial recommendation: the single highest-value change to make next.
 * `body` is a node so callers can inline <code> spans, bullet counts, etc.
 * `confidence` is a 0-3 signal strength; 0 means "we have no signal", which is
 * a different statement from "low", and the meter renders it as an empty rack.
 */
export interface Recommendation {
  id: string;
  headline: string;
  body: ReactNode;
  confidence: 0 | 1 | 2 | 3;
  confidenceLabel: string;
  cta: string;
}

export interface RecommendationCardProps {
  /** `[0]` is the active recommendation. The rest are the alternatives. */
  recommendations: Recommendation[];
  onAccept(id: string): void;
  onSelect(id: string): void;
}

/** CSS-Module lookups are `string | undefined` under `noUncheckedIndexedAccess`,
 *  so join them through here rather than interpolating a possible `undefined`
 *  into a template literal and shipping a literal "undefined" class name. */
function cx(...parts: Array<string | false | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** 3 = confident, 2 = worth a look, 0-1 = weak or no signal. Colour is only
 *  ever the second signal here — the bar count and the written label carry it. */
function tierClass(confidence: 0 | 1 | 2 | 3): string {
  if (confidence >= 3) return styles.tierHigh ?? "";
  if (confidence === 2) return styles.tierMid ?? "";
  return styles.tierLow ?? "";
}

/** Three bars drawn as divs. Never colour-only: the filled count is visible,
 *  the label is written out beside it, and the whole thing has a spoken
 *  equivalent. Prints correctly in greyscale. */
function ConfidenceMeter({
  confidence,
  label,
  compact = false,
}: {
  confidence: 0 | 1 | 2 | 3;
  label: string;
  compact?: boolean;
}) {
  return (
    <span
      className={cx(
        styles.meter,
        compact && styles.meterCompact,
        tierClass(confidence),
      )}
    >
      <span className={styles.bars} aria-hidden="true">
        <span className={confidence >= 1 ? styles.barOn : styles.barOff} />
        <span className={confidence >= 2 ? styles.barOn : styles.barOff} />
        <span className={confidence >= 3 ? styles.barOn : styles.barOff} />
      </span>
      <span className={styles.meterLabel}>{label}</span>
      <span className="sr-only">{` (${confidence} of 3)`}</span>
    </span>
  );
}

function Chevron() {
  return (
    <svg
      className={styles.chevron}
      viewBox="0 0 16 16"
      width="12"
      height="12"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M4 6.5 8 10.5 12 6.5" strokeWidth="1.5" strokeLinecap="square" />
    </svg>
  );
}

/**
 * Surfaces one next action instead of a list of complaints: headline, detail,
 * a confidence meter, and a drawer of the alternatives that lost.
 *
 * The active recommendation is `recommendations[0]`, but a click on an
 * alternative promotes it locally *and* calls `onSelect`, so the card responds
 * immediately whether or not the parent reorders the array. If the parent later
 * hands over a list that no longer contains the local pick, the card falls back
 * to `[0]` on its own — no effect, no stale state.
 */
export default function RecommendationCard({
  recommendations,
  onAccept,
  onSelect,
}: RecommendationCardProps) {
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const drawerId = useId();

  const active =
    (pickedId ? recommendations.find((r) => r.id === pickedId) : undefined) ??
    recommendations[0];

  // Nothing to recommend is a real state, not an error: the rubric passed, or
  // we have not graded yet. Say so quietly rather than rendering an empty card.
  if (!active) {
    return (
      <section className={cx(styles.card, styles.cardEmpty)}>
        <p className={styles.eyebrow}>next change</p>
        <p className={styles.emptyBody}>
          No recommendation yet — grade a resume against a job description and
          the highest-value edit shows up here.
        </p>
      </section>
    );
  }

  const alternatives = recommendations.filter((r) => r.id !== active.id);
  const position = recommendations.indexOf(active) + 1;

  function promote(id: string) {
    setPickedId(id);
    setOpen(false);
    onSelect(id);
  }

  return (
    <section className={styles.card} aria-labelledby={`${drawerId}-headline`}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>next change</p>
        <p className={styles.position}>
          {position}
          <span className={styles.positionSep}>/</span>
          {recommendations.length}
        </p>
      </header>

      {/* Keyed on the active id so the swap replays the enter animation — the
          promotion reads as a new sheet being laid down, not a text edit. */}
      <div className={styles.lede} key={active.id}>
        <h3 className={styles.headline} id={`${drawerId}-headline`}>
          {active.headline}
        </h3>
        <div className={styles.body}>{active.body}</div>
      </div>

      {/* Drawer: 0fr -> 1fr so the card grows to whatever the rows need
          without a hard-coded height. `inert` keeps the collapsed rows out of
          the tab order while they stay mounted for the animation. */}
      <div
        className={cx(styles.drawer, open && styles.drawerOpen)}
        id={drawerId}
        inert={!open}
      >
        <div className={styles.drawerClip}>
          <div className={styles.drawerInner}>
            <p className={styles.drawerCaption}>
              {alternatives.length > 0
                ? "other candidates, weakest last"
                : "no alternatives"}
            </p>
            <ul className={styles.altList}>
              {alternatives.map((alt, i) => (
                <li key={alt.id}>
                  <button
                    type="button"
                    className={styles.altRow}
                    onClick={() => promote(alt.id)}
                  >
                    <span className={styles.altIndex} aria-hidden="true">
                      {String(i + 2).padStart(2, "0")}
                    </span>
                    <span className={styles.altText}>
                      <span className={styles.altHeadline}>{alt.headline}</span>
                      <ConfidenceMeter
                        confidence={alt.confidence}
                        label={alt.confidenceLabel}
                        compact
                      />
                    </span>
                    <span className={styles.altPromote} aria-hidden="true">
                      promote
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <footer className={styles.foot}>
        <ConfidenceMeter
          confidence={active.confidence}
          label={active.confidenceLabel}
        />
        {/* The shared <Button>, not a local copy. This card used to declare its
            own .ghost and .primary: the same two variants, the same tokens and
            the same hover logic, at different padding and with no min-height —
            so a card button sat ~3px shorter than a rail button, and there were
            two definitions of "primary" free to drift apart. */}
        <div className={styles.actions}>
          <Button
            variant="ghost"
            className={styles.altToggle}
            aria-expanded={open}
            aria-controls={drawerId}
            disabled={alternatives.length === 0}
            onClick={() => setOpen((v) => !v)}
          >
            alternatives
            <span className={styles.count}>{alternatives.length}</span>
            <Chevron />
          </Button>
          <Button
            variant="primary"
            className={styles.accept}
            onClick={() => onAccept(active.id)}
          >
            {active.cta}
          </Button>
        </div>
      </footer>
    </section>
  );
}

export { RecommendationCard };
