import type { SpikeSeverity, ValidationResult } from "../types/index.ts";

export type AvailabilityStatus = "available" | "unavailable";

export interface CurrentDemandSnapshot {
  status: AvailabilityStatus;
  valueMw?: number;
  zoneId?: string;
}

export interface ForecastDemandSnapshot {
  status: AvailabilityStatus;
  horizon15mMw?: number;
  horizon30mMw?: number;
  horizon60mMw?: number;
  spikeRiskLevel?: SpikeSeverity;
  spikeProbability?: number;
}

export interface RenewableGenerationSnapshot {
  status: AvailabilityStatus;
  totalMw?: number;
  solarMw?: number;
  windMw?: number;
  assetCount?: number;
}

export interface AnomalyItem {
  assetId: string;
  assetType: string;
  expectedMw: number;
  actualMw: number;
  anomalyScore: number;
  likelyRootCause?: string;
}

export interface RenewableAnomaliesSnapshot {
  status: AvailabilityStatus;
  count?: number;
  anomalies?: AnomalyItem[];
}

export interface FlexibleResourcesSnapshot {
  status: AvailabilityStatus;
  batteryCapacityMwh?: number;
  batteryCurrentSocPercent?: number;
  batteryAvailableDischargeMw?: number;
  flexibleLoadCapacityMw?: number;
}

export interface CurtailmentSnapshot {
  status: AvailabilityStatus;
  currentCurtailmentMw?: number;
  curtailmentMitigatedMw?: number;
}

export interface GridStressSnapshot {
  status: AvailabilityStatus;
  stressIndex?: number;
  frequencyHz?: number;
  severity?: "normal" | "warning" | "critical";
}

export interface SystemHealthSnapshot {
  isDegraded: boolean;
  unavailableDependencies: string[];
}

export interface AggregatedGridSnapshot {
  timestamp: string;
  zoneId: string;
  currentDemand: CurrentDemandSnapshot;
  forecastDemand: ForecastDemandSnapshot;
  renewableGeneration: RenewableGenerationSnapshot;
  renewableAnomalies: RenewableAnomaliesSnapshot;
  availableFlexibleResources: FlexibleResourcesSnapshot;
  curtailment: CurtailmentSnapshot;
  gridStress: GridStressSnapshot;
  systemHealth: SystemHealthSnapshot;
}

export function validateAggregatedGridSnapshot(
  data: unknown
): ValidationResult<AggregatedGridSnapshot> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.timestamp !== "string" || isNaN(Date.parse(d.timestamp))) {
    errors.push("timestamp must be a valid ISO timestamp");
  }

  if (typeof d.zoneId !== "string" || d.zoneId.trim().length === 0) {
    errors.push("zoneId must be a non-empty string");
  }

  const validateStatusField = (field: any, name: string) => {
    if (!field || typeof field !== "object") {
      errors.push(`${name} must be an object`);
      return;
    }
    if (field.status !== "available" && field.status !== "unavailable") {
      errors.push(`${name}.status must be 'available' or 'unavailable'`);
    }
  };

  validateStatusField(d.currentDemand, "currentDemand");
  validateStatusField(d.forecastDemand, "forecastDemand");
  validateStatusField(d.renewableGeneration, "renewableGeneration");
  validateStatusField(d.renewableAnomalies, "renewableAnomalies");
  validateStatusField(d.availableFlexibleResources, "availableFlexibleResources");
  validateStatusField(d.curtailment, "curtailment");
  validateStatusField(d.gridStress, "gridStress");

  if (!d.systemHealth || typeof d.systemHealth !== "object") {
    errors.push("systemHealth must be an object");
  } else {
    if (typeof d.systemHealth.isDegraded !== "boolean") {
      errors.push("systemHealth.isDegraded must be a boolean");
    }
    if (!Array.isArray(d.systemHealth.unavailableDependencies)) {
      errors.push("systemHealth.unavailableDependencies must be an array");
    }
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as AggregatedGridSnapshot };
}
