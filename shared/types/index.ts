/**
 * Shared domain types and enums for GridPilot AI
 */

export type AssetType = "solar" | "wind" | "hydro" | "battery" | "flexible_load";

export type SpikeSeverity = "normal" | "moderate" | "severe";

export type RootCauseCategory =
  | "cloud_cover"
  | "inverter_fault"
  | "soiling"
  | "curtailment"
  | "sensor_error"
  | "grid_congestion"
  | "unknown";

export type OptimizationActionType =
  | "battery_charge"
  | "battery_discharge"
  | "shift_flexible_load"
  | "curtail_solar"
  | "curtail_wind";

export type SolverStatus = "optimal" | "feasible" | "infeasible";

export type RecommendationUrgency = "low" | "medium" | "high" | "critical";

export type RecommendationCategory =
  | "dispatch"
  | "curtailment_prevention"
  | "load_shifting"
  | "maintenance_alert";

export type EventType =
  | "demand_spike"
  | "solar_drop"
  | "wind_lull"
  | "inverter_failure"
  | "line_trip";

export type HorizonMinutes = 15 | 30 | 60;

export interface ValidationResult<T> {
  success: boolean;
  data?: T;
  errors?: string[];
}
