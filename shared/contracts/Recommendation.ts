import type {
  RecommendationCategory,
  RecommendationUrgency,
  ValidationResult,
} from "../types/index.ts";


export interface RecommendationAction {
  resourceId: string;
  actionType: string;
  powerMw: number;
  durationMinutes: number;
}

export interface RecommendationImpact {
  gridStressReduction: number;
  curtailmentAvoidedMw: number;
  estimatedSavingsUsd?: number;
}

export interface Recommendation {
  id: string;
  title: string;
  urgency: RecommendationUrgency;
  category: RecommendationCategory;
  description: string;
  rationale: string;
  associatedAction?: RecommendationAction;
  impactAssessment: RecommendationImpact;
  isAutomatedExecutable: boolean;
}

export function validateRecommendation(data: unknown): ValidationResult<Recommendation> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.id !== "string" || d.id.trim().length === 0) {
    errors.push("id must be a non-empty string");
  }

  if (typeof d.title !== "string" || d.title.trim().length === 0) {
    errors.push("title must be a non-empty string");
  }

  const validUrgencies: RecommendationUrgency[] = ["low", "medium", "high", "critical"];
  if (!validUrgencies.includes(d.urgency)) {
    errors.push(`urgency must be one of: ${validUrgencies.join(", ")}`);
  }

  const validCategories: RecommendationCategory[] = [
    "dispatch",
    "curtailment_prevention",
    "load_shifting",
    "maintenance_alert",
  ];
  if (!validCategories.includes(d.category)) {
    errors.push(`category must be one of: ${validCategories.join(", ")}`);
  }

  if (typeof d.description !== "string" || d.description.trim().length === 0) {
    errors.push("description must be a non-empty string");
  }

  if (typeof d.rationale !== "string" || d.rationale.trim().length === 0) {
    errors.push("rationale must be a non-empty string");
  }

  if (d.associatedAction !== undefined) {
    const act = d.associatedAction;
    if (!act || typeof act !== "object") {
      errors.push("associatedAction must be an object");
    } else {
      if (typeof act.resourceId !== "string" || act.resourceId.trim().length === 0) {
        errors.push("associatedAction.resourceId must be a non-empty string");
      }
      if (typeof act.actionType !== "string" || act.actionType.trim().length === 0) {
        errors.push("associatedAction.actionType must be a non-empty string");
      }
      if (typeof act.powerMw !== "number" || act.powerMw < 0) {
        errors.push("associatedAction.powerMw must be a non-negative number");
      }
      if (typeof act.durationMinutes !== "number" || act.durationMinutes <= 0) {
        errors.push("associatedAction.durationMinutes must be a positive number");
      }
    }
  }

  if (!d.impactAssessment || typeof d.impactAssessment !== "object") {
    errors.push("impactAssessment must be an object");
  } else {
    const imp = d.impactAssessment;
    if (typeof imp.gridStressReduction !== "number") {
      errors.push("impactAssessment.gridStressReduction must be a number");
    }
    if (typeof imp.curtailmentAvoidedMw !== "number" || imp.curtailmentAvoidedMw < 0) {
      errors.push("impactAssessment.curtailmentAvoidedMw must be a non-negative number");
    }
  }

  if (typeof d.isAutomatedExecutable !== "boolean") {
    errors.push("isAutomatedExecutable must be a boolean");
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as Recommendation };
}
