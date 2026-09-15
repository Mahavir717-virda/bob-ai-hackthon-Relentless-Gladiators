import test from "node:test";
import assert from "node:assert/strict";

import {
  validateDemandForecast,
  type DemandForecast,
} from "../../shared/contracts/DemandForecast.ts";
import {
  validateRenewableStatus,
  type RenewableStatus,
} from "../../shared/contracts/RenewableStatus.ts";
import {
  validateWeatherData,
  type WeatherData,
} from "../../shared/contracts/WeatherData.ts";
import {
  validateGridState,
  type GridState,
} from "../../shared/contracts/GridState.ts";
import {
  validateOptimizationInput,
  type OptimizationInput,
} from "../../shared/contracts/OptimizationInput.ts";
import {
  validateOptimizationResult,
  type OptimizationResult,
} from "../../shared/contracts/OptimizationResult.ts";
import {
  validateRecommendation,
  type Recommendation,
} from "../../shared/contracts/Recommendation.ts";
import {
  validateScenario,
  type Scenario,
} from "../../shared/contracts/Scenario.ts";
import {
  validateAgentContext,
  type AgentContext,
} from "../../shared/contracts/AgentContext.ts";


test("Contract: DemandForecast validation", () => {
  const validPayload: DemandForecast = {
    zoneId: "NL_LIANDER_SUB_01",
    generatedAt: "2026-09-15T12:00:00.000Z",
    horizonMinutes: 15,
    points: [
      {
        timestamp: "2026-09-15T12:15:00.000Z",
        demandMw: 45.8,
        lowerBoundMw: 42.0,
        upperBoundMw: 49.5,
      },
    ],
    spikeRisk: {
      level: "moderate",
      probability: 0.35,
      predictedPeakMw: 52.0,
    },
    modelVersion: "lgbm-demand-v1.0.4",
  };

  const passRes = validateDemandForecast(validPayload);
  assert.equal(passRes.success, true);

  // Negative demand test
  const invalidPayload = {
    ...validPayload,
    points: [{ timestamp: "2026-09-15T12:15:00.000Z", demandMw: -5 }],
  };
  const failRes = validateDemandForecast(invalidPayload);
  assert.equal(failRes.success, false);
  assert.ok(failRes.errors?.some((e) => e.includes("demandMw")));

  // Inverted confidence interval test
  const invertedBounds = {
    ...validPayload,
    points: [
      {
        timestamp: "2026-09-15T12:15:00.000Z",
        demandMw: 45.0,
        lowerBoundMw: 55.0,
        upperBoundMw: 40.0,
      },
    ],
  };
  const boundFail = validateDemandForecast(invertedBounds);
  assert.equal(boundFail.success, false);
});

test("Contract: RenewableStatus validation", () => {
  const validSolar: RenewableStatus = {
    assetId: "SOLAR_FARM_ZEELAND_03",
    assetType: "solar",
    timestamp: "2026-09-15T12:00:00.000Z",
    expectedMw: 42.0,
    actualMw: 19.0,
    performanceRatio: 0.452,
    anomaly: true,
    anomalyScore: 0.88,
    likelyRootCause: {
      category: "cloud_cover",
      confidence: 0.84,
      evidence: "GHI dropped 52% while ambient temperature remained steady",
    },
  };

  const passRes = validateRenewableStatus(validSolar);
  assert.equal(passRes.success, true);

  // Invalid asset type
  const badAssetType = { ...validSolar, assetType: "nuclear" as any };
  const failRes = validateRenewableStatus(badAssetType);
  assert.equal(failRes.success, false);

  // Confidence out of range
  const badConfidence = {
    ...validSolar,
    likelyRootCause: { category: "cloud_cover", confidence: 1.5 },
  };
  const confFail = validateRenewableStatus(badConfidence);
  assert.equal(confFail.success, false);
});

test("Contract: WeatherData validation", () => {
  const validWeather: WeatherData = {
    timestamp: "2026-09-15T12:00:00.000Z",
    location: {
      latitude: 51.5074,
      longitude: 3.8912,
      zoneId: "NL_LIANDER_SUB_01",
    },
    ghiWm2: 680.5,
    temperatureCelsius: 22.4,
    windSpeedMs: 6.2,
    cloudCoverPercent: 25,
    isForecast: false,
  };

  const passRes = validateWeatherData(validWeather);
  assert.equal(passRes.success, true);

  // Negative GHI
  const negGhi = { ...validWeather, ghiWm2: -10 };
  assert.equal(validateWeatherData(negGhi).success, false);

  // Cloud cover > 100
  const badCloud = { ...validWeather, cloudCoverPercent: 120 };
  assert.equal(validateWeatherData(badCloud).success, false);

  // Invalid latitude
  const badLat = {
    ...validWeather,
    location: { ...validWeather.location, latitude: 120 },
  };
  assert.equal(validateWeatherData(badLat).success, false);
});

