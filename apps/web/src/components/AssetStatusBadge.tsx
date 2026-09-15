import React from "react";
import { Sun, Wind, BatteryCharging, Factory, AlertTriangle, CheckCircle } from "lucide-react";
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
      className={`glass-panel rounded-xl p-4 transition-all duration-200 border ${
        asset.anomaly
          ? "border-amber-500/50 bg-amber-950/10 hover:border-amber-500"
          : "border-slate-800/80 hover:border-cyan-500/40"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div
            className={`flex h-9 w-9 items-center justify-center rounded-lg ${
              isSolar ? "bg-amber-500/10 text-amber-400" : "bg-cyan-500/10 text-cyan-400"
            }`}
          >
            {isSolar ? <Sun className="h-5 w-5" /> : <Wind className="h-5 w-5" />}
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white font-mono">{asset.assetId}</h4>
            <span className="text-xs text-slate-400 capitalize">{asset.assetType} Generation Plant</span>
          </div>
        </div>

        {asset.anomaly ? (
          <span className="flex items-center gap-1 rounded-md bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300 border border-amber-500/40 animate-pulse">
            <AlertTriangle className="h-3 w-3" /> Anomaly
          </span>
        ) : (
          <span className="flex items-center gap-1 rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-400 border border-emerald-500/30">
            <CheckCircle className="h-3 w-3" /> Nominal
          </span>
        )}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-slate-800/60 pt-3 text-center">
        <div>
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Actual</span>
          <p className="text-sm font-bold text-white font-mono mt-0.5">{asset.actualMw} MW</p>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Expected</span>
          <p className="text-sm font-medium text-slate-300 font-mono mt-0.5">{asset.expectedMw} MW</p>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Perf Ratio</span>
          <p
            className={`text-sm font-bold font-mono mt-0.5 ${
              prPercent < 85 ? "text-amber-400" : "text-emerald-400"
            }`}
          >
            {prPercent}%
          </p>
        </div>
      </div>

      {asset.likelyRootCause && (
        <div className="mt-3 rounded-lg bg-slate-900/80 p-2.5 text-xs border border-slate-800">
          <div className="flex items-center justify-between text-[11px] font-semibold text-cyan-400">
            <span>Root Cause: {asset.likelyRootCause.category.replace("_", " ").toUpperCase()}</span>
            <span>{(asset.likelyRootCause.confidence * 100).toFixed(0)}% conf</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-300 leading-snug">{asset.likelyRootCause.evidence}</p>
        </div>
      )}

      {onDiagnose && (
        <button
          onClick={() => onDiagnose(asset.assetId)}
          className="mt-3 w-full rounded-lg bg-slate-800/80 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-cyan-900/30 hover:text-cyan-300 hover:border-cyan-500/30 border border-transparent"
        >
          Diagnose with Copilot →
        </button>
      )}
    </div>
  );
};
