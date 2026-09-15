import React from "react";
import { Sun, Wind, AlertTriangle, CheckCircle } from "lucide-react";
import type { RenewableStatus } from "../services/types.ts";

export interface AssetStatusCardProps {
  asset: RenewableStatus;
  onDiagnose?: (assetId: string) => void;
}

export const AssetStatusBadge: React.FC<AssetStatusCardProps> = ({ asset, onDiagnose }) => {
  const isSolar = asset.assetType === "solar";
  const prPercent = Math.round(asset.performanceRatio * 100);

  return (
    <div
      className={`rounded-md p-4 transition-fast border bg-surface shadow-sm ${
        asset.anomaly
          ? "border-semantic-warning/50 bg-semantic-warning/5 hover:border-semantic-warning"
          : "border-border hover:border-copper/40"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div
            className={`flex h-9 w-9 items-center justify-center rounded-md ${
              isSolar
                ? "bg-spectrum-amber/15 text-spectrum-amber border border-spectrum-amber/30"
                : "bg-spectrum-radar/15 text-spectrum-radar border border-spectrum-radar/30"
            }`}
          >
            {isSolar ? <Sun className="h-5 w-5" /> : <Wind className="h-5 w-5" />}
          </div>
          <div>
            <h4 className="text-xs font-bold text-primary font-mono">{asset.assetId}</h4>
            <span className="text-[11px] text-secondary capitalize">{asset.assetType} Generation Plant</span>
          </div>
        </div>

        {asset.anomaly ? (
          <span className="flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold text-semantic-warning bg-semantic-warning/15 border border-semantic-warning/30 animate-pulse">
            <AlertTriangle className="h-3 w-3" /> Anomaly
          </span>
        ) : (
          <span className="flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold text-semantic-success bg-semantic-success/15 border border-semantic-success/30">
            <CheckCircle className="h-3 w-3" /> Nominal
          </span>
        )}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
        <div>
          <span className="text-[10px] text-secondary">Actual</span>
          <p className="text-xs font-bold text-primary font-metric mt-0.5">{asset.actualMw} MW</p>
        </div>
        <div>
          <span className="text-[10px] text-secondary">Expected</span>
          <p className="text-xs font-medium text-secondary font-metric mt-0.5">{asset.expectedMw} MW</p>
        </div>
        <div>
          <span className="text-[10px] text-secondary">Perf Ratio</span>
          <p
            className={`text-xs font-bold font-metric mt-0.5 ${
              prPercent < 85 ? "text-semantic-warning" : "text-semantic-success"
            }`}
          >
            {prPercent}%
          </p>
        </div>
      </div>

      {asset.likelyRootCause && (
        <div className="mt-3 rounded-md bg-surface-muted p-2.5 text-xs border border-border">
          <div className="flex items-center justify-between text-[11px] font-semibold text-copper">
            <span>Root Cause: {asset.likelyRootCause.category.replace("_", " ").toUpperCase()}</span>
            <span className="font-metric">{(asset.likelyRootCause.confidence * 100).toFixed(0)}% conf</span>
          </div>
          <p className="mt-1 text-[11px] text-secondary leading-snug">{asset.likelyRootCause.evidence}</p>
        </div>
      )}

      {onDiagnose && (
        <button
          onClick={() => onDiagnose(asset.assetId)}
          className="mt-3 w-full rounded-md bg-copper-subtle text-copper border border-copper/30 py-1.5 text-xs font-semibold hover:bg-copper hover:text-white transition-instant"
        >
          Diagnose with Copilot →
        </button>
      )}
    </div>
  );
};
