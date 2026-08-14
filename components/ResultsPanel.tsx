"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import styles from "./ResultsPanel.module.css";
import { Panel } from "./Panel";
import { Meter } from "./Meter";
import { ReadyChip } from "./ReadyChip";
import { GateTable } from "./GateTable";
import { KeywordGaps } from "./KeywordGaps";
import { Button } from "./Button";
import DiffPanel, { type BulletEdit } from "./DiffPanel";
import RecommendationCard, { type Recommendation } from "./RecommendationCard";
import { base64ToBlob, downloadBasename, downloadBlob, gateLabel } from "../lib/format";
import type { BuildResult, GateResult, Resume, ScanResponse } from "../lib/types";

type Result = ScanResponse | BuildResult;

interface ResultsPanelProps {
  result: Result;
  /**
   * What went in, for the per-bullet diff. Null on a score-only run and on any
   * tailor response older than `source_resume` — in which case the diff simply
   * does not appear (requirement 4).
   */
  sourceResume: Resume | null;
  /** Held by the page so accept/reject survives a re-render of this panel. */
  edits: BulletEdit[];
  onEditsChange: (next: BulletEdit[]) => void;
  /** The obvious next action when there is nothing left to recommend. */
  onTailor: () => void;
}

function isBuildResult(result: Result): result is BuildResult {
  return "pdf_b64" in result;
}

function deriveReady(result: Result): boolean {
  if (isBuildResult(result)) return result.ready;
  return (
    result.pages === 1 && result.scan.required_score === 100 && result.scan.score >= 95 && result.rubric.passed
  );
}

/* ==========================================================================
   Recommendations, derived from the response
   --------------------------------------------------------------------------
   One card per failing rubric gate, plus one for missing required keywords.
   Confidence is a statement about how much the grader actually knows:
     3  the gate failed AND named the offending lines — there is nothing to
        interpret, the fix is in front of you
     2  the gate failed but named nothing, so a human has to decide what moved
        it — "needs review"
     0  nothing is failing; there is no signal to act on
   ========================================================================== */

const GATE_ADVICE: Record<string, string> = {
  graduation: "Put your degree, school, and graduation date where a parser can find them.",
  semantics: "Open every bullet with a verb that does work.",
  metrics: "Give more of your bullets a real number.",
  storyline: "Rewrite these bullets as action, then what you built, then what changed.",
  one_page: "Cut the resume back to a single page.",
  mac: "Every bullet needs a metric, an action, and a context.",
  ats_parseable: "Keep the page single-column with standard section headers.",
};

const MAX_QUOTED_OFFENDERS = 3;

function gateRecommendation(gate: GateResult): Recommendation {
  const label = gateLabel(gate.name);
  const quoted = gate.offenders.slice(0, MAX_QUOTED_OFFENDERS);
  const remainder = gate.offenders.length - quoted.length;

  const body: ReactNode = (
    <>
      <p className={styles.recDetail}>
        <span className={styles.recGate}>{label}</span>
        {gate.detail}
      </p>
      {quoted.length > 0 ? (
        <ul className={styles.recQuotes}>
          {quoted.map((offender, i) => (
            <li key={i}>{offender}</li>
          ))}
          {remainder > 0 ? (
            <li className={styles.recMore}>
              + {remainder} more, listed under rubric gates below
            </li>
          ) : null}
        </ul>
      ) : (
        <p className={styles.recDetail}>
          The grader flagged the gate without naming lines, so read the section yourself before
          changing anything.
        </p>
      )}
    </>
  );

  const hasOffenders = gate.offenders.length > 0;
  return {
    id: `gate:${gate.name}`,
    headline: GATE_ADVICE[gate.name] ?? `Take another look at ${label}.`,
    body,
    confidence: hasOffenders ? 3 : 2,
    confidenceLabel: hasOffenders ? "high confidence" : "needs review",
    cta: "mark as handled",
  };
}

function keywordRecommendation(missing: string[]): Recommendation {
  const body: ReactNode = (
    <>
      <p className={styles.recDetail}>
        <span className={styles.recGate}>required quals</span>
        {missing.length} required {missing.length === 1 ? "term" : "terms"} from the posting never
        appear in the resume. Work them into a bullet you have already earned — never invent one.
      </p>
      <ul className={styles.recTerms}>
        {missing.map((term) => (
          <li key={term}>{term}</li>
        ))}
      </ul>
    </>
  );

  return {
    id: "keywords:required",
    headline: "Say the required terms the posting asks for.",
    body,
    confidence: 3,
    confidenceLabel: "high confidence",
    cta: "mark as handled",
  };
}

