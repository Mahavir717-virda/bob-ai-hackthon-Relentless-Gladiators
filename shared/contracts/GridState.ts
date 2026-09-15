import type { ValidationResult } from "../types/index.ts";


export interface GridState {
  timestamp: string;
  zoneId: string;
  demandMw: number;
  solarGenerationMw: number;
  windGenerationMw: number;
  netLoadMw: number;
  batterySocPercent: number;
  batteryPowerMw: number;
  curtailmentMw: number;
  gridFrequencyHz: number;
  gridStressIndex: number;
  activeAlertsCount: number;
}

export function validateGridState(data: unknown): ValidationResult<GridState> {
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

  if (typeof d.demandMw !== "number" || d.demandMw < 0) {
    errors.push("demandMw must be a non-negative number");
  }

  if (typeof d.solarGenerationMw !== "number" || d.solarGenerationMw < 0) {
    errors.push("solarGenerationMw must be a non-negative number");
  }

  if (typeof d.windGenerationMw !== "number" || d.windGenerationMw < 0) {
    errors.push("windGenerationMw must be a non-negative number");
  }

  if (typeof d.netLoadMw !== "number") {
    errors.push("netLoadMw must be a number");
  }

  if (
    typeof d.batterySocPercent !== "number" ||
    d.batterySocPercent < 0 ||
    d.batterySocPercent > 100
  ) {
    errors.push("batterySocPercent must be a number between 0 and 100");
  }

  if (typeof d.batteryPowerMw !== "number") {
    errors.push("batteryPowerMw must be a number");
  }

  if (typeof d.curtailmentMw !== "number" || d.curtailmentMw < 0) {
    errors.push("curtailmentMw must be a non-negative number");
  }

  if (typeof d.gridFrequencyHz !== "number" || d.gridFrequencyHz <= 0) {
    errors.push("gridFrequencyHz must be a positive number");
  }

  if (
    typeof d.gridStressIndex !== "number" ||
    d.gridStressIndex < 0 ||
    d.gridStressIndex > 1
  ) {
    errors.push("gridStressIndex must be a number between 0 and 1");
  }

  if (typeof d.activeAlertsCount !== "number" || d.activeAlertsCount < 0) {
    errors.push("activeAlertsCount must be a non-negative integer");
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as GridState };
}
