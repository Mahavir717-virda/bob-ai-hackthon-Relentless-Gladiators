import React, { useState, useEffect } from "react";
import { Zap, Play, Sliders, ShieldCheck, Clock } from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { OptimizationResult } from "../services/types.ts";
import { MetricCard } from "../components/MetricCard.tsx";
import { AlertBanner } from "../components/AlertBanner.tsx";
import { OptimizationActionsTable } from "../components/OptimizationActionsTable.tsx";
import { BeforeAfterComparison } from "../components/BeforeAfterComparison.tsx";

export const OptimizationCenterPage: React.FC = () => {
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [solving, setSolving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Constraint configuration state
  const [batterySoc, setBatterySoc] = useState<number>(55);
  const [maxDischargeMw, setMaxDischargeMw] = useState<number>(20);
  const [flexibleMw, setFlexibleMw] = useState<number>(10);

  const runSolver = async (overrides?: any) => {
    try {
      setSolving(true);
      setError(null);
      const gridState = await ApiClient.getGridState();
      const demandForecast = await ApiClient.getDemandForecast(gridState.zoneId, 15);
      const renewableStatuses = await ApiClient.getRenewableStatuses();

      let solarMw = 0;
      let windMw = 0;
      let expectedMw = 0;
      for (const r of renewableStatuses) {
        expectedMw += r.expectedMw || 0;
        if (r.assetType === "solar") solarMw += r.actualMw || 0;
        if (r.assetType === "wind") windMw += r.actualMw || 0;
      }
      solarMw = Math.round(solarMw * 100) / 100;
      windMw = Math.round(windMw * 100) / 100;
      expectedMw = Math.round(expectedMw * 100) / 100;

      const payload = {
        scenarioId: `SOLVER_RUN_${Date.now()}`,
        targetTimestamp: demandForecast.points[0]?.timestamp || new Date().toISOString(),
        horizonMinutes: 15,
        currentGridState: {
          ...gridState,
          solarGenerationMw: solarMw,
          windGenerationMw: windMw,
          netLoadMw: Math.round((gridState.demandMw - (solarMw + windMw)) * 100) / 100,
          batterySocPercent: overrides?.batterySoc ?? batterySoc,
        },
        demandForecast,
        renewableForecastMw: expectedMw,
        batteryConstraints: {
          maxCapacityMwh: 40.0,
          currentSocPercent: overrides?.batterySoc ?? batterySoc,
          minSocPercent: 10.0,
          maxSocPercent: 90.0,
          maxChargePowerMw: 20.0,
          maxDischargePowerMw: overrides?.maxDischargeMw ?? maxDischargeMw,
          roundTripEfficiency: 0.90,
        },
        flexibleLoadConstraints: {
          totalFlexibleMw: overrides?.flexibleMw ?? flexibleMw,
          maxShiftDurationMinutes: 60,
          shiftCostPerMw: 15.0,
        },
        curtailmentPenaltyPerMw: 50.0,
      };

      const optResult = await ApiClient.runOptimization(payload);
      setResult(optResult);
    } catch (err: any) {
      setError(err?.message || "Failed to execute optimization solver");
    } finally {
      setSolving(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    runSolver();
  }, []);

  const isInfeasible = result?.status === "infeasible";

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-primary flex items-center gap-2">
            <Zap className="h-5 w-5 text-copper" />
            Grid Optimization Center & Dispatch Engine
          </h2>
          <p className="text-xs text-secondary mt-0.5">
            Google OR-Tools Mixed-Integer Linear Programming (MILP) | Deterministic constraint enforcement
          </p>
        </div>

        <button
          onClick={() => runSolver()}
          disabled={solving}
          className="flex items-center gap-2 rounded-md bg-copper hover:bg-copper-hover px-4 py-2 text-xs font-bold text-white shadow-sm transition-fast active:scale-95 disabled:opacity-50"
        >
          <Play className={`h-4 w-4 ${solving ? "animate-spin" : ""}`} />
          <span>{solving ? "Solving MILP Formulation..." : "Execute OR-Tools Solver"}</span>
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <AlertBanner
          type="critical"
          title="MILP Optimization Execution Failed"
          message={error}
          actionText="Retry Solver"
          onAction={() => runSolver()}
        />
      )}

      {/* Solver Status Banner */}
      {result && (
        isInfeasible ? (
          <AlertBanner
            type="critical"
            title="Infeasible Optimization State"
            message="OR-Tools solver completed with status INFEASIBLE. The combined demand load and asset constraints cannot be met with current battery capacity. Operator manual intervention required."
          />
        ) : (
          <AlertBanner
            type="success"
            title="Mathematically Feasible Optimal Solution"
            message="OR-Tools MILP converged to optimal solution. Battery dispatch and load shifting schedules satisfy all physical thermal, state-of-charge, and ramp-rate limits."
          />
        )
      )}

      {/* Solver Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Solver Status"
          value={result?.status ? result.status.toUpperCase() : "Unavailable"}
          subtitle="Google OR-Tools MILP"
          icon={ShieldCheck}
          change={result ? (isInfeasible ? "Infeasible" : "Feasible") : undefined}
          changeType={result ? (isInfeasible ? "negative" : "positive") : undefined}
          status={result ? (isInfeasible ? "critical" : "nominal") : "nominal"}
        />

        <MetricCard
          title="Solve Latency"
          value={result?.solveDurationMs !== undefined ? result.solveDurationMs : "Unavailable"}
          unit={result?.solveDurationMs !== undefined ? "ms" : undefined}
          subtitle={result ? "MILP Branch & Bound" : "Solver unexecuted"}
          icon={Clock}
          status="nominal"
        />

        <MetricCard
          title="Scheduled Interventions"
          value={result?.actions !== undefined ? result.actions.length : "Unavailable"}
          unit={result?.actions !== undefined ? "actions" : undefined}
          subtitle="BESS + Demand response"
          icon={Zap}
          status="nominal"
        />

        <MetricCard
          title="Objective Value"
          value={result?.objectiveValue !== undefined ? result.objectiveValue.toFixed(1) : "Unavailable"}
          unit={result?.objectiveValue !== undefined ? "EUR" : undefined}
          subtitle="Minimized grid stress penalty"
          icon={Sliders}
          status="nominal"
        />
      </div>

      {/* Before / After Comparison */}
      {result && <BeforeAfterComparison before={result.before} after={result.after} />}

      {/* Dispatch Action Table */}
      {result && (
        <OptimizationActionsTable
          actions={result.actions}
          status={result.status}
          solveDurationMs={result.solveDurationMs}
        />
      )}

      {/* Interactive Constraint Sliders */}
      <div className="rounded-md p-5 border border-border bg-surface shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="h-4 w-4 text-copper" />
          <h3 className="text-xs font-bold text-primary tracking-wide">
            Adjustable Resource Constraints
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs">
          <div>
            <div className="flex justify-between mb-1.5">
              <span className="text-secondary">Battery Starting SOC:</span>
              <span className="font-metric font-bold text-copper">{batterySoc}%</span>
            </div>
            <input
              type="range"
              min="5"
              max="95"
              value={batterySoc}
              onChange={(e) => setBatterySoc(Number(e.target.value))}
              className="w-full accent-[#B5622E] cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between mb-1.5">
              <span className="text-secondary">Max Inverter Discharge:</span>
              <span className="font-metric font-bold text-copper">{maxDischargeMw} MW</span>
            </div>
            <input
              type="range"
              min="5"
              max="35"
              value={maxDischargeMw}
              onChange={(e) => setMaxDischargeMw(Number(e.target.value))}
              className="w-full accent-[#B5622E] cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between mb-1.5">
              <span className="text-secondary">Available Flexible Load:</span>
              <span className="font-metric font-bold text-copper">{flexibleMw} MW</span>
            </div>
            <input
              type="range"
              min="0"
              max="25"
              value={flexibleMw}
              onChange={(e) => setFlexibleMw(Number(e.target.value))}
              className="w-full accent-[#B5622E] cursor-pointer"
            />
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={() => runSolver({ batterySoc, maxDischargeMw, flexibleMw })}
            disabled={solving}
            className="rounded-md bg-copper-subtle text-copper border border-copper/30 px-4 py-2 text-xs font-semibold hover:bg-copper hover:text-white transition-instant disabled:opacity-50"
          >
            Re-solve with Updated Constraints
          </button>
        </div>
      </div>
    </div>
  );
};
