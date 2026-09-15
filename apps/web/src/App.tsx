import React, { useState, useEffect } from "react";
import { Header } from "./components/Header.tsx";
import { Navigation, type NavPageId } from "./components/Navigation.tsx";
import { CommandCenter } from "./pages/CommandCenter.tsx";
import { DemandForecastPage } from "./pages/DemandForecast.tsx";
import { RenewableAssetsPage } from "./pages/RenewableAssets.tsx";
import { OptimizationCenterPage } from "./pages/OptimizationCenter.tsx";
import { AICopilotPage } from "./pages/AICopilot.tsx";
import { ScenarioSimulatorPage } from "./pages/ScenarioSimulator.tsx";
import { ApiClient } from "./services/api-client.ts";

export function App() {
  const [activePage, setActivePage] = useState<NavPageId>("command_center");
  const [lastUpdated, setLastUpdated] = useState<string>(
    new Date().toISOString(),
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [anomaliesCount, setAnomaliesCount] = useState(0);
  const [systemHealth, setSystemHealth] = useState<
    "healthy" | "degraded" | "offline"
  >("healthy");

  const syncSystem = async () => {
    try {
      setIsRefreshing(true);
      const [health, anomalies] = await Promise.allSettled([
        ApiClient.checkHealth(),
        ApiClient.getRenewableAnomalies(),
      ]);

      if (health.status === "fulfilled") {
        setSystemHealth(
          health.value.status === "healthy" ? "healthy" : "degraded",
        );
      } else {
        setSystemHealth("offline");
      }

      if (anomalies.status === "fulfilled") {
        setAnomaliesCount(anomalies.value.length);
      }

      setLastUpdated(new Date().toISOString());
    } catch {
      setSystemHealth("offline");
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    syncSystem();
    const interval = setInterval(syncSystem, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col font-sans transition-colors duration-200">
      {/* Shell Header */}
      <Header
        lastUpdated={lastUpdated}
        onRefresh={syncSystem}
        isRefreshing={isRefreshing}
        systemHealth={systemHealth}
      />

      {/* Top Nav Tabs */}
      <Navigation
        activePage={activePage}
        onPageSelect={setActivePage}
        anomaliesCount={anomaliesCount}
      />

      {/* Main Content Area */}
      <main className="flex-1 overflow-x-hidden">
        {activePage === "command_center" && (
          <CommandCenter onNavigate={(page) => setActivePage(page)} />
        )}
        {activePage === "demand_forecast" && <DemandForecastPage />}
        {activePage === "renewable_assets" && (
          <RenewableAssetsPage
            onNavigateCopilot={() => setActivePage("ai_copilot")}
          />
        )}
        {activePage === "optimization_center" && <OptimizationCenterPage />}
        {activePage === "ai_copilot" && <AICopilotPage />}
        {activePage === "scenario_simulator" && <ScenarioSimulatorPage />}
      </main>

      {/* Minimal Footer with Invariant Rules reminder */}
      <footer className="border-t border-border bg-surface-muted/80 px-6 py-3 text-[11px] text-secondary flex flex-col sm:flex-row items-center justify-between gap-2 transition-colors duration-200">
        <div>
          GridPilot AI &bull; Relentless Gladiators &bull; IBM Bob AI Hackathon
          2026
        </div>
        <div className="flex items-center gap-3 font-metric text-[10px] text-secondary">
          <span>RULE A: ML PREDICTS</span>
          <span>&bull;</span>
          <span>RULE B: OPTIMIZER DECIDES</span>
          <span>&bull;</span>
          <span>RULE C: LLM COMMUNICATES</span>
          <span>&bull;</span>
          <span>RULE D: FRONTEND PRESENTS</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