test("Contract: GridState validation", () => {
  const validState: GridState = {
    timestamp: "2026-09-15T12:00:00.000Z",
    zoneId: "NL_LIANDER_SUB_01",
    demandMw: 85.0,
    solarGenerationMw: 35.0,
    windGenerationMw: 20.0,
    netLoadMw: 30.0,
    batterySocPercent: 65.0,
    batteryPowerMw: 0.0,
    curtailmentMw: 0.0,
    gridFrequencyHz: 50.02,
    gridStressIndex: 0.42,
    activeAlertsCount: 0,
  };

  const passRes = validateGridState(validState);
  assert.equal(passRes.success, true);

  // Stress index > 1.0
  const badStress = { ...validState, gridStressIndex: 1.5 };
  assert.equal(validateGridState(badStress).success, false);

  // SOC < 0
  const badSoc = { ...validState, batterySocPercent: -5 };
  assert.equal(validateGridState(badSoc).success, false);
});

test("Contract: OptimizationInput & OptimizationResult validation", () => {
  const validState: GridState = {
    timestamp: "2026-09-15T12:00:00.000Z",
    zoneId: "NL_LIANDER_SUB_01",
    demandMw: 85.0,
    solarGenerationMw: 35.0,
    windGenerationMw: 20.0,
    netLoadMw: 30.0,
    batterySocPercent: 65.0,
    batteryPowerMw: 0.0,
    curtailmentMw: 0.0,
    gridFrequencyHz: 50.0,
    gridStressIndex: 0.89,
    activeAlertsCount: 1,
  };

  const validForecast: DemandForecast = {
    zoneId: "NL_LIANDER_SUB_01",
    generatedAt: "2026-09-15T12:00:00.000Z",
    horizonMinutes: 15,
    points: [{ timestamp: "2026-09-15T12:15:00.000Z", demandMw: 98.0 }],
    spikeRisk: { level: "severe", probability: 0.82, predictedPeakMw: 104.0 },
    modelVersion: "lgbm-v1",
  };

  const validOptInput: OptimizationInput = {
    scenarioId: "SCENARIO_SPIKE_REPLAY_01",
    targetTimestamp: "2026-09-15T12:15:00.000Z",
    horizonMinutes: 15,
    currentGridState: validState,
    demandForecast: validForecast,
    renewableForecastMw: 19.0,
    batteryConstraints: {
      maxCapacityMwh: 40.0,
      currentSocPercent: 65.0,
      minSocPercent: 10.0,
      maxSocPercent: 90.0,
      maxChargePowerMw: 20.0,
      maxDischargePowerMw: 20.0,
      roundTripEfficiency: 0.90,
    },
    flexibleLoadConstraints: {
      totalFlexibleMw: 10.0,
      maxShiftDurationMinutes: 60,
      shiftCostPerMw: 15.0,
    },
    curtailmentPenaltyPerMw: 50.0,
  };

  assert.equal(validateOptimizationInput(validOptInput).success, true);

  // Inverted battery SOC bounds
  const badBatteryInput = {
    ...validOptInput,
    batteryConstraints: {
      ...validOptInput.batteryConstraints,
      minSocPercent: 85.0,
      maxSocPercent: 20.0,
    },
  };
  assert.equal(validateOptimizationInput(badBatteryInput).success, false);

  // Valid OptimizationResult
  const validOptResult: OptimizationResult = {
    scenarioId: "SCENARIO_SPIKE_REPLAY_01",
    status: "feasible",
    solverStatus: "optimal",
    actions: [
      {
        resourceId: "BESS_SUB_01",
        actionType: "battery_discharge",
        powerMw: 15.0,
        startTime: "2026-09-15T12:15:00.000Z",
        endTime: "2026-09-15T12:30:00.000Z",
      },
      {
        resourceId: "FLEX_LOAD_IND_PARK",
        actionType: "shift_flexible_load",
        powerMw: 8.0,
        startTime: "2026-09-15T12:15:00.000Z",
        endTime: "2026-09-15T12:45:00.000Z",
      },
    ],
    before: {
      demandMw: 98.0,
      renewableMw: 19.0,
      curtailmentMw: 0.0,
      gridStressIndex: 0.89,
    },
    after: {
      demandMw: 90.0,
      renewableMw: 19.0,
      curtailmentMw: 0.0,
      gridStressIndex: 0.42,
    },
    objectiveValue: 142.5,
    solveDurationMs: 38,
  };

  assert.equal(validateOptimizationResult(validOptResult).success, true);

  // Illegal status
  const badOptStatus = { ...validOptResult, status: "partial" as any };
  assert.equal(validateOptimizationResult(badOptStatus).success, false);
});

