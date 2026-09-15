import type { EventType, SpikeSeverity, ValidationResult } from "../types/index.ts";


export interface InjectedScenarioEvent {
  timestampOffsetMinutes: number;
  eventType: EventType | string;
  severity: number;
  assetOrZoneId: string;
  parameters?: Record<string, any>;
}

export interface ScenarioExpectedOutcome {
  expectedSpikeClass?: SpikeSeverity;
  expectedAnomalyScoreMin?: number;
  expectedFeasibleOptimization: boolean;
}

export interface Scenario {
  scenarioId: string;
  name: string;
  description: string;
  historicalSourceTimestamp: string;
  injectedEvents: InjectedScenarioEvent[];
  expectedOutcome: ScenarioExpectedOutcome;
}

export function validateScenario(data: unknown): ValidationResult<Scenario> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.scenarioId !== "string" || d.scenarioId.trim().length === 0) {
    errors.push("scenarioId must be a non-empty string");
  }

  if (typeof d.name !== "string" || d.name.trim().length === 0) {
    errors.push("name must be a non-empty string");
  }

  if (typeof d.description !== "string" || d.description.trim().length === 0) {
    errors.push("description must be a non-empty string");
  }

  if (typeof d.historicalSourceTimestamp !== "string" || isNaN(Date.parse(d.historicalSourceTimestamp))) {
    errors.push("historicalSourceTimestamp must be a valid ISO timestamp");
  }

  if (!Array.isArray(d.injectedEvents)) {
    errors.push("injectedEvents must be an array");
  } else {
    d.injectedEvents.forEach((ev: any, idx: number) => {
      if (typeof ev.timestampOffsetMinutes !== "number") {
        errors.push(`injectedEvents[${idx}].timestampOffsetMinutes must be a number`);
      }
      if (typeof ev.eventType !== "string" || ev.eventType.trim().length === 0) {
        errors.push(`injectedEvents[${idx}].eventType must be a non-empty string`);
      }
      if (typeof ev.severity !== "number" || ev.severity < 0) {
        errors.push(`injectedEvents[${idx}].severity must be a non-negative number`);
      }
      if (typeof ev.assetOrZoneId !== "string" || ev.assetOrZoneId.trim().length === 0) {
        errors.push(`injectedEvents[${idx}].assetOrZoneId must be a non-empty string`);
      }
    });
  }

  if (!d.expectedOutcome || typeof d.expectedOutcome !== "object") {
    errors.push("expectedOutcome must be an object");
  } else {
    if (typeof d.expectedOutcome.expectedFeasibleOptimization !== "boolean") {
      errors.push("expectedOutcome.expectedFeasibleOptimization must be a boolean");
    }
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as Scenario };
}
