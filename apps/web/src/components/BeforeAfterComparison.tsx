import React from "react";
import { ArrowRight, TrendingDown, ShieldCheck, Zap } from "lucide-react";

export interface BeforeAfterComparisonProps {
  before: {
    gridStressIndex: number;
    curtailmentMw: number;
    demandMw?: number;
    batterySocPercent?: number;
  };
  after: {
    gridStressIndex: number;
    curtailmentMw: number;
    demandMw?: number;
    batterySocPercent?: number;
  };
}

export const BeforeAfterComparison: React.FC<BeforeAfterComparisonProps> = ({ before, after }) => {
  const stressDelta = Math.round((after.gridStressIndex - before.gridStressIndex) * 100) / 100;
  const curtailmentSaved = Math.max(0, before.curtailmentMw - after.curtailmentMw);

  return (
    <div className="glass-panel rounded-xl p-5 border border-slate-800/80">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-white tracking-wide">
          Optimization Impact: Before vs. After
        </h3>
        <span className="flex items-center gap-1 text-xs font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/30">
          <TrendingDown className="h-3 w-3" /> Stress Reduction: {Math.abs(stressDelta).toFixed(2)}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Before Panel */}
        <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold mb-3">
            <span>BASELINE / UNMITIGATED</span>
            <span className="text-rose-400">Pre-Dispatch</span>
          </div>

          <div className="space-y-2.5">
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400">Grid Stress Index:</span>
              <span className="font-mono font-bold text-rose-300">
                {before.gridStressIndex.toFixed(2)}
              </span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-rose-500 h-full"
                style={{ width: `${Math.min(100, before.gridStressIndex * 100)}%` }}
              />
            </div>

            <div className="flex justify-between items-center text-xs pt-1">
              <span className="text-slate-400">Renewable Curtailment:</span>
              <span className="font-mono font-medium text-amber-300">
                {before.curtailmentMw.toFixed(1)} MW
              </span>
            </div>

            {before.batterySocPercent !== undefined && (
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400">Battery SOC:</span>
                <span className="font-mono text-slate-200">
                  {before.batterySocPercent.toFixed(0)}%
                </span>
              </div>
            )}
          </div>
        </div>

        {/* After Panel */}
        <div className="rounded-lg bg-slate-900/80 border border-cyan-900/30 p-4">
          <div className="flex items-center justify-between text-xs text-cyan-400 font-semibold mb-3">
            <span>OPTIMIZED / MITIGATED</span>
            <span className="text-emerald-400">Post-Dispatch</span>
          </div>

          <div className="space-y-2.5">
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400">Grid Stress Index:</span>
              <span className="font-mono font-bold text-emerald-300">
                {after.gridStressIndex.toFixed(2)}
              </span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-emerald-500 h-full"
                style={{ width: `${Math.min(100, after.gridStressIndex * 100)}%` }}
              />
            </div>

            <div className="flex justify-between items-center text-xs pt-1">
              <span className="text-slate-400">Renewable Curtailment:</span>
              <span className="font-mono font-medium text-emerald-300">
                {after.curtailmentMw.toFixed(1)} MW
              </span>
            </div>

            {after.batterySocPercent !== undefined && (
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400">Battery SOC:</span>
                <span className="font-mono text-slate-200">
                  {after.batterySocPercent.toFixed(0)}%
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
