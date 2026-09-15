import type { ValidationResult } from "../types/index.ts";
import { type GridState, validateGridState } from "./GridState.ts";
import { type DemandForecast, validateDemandForecast } from "./DemandForecast.ts";


export interface BatteryConstraints {
  maxCapacityMwh: number;
  currentSocPercent: number;
  minSocPercent: number;
  maxSocPercent: number;
  maxChargePowerMw: number;
  maxDischargePowerMw: number;
  roundTripEfficiency: number;
}

export interface FlexibleLoadConstraints {
  totalFlexibleMw: number;
  maxShiftDurationMinutes: number;
  shiftCostPerMw: number;
}

export interface OptimizationInput {
  scenarioId: string;
  targetTimestamp: string;
  horizonMinutes: number;
  currentGridState: GridState;
  demandForecast: DemandForecast;
  renewableForecastMw: number;
  batteryConstraints: BatteryConstraints;
  flexibleLoadConstraints: FlexibleLoadConstraints;
  curtailmentPenaltyPerMw: number;
}

export function validateOptimizationInput(data: unknown): ValidationResult<OptimizationInput> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.scenarioId !== "string" || d.scenarioId.trim().length === 0) {
    errors.push("scenarioId must be a non-empty string");
  }

  if (typeof d.targetTimestamp !== "string" || isNaN(Date.parse(d.targetTimestamp))) {
    errors.push("targetTimestamp must be a valid ISO timestamp");
  }

  if (typeof d.horizonMinutes !== "number" || d.horizonMinutes <= 0) {
    errors.push("horizonMinutes must be a positive number");
  }

  const gridStateValidation = validateGridState(d.currentGridState);
  if (!gridStateValidation.success) {
    errors.push(...(gridStateValidation.errors || []).map((e) => `currentGridState: ${e}`));
  }

  const demandForecastValidation = validateDemandForecast(d.demandForecast);
  if (!demandForecastValidation.success) {
    errors.push(...(demandForecastValidation.errors || []).map((e) => `demandForecast: ${e}`));
  }

  if (typeof d.renewableForecastMw !== "number" || d.renewableForecastMw < 0) {
    errors.push("renewableForecastMw must be a non-negative number");
  }

  if (!d.batteryConstraints || typeof d.batteryConstraints !== "object") {
    errors.push("batteryConstraints must be an object");
  } else {
    const b = d.batteryConstraints;
    if (typeof b.maxCapacityMwh !== "number" || b.maxCapacityMwh <= 0) {
      errors.push("batteryConstraints.maxCapacityMwh must be a positive number");
    }
    if (typeof b.currentSocPercent !== "number" || b.currentSocPercent < 0 || b.currentSocPercent > 100) {
      errors.push("batteryConstraints.currentSocPercent must be between 0 and 100");
    }
    if (typeof b.minSocPercent !== "number" || b.minSocPercent < 0 || b.minSocPercent > 100) {
      errors.push("batteryConstraints.minSocPercent must be between 0 and 100");
    }
    if (typeof b.maxSocPercent !== "number" || b.maxSocPercent < 0 || b.maxSocPercent > 100) {
      errors.push("batteryConstraints.maxSocPercent must be between 0 and 100");
    }
    if (b.minSocPercent !== undefined && b.maxSocPercent !== undefined && b.minSocPercent > b.maxSocPercent) {
      errors.push("batteryConstraints.minSocPercent cannot exceed maxSocPercent");
    }
    if (typeof b.maxChargePowerMw !== "number" || b.maxChargePowerMw < 0) {
      errors.push("batteryConstraints.maxChargePowerMw must be a non-negative number");
    }
    if (typeof b.maxDischargePowerMw !== "number" || b.maxDischargePowerMw < 0) {
      errors.push("batteryConstraints.maxDischargePowerMw must be a non-negative number");
    }
    if (typeof b.roundTripEfficiency !== "number" || b.roundTripEfficiency <= 0 || b.roundTripEfficiency > 1) {
      errors.push("batteryConstraints.roundTripEfficiency must be a number between 0 and 1");
    }
  }

  if (!d.flexibleLoadConstraints || typeof d.flexibleLoadConstraints !== "object") {
    errors.push("flexibleLoadConstraints must be an object");
  } else {
    const fl = d.flexibleLoadConstraints;
    if (typeof fl.totalFlexibleMw !== "number" || fl.totalFlexibleMw < 0) {
      errors.push("flexibleLoadConstraints.totalFlexibleMw must be a non-negative number");
    }
    if (typeof fl.maxShiftDurationMinutes !== "number" || fl.maxShiftDurationMinutes < 0) {
      errors.push("flexibleLoadConstraints.maxShiftDurationMinutes must be a non-negative number");
    }
    if (typeof fl.shiftCostPerMw !== "number" || fl.shiftCostPerMw < 0) {
      errors.push("flexibleLoadConstraints.shiftCostPerMw must be a non-negative number");
    }
  }

  if (typeof d.curtailmentPenaltyPerMw !== "number" || d.curtailmentPenaltyPerMw < 0) {
    errors.push("curtailmentPenaltyPerMw must be a non-negative number");
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as OptimizationInput };
}
