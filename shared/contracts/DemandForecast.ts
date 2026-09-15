import type { SpikeSeverity, ValidationResult } from "../types/index.ts";


export interface DemandForecastPoint {
  timestamp: string;
  demandMw: number;
  lowerBoundMw?: number;
  upperBoundMw?: number;
}

export interface SpikeRisk {
  level: SpikeSeverity;
  probability: number;
  predictedPeakMw: number;
}

export interface DemandForecast {
  zoneId: string;
  generatedAt: string;
  horizonMinutes: number;
  points: DemandForecastPoint[];
  spikeRisk: SpikeRisk;
  modelVersion: string;
}

export function validateDemandForecast(data: unknown): ValidationResult<DemandForecast> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.zoneId !== "string" || d.zoneId.trim().length === 0) {
    errors.push("zoneId must be a non-empty string");
  }

  if (typeof d.generatedAt !== "string" || isNaN(Date.parse(d.generatedAt))) {
    errors.push("generatedAt must be a valid ISO timestamp");
  }

  if (typeof d.horizonMinutes !== "number" || d.horizonMinutes <= 0) {
    errors.push("horizonMinutes must be a positive number");
  }

  if (!Array.isArray(d.points) || d.points.length === 0) {
    errors.push("points must be a non-empty array of forecast points");
  } else {
    d.points.forEach((pt: any, idx: number) => {
      if (typeof pt.timestamp !== "string" || isNaN(Date.parse(pt.timestamp))) {
        errors.push(`points[${idx}].timestamp must be a valid ISO timestamp`);
      }
      if (typeof pt.demandMw !== "number" || pt.demandMw < 0) {
        errors.push(`points[${idx}].demandMw must be a non-negative number`);
      }
      if (pt.lowerBoundMw !== undefined && (typeof pt.lowerBoundMw !== "number" || pt.lowerBoundMw < 0)) {
        errors.push(`points[${idx}].lowerBoundMw must be a non-negative number`);
      }
      if (pt.upperBoundMw !== undefined && (typeof pt.upperBoundMw !== "number" || pt.upperBoundMw < 0)) {
        errors.push(`points[${idx}].upperBoundMw must be a non-negative number`);
      }
      if (
        pt.lowerBoundMw !== undefined &&
        pt.upperBoundMw !== undefined &&
        pt.lowerBoundMw > pt.upperBoundMw
      ) {
        errors.push(`points[${idx}].lowerBoundMw cannot exceed upperBoundMw`);
      }
    });
  }

  if (!d.spikeRisk || typeof d.spikeRisk !== "object") {
    errors.push("spikeRisk must be an object");
  } else {
    const validLevels = ["normal", "moderate", "severe"];
    if (!validLevels.includes(d.spikeRisk.level)) {
      errors.push("spikeRisk.level must be 'normal', 'moderate', or 'severe'");
    }
    if (
      typeof d.spikeRisk.probability !== "number" ||
      d.spikeRisk.probability < 0 ||
      d.spikeRisk.probability > 1
    ) {
      errors.push("spikeRisk.probability must be a number between 0 and 1");
    }
    if (typeof d.spikeRisk.predictedPeakMw !== "number" || d.spikeRisk.predictedPeakMw < 0) {
      errors.push("spikeRisk.predictedPeakMw must be a non-negative number");
    }
  }

  if (typeof d.modelVersion !== "string" || d.modelVersion.trim().length === 0) {
    errors.push("modelVersion must be a non-empty string");
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as DemandForecast };
}
