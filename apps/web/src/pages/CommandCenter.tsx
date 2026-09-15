import React, { useState, useEffect } from "react";
import {
  Activity,
  Zap,
  Sun,
  Battery,
  FileText,
  ArrowRight,
} from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { OperationalSnapshot, OperatorBrief, DemandForecast } from "../services/types.ts";
import { MetricCard } from "../components/MetricCard.tsx";
import { AlertBanner } from "../components/AlertBanner.tsx";
import { TimeSeriesChart, CHART_PALETTE } from "../components/TimeSeriesChart.tsx";
import { OperatorBriefViewer } from "../components/OperatorBriefViewer.tsx";

export interface CommandCenterProps {
  onNavigate: (pageId: any) => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({ onNavigate }) => {
  const [snapshot, setSnapshot] = useState<OperationalSnapshot | null>(null);
  const [forecast, setForecast] = useState<DemandForecast | null>(null);
  const [brief, setBrief] = useState<OperatorBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingBrief, setGeneratingBrief] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [snapData, fcData] = await Promise.all([
        ApiClient.getOperationalSnapshot(),
        ApiClient.getDemandForecast("NL_LIANDER_SUB_01", 60).catch(() => null),
      ]);
      setSnapshot(snapData);
      setForecast(fcData);
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
      const currentMw = snapshot.currentDemand?.valueMw;
      const forecastMw = snapshot.forecastDemand?.horizon15mMw ?? forecast?.points[0]?.demandMw;
      const solarMw = snapshot.renewableGeneration?.solarMw;
      const windMw = snapshot.renewableGeneration?.windMw;
      const socPercent = snapshot.availableFlexibleResources?.batteryCurrentSocPercent;
      const curtailmentMw = snapshot.curtailment?.currentCurtailmentMw;
      const stressVal = snapshot.gridStress?.stressIndex;

      if (currentMw === undefined || solarMw === undefined || windMw === undefined || socPercent === undefined || stressVal === undefined) {
        throw new Error("Cannot generate incident brief because backend grid telemetry is unavailable");
      }

