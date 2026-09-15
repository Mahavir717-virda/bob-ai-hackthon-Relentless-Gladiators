import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

export const CHART_PALETTE = [
  "#B5622E", // Signal Copper
  "#1B8A8A", // Deep Cyan-Teal
  "#7C4A8C", // Plum
  "#C98A2E", // Amber Gold
  "#4F6B52", // Sage
  "#8C6A3F", // Bronze
];

export interface DataSeries {
  key: string;
  name: string;
  color: string;
  type?: "line" | "area";
  fillOpacity?: number;
  strokeDasharray?: string;
}

export interface TimeSeriesChartProps {
  title: string;
  subtitle?: string;
  data: Array<Record<string, any>>;
  series: DataSeries[];
  xAxisKey?: string;
  yAxisUnit?: string;
  height?: number;
  confidenceEnvelope?: {
    lowerKey: string;
    upperKey: string;
    color?: string;
  };
}

export const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({
  title,
  subtitle,
  data,
  series,
  xAxisKey = "time",
  yAxisUnit = "MW",
  height = 280,
  confidenceEnvelope,
}) => {
  return (
    <div className="rounded-md p-5 border border-border bg-surface shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold text-primary tracking-wide">{title}</h3>
          {subtitle && <p className="text-[11px] text-secondary mt-0.5">{subtitle}</p>}
        </div>
        <span className="rounded bg-surface-muted border border-border px-2 py-0.5 text-xs font-metric text-copper font-medium">
          Unit: {yAxisUnit}
        </span>
      </div>

      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              {series.map((s, idx) => {
                const color = s.color || CHART_PALETTE[idx % CHART_PALETTE.length];
                return (
                  <linearGradient key={`grad-${s.key}`} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={s.fillOpacity ?? 0.3} />
                    <stop offset="95%" stopColor={color} stopOpacity={0.0} />
                  </linearGradient>
                );
              })}
              {confidenceEnvelope && (
                <linearGradient id="grad-confidence" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={confidenceEnvelope.color || "#1B8A8A"} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={confidenceEnvelope.color || "#1B8A8A"} stopOpacity={0.05} />
                </linearGradient>
              )}
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" vertical={false} />

            <XAxis
              dataKey={xAxisKey}
              stroke="var(--text-tertiary)"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "var(--border-default)" }}
            />

            <YAxis
              stroke="var(--text-tertiary)"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "var(--border-default)" }}
              tickFormatter={(v) => `${v}`}
            />

            <Tooltip
              contentStyle={{
                backgroundColor: "var(--bg-surface)",
                borderColor: "var(--border-default)",
                borderRadius: "6px",
                fontSize: "12px",
                color: "var(--text-primary)",
                boxShadow: "0 4px 12px rgba(0, 0, 0, 0.25)",
              }}
              labelStyle={{ color: "var(--text-secondary)", fontWeight: 600, marginBottom: "4px" }}
            />

            <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />

            {confidenceEnvelope && (
              <Area
                type="monotone"
                dataKey={confidenceEnvelope.upperKey}
                stroke="transparent"
                fill="url(#grad-confidence)"
                name="Confidence Bound (80%)"
              />
            )}

            {series.map((s, idx) => {
              const color = s.color || CHART_PALETTE[idx % CHART_PALETTE.length];
              return s.type === "line" ? (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.name}
                  stroke={color}
                  strokeWidth={2}
                  strokeDasharray={s.strokeDasharray}
                  dot={{ r: 2, fill: color }}
                  activeDot={{ r: 4 }}
                />
              ) : (
                <Area
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.name}
                  stroke={color}
                  strokeWidth={2}
                  fill={`url(#grad-${s.key})`}
                />
              );
            })}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
