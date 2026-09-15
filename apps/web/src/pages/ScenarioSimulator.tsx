import React, { useState, useEffect } from "react";
import { PlaySquare, History, Play, AlertCircle, CheckCircle2, Sliders, ArrowRight } from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { Scenario, OptimizationResult, SimulationResult } from "../services/types.ts";
import { MetricCard } from "../components/MetricCard.tsx";
import { AlertBanner } from "../components/AlertBanner.tsx";
import { OptimizationActionsTable } from "../components/OptimizationActionsTable.tsx";
import { BeforeAfterComparison } from "../components/BeforeAfterComparison.tsx";

export const ScenarioSimulatorPage: React.FC = () => {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null);
  const [replayResult, setReplayResult] = useState<OptimizationResult | null>(null);
  const [replaying, setReplaying] = useState(false);

  // What-If Simulation State
  const [simAsset, setSimAsset] = useState("BESS_SUB_01");
  const [simAction, setSimAction] = useState("battery_discharge");
  const [simPowerMw, setSimPowerMw] = useState(15);
  const [simResult, setSimResult] = useState<SimulationResult | null>(null);
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        const list = await ApiClient.getScenarios();
        setScenarios(list);
        if (list.length > 0) {
          setSelectedScenario(list[0]);
        }
      } catch (err: any) {
        console.error("Failed to load scenarios", err);
      }
    };
    fetchScenarios();
  }, []);

  const handleReplay = async () => {
    if (!selectedScenario) return;
    try {
      setReplaying(true);
      const res = await ApiClient.replayScenario(selectedScenario.scenarioId);
      setReplayResult(res.result);
    } catch (err: any) {
      alert(`Replay error: ${err.message}`);
    } finally {
      setReplaying(false);
    }
  };

  const handleSimulateAction = async () => {
    try {
      setSimulating(true);
      const copilotRes = await ApiClient.queryCopilot("Simulate action", {
        explicitTools: ["simulate_action"],
        simulationArgs: {
          resourceId: simAsset,
          actionType: simAction,
          powerMw: simPowerMw,
          durationMinutes: 15,
        },
      });

      if (copilotRes.toolResults.simulate_action) {
        setSimResult(copilotRes.toolResults.simulate_action);
      }
    } catch (err: any) {
      alert(`Simulation error: ${err.message}`);
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <PlaySquare className="h-6 w-6 text-cyan-400" />
          Scenario Simulator & What-If Action Sandbox
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Replay historical Liander 2024 incidents or evaluate prospective operator actions without mutating live grid state
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Historical Incident Replay */}
        <div className="glass-panel rounded-xl p-5 border border-slate-800/80 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <History className="h-5 w-5 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold text-white">Historical Incident Replay</h3>
              <span className="text-xs text-slate-400">Deterministic OpenSTEF/Liander 2024 Event</span>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-slate-300 font-semibold">Select Scenario Template:</label>
            <select
              value={selectedScenario?.scenarioId || ""}
              onChange={(e) => {
                const found = scenarios.find((s) => s.scenarioId === e.target.value);
                if (found) setSelectedScenario(found);
              }}
              className="w-full rounded-lg bg-slate-900 border border-slate-800 p-2.5 text-xs text-white focus:outline-none focus:border-cyan-500 font-mono"
            >
              {scenarios.map((s) => (
                <option key={s.scenarioId} value={s.scenarioId}>
                  {s.scenarioId} — {s.name}
                </option>
              ))}
            </select>
          </div>

          {selectedScenario && (
            <div className="rounded-lg bg-slate-900/80 p-3.5 text-xs border border-slate-800 space-y-2">
              <p className="text-slate-300 leading-relaxed">{selectedScenario.description}</p>
              <div className="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
                <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                  Source: {selectedScenario.historicalSourceTimestamp?.slice(0, 10) || "2024-06-12"}
                </span>
                {selectedScenario.expectedOutcome?.expectedSpikeClass && (
                  <span className="rounded bg-amber-950 text-amber-300 border border-amber-800 px-2 py-0.5">
                    Spike Class: {selectedScenario.expectedOutcome.expectedSpikeClass.toUpperCase()}
                  </span>
                )}
                {selectedScenario.expectedOutcome?.expectedAnomalyScoreMin !== undefined && (
                  <span className="rounded bg-cyan-950 text-cyan-300 border border-cyan-800 px-2 py-0.5">
                    Min Anomaly Score: {selectedScenario.expectedOutcome.expectedAnomalyScoreMin}
                  </span>
                )}
              </div>
            </div>
          )}

          <button
            onClick={handleReplay}
            disabled={replaying || !selectedScenario}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 py-2.5 text-xs font-bold text-white shadow-lg shadow-cyan-900/30 transition active:scale-95 disabled:opacity-50"
          >
            <Play className={`h-4 w-4 ${replaying ? "animate-spin" : ""}`} />
            <span>{replaying ? "Replaying Liander Grid Incident..." : "Replay Scenario Through Engine"}</span>
          </button>
        </div>

        {/* Right Column: Interactive What-If Simulator */}
        <div className="glass-panel rounded-xl p-5 border border-slate-800/80 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Sliders className="h-5 w-5 text-indigo-400" />
            <div>
              <h3 className="text-sm font-bold text-white">Prospective Action Simulator</h3>
              <span className="text-xs text-slate-400">Evaluate impact on grid stress before committing</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="text-slate-300 font-semibold block mb-1">Target Resource:</label>
              <select
                value={simAsset}
                onChange={(e) => setSimAsset(e.target.value)}
                className="w-full rounded-lg bg-slate-900 border border-slate-800 p-2 text-white font-mono"
              >
                <option value="BESS_SUB_01">BESS_SUB_01 (40 MWh Battery)</option>
                <option value="FLEX_LOAD_IND_PARK">FLEX_LOAD_IND_PARK (Flexible Load)</option>
                <option value="SOLAR_FARM_ZEELAND_01">SOLAR_FARM_ZEELAND_01 (Solar)</option>
              </select>
            </div>

            <div>
              <label className="text-slate-300 font-semibold block mb-1">Action Type:</label>
              <select
                value={simAction}
                onChange={(e) => setSimAction(e.target.value)}
                className="w-full rounded-lg bg-slate-900 border border-slate-800 p-2 text-white font-mono"
              >
                <option value="battery_discharge">Battery Discharge</option>
                <option value="battery_charge">Battery Charge</option>
                <option value="shift_flexible_load">Shift Flexible Load</option>
                <option value="curtail_solar">Curtail Solar</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-slate-300 font-semibold">Simulated Power:</span>
              <span className="font-mono font-bold text-cyan-300">{simPowerMw} MW</span>
            </div>
            <input
              type="range"
              min="1"
              max="30"
              value={simPowerMw}
              onChange={(e) => setSimPowerMw(Number(e.target.value))}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>

          <button
            onClick={handleSimulateAction}
            disabled={simulating}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 py-2.5 text-xs font-bold text-white shadow-lg shadow-indigo-900/30 transition active:scale-95 disabled:opacity-50"
          >
            <Sliders className="h-4 w-4" />
            <span>{simulating ? "Evaluating Constraints..." : "Run simulate_action() Sandbox"}</span>
          </button>

          {/* Simulation Output Card */}
          {simResult && (
            <div className="rounded-lg bg-slate-900/90 border border-slate-800 p-3.5 text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-white">Projected Grid Stress:</span>
                <span className="font-mono font-bold text-emerald-300 text-sm">
                  {simResult.projectedGridStress.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Delta Stress Effect:</span>
                <span className="font-mono font-semibold text-emerald-400">
                  {simResult.deltaGridStress > 0 ? `+${simResult.deltaGridStress.toFixed(2)}` : simResult.deltaGridStress.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Feasibility Check:</span>
                <span
                  className={`font-semibold font-mono ${
                    simResult.isFeasible ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {simResult.isFeasible ? "FEASIBLE" : "INFEASIBLE / CONSTRAINT VIOLATION"}
                </span>
              </div>

              {simResult.constraintWarnings.length > 0 && (
                <div className="rounded bg-rose-950/40 border border-rose-500/40 p-2 text-rose-300 text-[11px]">
                  {simResult.constraintWarnings.map((w, i) => (
                    <p key={i}>⚠️ {w}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Replay Result Panel */}
      {replayResult && (
        <div className="space-y-4 pt-4 border-t border-slate-800">
          <h3 className="text-base font-bold text-white">
            Replay Outcome: Solver Dispatch & Impact Analysis
          </h3>
          <BeforeAfterComparison before={replayResult.before} after={replayResult.after} />
          <OptimizationActionsTable actions={replayResult.actions} status={replayResult.status} />
        </div>
      )}
    </div>
  );
};
