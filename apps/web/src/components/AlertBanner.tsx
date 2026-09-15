import React from "react";
import { AlertTriangle, AlertCircle, Info, CheckCircle2 } from "lucide-react";

export interface AlertBannerProps {
  type: "info" | "success" | "warning" | "critical";
  title: string;
  message: string;
  actionText?: string;
  onAction?: () => void;
  timestamp?: string;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({
  type,
  title,
  message,
  actionText,
  onAction,
  timestamp,
}) => {
  const styles = {
    info: {
      bg: "bg-spectrum-radar/10 border-spectrum-radar/30 text-primary",
      icon: Info,
      iconColor: "text-spectrum-radar",
    },
    success: {
      bg: "bg-semantic-success/10 border-semantic-success/30 text-primary",
      icon: CheckCircle2,
      iconColor: "text-semantic-success",
    },
    warning: {
      bg: "bg-semantic-warning/10 border-semantic-warning/30 text-primary",
      icon: AlertTriangle,
      iconColor: "text-semantic-warning",
    },
    critical: {
      bg: "bg-semantic-error/15 border-semantic-error/40 text-primary",
      icon: AlertCircle,
      iconColor: "text-semantic-error animate-pulse",
    },
  }[type];

  const IconComponent = styles.icon;

  return (
    <div className={`flex items-start gap-3 rounded-md border p-4 shadow-sm ${styles.bg}`}>
      <IconComponent className={`h-5 w-5 shrink-0 mt-0.5 ${styles.iconColor}`} />
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold tracking-wide text-primary">{title}</h4>
          {timestamp && (
            <span className="text-xs font-metric text-secondary">
              {new Date(timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs leading-relaxed text-secondary">{message}</p>
      </div>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="shrink-0 rounded-md bg-copper text-white hover:bg-copper-hover px-3 py-1.5 text-xs font-semibold shadow-sm transition-fast active:scale-95"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
