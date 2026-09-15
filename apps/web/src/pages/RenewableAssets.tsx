import React, { useState, useEffect } from "react";
import { Sun, Wind, CloudSun, AlertTriangle, ShieldCheck, Thermometer, Gauge } from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { RenewableStatus } from "../services/types.ts";
import { MetricCard } from "../components/MetricCard.tsx";
import { AlertBanner } from "../components/AlertBanner.tsx";
import { AssetStatusBadge } from "../components/AssetStatusBadge.tsx";

export interface RenewableAssetsProps {
  onNavigateCopilot?: (assetId: string) => void;
}

export const RenewableAssetsPage: React.FC<RenewableAssetsProps> = ({ onNavigateCopilot }) => {
  const [assets, setAssets] = useState<RenewableStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAssets = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await ApiClient.getRenewableStatuses();
      setAssets(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load renewable assets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssets();
  }, []);

  const totalActual = assets.reduce((sum, a) => sum + a.actualMw, 0);
  const totalExpected = assets.reduce((sum, a) => sum + a.expectedMw, 0);
  const totalSolar = assets.filter((a) => a.assetType === "solar").reduce((sum, a) => sum + a.actualMw, 0);
  const totalWind = assets.filter((a) => a.assetType === "wind").reduce((sum, a) => sum + a.actualMw, 0);
  const anomalies = assets.filter((a) => a.anomaly);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Sun className="h-6 w-6 text-amber-400" />
            Renewable Asset Intelligence & Anomaly Diagnostics
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time solar PV & wind turbine health | Isolation Forest anomaly detection & SHAP attribution
          </p>
        </div>

        <button
          onClick={loadAssets}
          className="rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 transition"
        >
          Refresh Telemetry
        </button>
      </div>

      {/* Top Anomalies Banner */}
      {anomalies.length > 0 && (
        <AlertBanner
          type="warning"
          title={`${anomalies.length} Renewable Asset Anomaly Detected`}
          message={`Isolation forest detected generation shortfall below expected envelope for ${anomalies.map((a) => a.assetId).join(", ")}. Diagnostic SHAP feature attribution indicates physical atmospheric or mechanical causes.`}
          actionText="Consult Copilot"
          onAction={() => onNavigateCopilot && onNavigateCopilot(anomalies[0].assetId)}
        />
      )}

      {/* Key Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Renewable Generation"
          value={totalActual.toFixed(1)}
          unit="MW"
          subtitle={`Expected: ${totalExpected.toFixed(1)} MW (${Math.round((totalActual / (totalExpected || 1)) * 100)}% capacity)`}
          icon={Sun}
          status="nominal"
        />

        <MetricCard
          title="Solar PV Output"
          value={totalSolar.toFixed(1)}
          unit="MW"
          subtitle="GHI: 640 W/m² | Cloud Cover: 28%"
          icon={CloudSun}
          status="nominal"
        />

        <MetricCard
          title="Wind Turbine Output"
          value={totalWind.toFixed(1)}
          unit="MW"
          subtitle="Wind Speed: 6.8 m/s"
          icon={Wind}
          status="nominal"
        />

        <MetricCard
          title="Active Anomalies"
          value={anomalies.length}
          subtitle={anomalies.length > 0 ? "Underperforming assets" : "All assets nominal"}
          icon={AlertTriangle}
          change={anomalies.length > 0 ? "Underperformance" : "All Nominal"}
          changeType={anomalies.length > 0 ? "warning" : "positive"}
          status={anomalies.length > 0 ? "warning" : "nominal"}
        />
      </div>

      {/* Asset Cards Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white tracking-wide">
            Connected Solar & Wind Power Stations ({assets.length})
          </h3>
          <span className="text-xs text-slate-400">
            Click 'Diagnose with Copilot' for automated root cause analysis
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {assets.map((asset) => (
            <AssetStatusBadge
              key={asset.assetId}
              asset={asset}
              onDiagnose={onNavigateCopilot}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
