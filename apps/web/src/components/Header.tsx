import React, { useEffect, useState } from "react";
import { Radio, Shield, Zap, RefreshCw, Sun, Moon } from "lucide-react";

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
  const [theme, setTheme] = useState<"dark" | "light">("light");

  useEffect(() => {
    const savedTheme = localStorage.getItem("gridpilot-theme") as "dark" | "light" | null;
    const initialTheme = savedTheme || "light";
    setTheme(initialTheme);
    document.documentElement.setAttribute("data-theme", initialTheme);
    if (initialTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("gridpilot-theme", nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur-md px-6 py-3.5 transition-colors duration-200">
      <div className="flex items-center justify-between">
        {/* Left: Radio Signal Brand Header */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-copper text-white shadow-sm">
              <Radio className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight text-primary">
                  GridPilot <span className="text-copper">AI</span>
                </span>
                <span className="rounded bg-copper-subtle px-1.5 py-0.5 text-[10px] font-bold font-mono text-copper border border-copper/30">
                  SIGNAL U2
                </span>
              </div>
              <span className="text-[11px] text-secondary font-medium">
                Radio, Signal & Transmission Operator Center
              </span>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-1.5 rounded-md bg-surface-muted border border-border px-3 py-1 text-xs text-secondary">
            <Shield className="h-3.5 w-3.5 text-copper" />
            <span>Active Substation:</span>
            <span className="font-mono font-semibold text-primary">{activeZoneId}</span>
          </div>
        </div>

        {/* Right: Live Signal Pulse Indicator, Theme Toggle & Refresh */}
        <div className="flex items-center gap-3">
          {/* Telemetry Status Badge */}
          <div className="flex items-center gap-2 rounded-md bg-surface-muted border border-border px-3 py-1.5 text-xs">
            <span className="relative flex h-2.5 w-2.5 items-center justify-center">
              <span
                className={`animate-voice-pulse absolute inline-flex h-4 w-4 rounded-full ${
                  systemHealth === "healthy"
                    ? "bg-spectrum-teal/40"
                    : systemHealth === "degraded"
                    ? "bg-spectrum-amber/40"
                    : "bg-semantic-error/40"
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  systemHealth === "healthy"
                    ? "bg-spectrum-teal"
                    : systemHealth === "degraded"
                    ? "bg-spectrum-amber"
                    : "bg-semantic-error"
                }`}
              />
            </span>
            <span className="font-mono text-primary capitalize font-medium">{systemHealth}</span>
            <span className="text-tertiary">|</span>
            <span className="font-metric text-secondary text-xs tracking-wide">
              {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "--:--:--"}
            </span>
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-surface-muted text-secondary hover:text-primary hover:border-copper/50 transition-instant"
            title={`Switch to ${theme === "dark" ? "Light Parchment" : "Dark Pine Ink"} theme`}
          >
            {theme === "dark" ? <Sun className="h-4 w-4 text-copper" /> : <Moon className="h-4 w-4 text-copper" />}
          </button>

          {/* Refresh Action */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-1.5 rounded-md bg-copper text-white hover:bg-copper-hover px-3.5 py-1.5 text-xs font-semibold shadow-sm transition-fast active:scale-95 disabled:opacity-50"
              title="Refresh telemetry snapshot"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Sync Signal</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
