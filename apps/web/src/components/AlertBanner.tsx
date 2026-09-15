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
      bg: "bg-cyan-950/30 border-cyan-500/40 text-cyan-200",
      icon: Info,
      iconColor: "text-cyan-400",
    },
    success: {
      bg: "bg-emerald-950/30 border-emerald-500/40 text-emerald-200",
      icon: CheckCircle2,
      iconColor: "text-emerald-400",
    },
    warning: {
      bg: "bg-amber-950/30 border-amber-500/40 text-amber-200",
      icon: AlertTriangle,
      iconColor: "text-amber-400",
    },
    critical: {
      bg: "bg-rose-950/40 border-rose-500/60 text-rose-200",
      icon: AlertCircle,
      iconColor: "text-rose-400 animate-pulse",
    },
  }[type];

  const IconComponent = styles.icon;

  return (
    <div className={`flex items-start gap-3 rounded-xl border p-4 backdrop-blur-md ${styles.bg}`}>
      <IconComponent className={`h-5 w-5 shrink-0 mt-0.5 ${styles.iconColor}`} />
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold tracking-wide text-white">{title}</h4>
          {timestamp && (
            <span className="text-xs font-mono text-slate-400">
              {new Date(timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs leading-relaxed text-slate-300">{message}</p>
      </div>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="shrink-0 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-white/20 active:scale-95"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
