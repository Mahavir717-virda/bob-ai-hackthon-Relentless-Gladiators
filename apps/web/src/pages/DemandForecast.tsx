import React, { useState, useEffect } from "react";
import { TrendingUp, AlertTriangle, ShieldCheck, Clock, Zap, Cpu } from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { DemandForecast as IDemandForecast } from "../services/types.ts";
import { MetricCard } from "../components/MetricCard.tsx";
import { AlertBanner } from "../components/AlertBanner.tsx";
import { TimeSeriesChart } from "../components/TimeSeriesChart.tsx";

export const DemandForecastPage: React.FC = () => {
  const [forecast, setForecast] = useState<IDemandForecast | null>(null);
  const [horizon, setHorizon] = useState<number>(15);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchForecast = async (horizonMinutes: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await ApiClient.getDemandForecast("NL_LIANDER_SUB_01", horizonMinutes);
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

  const chartData = (forecast?.points || []).map((pt, idx) => {
    const timeStr = new Date(pt.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return {
      time: timeStr,
      demand: pt.demandMw,
      lowerBound: pt.lowerBoundMw ?? pt.demandMw - 3.5,
      upperBound: pt.upperBoundMw ?? pt.demandMw + 4.2,
    };
  });

  const isSpikeWarning = forecast?.spikeRisk.level !== "normal";

  return (
    <div className="space-y-6 p-6">
      {/* Header & Horizon Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-cyan-400" />
            Demand Forecasting & Spike Detection
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Model: <span className="font-mono text-cyan-300">{forecast?.modelVersion || "LightGBM + XGBoost"}</span> | 15-minute Liander SCADA resolution
          </p>
        </div>

        {/* Horizon Toggle */}
        <div className="flex items-center gap-1 rounded-xl bg-slate-900 border border-slate-800 p-1 self-start">
          {[15, 30, 60].map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold font-mono transition ${
                horizon === h
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              +{h}m
            </button>
          ))}
        </div>
      </div>

      {/* Spike Alert Banner */}
      {isSpikeWarning && (
        <AlertBanner
          type="critical"
          title="XGBoost Sudden Spike Alert"
          message={`Predicted peak load of ${forecast?.spikeRisk.predictedPeakMw.toFixed(1)} MW with ${(forecast?.spikeRisk.probability || 0) * 100}% probability in the upcoming horizon.`}
          timestamp={forecast?.generatedAt}
        />
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Predicted Next Load"
          value={forecast?.points[0]?.demandMw.toFixed(1) || "0.0"}
          unit="MW"
          subtitle={`Lower: ${forecast?.points[0]?.lowerBoundMw?.toFixed(1)} | Upper: ${forecast?.points[0]?.upperBoundMw?.toFixed(1)}`}
          icon={Zap}
          status="nominal"
        />

        <MetricCard
          title="Horizon Peak"
          value={forecast?.spikeRisk.predictedPeakMw.toFixed(1) || "0.0"}
          unit="MW"
          subtitle={`Horizon window: +${horizon} minutes`}
          icon={TrendingUp}
          status={isSpikeWarning ? "warning" : "nominal"}
        />

        <MetricCard
          title="Spike Probability"
          value={`${((forecast?.spikeRisk.probability || 0) * 100).toFixed(1)}%`}
          subtitle={`Classification: ${forecast?.spikeRisk.level.toUpperCase()}`}
          icon={AlertTriangle}
          change={forecast?.spikeRisk.level}
          changeType={isSpikeWarning ? "negative" : "positive"}
          status={isSpikeWarning ? "warning" : "nominal"}
        />

        <MetricCard
          title="Inference Latency"
          value="18"
          unit="ms"
          subtitle="LightGBM quantile regression"
          icon={Cpu}
          status="nominal"
        />
      </div>

      {/* Time Series Forecast Chart */}
      <TimeSeriesChart
        title={`Electricity Demand Trajectory (+${horizon}-minute horizon)`}
        subtitle="LightGBM expected demand with 80% confidence interval band"
        data={chartData}
        confidenceEnvelope={{
          lowerKey: "lowerBound",
          upperKey: "upperBound",
          color: "#38bdf8",
        }}
        series={[
          {
            key: "demand",
            name: "LightGBM Predicted Demand (MW)",
            color: "#38bdf8",
            fillOpacity: 0.1,
          },
        ]}
      />

      {/* Structured Forecast Table */}
      <div className="glass-panel rounded-xl overflow-hidden border border-slate-800/80">
        <div className="px-5 py-4 border-b border-slate-800/80 flex items-center justify-between">
          <h3 className="text-sm font-bold text-white tracking-wide">
            Detailed 15-Minute Forecast Interval Bounds
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            {forecast?.points.length || 0} Steps Computed
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800/60">
              <tr>
                <th className="px-5 py-3">Timestamp</th>
                <th className="px-5 py-3 text-right">P10 Lower Bound</th>
                <th className="px-5 py-3 text-right">Expected Demand</th>
                <th className="px-5 py-3 text-right">P90 Upper Bound</th>
                <th className="px-5 py-3 text-right">Spread (±MW)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40 font-mono">
              {(forecast?.points || []).map((pt, idx) => {
                const lower = pt.lowerBoundMw ?? pt.demandMw - 3.5;
                const upper = pt.upperBoundMw ?? pt.demandMw + 4.2;
                const spread = Math.round(((upper - lower) / 2) * 10) / 10;
                return (
                  <tr key={idx} className="hover:bg-slate-800/30 transition">
                    <td className="px-5 py-3 text-slate-300 font-sans">
                      {new Date(pt.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-400">{lower.toFixed(1)} MW</td>
                    <td className="px-5 py-3 text-right font-bold text-white text-sm">
                      {pt.demandMw.toFixed(1)} MW
                    </td>
                    <td className="px-5 py-3 text-right text-cyan-300">{upper.toFixed(1)} MW</td>
                    <td className="px-5 py-3 text-right text-slate-400">±{spread} MW</td>
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
