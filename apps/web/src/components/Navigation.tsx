import React from "react";
import {
  LayoutDashboard,
  TrendingUp,
  Sun,
  Zap,
  Bot,
  PlaySquare,
} from "lucide-react";

export type NavPageId =
  | "command_center"
  | "demand_forecast"
  | "renewable_assets"
  | "optimization_center"
  | "ai_copilot"
  | "scenario_simulator";

export interface NavigationProps {
  activePage: NavPageId;
  onPageSelect: (page: NavPageId) => void;
  anomaliesCount?: number;
}

export const Navigation: React.FC<NavigationProps> = ({
  activePage,
  onPageSelect,
  anomaliesCount = 0,
}) => {
  const navItems = [
    {
      id: "command_center" as NavPageId,
      label: "Command Center",
      icon: LayoutDashboard,
    },
    {
      id: "demand_forecast" as NavPageId,
      label: "Demand Forecast",
      icon: TrendingUp,
    },
    {
      id: "renewable_assets" as NavPageId,
      label: "Renewable Assets",
      icon: Sun,
      badge: anomaliesCount > 0 ? `${anomaliesCount} alert` : undefined,
      badgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    },
    {
      id: "optimization_center" as NavPageId,
      label: "Optimization Center",
      icon: Zap,
    },
    {
      id: "ai_copilot" as NavPageId,
      label: "AI Copilot",
      icon: Bot,
      badge: "Bob MCP",
      badgeColor: "bg-indigo-500/20 text-indigo-300 border-indigo-500/40",
    },
    {
      id: "scenario_simulator" as NavPageId,
      label: "Scenario Simulator",
      icon: PlaySquare,
    },
  ];

  return (
    <nav className="border-b border-slate-800/80 bg-slate-950/60 px-6 backdrop-blur-md">
      <div className="flex gap-1 overflow-x-auto py-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onPageSelect(item.id)}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition whitespace-nowrap ${
                isActive
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent"
              }`}
            >
              <Icon className={`h-4 w-4 ${isActive ? "text-cyan-400" : "text-slate-400"}`} />
              <span>{item.label}</span>
              {item.badge && (
                <span
                  className={`rounded px-1.5 py-0.2 text-[10px] font-mono border ${item.badgeColor}`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
