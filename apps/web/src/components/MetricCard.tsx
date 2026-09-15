import React from "react";
import { LucideIcon } from "lucide-react";

export interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  change?: string;
  changeType?: "positive" | "negative" | "neutral" | "warning";
  subtitle?: string;
  icon?: LucideIcon;
  status?: "nominal" | "warning" | "critical";
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  change,
  changeType = "neutral",
  subtitle,
  icon: Icon,
  status = "nominal",
}) => {
  const statusBorder =
    status === "critical"
      ? "border-rose-500/40 hover:border-rose-500/70"
      : status === "warning"
      ? "border-amber-500/40 hover:border-amber-500/70"
      : "border-slate-800/80 hover:border-cyan-500/40";

  const statusGlow =
    status === "critical"
      ? "from-rose-950/20"
      : status === "warning"
      ? "from-amber-950/20"
      : "from-cyan-950/15";

  return (
    <div
      className={`glass-panel relative overflow-hidden rounded-xl p-5 transition-all duration-300 hover:shadow-lg bg-gradient-to-b ${statusGlow} to-transparent border ${statusBorder}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
          {title}
        </span>
        {Icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800/80 text-cyan-400">
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight text-white font-mono">
          {value}
        </span>
        {unit && <span className="text-sm font-medium text-slate-400">{unit}</span>}
      </div>

      {(change || subtitle) && (
        <div className="mt-2 flex items-center justify-between text-xs">
          {subtitle && <span className="text-slate-400">{subtitle}</span>}
          {change && (
            <span
              className={`font-semibold ${
                changeType === "positive"
                  ? "text-emerald-400"
                  : changeType === "negative"
                  ? "text-rose-400"
                  : changeType === "warning"
                  ? "text-amber-400"
                  : "text-slate-400"
              }`}
            >
              {change}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
