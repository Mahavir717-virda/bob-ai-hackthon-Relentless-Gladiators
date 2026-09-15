export interface GridStressIndicators {
  stressIndex: number;
  level: "low" | "medium" | "high" | "critical";
  isSpikePredicted: boolean;
  activeAnomaliesCount: number;
}

export interface GridState {
  timestamp: string;
  zoneId: string;
  demandMw: number;
  solarGenerationMw: number;
  windGenerationMw: number;
  batterySocPercent: number;
  curtailmentMw: number;
  gridStressIndex: number;
}

export interface OperationalSnapshot {
  timestamp: string;
  zoneId: string;
  currentDemand: {
    status?: string;
    valueMw?: number;
    zoneId?: string;
    timestamp?: string;
    isAvailable?: boolean;
  };
  forecastDemand: {
    status?: string;
    horizon15mMw?: number;
    horizon30mMw?: number;
    horizon60mMw?: number;
    next15MinMw?: number;
    spikeProbability?: number;
    spikeRiskLevel?: "normal" | "warning" | "severe";
    isAvailable?: boolean;
  };
  renewableGeneration: {
    status?: string;
    solarMw?: number;
    windMw?: number;
    totalMw?: number;
    assetCount?: number;
    isAvailable?: boolean;
  };
  renewableAnomalies: {
    status?: string;
    count?: number;
    anomalies?: any[];
    totalDetected?: number;
    hasActiveAnomalies?: boolean;
    isAvailable?: boolean;
  };
  availableFlexibleResources: {
    status?: string;
    batteryCapacityMwh?: number;
    batteryCurrentSocPercent?: number;
    batteryAvailableDischargeMw?: number;
    flexibleLoadCapacityMw?: number;
    isAvailable?: boolean;
  };
  curtailment: {
    status?: string;
    currentCurtailmentMw?: number;
    curtailmentMitigatedMw?: number;
    curtailedMw?: number;
    economicCostEur?: number;
    isAvailable?: boolean;
  };
  gridStress: {
    status?: string;
    stressIndex?: number;
    frequencyHz?: number;
    severity?: "normal" | "warning" | "critical";
    level?: "low" | "medium" | "high" | "critical";
    isSpikePredicted?: boolean;
    activeAnomaliesCount?: number;
  };
  systemHealth?: {
    isDegraded: boolean;
    unavailableDependencies: string[];
  };
}

export interface DemandForecastPoint {
  timestamp: string;
  demandMw: number;
  lowerBoundMw?: number;
  upperBoundMw?: number;
}

export interface DemandForecast {
  zoneId: string;
  generatedAt: string;
  horizonMinutes: number;
  points: DemandForecastPoint[];
  spikeRisk: {
    level: "normal" | "warning" | "severe";
    probability: number;
    predictedPeakMw: number;
  };
  modelVersion: string;
}

export interface RenewableStatus {
  assetId: string;
  assetType: "solar" | "wind";
  timestamp: string;
  expectedMw: number;
  actualMw: number;
  performanceRatio: number;
  anomaly: boolean;
  anomalyScore?: number;
  likelyRootCause?: {
    category: "cloud_cover" | "inverter_fault" | "soiling" | "wake_effect" | "curtailment" | "sensor_drift" | "unknown";
    confidence: number;
    evidence: string;
  };
}

export interface OptimizationAction {
  resourceId: string;
  actionType: "battery_discharge" | "battery_charge" | "curtailment" | "load_shift";
  powerMw: number;
  startTime: string;
  endTime: string;
  costEur?: number;
}

export interface OptimizationResult {
  scenarioId: string;
  status: "feasible" | "infeasible" | "optimal";
  solverStatus: "optimal" | "feasible" | "infeasible";
  actions: OptimizationAction[];
  before: {
    demandMw?: number;
    renewableMw?: number;
    curtailmentMw: number;
    gridStressIndex: number;
    batterySocPercent?: number;
  };
  after: {
    demandMw?: number;
    renewableMw?: number;
    curtailmentMw: number;
    gridStressIndex: number;
    batterySocPercent?: number;
  };
  objectiveValue?: number;
  solveDurationMs?: number;
  recommendations?: Array<{
    id: string;
    type: string;
    message: string;
    priority: "low" | "medium" | "high" | "critical";
  }>;
}

export interface OperatorBrief {
  briefId: string;
  timestamp: string;
  zoneId: string;
  sections: {
    currentSituation: string;
    risk: string;
    renewableAlert: string;
    rootCause: string;
    recommendedActions: string;
    expectedImpact: string;
    confidenceUncertainty: string;
    dataLimitations: string;
  };
  rawMarkdown: string;
  status: "feasible" | "infeasible";
  missingDataWarnings: string[];
  groundTruthVerified: boolean;
}

export interface CopilotResponse {
  query: string;
  toolsCalled: string[];
  toolSummaries: Array<{
    name: string;
    success: boolean;
    durationMs: number;
    error?: string;
  }>;
  toolResults: Record<string, any>;
  explanation: string;
  recommendedActions: OptimizationAction[];
  uncertainty: string;
  solverStatus: "feasible" | "infeasible" | "not_run";
  missingData: string[];
  toolErrors: string[];
  guardrailVerified: boolean;
  guardrailViolations: string[];
  provider?: string;
  modelId?: string;
}

export interface Scenario {
  scenarioId: string;
  name: string;
  description: string;
  historicalSourceTimestamp: string;
  injectedEvents: Array<{
    timestampOffsetMinutes: number;
    eventType: string;
    severity: number;
    assetOrZoneId: string;
  }>;
  expectedOutcome: {
    expectedSpikeClass: string;
    expectedAnomalyScoreMin: number;
    expectedFeasibleOptimization: boolean;
  };
}

export interface SimulationResult {
  actionEvaluated: {
    resourceId: string;
    actionType: string;
    powerMw: number;
    durationMinutes: number;
  };
  projectedGridStress: number;
  deltaGridStress: number;
  isFeasible: boolean;
  constraintWarnings: string[];
}
