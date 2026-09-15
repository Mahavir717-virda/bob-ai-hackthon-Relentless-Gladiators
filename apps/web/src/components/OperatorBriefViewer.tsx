import React, { useState } from "react";
import { FileText, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
import type { OperatorBrief } from "../services/types.ts";

export interface OperatorBriefViewerProps {
  brief: OperatorBrief;
}

export const OperatorBriefViewer: React.FC<OperatorBriefViewerProps> = ({ brief }) => {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(true);

  const handleCopy = () => {
    navigator.clipboard.writeText(brief.rawMarkdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const sectionsList = [
    { num: 1, title: "Current Situation", content: brief.sections.currentSituation },
    { num: 2, title: "Risk Assessment", content: brief.sections.risk },
    { num: 3, title: "Renewable Alert", content: brief.sections.renewableAlert },
    { num: 4, title: "Root Cause Diagnostics", content: brief.sections.rootCause },
    { num: 5, title: "Recommended Actions", content: brief.sections.recommendedActions },
    { num: 6, title: "Expected Impact", content: brief.sections.expectedImpact },
    { num: 7, title: "Confidence & Uncertainty", content: brief.sections.confidenceUncertainty },
    { num: 8, title: "Data Limitations", content: brief.sections.dataLimitations },
  ];

  return (
    <div className="rounded-md overflow-hidden border border-border bg-surface shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3.5 bg-surface-muted/40">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-spectrum-tech/15 text-spectrum-tech border border-spectrum-tech/30">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-primary tracking-wide">
                8-Section Operator Incident Brief
              </h3>
              <span className="font-metric text-xs text-secondary">({brief.briefId})</span>
            </div>
            <span className="text-[11px] text-secondary">
              Generated {new Date(brief.timestamp).toLocaleTimeString()} for Substation {brief.zoneId}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2.5 py-0.5 text-xs font-semibold font-mono border ${
              brief.status === "infeasible"
                ? "bg-semantic-error/15 text-semantic-error border-semantic-error/30"
                : "bg-semantic-success/15 text-semantic-success border-semantic-success/30"
            }`}
          >
            {brief.status.toUpperCase()}
          </span>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-md bg-copper-subtle px-2.5 py-1 text-xs font-semibold text-copper border border-copper/30 hover:bg-copper hover:text-white transition-instant"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>

          <button
            onClick={() => setExpanded(!expanded)}
            className="rounded-md bg-surface-muted p-1 text-secondary hover:text-primary border border-border transition-instant"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Content */}
      {expanded && (
        <div className="p-5 space-y-4">
          {brief.missingDataWarnings.length > 0 && (
            <div className="rounded-md bg-semantic-warning/10 border border-semantic-warning/30 p-3 text-xs text-semantic-warning">
              <span className="font-semibold">⚠️ Data Telemetry Disclosures:</span>
              <ul className="mt-1 list-disc list-inside space-y-0.5 text-secondary">
                {brief.missingDataWarnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {sectionsList.map((sec) => (
              <div
                key={sec.num}
                className="rounded-md bg-surface-muted/40 border border-border p-3.5 hover:border-copper/40 transition-fast"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-copper-subtle text-copper text-[10px] font-bold font-metric border border-copper/30">
                    {sec.num}
                  </span>
                  <h4 className="text-xs font-bold text-primary tracking-wide">
                    {sec.title}
                  </h4>
                </div>
                <div className="text-xs leading-relaxed text-secondary whitespace-pre-wrap pl-7 font-sans">
                  {sec.content.replace(/^##\s*\d+\.\s*[^\n]+\n*/, "").trim()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
