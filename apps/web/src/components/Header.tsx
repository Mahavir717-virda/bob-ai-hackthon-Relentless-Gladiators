import React from "react";
import { Activity, Shield, Zap, RefreshCw } from "lucide-react";

export interface HeaderProps {
  lastUpdated?: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  activeZoneId?: string;
  systemHealth?: "healthy" | "degraded" | "offline";
}

export const Header: React.FC<HeaderProps> = ({
  lastUpdated,
  onRefresh,
  isRefreshing,
  activeZoneId = "NL_LIANDER_SUB_01",
  systemHealth = "healthy",
}) => {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#090d16]/90 backdrop-blur-md px-6 py-3.5">
      <div className="flex items-center justify-between">
        {/* Left: Brand & Architecture Invariant Badge */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 shadow-md shadow-cyan-500/20">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-extrabold tracking-tight text-white">
                  GridPilot <span className="text-cyan-400">AI</span>
                </span>
                <span className="rounded bg-cyan-950 px-1.5 py-0.5 text-[10px] font-bold font-mono text-cyan-400 border border-cyan-800/60">
                  U2 v1.0
                </span>
              </div>
              <span className="text-[11px] text-slate-400 font-medium">
                Autonomous Grid Load & Renewable Intelligence
              </span>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-1.5 rounded-full bg-slate-900/80 border border-slate-800 px-3 py-1 text-xs text-slate-300">
            <Shield className="h-3.5 w-3.5 text-cyan-400" />
            <span>Active Substation:</span>
            <span className="font-mono font-semibold text-white">{activeZoneId}</span>
          </div>
        </div>

        {/* Right: Live Connection Indicator, Refresh Button & Time */}
        <div className="flex items-center gap-3.5">
          <div className="flex items-center gap-2 rounded-lg bg-slate-900/80 border border-slate-800/80 px-3 py-1.5 text-xs">
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  systemHealth === "healthy" ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  systemHealth === "healthy" ? "bg-emerald-500" : "bg-amber-500"
                }`}
              />
            </span>
            <span className="font-mono text-slate-300 capitalize">{systemHealth}</span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-400 font-mono text-[11px]">
              {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "--:--:--"}
            </span>
          </div>

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 px-3 py-1.5 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/20 active:scale-95 transition disabled:opacity-50"
              title="Refresh telemetry snapshot"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Sync</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
