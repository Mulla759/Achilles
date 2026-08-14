"use client";

import { useId, useMemo, type ReactNode } from "react";
import styles from "./DiffPanel.module.css";
import type { Entry, Resume } from "../lib/types";

/* ==========================================================================
   Types
   ========================================================================== */

/** The four resume sections that carry bullets. `lib/types.ts` `SectionName`
 *  deliberately excludes `education`, but education entries do have bullets
 *  and the tailorer may touch them, so the diff covers all four. */
export type DiffSection = "experience" | "projects" | "leadership" | "education";

export interface BulletEdit {
  section: DiffSection;
  entryIndex: number;
  entryLabel: string; // e.g. "Software Engineer Intern - Westinghouse"
  bulletIndex: number;
  before: string | null; // null = a purely added bullet
  after: string | null; // null = a removed bullet
  status: "accepted" | "rejected";
}

/** One run of text inside a diff line. `changed: true` is the part that
 *  actually differs between before/after — everything else is shared context. */
export interface DiffSegment {
  text: string;
  changed: boolean;
}

/* ==========================================================================
   Pure diff helpers — no React, no side effects
   ========================================================================== */

const DIFF_SECTIONS: readonly DiffSection[] = [
  "experience",
  "projects",
  "leadership",
  "education",
];

function entriesOf(resume: Resume, section: DiffSection): Entry[] {
  const list = resume[section];
  return Array.isArray(list) ? list : [];
}

/** "Software Engineer Intern - Westinghouse", degrading gracefully when one
 *  half is blank and falling back to a 1-based ordinal when both are. */
function labelFor(entry: Entry | null, entryIndex: number): string {
  const role = entry ? entry.role.trim() : "";
  const org = entry ? entry.org.trim() : "";
  if (role && org) return `${role} - ${org}`;
  return role || org || `Entry ${entryIndex + 1}`;
}

/**
 * Pair bullets by (section, entryIndex, bulletIndex) and emit one edit per
 * bullet that actually moved. Byte-identical bullets are skipped entirely.
 * Where the counts differ the extras are additions (`before: null`) or
 * removals (`after: null`); a whole entry present on only one side yields a
 * full run of additions or removals.
 *
 * Pure: same inputs, same output, no React, no mutation of the arguments.
 */
export function diffResumes(source: Resume, tailored: Resume): BulletEdit[] {
  const edits: BulletEdit[] = [];

  for (const section of DIFF_SECTIONS) {
    const before = entriesOf(source, section);
    const after = entriesOf(tailored, section);
    const entryCount = Math.max(before.length, after.length);

    for (let entryIndex = 0; entryIndex < entryCount; entryIndex++) {
      const beforeEntry = before[entryIndex] ?? null;
      const afterEntry = after[entryIndex] ?? null;
      // Prefer the tailored heading — that is what the user will read on the
      // finished page — and fall back to the source when the entry was cut.
      const entryLabel = labelFor(afterEntry ?? beforeEntry, entryIndex);

      const beforeBullets = beforeEntry ? beforeEntry.bullets : [];
      const afterBullets = afterEntry ? afterEntry.bullets : [];
      const bulletCount = Math.max(beforeBullets.length, afterBullets.length);

      for (let bulletIndex = 0; bulletIndex < bulletCount; bulletIndex++) {
        const beforeText = beforeBullets[bulletIndex] ?? null;
        const afterText = afterBullets[bulletIndex] ?? null;

        // Untouched, or nothing on either side: not an edit.
        if (beforeText === afterText) continue;
        if (beforeText === null && afterText === null) continue;

        edits.push({
          section,
          entryIndex,
          entryLabel,
          bulletIndex,
          before: beforeText,
          after: afterText,
          // The AI's proposal starts adopted; review is opt-out, not opt-in.
          status: "accepted",
        });
      }
    }
  }

  return edits;
}

/** Split on whitespace but keep the whitespace as its own token, so joining
 *  a slice back together reproduces the original string byte for byte. */
function tokenize(text: string): string[] {
  return text.split(/(\s+)/).filter((token) => token.length > 0);
}

function toSegments(
  tokens: string[],
  prefix: number,
  suffix: number,
): DiffSegment[] {
  let head = tokens.slice(0, prefix).join("");
  let middle = tokens.slice(prefix, tokens.length - suffix).join("");
  let tail = tokens.slice(tokens.length - suffix).join("");

  // Push boundary whitespace out of the highlight — a tint that extends over a
  // trailing space reads as a rendering bug, not as an edit. Concatenation is
  // unchanged, so the segments still rebuild the original string exactly.
  const leading = /^\s+/.exec(middle);
  if (leading) {
    head += leading[0];
    middle = middle.slice(leading[0].length);
  }
  const trailing = /\s+$/.exec(middle);
  if (trailing) {
    tail = trailing[0] + tail;
    middle = middle.slice(0, middle.length - trailing[0].length);
  }

  const out: DiffSegment[] = [];
  if (head) out.push({ text: head, changed: false });
  if (middle) out.push({ text: middle, changed: true });
  if (tail) out.push({ text: tail, changed: false });
  return out;
}

