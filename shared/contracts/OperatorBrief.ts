import type { ValidationResult } from "../types/index.ts";
import type { GridState } from "./GridState.ts";
import type { DemandForecast, SpikeRisk } from "./DemandForecast.ts";
import type { RenewableStatus, RenewableRootCause } from "./RenewableStatus.ts";
import type { OptimizationResult } from "./OptimizationResult.ts";

export interface OperatorBriefSections {
  currentSituation: string;
  risk: string;
  renewableAlert: string;
  rootCause: string;
  recommendedActions: string;
  expectedImpact: string;
  confidenceUncertainty: string;
  dataLimitations: string;
}

export interface OperatorBrief {
  briefId: string;
  timestamp: string;
  zoneId: string;
  sections: OperatorBriefSections;
  rawMarkdown: string;
  status: "feasible" | "infeasible";
  missingDataWarnings: string[];
  groundTruthVerified: boolean;
}

export interface CurtailmentResult {
  currentCurtailmentMw: number;
  mitigatedMw: number;
}

export interface OperatorBriefInput {
  currentGridState?: GridState | null;
  demandForecast?: DemandForecast | null;
  demandSpikeRisk?: SpikeRisk | null;
  renewableForecasts?: Array<{ assetId: string; expectedMw: number }> | null;
  renewableAnomalies?: RenewableStatus[] | null;
  rootCauses?: RenewableRootCause[] | null;
  optimizationResult?: OptimizationResult | null;
  curtailmentResult?: CurtailmentResult | null;
}

export function validateOperatorBrief(data: unknown): ValidationResult<OperatorBrief> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.briefId !== "string" || d.briefId.trim().length === 0) {
    errors.push("briefId must be a non-empty string");
  }

  if (typeof d.timestamp !== "string" || isNaN(Date.parse(d.timestamp))) {
    errors.push("timestamp must be a valid ISO timestamp");
  }

  if (typeof d.zoneId !== "string" || d.zoneId.trim().length === 0) {
    errors.push("zoneId must be a non-empty string");
  }

  if (!d.sections || typeof d.sections !== "object") {
    errors.push("sections must be an object containing all 8 sections");
  } else {
    const requiredSections = [
      "currentSituation",
      "risk",
      "renewableAlert",
      "rootCause",
      "recommendedActions",
      "expectedImpact",
      "confidenceUncertainty",
      "dataLimitations",
    ];
    for (const sec of requiredSections) {
      if (typeof d.sections[sec] !== "string" || d.sections[sec].trim().length === 0) {
        errors.push(`sections.${sec} must be a non-empty string`);
      }
    }
  }

  if (typeof d.rawMarkdown !== "string" || d.rawMarkdown.trim().length === 0) {
    errors.push("rawMarkdown must be a non-empty string");
  }

  if (d.status !== "feasible" && d.status !== "infeasible") {
    errors.push("status must be either 'feasible' or 'infeasible'");
  }

  if (!Array.isArray(d.missingDataWarnings)) {
    errors.push("missingDataWarnings must be an array");
  }

  if (typeof d.groundTruthVerified !== "boolean") {
    errors.push("groundTruthVerified must be a boolean");
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as OperatorBrief };
}
