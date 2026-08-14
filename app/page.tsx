"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./page.module.css";
import { InputRail, type FieldErrors } from "../components/InputRail";
import { ResultsPanel } from "../components/ResultsPanel";
import { ErrorBanner } from "../components/ErrorBanner";
import { Panel } from "../components/Panel";
import { TopBar } from "../components/TopBar";
import { StatusBar } from "../components/StatusBar";
import { HelpOverlay } from "../components/HelpOverlay";
import TaskRows, { type Task, type TaskDetail, type TaskState } from "../components/TaskRows";
import ThinkingTrace, { type TraceStep } from "../components/ThinkingTrace";
import LoadingState from "../components/LoadingState";
import { diffResumes, type BulletEdit } from "../components/DiffPanel";
import { getHealth, scanResume, tailorResume } from "../lib/api";
import { purgeStoredData } from "../lib/storage";
import {
  ApiError,
  type BuildResult,
  type HealthResponse,
  type Resume,
  type ScanResponse,
} from "../lib/types";

/**
 * `source_resume` is in the response (docs/API.md, the /api/tailor 200 block)
 * but not on `BuildResult` in lib/types.ts, which is contract-frozen and must
 * not be edited. Declaring it optional here is what lets the diff read it
 * without a cast, and it is honest about the older responses that never sent
 * it: null / undefined both mean "we do not know what went in".
 */
interface TailorResult extends BuildResult {
  source_resume?: Resume | null;
}

type Status = "idle" | "scanning" | "tailoring";
type Result = ScanResponse | TailorResult;

interface RunState {
  /** "running" while the request is in flight; "failed" once it threw. */
  phase: "running" | "failed";
  /** Which stage the schedule below believes we are in. */
  stageIndex: number;
  /** ms epoch, handed to LoadingState so the timer survives a re-render. */
  startedAt: number;
}

const DEFAULT_MAX_PASSES = 3;

/**
 * The five real stages of `achilles/pipeline.py`'s build loop, and what each
 * one is actually doing. The prose is written to be true of every run — none
 * of it reports a number the server has not sent us.
 */
const STAGES = [
  {
    id: "read",
    label: "reading the job description",
    trace: "Splitting the posting into requirements, responsibilities, and nice-to-haves.",
  },
  {
    id: "keywords",
    label: "extracting keywords",
    trace:
      "Matching the posting against the keyword ontology and marking which terms are hard requirements.",
  },
  {
    id: "bullets",
    label: "rewriting bullets",
    trace:
      "Rewording the experience you already have into the posting's vocabulary. Nothing gets invented.",
  },
  {
    id: "render",
    label: "rendering the pdf",
    trace:
      "Typesetting through the density ladder until it holds one page, then reading the text back out of the PDF.",
  },
  {
    id: "grading",
    label: "grading",
    trace: "Scoring keyword coverage, then running the seven rubric gates over the result.",
  },
] as const;

/**
 * Rough time-in-stage schedule for the five-stage tailor loop (30-90s typical,
 * per docs/API.md). We hold on the last stage for as long as the request
 * actually takes — clearStageTimers() cancels anything still pending once the
 * response lands. These are estimates, and the UI says so out loud.
 */
const STAGE_DELAYS_MS = [0, 4000, 10000, 30000, 55000];

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

/** A response can carry `source_resume: null`, or a shape we do not recognise.
 *  Either way the diff must simply not render rather than throw. */
function asResume(value: Resume | null | undefined): Resume | null {
  if (!value || typeof value !== "object") return null;
  return Array.isArray(value.experience) ? value : null;
}

/** The one verdict rule, per docs/API.md: a scan has to derive what a build
 *  reports directly. */
function isReady(result: Result): boolean {
  if ("ready" in result) return result.ready;
  return (
    result.pages === 1 &&
    result.scan.required_score === 100 &&
    result.scan.score >= 95 &&
    result.rubric.passed
  );
}

/**
 * The `run n` prefix is load-bearing, not decoration. React bails out of an
 * update when the next state is identical, so re-running and landing the same
 * score produced the same string, the text node never mutated, and
 * `role="status"` announced nothing at all — the one moment a screen-reader
 * user most needs confirmation. The run number makes every landed run a
 * distinct mutation, and it is genuinely useful information besides.
 */
function landedMessage(result: Result, run: number): string {
  return `run ${run} finished. ${
    isReady(result) ? "ready to send" : "not ready yet"
  } — coverage ${result.scan.score} percent, required qualifications ${
    result.scan.required_score
  } percent.`;
}

function stageState(index: number, run: RunState): TaskState {
  if (run.phase === "failed") {
    if (index < run.stageIndex) return "done";
    return index === run.stageIndex ? "failed" : "pending";
  }
  if (index < run.stageIndex) return "done";
  return index === run.stageIndex ? "running" : "pending";
}

