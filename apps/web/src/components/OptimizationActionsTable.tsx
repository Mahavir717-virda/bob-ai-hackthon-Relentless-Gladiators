import React from "react";
import { ArrowDownRight, ArrowUpRight, Zap, Clock } from "lucide-react";
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
          color: "bg-spectrum-moss/15 text-spectrum-moss border-spectrum-moss/30",
          icon: ArrowDownRight,
        };
      case "battery_charge":
        return {
          label: "BESS Charge",
          color: "bg-spectrum-radar/15 text-spectrum-radar border-spectrum-radar/30",
          icon: ArrowUpRight,
        };
      case "load_shift":
      case "shift_flexible_load":
        return {
          label: "Flexible Load Shift",
          color: "bg-spectrum-tech/15 text-spectrum-tech border-spectrum-tech/30",
          icon: Zap,
        };
      case "curtailment":
        return {
          label: "Renewable Curtailment",
          color: "bg-spectrum-amber/15 text-spectrum-amber border-spectrum-amber/30",
          icon: Clock,
        };
      default:
        return {
          label: actionType,
          color: "bg-surface-muted text-secondary border-border",
          icon: Zap,
        };
    }
  };

  return (
    <div className="rounded-md overflow-hidden border border-border bg-surface shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-5 py-3.5 bg-surface-muted/40">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-copper-subtle text-copper border border-copper/30">
            <Zap className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-primary tracking-wide">
              OR-Tools MILP Mathematical Dispatch Schedule
            </h3>
            <span className="text-[11px] text-secondary">
              Deterministic actions computed to minimize grid stress & cost
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {solveDurationMs !== undefined && (
            <span className="text-xs text-secondary font-metric">
              Solved in {solveDurationMs}ms
            </span>
          )}
          <span
            className={`rounded px-2.5 py-0.5 text-xs font-semibold font-mono border ${
              status === "infeasible"
                ? "bg-semantic-error/15 text-semantic-error border-semantic-error/30"
                : "bg-spectrum-moss/15 text-spectrum-moss border-spectrum-moss/30"
            }`}
          >
            {status.toUpperCase()}
          </span>
        </div>
      </div>

      {actions.length === 0 ? (
        <div className="p-8 text-center text-xs text-secondary">
          {status === "infeasible"
            ? "Solver returned INFEASIBLE. Available grid flexibility cannot resolve demand overload without violating physical constraints."
            : "No active dispatch interventions required. Grid operating within nominal reserves."}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-muted/80 text-secondary tracking-wider font-semibold border-b border-border">
              <tr>
                <th className="px-5 py-2.5 text-[11px] uppercase">Resource ID</th>
                <th className="px-5 py-2.5 text-[11px] uppercase">Action Type</th>
                <th className="px-5 py-2.5 text-right text-[11px] uppercase">Power Magnitude</th>
                <th className="px-5 py-2.5 text-[11px] uppercase">Execution Window</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {actions.map((action, idx) => {
                const badge = getActionBadge(action.actionType);
                const Icon = badge.icon;
                return (
                  <tr key={idx} className="hover:bg-surface-muted/40 transition-fast">
                    <td className="px-5 py-3 font-mono font-medium text-primary">
                      {action.resourceId}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium border ${badge.color}`}
                      >
                        <Icon className="h-3 w-3" />
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-metric font-bold text-primary text-sm">
                      {action.powerMw} <span className="text-xs font-normal text-secondary">MW</span>
                    </td>
                    <td className="px-5 py-3 font-metric text-secondary text-xs">
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