/**
 * Word-level highlight: strip the longest common prefix and suffix (compared
 * whole-word, not per-character, so a shared word never splits mid-token) and
 * mark only the middle as changed.
 *
 * Deliberately simple — no LCS matrix. If nothing at all is shared at either
 * end the two strings are unrelated rewrites, and emphasising 100% of both
 * lines emphasises nothing, so both come back as a single unchanged segment.
 *
 * Pure: no React, no mutation.
 */
export function wordDiff(
  before: string,
  after: string,
): { before: DiffSegment[]; after: DiffSegment[] } {
  const a = tokenize(before);
  const b = tokenize(after);

  let prefix = 0;
  while (prefix < a.length && prefix < b.length && a[prefix] === b[prefix]) {
    prefix++;
  }

  let suffix = 0;
  while (
    suffix < a.length - prefix &&
    suffix < b.length - prefix &&
    a[a.length - 1 - suffix] === b[b.length - 1 - suffix]
  ) {
    suffix++;
  }

  if (prefix === 0 && suffix === 0) {
    return {
      before: before ? [{ text: before, changed: false }] : [],
      after: after ? [{ text: after, changed: false }] : [],
    };
  }

  return {
    before: toSegments(a, prefix, suffix),
    after: toSegments(b, prefix, suffix),
  };
}

/* ==========================================================================
   View
   ========================================================================== */

interface Group {
  key: string;
  section: DiffSection;
  entryLabel: string;
  rows: { edit: BulletEdit; index: number }[];
}

/** Group edits by entry while keeping each edit's index in the original array,
 *  so a toggle can rebuild the list without re-deriving identity. */
function groupEdits(edits: BulletEdit[]): Group[] {
  const groups: Group[] = [];
  const byKey = new Map<string, Group>();

  edits.forEach((edit, index) => {
    const key = `${edit.section}:${edit.entryIndex}`;
    let group = byKey.get(key);
    if (!group) {
      group = {
        key,
        section: edit.section,
        entryLabel: edit.entryLabel,
        rows: [],
      };
      byKey.set(key, group);
      groups.push(group);
    }
    group.rows.push({ edit, index });
  });

  return groups;
}

function Segments({ segments }: { segments: DiffSegment[] }) {
  return (
    <>
      {segments.map((segment, i) =>
        segment.changed ? (
          <strong key={i} className={styles.emph}>
            {segment.text}
          </strong>
        ) : (
          <span key={i}>{segment.text}</span>
        ),
      )}
    </>
  );
}

/** One diff line: a glyph gutter that carries the meaning without colour,
 *  plus the text. `kind` picks the wash; the glyph and strike do the rest. */
function DiffLine({
  kind,
  glyph,
  spoken,
  children,
}: {
  kind: "del" | "ins" | "plain";
  glyph: string;
  spoken: string;
  children: ReactNode;
}) {
  const tone =
    kind === "del" ? styles.del : kind === "ins" ? styles.ins : styles.plain;
  return (
    <p className={`${styles.line} ${tone}`}>
      <span aria-hidden="true" className={styles.glyph}>
        {glyph}
      </span>
      <span className="sr-only">{spoken}</span>
      <span className={styles.lineText}>{children}</span>
    </p>
  );
}

