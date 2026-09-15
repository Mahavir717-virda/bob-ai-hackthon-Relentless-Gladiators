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
  loading?: boolean;
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
  loading = false,
}) => {
  const statusBorder =
    status === "critical"
      ? "border-semantic-error/40 hover:border-semantic-error/70"
      : status === "warning"
      ? "border-semantic-warning/40 hover:border-semantic-warning/70"
      : "border-border hover:border-copper/40";

  return (
    <div
      className={`relative overflow-hidden rounded-md p-5 bg-surface border ${statusBorder} transition-fast shadow-sm`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-secondary">
          {title}
        </span>
        {Icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-surface-muted text-copper border border-border">
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        {loading ? (
          <div className="h-9 w-28 skeleton rounded" />
        ) : (
          <span className="font-metric text-3xl font-semibold tracking-tight text-primary">
            {value}
          </span>
        )}
        {unit && !loading && <span className="text-xs font-medium text-secondary">{unit}</span>}
      </div>

      {(change || subtitle) && (
        <div className="mt-2.5 flex items-center justify-between text-xs">
          {subtitle && <span className="text-secondary">{subtitle}</span>}
          {change && (
            <span
              className={`font-semibold font-metric ${
                changeType === "positive"
                  ? "text-semantic-success"
                  : changeType === "negative"
                  ? "text-semantic-error"
                  : changeType === "warning"
                  ? "text-semantic-warning"
                  : "text-secondary"
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