      const briefData = await ApiClient.generateOperatorBrief({
        currentGridState: {
          timestamp: snapshot.timestamp,
          zoneId: snapshot.zoneId,
          demandMw: currentMw,
          solarGenerationMw: solarMw,
          windGenerationMw: windMw,
          batterySocPercent: socPercent,
          curtailmentMw: curtailmentMw ?? 0.0,
          gridStressIndex: stressVal,
        },
        demandForecast: {
          zoneId: snapshot.zoneId,
          generatedAt: snapshot.timestamp,
          horizonMinutes: 15,
          points: [{ timestamp: snapshot.timestamp, demandMw: forecastMw ?? currentMw }],
          spikeRisk: {
            level: snapshot.forecastDemand?.spikeRiskLevel || "normal",
            probability: snapshot.forecastDemand?.spikeProbability ?? 0.0,
            predictedPeakMw: forecastMw ?? currentMw,
          },
          modelVersion: forecast?.modelVersion || "lightgbm-v1",
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
        <div className="flex flex-col items-center gap-3 text-secondary">
          <Activity className="h-8 w-8 animate-spin text-copper" />
          <span className="text-xs font-mono">Aggregating telemetry from microservices...</span>
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

  // Real backend metrics mapping without hardcoded demo fallbacks
  const currentDemandVal = snapshot?.currentDemand?.status === "available" ? snapshot.currentDemand.valueMw : undefined;
  const forecast15mVal = snapshot?.forecastDemand?.status === "available" ? snapshot.forecastDemand.horizon15mMw : forecast?.points[0]?.demandMw;
  const renewableTotalVal = snapshot?.renewableGeneration?.status === "available" ? snapshot.renewableGeneration.totalMw : undefined;
  const solarVal = snapshot?.renewableGeneration?.status === "available" ? snapshot.renewableGeneration.solarMw : undefined;
  const windVal = snapshot?.renewableGeneration?.status === "available" ? snapshot.renewableGeneration.windMw : undefined;
  const socVal = snapshot?.availableFlexibleResources?.status === "available" ? snapshot.availableFlexibleResources.batteryCurrentSocPercent : undefined;
  const batteryCap = snapshot?.availableFlexibleResources?.batteryCapacityMwh;
  const stressVal = snapshot?.gridStress?.status === "available" ? snapshot.gridStress.stressIndex : undefined;
  const stressPercent = stressVal !== undefined ? Math.round(stressVal * 100) : undefined;
  const stressStatus = stressPercent !== undefined ? (stressPercent > 75 ? "critical" : stressPercent > 50 ? "warning" : "nominal") : "nominal";
  const stressLevel = snapshot?.gridStress?.severity ?? snapshot?.gridStress?.level ?? (stressVal !== undefined ? (stressVal > 0.7 ? "warning" : "normal") : "unavailable");

  const anomalyCount = snapshot?.renewableAnomalies?.status === "available" ? snapshot.renewableAnomalies.count : 0;
  const hasActiveAnomalies = (anomalyCount ?? 0) > 0;
  const spikeRiskLevel = snapshot?.forecastDemand?.spikeRiskLevel ?? forecast?.spikeRisk.level ?? "normal";
  const spikeProb = snapshot?.forecastDemand?.spikeProbability ?? forecast?.spikeRisk.probability ?? 0.0;

  // Build trend chart dynamically from real forecast API points
  const forecastPoints = forecast?.points || [];
  const trendData = forecastPoints.map((pt, idx) => {
    const timeStr = new Date(pt.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const demand = pt.demandMw;
    const ren = renewableTotalVal ?? 0;
    const netLoad = Math.max(0, demand - ren);
    return {
      time: idx === 0 ? `${timeStr} (Live)` : `${timeStr} (F)`,
      demand: Math.round(demand * 10) / 10,
      renewable: Math.round(ren * 10) / 10,
      netLoad: Math.round(netLoad * 10) / 10,
    };
  });

  return (
    <div className="space-y-6 p-6">
      {/* Top Banner Alarms */}
      {hasActiveAnomalies && (
        <AlertBanner
          type="warning"
          title="Renewable Underproduction Detected"
          message={`${anomalyCount} asset(s) flagged by Isolation Forest. Diagnostic root cause analysis available.`}
          actionText="Inspect Assets"
          onAction={() => onNavigate("renewable_assets")}
        />
      )}

      {spikeRiskLevel !== "normal" && (
        <AlertBanner
          type="critical"
          title="Imminent Demand Spike Warning"
          message={`XGBoost classifier predicts a demand spike with ${(spikeProb * 100).toFixed(0)}% probability in the next 15 minutes.`}
          actionText="View Forecast"
          onAction={() => onNavigate("demand_forecast")}
        />
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Current Demand"
          value={currentDemandVal !== undefined ? currentDemandVal.toFixed(1) : "Unavailable"}
          unit={currentDemandVal !== undefined ? "MW" : undefined}
          subtitle={forecast15mVal !== undefined ? `Forecast +15m: ${forecast15mVal.toFixed(1)} MW` : "Forecast unavailable"}
          icon={Zap}
          status="nominal"
        />

        <MetricCard
          title="Renewable Output"
          value={renewableTotalVal !== undefined ? renewableTotalVal.toFixed(1) : "Unavailable"}
          unit={renewableTotalVal !== undefined ? "MW" : undefined}
          subtitle={solarVal !== undefined && windVal !== undefined ? `Solar: ${solarVal.toFixed(1)} MW | Wind: ${windVal.toFixed(1)} MW` : "Breakdown unavailable"}
          icon={Sun}
          change={hasActiveAnomalies ? "Anomaly Alert" : "Nominal"}
          changeType={hasActiveAnomalies ? "warning" : "positive"}
          status={hasActiveAnomalies ? "warning" : "nominal"}
        />

        <MetricCard
          title="Storage SOC"
          value={socVal !== undefined ? socVal.toFixed(0) : "Unavailable"}
          unit={socVal !== undefined ? "%" : undefined}
          subtitle={batteryCap ? `Capacity: ${batteryCap} MWh` : "Resource capacity"}
          icon={Battery}
          status="nominal"
        />

        <MetricCard
          title="Grid Stress Index"
          value={stressVal !== undefined ? stressVal.toFixed(2) : "Unavailable"}
          unit={stressVal !== undefined ? "/ 1.0" : undefined}
          subtitle={`Level: ${stressLevel.toUpperCase()}`}
          icon={Activity}
          change={stressPercent !== undefined && stressPercent > 70 ? "High Stress" : "Stable"}
          changeType={stressPercent !== undefined && stressPercent > 70 ? "negative" : "positive"}
          status={stressStatus}
        />
      </div>

      {/* Main Charts & Quick Action Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {trendData.length > 0 ? (
            <TimeSeriesChart
              title="Grid Load & Renewable Generation Balance"
              subtitle="15-minute historical SCADA telemetry vs. next-horizon LightGBM projection"
              data={trendData}
              series={[
                { key: "demand", name: "Total Demand (MW)", color: CHART_PALETTE[0], fillOpacity: 0.15 },
                { key: "renewable", name: "Renewable Generation (MW)", color: CHART_PALETTE[1], fillOpacity: 0.2 },
                { key: "netLoad", name: "Net Deficit / Load (MW)", color: CHART_PALETTE[3], type: "line", strokeDasharray: "4 4" },
              ]}
            />
          ) : (
            <div className="flex h-72 items-center justify-center rounded-md border border-border bg-surface p-6 text-center text-secondary text-xs">
              No telemetry time-series points available from backend service.
            </div>
          )}
        </div>

        {/* Quick Operations & Copilot Card */}
        <div className="flex flex-col justify-between rounded-md p-5 border border-border bg-surface shadow-sm">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="flex h-2.5 w-2.5 rounded-full bg-copper animate-voice-pulse" />
              <h3 className="text-xs font-bold text-primary tracking-wide">
                Autonomous Dispatch & Incident Brief
              </h3>
            </div>
            <p className="text-xs text-secondary leading-relaxed mb-4">
              Trigger OR-Tools Mixed-Integer Linear Programming solver to compute optimal BESS discharge, or synthesize the 8-part operator incident brief via watsonx.ai / Bob.
            </p>

            <div className="space-y-2 mb-4">
              <button
                onClick={() => onNavigate("optimization_center")}
                className="w-full flex items-center justify-between rounded-md bg-copper-subtle hover:bg-copper hover:text-white border border-copper/30 p-3 text-xs font-semibold text-copper transition-instant"
              >
                <span>Run OR-Tools Grid Optimization</span>
                <ArrowRight className="h-4 w-4" />
              </button>

              <button
                onClick={() => onNavigate("ai_copilot")}
                className="w-full flex items-center justify-between rounded-md bg-surface-muted hover:bg-surface border border-border p-3 text-xs font-semibold text-primary transition-instant"
              >
                <span>Open Operator Copilot (Bob MCP)</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="border-t border-border pt-4">
            <button
              onClick={handleGenerateBrief}
              disabled={generatingBrief}
              className="w-full flex items-center justify-center gap-2 rounded-md bg-copper hover:bg-copper-hover py-2.5 text-xs font-bold text-white shadow-sm transition-fast active:scale-95 disabled:opacity-50"
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
