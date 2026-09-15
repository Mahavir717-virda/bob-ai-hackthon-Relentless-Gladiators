import React, { useState, useEffect } from "react";
import { Sun, Wind, CloudSun, AlertTriangle } from "lucide-react";
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

  const totalActual = assets.reduce((sum, a) => sum + (a.actualMw || 0), 0);
  const totalExpected = assets.reduce((sum, a) => sum + (a.expectedMw || 0), 0);
  const solarAssets = assets.filter((a) => a.assetType === "solar");
  const windAssets = assets.filter((a) => a.assetType === "wind");
  const totalSolar = solarAssets.reduce((sum, a) => sum + (a.actualMw || 0), 0);
  const totalWind = windAssets.reduce((sum, a) => sum + (a.actualMw || 0), 0);
  const anomalies = assets.filter((a) => a.anomaly);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-primary flex items-center gap-2">
            <Sun className="h-5 w-5 text-spectrum-amber" />
            Renewable Asset Intelligence & Anomaly Diagnostics
          </h2>
          <p className="text-xs text-secondary mt-0.5">
            Real-time solar PV & wind turbine health | Isolation Forest anomaly detection & SHAP attribution
          </p>
        </div>

        <button
          onClick={loadAssets}
          className="rounded-md bg-copper text-white hover:bg-copper-hover px-3.5 py-1.5 text-xs font-semibold shadow-sm transition-fast"
        >
          Refresh Telemetry
        </button>
      </div>

      {/* Error State */}
      {error && (
        <AlertBanner
          type="critical"
          title="Renewable Intelligence API Error"
          message={error}
          actionText="Retry"
          onAction={loadAssets}
        />
      )}

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
          value={assets.length > 0 ? totalActual.toFixed(1) : "Unavailable"}
          unit={assets.length > 0 ? "MW" : undefined}
          subtitle={assets.length > 0 ? `Expected: ${totalExpected.toFixed(1)} MW (${Math.round((totalActual / (totalExpected || 1)) * 100)}% capacity)` : "Telemetry unavailable"}
          icon={Sun}
          status="nominal"
        />

        <MetricCard
          title="Solar PV Output"
          value={solarAssets.length > 0 ? totalSolar.toFixed(1) : "Unavailable"}
          unit={solarAssets.length > 0 ? "MW" : undefined}
          subtitle={`${solarAssets.length} Solar Generating Stations Active`}
          icon={CloudSun}
          status="nominal"
        />

        <MetricCard
          title="Wind Turbine Output"
          value={windAssets.length > 0 ? totalWind.toFixed(1) : "Unavailable"}
          unit={windAssets.length > 0 ? "MW" : undefined}
          subtitle={`${windAssets.length} Wind Turbines Active`}
          icon={Wind}
          status="nominal"
        />

        <MetricCard
          title="Active Anomalies"
          value={assets.length > 0 ? anomalies.length : "Unavailable"}
          subtitle={assets.length > 0 ? (anomalies.length > 0 ? "Underperforming assets detected" : "All assets nominal") : "Anomaly detector offline"}
          icon={AlertTriangle}
          change={anomalies.length > 0 ? "Underperformance" : "All Nominal"}
          changeType={anomalies.length > 0 ? "warning" : "positive"}
          status={anomalies.length > 0 ? "warning" : "nominal"}
        />
      </div>

      {/* Asset Cards Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold text-primary tracking-wide">
            Connected Solar & Wind Power Stations ({assets.length})
          </h3>
          <span className="text-xs text-secondary">
            Click 'Diagnose with Copilot' for automated root cause analysis
          </span>
        </div>

        {assets.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {assets.map((asset) => (
              <AssetStatusBadge
                key={asset.assetId}
                asset={asset}
                onDiagnose={onNavigateCopilot}
              />
            ))}
          </div>
        ) : (
          <div className="flex h-48 items-center justify-center rounded-md border border-border bg-surface p-6 text-center text-secondary text-xs">
            No renewable telemetry data currently available.
          </div>
        )}
      </div>
    </div>
  );
};
