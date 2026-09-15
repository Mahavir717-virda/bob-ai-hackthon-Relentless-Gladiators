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
    <div className="glass-panel rounded-xl p-5 border border-slate-800/80">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-white tracking-wide">{title}</h3>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs font-mono text-cyan-400">
          Unit: {yAxisUnit}
        </span>
      </div>

      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              {series.map((s) => (
                <linearGradient key={`grad-${s.key}`} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={s.color} stopOpacity={s.fillOpacity ?? 0.3} />
                  <stop offset="95%" stopColor={s.color} stopOpacity={0.0} />
                </linearGradient>
              ))}
              {confidenceEnvelope && (
                <linearGradient id="grad-confidence" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={confidenceEnvelope.color || "#06b6d4"} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={confidenceEnvelope.color || "#06b6d4"} stopOpacity={0.05} />
                </linearGradient>
              )}
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />

            <XAxis
              dataKey={xAxisKey}
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "#1e293b" }}
            />

            <YAxis
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "#1e293b" }}
              tickFormatter={(v) => `${v}`}
            />

            <Tooltip
              contentStyle={{
                backgroundColor: "#0f172a",
                borderColor: "#334155",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#f8fafc",
                boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
              }}
              labelStyle={{ color: "#94a3b8", fontWeight: 600, marginBottom: "4px" }}
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

            {series.map((s) =>
              s.type === "line" ? (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.name}
                  stroke={s.color}
                  strokeWidth={2}
                  strokeDasharray={s.strokeDasharray}
                  dot={{ r: 2, fill: s.color }}
                  activeDot={{ r: 4 }}
                />
              ) : (
                <Area
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.name}
                  stroke={s.color}
                  strokeWidth={2}
                  fill={`url(#grad-${s.key})`}
                />
              )
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