function deriveRecommendations(
  result: Result,
  acknowledged: ReadonlySet<string>,
  hasPdf: boolean,
): Recommendation[] {
  const failing = result.rubric.gates.filter((gate) => !gate.passed);
  // Deduped: the same label can appear in more than one keyword group, and a
  // term listed twice reads as a bug rather than as emphasis.
  const missingRequired = [
    ...new Set(result.scan.hits.filter((hit) => hit.required && !hit.hit).map((h) => h.label)),
  ];

  const all: Recommendation[] = [
    ...failing.map(gateRecommendation),
    ...(missingRequired.length > 0 ? [keywordRecommendation(missingRequired)] : []),
  ];

  // Strongest opinion first, so the card that opens is the one worth reading.
  all.sort((a, b) => b.confidence - a.confidence);

  const open = all.filter((rec) => !acknowledged.has(rec.id));
  if (open.length > 0) return open;

  // Two different kinds of nothing-left, and they deserve different sentences.
  if (all.length === 0) {
    return [
      {
        id: "all-clear",
        headline: "Nothing is failing — this one is ready to send.",
        body: (
          <p className={styles.recDetail}>
            Every rubric gate passes and every required qualification appears in the text a parser
            reads. There is no edit left that the grader can argue for.
          </p>
        ),
        confidence: 0,
        confidenceLabel: "no signal",
        cta: hasPdf ? "download the pdf" : "run the full tailor pass",
      },
    ];
  }

  return [
    {
      id: "all-handled",
      headline: "You have worked through every note.",
      body: (
        <p className={styles.recDetail}>
          {all.length} {all.length === 1 ? "recommendation was" : "recommendations were"} marked as
          handled, but the grade above still reflects the last run. Re-run the pass to see where
          your edits landed.
        </p>
      ),
      confidence: 0,
      confidenceLabel: "no signal",
      cta: "run the pass again",
    },
  ];
}

/* ========================================================================== */

