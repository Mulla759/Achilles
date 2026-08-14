"use client";

import type { RefObject } from "react";
import styles from "./InputRail.module.css";
import { Panel } from "./Panel";
import { TextArea } from "./TextArea";
import { TextField } from "./TextField";
import { AdvancedSection } from "./AdvancedSection";
import { Button } from "./Button";

export interface FieldErrors {
  jd?: string;
  resume?: string;
  targetRole?: string;
  apiKey?: string;
}

interface InputRailProps {
  jdText: string;
  onJdText: (v: string) => void;
  resumeText: string;
  onResumeText: (v: string) => void;
  targetRole: string;
  onTargetRole: (v: string) => void;
  availability: string;
  onAvailability: (v: string) => void;
  companyUrl: string;
  onCompanyUrl: (v: string) => void;
  errors: FieldErrors;

  advancedOpen: boolean;
  onAdvancedOpenChange: (v: boolean) => void;
  apiKey: string;
  onApiKeyChange: (v: string) => void;
  keyRequired: boolean;
  maxPasses: number;
  onMaxPassesChange: (v: number) => void;
  apiKeyRef?: RefObject<HTMLInputElement | null>;

  onTailor: () => void;
  onScan: () => void;
  busy: boolean;
}

export function InputRail({
  jdText,
  onJdText,
  resumeText,
  onResumeText,
  targetRole,
  onTargetRole,
  availability,
  onAvailability,
  companyUrl,
  onCompanyUrl,
  errors,
  advancedOpen,
  onAdvancedOpenChange,
  apiKey,
  onApiKeyChange,
  keyRequired,
  maxPasses,
  onMaxPassesChange,
  apiKeyRef,
  onTailor,
  onScan,
  busy,
}: InputRailProps) {
  return (
    <div className={styles.rail}>
      <Panel title="job description" statusLine={`${jdText.trim().length} chars · min 40`}>
        <TextArea
          label="job description"
          value={jdText}
          onChange={onJdText}
          placeholder="paste the full job description here..."
          minLength={40}
          rows={9}
          required
          showPasteButton
          error={errors.jd}
        />
      </Panel>

      <Panel title="your resume" statusLine={`${resumeText.trim().length.toLocaleString()} chars`}>
        <TextArea
          label="your current resume"
          value={resumeText}
          onChange={onResumeText}
          placeholder="paste your resume text, or drop a .txt / .md file..."
          rows={9}
          required
          acceptFileDrop
          error={errors.resume}
        />
      </Panel>

      {/* A privacy promise, not a caption. Do not reword it. */}
      <p className={styles.hint}>nothing is saved in the browser — a reload clears the form.</p>

      <Panel title="details">
        <div className={styles.detailsBody}>
          <TextField
            label="target role"
            value={targetRole}
            onChange={onTargetRole}
            placeholder="Product Manager Intern"
            required
            error={errors.targetRole}
          />
          <div className={styles.grid2}>
            <TextField
              label="availability"
              value={availability}
              onChange={onAvailability}
              placeholder="May 2027 – Aug 2027"
              optional
            />
            <TextField
              label="company url"
              value={companyUrl}
              onChange={onCompanyUrl}
              placeholder="https://..."
              optional
            />
          </div>
        </div>
      </Panel>

      <AdvancedSection
        open={advancedOpen}
        onOpenChange={onAdvancedOpenChange}
        apiKey={apiKey}
        onApiKeyChange={onApiKeyChange}
        keyRequired={keyRequired}
        maxPasses={maxPasses}
        onMaxPassesChange={onMaxPassesChange}
        apiKeyRef={apiKeyRef}
        error={errors.apiKey}
      />

      <div className={styles.actions}>
        <Button variant="primary" onClick={onTailor} disabled={busy}>
          run tailor
          <span className={styles.shortcut} aria-hidden="true">
            ctrl ↵
          </span>
        </Button>
        <Button variant="ghost" onClick={onScan} disabled={busy}>
          just score
          <span className={styles.shortcut} aria-hidden="true">
            ctrl s
          </span>
        </Button>
      </div>
    </div>
  );
}
