import React, { useState, useEffect } from "react";
import { TrendingUp, AlertTriangle, Zap, Cpu } from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { DemandForecast as IDemandForecast } from "../services/types.ts";
import { MetricCard } from "../components/MetricCard.tsx";
import { AlertBanner } from "../components/AlertBanner.tsx";
import { TimeSeriesChart, CHART_PALETTE } from "../components/TimeSeriesChart.tsx";

export const DemandForecastPage: React.FC = () => {
  const [forecast, setForecast] = useState<IDemandForecast | null>(null);
  const [horizon, setHorizon] = useState<number>(15);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchForecast = async (horizonMinutes: number) => {
    const startTime = performance.now();
    try {
      setLoading(true);
      setError(null);
      const data = await ApiClient.getDemandForecast("NL_LIANDER_SUB_01", horizonMinutes);
      const duration = Math.round(performance.now() - startTime);
      setLatencyMs(duration);
      setForecast(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load demand forecast");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast(horizon);
  }, [horizon]);

  const chartData = (forecast?.points || []).map((pt) => {
    const timeStr = new Date(pt.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return {
      time: timeStr,
      demand: pt.demandMw,
      lowerBound: pt.lowerBoundMw ?? pt.demandMw,
      upperBound: pt.upperBoundMw ?? pt.demandMw,
    };
  });

  const isSpikeWarning = forecast?.spikeRisk.level !== undefined && forecast.spikeRisk.level !== "normal";

  return (
    <div className="space-y-6 p-6">
      {/* Header & Horizon Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-primary flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-copper" />
            Demand Forecasting & Spike Detection
          </h2>
          <p className="text-xs text-secondary mt-0.5">
            Model: <span className="font-mono text-copper font-medium">{forecast?.modelVersion || "LightGBM + XGBoost"}</span> | 15-minute SCADA resolution
          </p>
        </div>

        {/* Horizon Toggle */}
        <div className="flex items-center gap-1 rounded-md bg-surface-muted border border-border p-1 self-start">
          {[15, 30, 60].map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={`rounded px-3 py-1 text-xs font-semibold font-metric transition-instant ${
                horizon === h
                  ? "bg-copper text-white shadow-sm"
                  : "text-secondary hover:text-primary"
              }`}
            >
              +{h}m
            </button>
          ))}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <AlertBanner
          type="critical"
          title="Demand Forecasting API Error"
          message={error}
          actionText="Retry"
          onAction={() => fetchForecast(horizon)}
        />
      )}

      {/* Spike Alert Banner */}
      {isSpikeWarning && forecast && (
        <AlertBanner
          type="critical"
          title="XGBoost Sudden Spike Alert"
          message={`Predicted peak load of ${forecast.spikeRisk.predictedPeakMw.toFixed(1)} MW with ${((forecast.spikeRisk.probability || 0) * 100).toFixed(0)}% probability in the upcoming horizon.`}
          timestamp={forecast.generatedAt}
        />
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Predicted Next Load"
          value={forecast?.points[0]?.demandMw !== undefined ? forecast.points[0].demandMw.toFixed(1) : "Unavailable"}
          unit={forecast?.points[0]?.demandMw !== undefined ? "MW" : undefined}
          subtitle={
            forecast?.points[0]?.lowerBoundMw !== undefined && forecast?.points[0]?.upperBoundMw !== undefined
              ? `Lower: ${forecast.points[0].lowerBoundMw.toFixed(1)} | Upper: ${forecast.points[0].upperBoundMw.toFixed(1)}`
              : "Quantile bounds available"
          }
          icon={Zap}
          status="nominal"
        />

        <MetricCard
          title="Horizon Peak"
          value={forecast?.spikeRisk.predictedPeakMw !== undefined ? forecast.spikeRisk.predictedPeakMw.toFixed(1) : "Unavailable"}
          unit={forecast?.spikeRisk.predictedPeakMw !== undefined ? "MW" : undefined}
          subtitle={`Horizon window: +${horizon} minutes`}
          icon={TrendingUp}
          status={isSpikeWarning ? "warning" : "nominal"}
        />

        <MetricCard
          title="Spike Probability"
          value={forecast?.spikeRisk.probability !== undefined ? `${(forecast.spikeRisk.probability * 100).toFixed(1)}%` : "Unavailable"}
          subtitle={`Classification: ${forecast?.spikeRisk.level ? forecast.spikeRisk.level.toUpperCase() : "UNAVAILABLE"}`}
          icon={AlertTriangle}
          change={forecast?.spikeRisk.level}
          changeType={isSpikeWarning ? "negative" : "positive"}
          status={isSpikeWarning ? "warning" : "nominal"}
        />

        <MetricCard
          title="Inference Latency"
          value={latencyMs !== null ? latencyMs : "Unavailable"}
          unit={latencyMs !== null ? "ms" : undefined}
          subtitle={`Model: ${forecast?.modelVersion || "lightgbm-v1"}`}
          icon={Cpu}
          status="nominal"
        />
      </div>

      {/* Time Series Forecast Chart */}
      {chartData.length > 0 ? (
        <TimeSeriesChart
          title={`Electricity Demand Trajectory (+${horizon}-minute horizon)`}
          subtitle="LightGBM expected demand with 80% confidence interval band"
          data={chartData}
          confidenceEnvelope={{
            lowerKey: "lowerBound",
            upperKey: "upperBound",
            color: CHART_PALETTE[0],
          }}
          series={[
            {
              key: "demand",
              name: "LightGBM Predicted Demand (MW)",
              color: CHART_PALETTE[0],
              fillOpacity: 0.12,
            },
          ]}
        />
      ) : (
        <div className="flex h-64 items-center justify-center rounded-md border border-border bg-surface p-6 text-center text-secondary text-xs">
          No demand forecast telemetry available.
        </div>
      )}

      {/* Structured Dense Forecast Table */}
      <div className="rounded-md overflow-hidden border border-border bg-surface shadow-sm">
        <div className="px-5 py-3.5 border-b border-border flex items-center justify-between bg-surface-muted/40">
          <h3 className="text-xs font-bold text-primary tracking-wide">
            Detailed 15-Minute Forecast Interval Bounds
          </h3>
          <span className="text-xs text-secondary font-metric">
            {forecast?.points.length || 0} Steps Computed
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-muted/80 text-secondary tracking-wider font-semibold border-b border-border">
              <tr>
                <th className="px-5 py-2.5 text-[11px] uppercase">Timestamp</th>
                <th className="px-5 py-2.5 text-right text-[11px] uppercase">P10 Lower Bound</th>
                <th className="px-5 py-2.5 text-right text-[11px] uppercase">Expected Demand</th>
                <th className="px-5 py-2.5 text-right text-[11px] uppercase">P90 Upper Bound</th>
                <th className="px-5 py-2.5 text-right text-[11px] uppercase">Spread (±MW)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(forecast?.points || []).map((pt, idx) => {
                const lower = pt.lowerBoundMw ?? pt.demandMw;
                const upper = pt.upperBoundMw ?? pt.demandMw;
                const spread = Math.round(((upper - lower) / 2) * 10) / 10;
                return (
                  <tr key={idx} className="hover:bg-surface-muted/40 transition-fast">
                    <td className="px-5 py-3 text-secondary font-metric">
                      {new Date(pt.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="px-5 py-3 text-right text-secondary font-metric">{lower.toFixed(1)} MW</td>
                    <td className="px-5 py-3 text-right font-bold text-primary font-metric text-sm">
                      {pt.demandMw.toFixed(1)} MW
                    </td>
                    <td className="px-5 py-3 text-right text-copper font-metric">{upper.toFixed(1)} MW</td>
                    <td className="px-5 py-3 text-right text-secondary font-metric">±{spread} MW</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
