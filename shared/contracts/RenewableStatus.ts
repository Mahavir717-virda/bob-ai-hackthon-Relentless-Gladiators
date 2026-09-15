import type { AssetType, RootCauseCategory, ValidationResult } from "../types/index.ts";


export interface RenewableRootCause {
  category: RootCauseCategory | string;
  confidence: number;
  evidence?: string;
}

export interface RenewableStatus {
  assetId: string;
  assetType: AssetType;
  timestamp: string;
  expectedMw: number;
  actualMw: number;
  performanceRatio: number;
  anomaly: boolean;
  anomalyScore?: number;
  likelyRootCause?: RenewableRootCause;
}

export function validateRenewableStatus(data: unknown): ValidationResult<RenewableStatus> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.assetId !== "string" || d.assetId.trim().length === 0) {
    errors.push("assetId must be a non-empty string");
  }

  const validAssetTypes: AssetType[] = ["solar", "wind", "hydro", "battery", "flexible_load"];
  if (!validAssetTypes.includes(d.assetType)) {
    errors.push(`assetType must be one of: ${validAssetTypes.join(", ")}`);
  }

  if (typeof d.timestamp !== "string" || isNaN(Date.parse(d.timestamp))) {
    errors.push("timestamp must be a valid ISO timestamp");
  }

  if (typeof d.expectedMw !== "number" || d.expectedMw < 0) {
    errors.push("expectedMw must be a non-negative number");
  }

  if (typeof d.actualMw !== "number" || d.actualMw < 0) {
    errors.push("actualMw must be a non-negative number");
  }

  if (typeof d.performanceRatio !== "number" || d.performanceRatio < 0) {
    errors.push("performanceRatio must be a non-negative number");
  }

  if (typeof d.anomaly !== "boolean") {
    errors.push("anomaly must be a boolean");
  }

  if (d.anomalyScore !== undefined) {
    if (typeof d.anomalyScore !== "number" || d.anomalyScore < 0 || d.anomalyScore > 1) {
      errors.push("anomalyScore must be a number between 0 and 1");
    }
  }

  if (d.likelyRootCause !== undefined) {
    if (typeof d.likelyRootCause !== "object" || d.likelyRootCause === null) {
      errors.push("likelyRootCause must be an object");
    } else {
      if (
        typeof d.likelyRootCause.category !== "string" ||
        d.likelyRootCause.category.trim().length === 0
      ) {
        errors.push("likelyRootCause.category must be a non-empty string");
      }
      if (
        typeof d.likelyRootCause.confidence !== "number" ||
        d.likelyRootCause.confidence < 0 ||
        d.likelyRootCause.confidence > 1
      ) {
        errors.push("likelyRootCause.confidence must be a number between 0 and 1");
      }
    }
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as RenewableStatus };
}