export function ResultsPanel({ result, sourceResume, edits, onEditsChange, onTailor }: ResultsPanelProps) {
  const ready = deriveReady(result);
  const build = isBuildResult(result) ? result : null;
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [acknowledged, setAcknowledged] = useState<ReadonlySet<string>>(() => new Set<string>());
  const [pickedId, setPickedId] = useState<string | null>(null);

  useEffect(() => {
    if (!build?.pdf_b64) {
      setPdfUrl(null);
      return;
    }
    const blob = base64ToBlob(build.pdf_b64, "application/pdf");
    const url = URL.createObjectURL(blob);
    setPdfUrl(url);
    return () => URL.revokeObjectURL(url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [build?.pdf_b64]);

  const basename = useMemo(() => {
    if (!build) return "resume";
    return downloadBasename(build.resume.contact.name, build.resume.target_role);
  }, [build]);

  function handleDownloadPdf() {
    if (!build?.pdf_b64) return;
    const blob = base64ToBlob(build.pdf_b64, "application/pdf");
    downloadBlob(blob, `${basename}.pdf`);
  }

  function handleDownloadTyp() {
    if (!build?.typst_source) return;
    const blob = new Blob([build.typst_source], { type: "text/plain;charset=utf-8" });
    downloadBlob(blob, `${basename}.typ`);
  }

  // --- score header figures ------------------------------------------------
  const requiredHits = result.scan.hits.filter((hit) => hit.required);
  const requiredMet = requiredHits.filter((hit) => hit.hit).length;
  const failingGates = result.rubric.gates.filter((gate) => !gate.passed);
  const missingRequired = requiredHits.length - requiredMet;

  const reasons: string[] = [];
  if (result.pages !== 1) reasons.push(`it runs to ${result.pages} pages`);
  if (missingRequired > 0) {
    reasons.push(
      `${missingRequired} required ${missingRequired === 1 ? "term is" : "terms are"} missing`,
    );
  }
  if (failingGates.length > 0) {
    reasons.push(`${failingGates.length} ${failingGates.length === 1 ? "gate" : "gates"} still fail`);
  }
  if (result.scan.score < 95 && reasons.length === 0) reasons.push("overall coverage is under 95");

  const readyDetail = ready
    ? "one page, every required qualification covered, and all seven gates pass."
    : reasons.length > 0
      ? `${reasons.join(", ")}.`
      : "the grade did not clear every threshold — read the gates below.";

  // --- recommendations ----------------------------------------------------
  const recommendations = useMemo(() => {
    const derived = deriveRecommendations(result, acknowledged, Boolean(build?.pdf_b64));
    if (!pickedId) return derived;
    const picked = derived.find((rec) => rec.id === pickedId);
    // Promote the reader's pick to [0] so the card and the page agree on which
    // recommendation is active. If it is gone, the list is already correct.
    return picked ? [picked, ...derived.filter((rec) => rec.id !== pickedId)] : derived;
  }, [result, acknowledged, build?.pdf_b64, pickedId]);

  function handleAccept(id: string) {
    if (id === "all-clear") {
      if (build?.pdf_b64) handleDownloadPdf();
      else onTailor();
      return;
    }
    if (id === "all-handled") {
      onTailor();
      return;
    }
    setAcknowledged((prev) => new Set(prev).add(id));
    setPickedId(null);
  }

  // No live region on this wrapper: it would announce the entire review — diff
  // table included — every time a decision changes. And not on ReadyChip
  // either: this whole panel is remounted per run (key={runSeq}), so a region
  // inside it enters the DOM with its text already in place, which is exactly
  // the case a live region does NOT announce. The page owns one short polite
  // region, mounted from first paint, and its message carries the verdict.
  return (
    <div className={styles.stack}>
      {/* (a) the score header */}
      <Panel
        title="score"
        aside={
          <span className={`${styles.headFigures} tabular`}>
            rubric {result.rubric.score}
            {build ? ` · ${build.passes} ${build.passes === 1 ? "pass" : "passes"}` : null}
          </span>
        }
      >
        <ReadyChip ready={ready} detail={readyDetail} />

        <div className={styles.meters}>
          <Meter
            label="coverage"
            value={result.scan.score}
            target={95}
            note={`${result.scan.matched} of ${result.scan.total} terms`}
          />
          <Meter
            label="required quals"
            value={result.scan.required_score}
            target={100}
            note={`${requiredMet} of ${requiredHits.length} required`}
          />
        </div>

        <dl className={`${styles.figures} tabular`}>
          <div>
            <dt>pages</dt>
            <dd>{result.pages}</dd>
          </div>
          <div>
            <dt>words</dt>
            <dd>{result.scan.word_count}</dd>
          </div>
          <div>
            <dt>gates passed</dt>
            <dd>
              {result.rubric.gates.length - failingGates.length}/{result.rubric.gates.length}
            </dd>
          </div>
        </dl>
      </Panel>

      {/* (b) the editor's next note */}
      <RecommendationCard
        recommendations={recommendations}
        onAccept={handleAccept}
        onSelect={setPickedId}
      />

      {/* (c) the marked-up proof — only when we know what went in */}
      {sourceResume ? <DiffPanel edits={edits} onChange={onEditsChange} /> : null}

      {/* (d) every gate, with its offenders */}
      <Panel title="rubric gates">
        <GateTable gates={result.rubric.gates} />
      </Panel>

      {/* (e) what the posting asks for and the resume never says */}
      <Panel title="keyword gaps">
        <KeywordGaps hits={result.scan.hits} />
      </Panel>

      {/* (f) the artifact */}
      {build ? (
        <Panel title="artifact">
          <div className={styles.buttonRow}>
            <Button variant="primary" onClick={handleDownloadPdf} disabled={!build.pdf_b64}>
              download pdf
            </Button>
            <Button variant="ghost" onClick={handleDownloadTyp} disabled={!build.typst_source}>
              download .typ
            </Button>
          </div>

          {pdfUrl ? (
            <div className={styles.preview}>
              <button
                type="button"
                className={styles.previewToggle}
                onClick={() => setPreviewOpen((v) => !v)}
                aria-expanded={previewOpen}
                /* Only while the target exists. The other disclosures in the
                   app keep their panel mounted and toggle visibility, so their
                   aria-controls always resolves; this one cannot — a mounted
                   <iframe> downloads and renders a PDF the reader is not
                   looking at. An IDREF pointing at nothing is worse than no
                   IDREF, and aria-expanded already carries the state. */
                aria-controls={previewOpen ? "pdf-preview" : undefined}
              >
                <svg
                  className={styles.previewChevron}
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
                {previewOpen ? "hide the page" : "look at the page"}
              </button>
              {previewOpen ? (
                <iframe
                  id="pdf-preview"
                  title="Tailored resume preview"
                  src={pdfUrl}
                  className={styles.previewFrame}
                />
              ) : null}
            </div>
          ) : null}
        </Panel>
      ) : null}

      {/* (g) the run's own notes — this is where the sanitizer reports any
          invisible characters it stripped, so it is never hidden or folded. */}
      {build && build.notes.length > 0 ? (
        <section className={styles.notes}>
          <h2 className={styles.notesTitle}>notes from the run</h2>
          <ul className={styles.notesList}>
            {build.notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
