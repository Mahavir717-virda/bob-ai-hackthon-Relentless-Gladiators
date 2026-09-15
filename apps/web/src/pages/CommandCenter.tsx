import React, { useState, useEffect } from "react";
import {
  Activity,
  Zap,
  Sun,
  Battery,
  ShieldAlert,
  FileText,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { OperationalSnapshot, OperatorBrief } from "../services/types.ts";
import { MetricCard } from "../components/MetricCard.tsx";
import { AlertBanner } from "../components/AlertBanner.tsx";
import { TimeSeriesChart } from "../components/TimeSeriesChart.tsx";
import { OperatorBriefViewer } from "../components/OperatorBriefViewer.tsx";

export interface CommandCenterProps {
  onNavigate: (pageId: any) => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({ onNavigate }) => {
  const [snapshot, setSnapshot] = useState<OperationalSnapshot | null>(null);
  const [brief, setBrief] = useState<OperatorBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingBrief, setGeneratingBrief] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await ApiClient.getOperationalSnapshot();
      setSnapshot(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load operational snapshot");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleGenerateBrief = async () => {
    if (!snapshot) return;
    try {
      setGeneratingBrief(true);
      const briefData = await ApiClient.generateOperatorBrief({
        currentGridState: {
          timestamp: snapshot.timestamp,
          zoneId: snapshot.zoneId,
          demandMw: snapshot.currentDemand.valueMw,
          solarGenerationMw: snapshot.renewableGeneration.solarMw,
          windGenerationMw: snapshot.renewableGeneration.windMw,
          batterySocPercent: snapshot.availableFlexibleResources.batteryCurrentSocPercent,
          curtailmentMw: snapshot.curtailment.curtailedMw,
          gridStressIndex: snapshot.gridStress.stressIndex,
        },
        demandForecast: {
          zoneId: snapshot.zoneId,
          generatedAt: snapshot.timestamp,
          horizonMinutes: 15,
          points: [{ timestamp: snapshot.timestamp, demandMw: snapshot.forecastDemand.next15MinMw }],
          spikeRisk: {
            level: snapshot.forecastDemand.spikeRiskLevel,
            probability: snapshot.forecastDemand.spikeProbability,
            predictedPeakMw: snapshot.forecastDemand.next15MinMw,
          },
          modelVersion: "lightgbm-v1",
        },
      });
      setBrief(briefData);
    } catch (err: any) {
      alert(`Failed to generate brief: ${err.message}`);
    } finally {
      setGeneratingBrief(false);
    }
  };

  if (loading && !snapshot) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <Activity className="h-8 w-8 animate-spin text-cyan-400" />
          <span className="text-sm font-mono">Aggregating telemetry from microservices...</span>
        </div>
      </div>
    );
  }

  if (error && !snapshot) {
    return (
      <div className="p-8">
        <AlertBanner
          type="critical"
          title="Telemetry Aggregation Error"
          message={error}
          actionText="Retry"
          onAction={loadData}
        />
      </div>
    );
  }

  const stressPercent = Math.round((snapshot?.gridStress.stressIndex || 0) * 100);
  const stressStatus =
    stressPercent > 75 ? "critical" : stressPercent > 50 ? "warning" : "nominal";

  // Simulated 6-step 15-min trend data from snapshot
  const trendData = [
    { time: "14:00", demand: 82, renewable: 38, netLoad: 44 },
    { time: "14:15", demand: 84, renewable: 40, netLoad: 44 },
    { time: "14:30", demand: 87, renewable: 35, netLoad: 52 },
    { time: "14:45", demand: snapshot?.currentDemand.valueMw || 89, renewable: snapshot?.renewableGeneration.totalMw || 32, netLoad: (snapshot?.currentDemand.valueMw || 89) - (snapshot?.renewableGeneration.totalMw || 32) },
    { time: "15:00 (F)", demand: snapshot?.forecastDemand.next15MinMw || 94, renewable: 30, netLoad: 64 },
    { time: "15:15 (F)", demand: (snapshot?.forecastDemand.next15MinMw || 94) + 2, renewable: 28, netLoad: 68 },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Top Banner Alarms */}
      {snapshot?.renewableAnomalies.hasActiveAnomalies && (
        <AlertBanner
          type="warning"
          title="Renewable Underproduction Detected"
          message={`${snapshot.renewableAnomalies.totalDetected} asset(s) flagged by Isolation Forest. Diagnostic root cause analysis available.`}
          actionText="Inspect Assets"
          onAction={() => onNavigate("renewable_assets")}
        />
      )}

      {snapshot?.forecastDemand.spikeRiskLevel !== "normal" && (
        <AlertBanner
          type="critical"
          title="Imminent Demand Spike Warning"
          message={`XGBoost classifier predicts a demand spike with ${(snapshot?.forecastDemand.spikeProbability || 0) * 100}% probability in the next 15 minutes.`}
          actionText="View Forecast"
          onAction={() => onNavigate("demand_forecast")}
        />
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Current Demand"
          value={snapshot?.currentDemand.valueMw.toFixed(1) || "0.0"}
          unit="MW"
          subtitle={`Forecast +15m: ${snapshot?.forecastDemand.next15MinMw.toFixed(1)} MW`}
          icon={Zap}
          status="nominal"
        />

        <MetricCard
          title="Renewable Output"
          value={snapshot?.renewableGeneration.totalMw.toFixed(1) || "0.0"}
          unit="MW"
          subtitle={`Solar: ${snapshot?.renewableGeneration.solarMw.toFixed(1)} MW | Wind: ${snapshot?.renewableGeneration.windMw.toFixed(1)} MW`}
          icon={Sun}
          change={snapshot?.renewableAnomalies.hasActiveAnomalies ? "Anomaly Alert" : "Nominal"}
          changeType={snapshot?.renewableAnomalies.hasActiveAnomalies ? "warning" : "positive"}
          status={snapshot?.renewableAnomalies.hasActiveAnomalies ? "warning" : "nominal"}
        />

        <MetricCard
          title="Storage SOC"
          value={snapshot?.availableFlexibleResources.batteryCurrentSocPercent.toFixed(0) || "0"}
          unit="%"
          subtitle={`Capacity: ${snapshot?.availableFlexibleResources.batteryCapacityMwh} MWh`}
          icon={Battery}
          status="nominal"
        />

        <MetricCard
          title="Grid Stress Index"
          value={snapshot?.gridStress.stressIndex.toFixed(2) || "0.00"}
          unit="/ 1.0"
          subtitle={`Level: ${snapshot?.gridStress.level.toUpperCase()}`}
          icon={Activity}
          change={stressPercent > 70 ? "High Stress" : "Stable"}
          changeType={stressPercent > 70 ? "negative" : "positive"}
          status={stressStatus}
        />
      </div>

      {/* Main Charts & Quick Action Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TimeSeriesChart
            title="Grid Load & Renewable Generation Balance"
            subtitle="15-minute historical telemetry vs. next-horizon LightGBM projection"
            data={trendData}
            series={[
              { key: "demand", name: "Total Demand (MW)", color: "#38bdf8", fillOpacity: 0.15 },
              { key: "renewable", name: "Renewable Generation (MW)", color: "#10b981", fillOpacity: 0.2 },
              { key: "netLoad", name: "Net Deficit / Load (MW)", color: "#f59e0b", type: "line", strokeDasharray: "4 4" },
            ]}
          />
        </div>

        {/* Quick Operations & Copilot Card */}
        <div className="glass-panel flex flex-col justify-between rounded-xl p-5 border border-slate-800/80">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="flex h-2.5 w-2.5 rounded-full bg-cyan-400 animate-ping" />
              <h3 className="text-sm font-bold text-white tracking-wide">
                Autonomous Dispatch & Incident Brief
              </h3>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed mb-4">
              Trigger OR-Tools Mixed-Integer Linear Programming solver to compute optimal BESS discharge, or synthesize the 8-part operator incident brief via IBM watsonx.ai.
            </p>

            <div className="space-y-2 mb-4">
              <button
                onClick={() => onNavigate("optimization_center")}
                className="w-full flex items-center justify-between rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 p-3 text-xs font-semibold text-cyan-300 transition"
              >
                <span>Run OR-Tools Grid Optimization</span>
                <ArrowRight className="h-4 w-4" />
              </button>

              <button
                onClick={() => onNavigate("ai_copilot")}
                className="w-full flex items-center justify-between rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 p-3 text-xs font-semibold text-indigo-300 transition"
              >
                <span>Open Operator Copilot (Bob MCP)</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="border-t border-slate-800 pt-4">
            <button
              onClick={handleGenerateBrief}
              disabled={generatingBrief}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 py-2.5 text-xs font-bold text-white shadow-lg shadow-cyan-900/30 transition active:scale-95 disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              <span>{generatingBrief ? "Synthesizing 8-Part Brief..." : "Generate 8-Section Operator Brief"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Operator Brief Viewer (if generated) */}
      {brief && <OperatorBriefViewer brief={brief} />}
    </div>
  );
};