export default function DiffPanel({
  edits,
  onChange,
}: {
  edits: BulletEdit[];
  onChange(next: BulletEdit[]): void;
}) {
  const baseId = useId();
  const groups = useMemo(() => groupEdits(edits), [edits]);

  const total = edits.length;
  const reverted = edits.reduce(
    (n, edit) => (edit.status === "rejected" ? n + 1 : n),
    0,
  );
  const kept = total - reverted;

  const setStatus = (index: number, status: BulletEdit["status"]) => {
    const target = edits[index];
    if (!target || target.status === status) return;
    onChange(edits.map((edit, i) => (i === index ? { ...edit, status } : edit)));
  };

  const setAll = (status: BulletEdit["status"]) => {
    if (edits.every((edit) => edit.status === status)) return;
    onChange(edits.map((edit) => ({ ...edit, status })));
  };

  return (
    <section className={styles.panel} aria-labelledby={`${baseId}-title`}>
      <header className={styles.header}>
        <div className={styles.titleGroup}>
          <h2 id={`${baseId}-title`} className={styles.title}>
            Proposed edits
          </h2>
          <p className={styles.count}>
            {total} {total === 1 ? "change" : "changes"}
            {total > 0 ? (
              <>
                <span className={styles.dot} aria-hidden="true">
                  ·
                </span>
                {kept} kept
                <span className={styles.dot} aria-hidden="true">
                  ·
                </span>
                {reverted} reverted
              </>
            ) : null}
          </p>
        </div>

        {total > 0 ? (
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.btn}
              onClick={() => setAll("accepted")}
              disabled={kept === total}
            >
              accept all
            </button>
            <button
              type="button"
              className={styles.btn}
              onClick={() => setAll("rejected")}
              disabled={reverted === total}
            >
              revert all
            </button>
          </div>
        ) : null}
      </header>

      {total === 0 ? (
        <p className={styles.empty}>
          No bullets changed. The tailored resume is byte-identical to the one
          you supplied.
        </p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption className={styles.caption}>
              Every bullet the tailorer rewrote. The struck line is your
              original, the inserted line is the replacement; revert a row and
              only the original is kept.
            </caption>
            <thead>
              <tr>
                <th scope="col" className={styles.numHead}>
                  #
                </th>
                <th scope="col">change</th>
                <th scope="col" className={styles.decisionHead}>
                  decision
                </th>
              </tr>
            </thead>

            {groups.map((group, groupIndex) => (
              <tbody
                key={group.key}
                className={styles.group}
                style={{ animationDelay: `${Math.min(groupIndex, 6) * 30}ms` }}
              >
                <tr>
                  {/* rowgroup, not colgroup: this <th> spans the width of its
                      own <tbody> and labels the ROWS beneath it. As colgroup it
                      published the entry name on the wrong axis, where it can
                      be announced against unrelated cells. */}
                  <th scope="rowgroup" colSpan={3} className={styles.groupHead}>
                    <span className={styles.groupLabel}>{group.entryLabel}</span>
                    <span className={styles.groupMeta}>
                      {group.section} · {group.rows.length}{" "}
                      {group.rows.length === 1 ? "edit" : "edits"}
                    </span>
                  </th>
                </tr>

                {group.rows.map(({ edit, index }) => {
                  const rejected = edit.status === "rejected";
                  const pair =
                    edit.before !== null && edit.after !== null
                      ? wordDiff(edit.before, edit.after)
                      : null;

                  return (
                    <tr key={`${edit.section}:${edit.entryIndex}:${edit.bulletIndex}`}>
                      <th scope="row" className={styles.numCell}>
                        {edit.bulletIndex + 1}
                      </th>

                      <td className={styles.changeCell}>
                        {rejected ? (
                          edit.before !== null ? (
                            // Reverted: the original stands, untinted.
                            <DiffLine
                              kind="plain"
                              glyph="="
                              spoken="unchanged, original kept:"
                            >
                              {edit.before}
                            </DiffLine>
                          ) : (
                            // A reverted addition leaves nothing behind.
                            <DiffLine
                              kind="plain"
                              glyph="="
                              spoken="unchanged:"
                            >
                              <span className={styles.void}>
                                no bullet — proposed addition reverted
                              </span>
                            </DiffLine>
                          )
                        ) : (
                          <>
                            {edit.before !== null ? (
                              <DiffLine
                                kind="del"
                                glyph="−"
                                spoken="deleted:"
                              >
                                {pair ? (
                                  <Segments segments={pair.before} />
                                ) : (
                                  edit.before
                                )}
                              </DiffLine>
                            ) : null}
                            {edit.after !== null ? (
                              <DiffLine
                                kind="ins"
                                glyph="+"
                                spoken="inserted:"
                              >
                                {pair ? (
                                  <Segments segments={pair.after} />
                                ) : (
                                  edit.after
                                )}
                              </DiffLine>
                            ) : null}
                          </>
                        )}
                      </td>

                      <td className={styles.decisionCell}>
                        <div
                          className={styles.toggle}
                          role="group"
                          aria-label={`Bullet ${edit.bulletIndex + 1} of ${
                            edit.entryLabel
                          }`}
                        >
                          <button
                            type="button"
                            className={styles.segBtn}
                            aria-pressed={!rejected}
                            onClick={() => setStatus(index, "accepted")}
                          >
                            keep
                          </button>
                          <button
                            type="button"
                            className={styles.segBtn}
                            aria-pressed={rejected}
                            onClick={() => setStatus(index, "rejected")}
                          >
                            revert
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            ))}
          </table>
        </div>
      )}
    </section>
  );
}
