import React, { useState } from "react";
import { FileText, ShieldAlert, CheckCircle2, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
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
    <div className="glass-panel rounded-xl overflow-hidden border border-slate-800/80">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4 bg-slate-900/40">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white tracking-wide">
                8-Section Operator Incident Brief
              </h3>
              <span className="font-mono text-xs text-slate-400">({brief.briefId})</span>
            </div>
            <span className="text-xs text-slate-400">
              Generated {new Date(brief.timestamp).toLocaleTimeString()} for Substation {brief.zoneId}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold font-mono border ${
              brief.status === "infeasible"
                ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
                : "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
            }`}
          >
            {brief.status.toUpperCase()}
          </span>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs text-slate-300 hover:bg-slate-700 transition"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>

          <button
            onClick={() => setExpanded(!expanded)}
            className="rounded-lg bg-slate-800 p-1.5 text-slate-300 hover:bg-slate-700 transition"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Content */}
      {expanded && (
        <div className="p-5 space-y-4">
          {brief.missingDataWarnings.length > 0 && (
            <div className="rounded-lg bg-amber-950/20 border border-amber-500/30 p-3 text-xs text-amber-300">
              <span className="font-semibold">⚠️ Data Telemetry Disclosures:</span>
              <ul className="mt-1 list-disc list-inside space-y-0.5 text-amber-200/80">
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
                className="rounded-lg bg-slate-900/60 border border-slate-800/80 p-3.5 hover:border-slate-700 transition"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan-950 text-cyan-400 text-[10px] font-bold font-mono border border-cyan-800">
                    {sec.num}
                  </span>
                  <h4 className="text-xs font-bold text-slate-200 tracking-wide">
                    {sec.title}
                  </h4>
                </div>
                <div className="text-xs leading-relaxed text-slate-300 whitespace-pre-wrap pl-7">
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
