import React from "react";
import {
  Radio,
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
      icon: Radio,
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
      badgeColor: "bg-spectrum-amber/15 text-spectrum-amber border-spectrum-amber/30",
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
      badgeColor: "bg-spectrum-tech/15 text-spectrum-tech border-spectrum-tech/30",
    },
    {
      id: "scenario_simulator" as NavPageId,
      label: "Scenario Simulator",
      icon: PlaySquare,
    },
  ];

  return (
    <nav className="border-b border-border bg-surface-muted/60 px-6 backdrop-blur-md transition-colors duration-200">
      <div className="flex gap-1 overflow-x-auto py-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onPageSelect(item.id)}
              className={`relative flex items-center gap-2 rounded-md px-3.5 py-2 text-xs font-semibold transition-fast whitespace-nowrap ${
                isActive
                  ? "bg-copper-subtle text-copper border border-copper/30 shadow-sm"
                  : "text-secondary hover:bg-surface hover:text-primary border border-transparent"
              }`}
            >
              <Icon className={`h-4 w-4 ${isActive ? "text-copper" : "text-tertiary"}`} />
              <span>{item.label}</span>
              {item.badge && (
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-mono border ${item.badgeColor}`}
                >
                  {item.badge}
                </span>
              )}
              {/* Active Bottom Copper Indicator Line */}
              {isActive && (
                <span className="absolute bottom-0 left-2 right-2 h-[2px] bg-copper rounded-full" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