test("Contract: Recommendation validation", () => {
  const validRec: Recommendation = {
    id: "REC_20260915_01",
    title: "Dispatch BESS 15 MW & Shift 8 MW Flexible Load",
    urgency: "critical",
    category: "dispatch",
    description:
      "Mitigate severe demand surge (+18%) and solar generation drop (42 MW -> 19 MW).",
    rationale:
      "MILP optimization verified constraint feasibility and reduces grid stress index from 0.89 to 0.42.",
    associatedAction: {
      resourceId: "BESS_SUB_01",
      actionType: "battery_discharge",
      powerMw: 15.0,
      durationMinutes: 15,
    },
    impactAssessment: {
      gridStressReduction: 0.47,
      curtailmentAvoidedMw: 0.0,
      estimatedSavingsUsd: 1250,
    },
    isAutomatedExecutable: false,
  };

  assert.equal(validateRecommendation(validRec).success, true);

  const badUrgency = { ...validRec, urgency: "emergency" as any };
  assert.equal(validateRecommendation(badUrgency).success, false);
});

test("Contract: Scenario validation", () => {
  const validScenario: Scenario = {
    scenarioId: "DEMAND_SPIKE_PLUS_RENEWABLE_DROP",
    name: "Deterministic Demand Surge with Cloud Cover Drop",
    description: "Replays Liander 2024 grid event with simultaneous solar drop.",
    historicalSourceTimestamp: "2024-06-12T14:00:00.000Z",
    injectedEvents: [
      {
        timestampOffsetMinutes: 15,
        eventType: "demand_spike",
        severity: 0.18,
        assetOrZoneId: "NL_LIANDER_SUB_01",
      },
      {
        timestampOffsetMinutes: 15,
        eventType: "solar_drop",
        severity: 0.55,
        assetOrZoneId: "SOLAR_FARM_ZEELAND_03",
      },
    ],
    expectedOutcome: {
      expectedSpikeClass: "severe",
      expectedAnomalyScoreMin: 0.80,
      expectedFeasibleOptimization: true,
    },
  };

  assert.equal(validateScenario(validScenario).success, true);

  const missingName = { ...validScenario, name: "" };
  assert.equal(validateScenario(missingName).success, false);
});

test("Contract: AgentContext validation", () => {
  const validGridState: GridState = {
    timestamp: "2026-09-15T12:00:00.000Z",
    zoneId: "NL_LIANDER_SUB_01",
    demandMw: 85.0,
    solarGenerationMw: 19.0,
    windGenerationMw: 20.0,
    netLoadMw: 46.0,
    batterySocPercent: 65.0,
    batteryPowerMw: 0.0,
    curtailmentMw: 0.0,
    gridFrequencyHz: 50.0,
    gridStressIndex: 0.89,
    activeAlertsCount: 1,
  };

  const validDemandForecast: DemandForecast = {
    zoneId: "NL_LIANDER_SUB_01",
    generatedAt: "2026-09-15T12:00:00.000Z",
    horizonMinutes: 15,
    points: [{ timestamp: "2026-09-15T12:15:00.000Z", demandMw: 98.0 }],
    spikeRisk: { level: "severe", probability: 0.82, predictedPeakMw: 104.0 },
    modelVersion: "lgbm-v1",
  };

  const validRenewable: RenewableStatus = {
    assetId: "SOLAR_FARM_ZEELAND_03",
    assetType: "solar",
    timestamp: "2026-09-15T12:00:00.000Z",
    expectedMw: 42.0,
    actualMw: 19.0,
    performanceRatio: 0.452,
    anomaly: true,
    anomalyScore: 0.88,
  };

  const validContext: AgentContext = {
    sessionId: "SESSION_OPERATOR_001",
    timestamp: "2026-09-15T12:05:00.000Z",
    currentGridState: validGridState,
    demandForecast: validDemandForecast,
    renewableStatuses: [validRenewable],
    recommendations: [],
    conversationHistory: [
      {
        role: "user",
        content: "What is the primary cause of current grid stress?",
        timestamp: "2026-09-15T12:05:10.000Z",
      },
    ],
    operatorQuery: "What is the primary cause of current grid stress?",
  };

  assert.equal(validateAgentContext(validContext).success, true);

  // Invalid nested grid state
  const badContext = {
    ...validContext,
    currentGridState: { ...validGridState, demandMw: -20 },
  };
  assert.equal(validateAgentContext(badContext).success, false);
});
