import React from "react";
import { BatteryCharging, ArrowDownRight, ArrowUpRight, Zap, Clock } from "lucide-react";
import type { OptimizationAction } from "../services/types.ts";

export interface OptimizationActionsTableProps {
  actions: OptimizationAction[];
  status?: "feasible" | "infeasible" | "optimal";
  objectiveValue?: number;
  solveDurationMs?: number;
}

export const OptimizationActionsTable: React.FC<OptimizationActionsTableProps> = ({
  actions,
  status = "feasible",
  objectiveValue,
  solveDurationMs,
}) => {
  const getActionBadge = (actionType: string) => {
    switch (actionType) {
      case "battery_discharge":
        return {
          label: "BESS Discharge",
          color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
          icon: ArrowDownRight,
        };
      case "battery_charge":
        return {
          label: "BESS Charge",
          color: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
          icon: ArrowUpRight,
        };
      case "load_shift":
      case "shift_flexible_load":
        return {
          label: "Flexible Load Shift",
          color: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
          icon: Zap,
        };
      case "curtailment":
        return {
          label: "Renewable Curtailment",
          color: "bg-amber-500/20 text-amber-300 border-amber-500/30",
          icon: Clock,
        };
      default:
        return {
          label: actionType,
          color: "bg-slate-700/50 text-slate-300 border-slate-600",
          icon: Zap,
        };
    }
  };

  return (
    <div className="glass-panel rounded-xl overflow-hidden border border-slate-800/80">
      <div className="flex items-center justify-between border-b border-slate-800/80 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">
            <Zap className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-wide">
              OR-Tools MILP Mathematical Dispatch Schedule
            </h3>
            <span className="text-xs text-slate-400">
              Deterministic actions computed to minimize grid stress & cost
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {solveDurationMs !== undefined && (
            <span className="text-xs text-slate-400 font-mono">
              Solved in {solveDurationMs}ms
            </span>
          )}
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold font-mono border ${
              status === "infeasible"
                ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
                : "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
            }`}
          >
            {status.toUpperCase()}
          </span>
        </div>
      </div>

      {actions.length === 0 ? (
        <div className="p-8 text-center text-sm text-slate-400">
          {status === "infeasible"
            ? "⚠️ Solver returned INFEASIBLE. Available grid flexibility cannot resolve demand overload without violating physical constraints."
            : "No active dispatch interventions required. Grid operating within nominal reserves."}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800/60">
              <tr>
                <th className="px-5 py-3">Resource</th>
                <th className="px-5 py-3">Action Type</th>
                <th className="px-5 py-3 text-right">Power Magnitude</th>
                <th className="px-5 py-3">Execution Window</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40">
              {actions.map((action, idx) => {
                const badge = getActionBadge(action.actionType);
                const Icon = badge.icon;
                return (
                  <tr key={idx} className="hover:bg-slate-800/30 transition">
                    <td className="px-5 py-3.5 font-mono font-medium text-white">
                      {action.resourceId}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium border ${badge.color}`}
                      >
                        <Icon className="h-3 w-3" />
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-bold text-white text-sm">
                      {action.powerMw} <span className="text-xs font-normal text-slate-400">MW</span>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-300">
                      {new Date(action.startTime).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}{" "}
                      -{" "}
                      {new Date(action.endTime).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