export default function Page() {
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [availability, setAvailability] = useState("");
  const [companyUrl, setCompanyUrl] = useState("");
  const [maxPasses, setMaxPasses] = useState(DEFAULT_MAX_PASSES);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [keyRequired, setKeyRequired] = useState(false);

  const [status, setStatus] = useState<Status>("idle");
  const [run, setRun] = useState<RunState | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  /** The reviewer's accept/reject decisions, held here so they survive every
   *  re-render of the review column. Replaced only when a new run lands. */
  const [edits, setEdits] = useState<BulletEdit[]>([]);
  /** Bumped per landed run, and used as ResultsPanel's key so the previous
   *  run's "handled" recommendations do not leak into the new grade. */
  const [runSeq, setRunSeq] = useState(0);
  const [errorBanner, setErrorBanner] = useState<{ message: string; hint?: string } | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [helpOpen, setHelpOpen] = useState(false);
  /** One short polite announcement per landed run. The region below is in the
   *  DOM from mount, which is what makes it reliably spoken. */
  const [liveMessage, setLiveMessage] = useState("");

  const stageTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const apiKeyInputRef = useRef<HTMLInputElement>(null);
  /**
   * The double-submit guard, and it has to be a ref rather than `status`.
   * `status` is only observable through a closure captured at the last render,
   * so two Ctrl+Enter keydowns delivered before React re-renders — key
   * auto-repeat, or a stuck modifier — both saw `status === "idle"` and both
   * fired the request. That is two paid model passes, and the second response
   * silently overwrote the first result and its diff. This flips synchronously.
   */
  const inFlight = useRef(false);
  /** Landed-run counter. Incremented synchronously so the live message below
   *  can name the run it is reporting; also keys ResultsPanel. */
  const runCount = useRef(0);

  // One-time cleanup: anyone who used an earlier build (before this app went
  // no-persistence) may still have a resume or API key sitting in
  // localStorage/sessionStorage from that version. Delete it on their next
  // visit. The form itself now lives purely in React state and is never
  // written to client storage, so this call needs to run exactly once.
  useEffect(() => {
    purgeStoredData();
  }, []);

  // Probe /api/health once on mount.
  useEffect(() => {
    getHealth().then((h) => {
      setHealth(h);
      if (h.byo_key_only) {
        setKeyRequired(true);
        setAdvancedOpen(true);
      }
    });

    return () => {
      stageTimers.current.forEach(clearTimeout);
    };
  }, []);

  function validate(opts: { needKey: boolean }): boolean {
    const errors: FieldErrors = {};
    if (jdText.trim().length < 40) {
      errors.jd = `paste the full job description (at least 40 characters, currently ${jdText.trim().length}).`;
    }
    if (resumeText.trim().length === 0) {
      errors.resume = "paste your resume, or drop a .txt / .md file.";
    }
    if (targetRole.trim().length === 0) {
      errors.targetRole = "target role is required.";
    }
    if (opts.needKey && keyRequired && apiKey.trim().length === 0) {
      errors.apiKey = "an api key is required on this deployment.";
      // The field lives inside a disclosure; a message behind a closed panel
      // is the same as no message at all.
      setAdvancedOpen(true);
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function clearStageTimers() {
    stageTimers.current.forEach(clearTimeout);
    stageTimers.current = [];
  }

  function focusApiKeyField() {
    setAdvancedOpen(true);
    requestAnimationFrame(() => {
      const field = apiKeyInputRef.current;
      if (!field) return;
      /*
       * preventScroll, then scroll the CARD instead. The field sits inside a
       * disclosure that is mounted-but-collapsed and is still animating open in
       * this frame; its clip box is `overflow: hidden`, which browsers will
       * happily scroll to bring a focused child into view. That would offset
       * the panel's own contents inside the clip and leave them there once the
       * animation finished. Scrolling the section moves the page, which is what
       * the reader actually wants — and Ctrl+K never did it before.
       */
      field.focus({ preventScroll: true });
      field.closest("section")?.scrollIntoView({ block: "nearest" });
    });
  }

  function handleApiError(err: unknown) {
    if (err instanceof ApiError) {
      setErrorBanner({ message: err.message, hint: err.hint });
      if (err.status === 401) {
        setKeyRequired(true);
        focusApiKeyField();
      }
    } else {
      setErrorBanner({
        message: "something went wrong.",
        hint: "try again in a moment.",
      });
    }
  }

  async function handleScan() {
    if (inFlight.current) return;
    setErrorBanner(null);
    if (!validate({ needKey: false })) return;
    inFlight.current = true;
    setStatus("scanning");
    try {
      const res = await scanResume({
        resume_text: resumeText,
        jd_text: jdText,
        target_role: targetRole,
      });
      setResult(res);
      // A score-only run never rewrites anything, so there is no diff to hold.
      setEdits([]);
      setRun(null);
      const seq = ++runCount.current;
      setRunSeq(seq);
      setLiveMessage(landedMessage(res, seq));
    } catch (err) {
      handleApiError(err);
    } finally {
      inFlight.current = false;
      setStatus("idle");
    }
  }

  async function handleTailor() {
    if (inFlight.current) return;
    setErrorBanner(null);
    if (!validate({ needKey: true })) return;

    inFlight.current = true;
    setStatus("tailoring");
    clearStageTimers();
    setRun({ phase: "running", stageIndex: 0, startedAt: Date.now() });
    STAGE_DELAYS_MS.slice(1).forEach((delay, i) => {
      const timer = setTimeout(() => {
        setRun((prev) => (prev && prev.phase === "running" ? { ...prev, stageIndex: i + 1 } : prev));
      }, delay);
      stageTimers.current.push(timer);
    });

    try {
      const res: TailorResult = await tailorResume({
        resume_text: resumeText,
        jd_text: jdText,
        target_role: targetRole,
        availability: availability || undefined,
        company_url: companyUrl || undefined,
        api_key: apiKey || undefined,
        max_passes: maxPasses,
      });
      clearStageTimers();
      const source = asResume(res.source_resume);
      setResult(res);
      setEdits(source ? diffResumes(source, res.resume) : []);
      // The whole pass landed: every stage really is finished, so drop the
      // schedule rather than leaving five ticks on screen above the review.
      setRun(null);
      const seq = ++runCount.current;
      setRunSeq(seq);
      setLiveMessage(landedMessage(res, seq));
    } catch (err) {
      clearStageTimers();
      // Fail the stage the schedule was on. We know the pass stopped; we do
      // not know that the stages before it completed, only that we passed them.
      setRun((prev) => (prev ? { ...prev, phase: "failed" } : prev));
      handleApiError(err);
    } finally {
      inFlight.current = false;
      setStatus("idle");
    }
  }

  /*
   * Keyboard-first bindings. Ctrl/Cmd combos fire regardless of focus (even
   * while typing in a field); plain keys like `?` only fire when the user isn't
   * typing, so they never clobber a resume/JD paste.
   *
   * The handlers are held in a ref and the listener is bound exactly once. The
   * effect used to run with no dependency array, which removed and re-added a
   * window listener on every render — i.e. on every keystroke into two
   * controlled textareas that can each hold a whole resume. Not a leak, but
   * pure churn on the hottest path in the app, and it needed an
   * `eslint-disable` to say so. The ref keeps the closure fresh without the
   * churn, and the intent is now in the code rather than in a suppression.
   */
  const keyHandlers = useRef({ handleTailor, handleScan, focusApiKeyField, helpOpen });

  // No dependency array on purpose: this re-points a ref after every render,
  // which is one object assignment. Deliberately not written during render —
  // a render React discards must not be able to leave a value behind in a ref.
  useEffect(() => {
    keyHandlers.current = { handleTailor, handleScan, focusApiKeyField, helpOpen };
  });

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const current = keyHandlers.current;
      const mod = e.ctrlKey || e.metaKey;

      if (mod && e.key === "Enter") {
        e.preventDefault();
        current.handleTailor();
        return;
      }
      if (mod && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        current.handleScan();
        return;
      }
      if (mod && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        current.focusApiKeyField();
        return;
      }
      if (e.key === "Escape") {
        if (current.helpOpen) {
          setHelpOpen(false);
          return;
        }
        if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
        return;
      }
      if (e.key === "?" && !mod && !isTypingTarget(e.target)) {
        e.preventDefault();
        setHelpOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const busy = status !== "idle";

  const sourceResume = useMemo(
    () => (result && "source_resume" in result ? asResume(result.source_resume) : null),
    [result],
  );

  const ready = result ? isReady(result) : null;

  const mode = helpOpen
    ? "HELP"
    : status === "tailoring"
      ? "RUNNING"
      : status === "scanning"
        ? "SCANNING"
        : "NORMAL";

  // --- the run panel's data ----------------------------------------------
  const jdChars = jdText.trim().length;

  const stageDetails: Record<string, TaskDetail[]> = useMemo(
    () => ({
      read: [
        { label: "job description", meta: `${jdChars} chars` },
        { label: "target role", meta: targetRole.trim() || "not set" },
      ],
      keywords: [
        { label: "required vs preferred split" },
        { label: "whitespace-collapsed substring match" },
      ],
      bullets: [
        { label: "reword only — never invent" },
        { label: "pass limit", meta: String(maxPasses) },
      ],
      render: [{ label: "single column, standard headers" }, { label: "one-page density ladder" }],
      grading: [{ label: "keyword scan" }, { label: "seven rubric gates" }],
    }),
    [jdChars, targetRole, maxPasses],
  );

  const tasks: Task[] = useMemo(() => {
    if (!run) return [];
    return STAGES.map((stage, i) => ({
      id: stage.id,
      label: stage.label,
      state: stageState(i, run),
      details: stageDetails[stage.id],
    }));
  }, [run, stageDetails]);

  const traceSteps: TraceStep[] = useMemo(() => {
    if (!run) return [];
    return STAGES.slice(0, run.stageIndex + 1).map((stage) => ({
      primary: stage.trace,
      secondary: stage.label,
    }));
  }, [run]);

  const currentStage = run ? (STAGES[run.stageIndex] ?? STAGES[STAGES.length - 1]) : null;

  return (
    <div className={styles.shell}>
      <TopBar health={health} />

      <main className={styles.body}>
        <div className={styles.leftCol}>
          <InputRail
            jdText={jdText}
            onJdText={setJdText}
            resumeText={resumeText}
            onResumeText={setResumeText}
            targetRole={targetRole}
            onTargetRole={setTargetRole}
            availability={availability}
            onAvailability={setAvailability}
            companyUrl={companyUrl}
            onCompanyUrl={setCompanyUrl}
            errors={fieldErrors}
            advancedOpen={advancedOpen}
            onAdvancedOpenChange={setAdvancedOpen}
            apiKey={apiKey}
            onApiKeyChange={setApiKey}
            keyRequired={keyRequired}
            maxPasses={maxPasses}
            onMaxPassesChange={setMaxPasses}
            apiKeyRef={apiKeyInputRef}
            onTailor={handleTailor}
            onScan={handleScan}
            busy={busy}
          />
        </div>

        <div className={styles.rightCol}>
          {errorBanner ? <ErrorBanner message={errorBanner.message} hint={errorBanner.hint} /> : null}

          {run && currentStage ? (
            <Panel
              title={run.phase === "failed" ? "tailoring — stopped" : "tailoring"}
              aside={
                run.phase === "running" ? (
                  <LoadingState label="working" startedAt={run.startedAt} />
                ) : (
                  <span className={styles.stopped}>the pass did not finish</span>
                )
              }
            >
              <TaskRows tasks={tasks} label="Tailoring pipeline" />

              <div className={styles.trace}>
                <ThinkingTrace
                  title={currentStage.label}
                  doneTitle={run.phase === "failed" ? "where it stopped" : "what it did"}
                  steps={traceSteps}
                  running={run.phase === "running"}
                />
              </div>

              {/* Honesty, not decoration: the ticks above follow a schedule,
                  not a server report, and the reader is told so. */}
              <p className={styles.honesty}>
                the server answers once, when the whole pass lands. the marks above follow a typical
                30–90 second schedule — they say where the run should be by now, not what the server
                has confirmed.
              </p>
            </Panel>
          ) : null}

          {status === "scanning" ? (
            <Panel title="scoring" aside={<LoadingState label="scoring" variant="dots" />}>
              <p className={styles.scanning}>
                grading the resume you pasted against the posting. no model call, no key — this is
                the deterministic scanner, and it is usually done inside a second.
              </p>
            </Panel>
          ) : null}

          {result ? (
            <ResultsPanel
              key={runSeq}
              result={result}
              sourceResume={sourceResume}
              edits={edits}
              onEditsChange={setEdits}
              onTailor={handleTailor}
            />
          ) : status === "idle" && !run ? (
            <Panel title="review">
              <div className={styles.empty}>
                <h3 className={styles.emptyTitle}>Nothing has been graded yet.</h3>
                <p className={styles.emptyLine}>
                  Paste a job description and your resume on the left. Everything you type stays in
                  this tab.
                </p>
                <p className={styles.emptyLine}>
                  <kbd>ctrl s</kbd> scores what you already have, deterministically and in under a
                  second. <kbd>ctrl ↵</kbd> runs the full five-stage pass:
                </p>
                <ol className={styles.emptyStages}>
                  {STAGES.map((stage, i) => (
                    <li key={stage.id}>
                      <span className={styles.emptyStageNum}>
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      {stage.label}
                    </li>
                  ))}
                </ol>
              </div>
            </Panel>
          ) : null}
        </div>
      </main>

      <StatusBar mode={mode} ready={ready} />

      {/* The app's one result region: short, in the DOM from first paint (which
          is what makes it reliably spoken), and mutated once per landed run —
          including the verdict, because ReadyChip cannot announce it from
          inside a panel that is remounted per run. While a run is in flight
          TaskRows owns a second polite region reporting the current stage, and
          those two are the only live regions in the review column. */}
      <p className="sr-only" role="status">
        {liveMessage}
      </p>

      <HelpOverlay open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
