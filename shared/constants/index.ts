/**
 * System-wide physical units and operational constants for GridPilot AI
 */

import type { HorizonMinutes } from "../types/index.ts";

export const TIME_STEP_MINUTES = 15;

export const DEFAULT_HORIZONS: readonly HorizonMinutes[] = [15, 30, 60] as const;

export const POWER_UNIT = "MW";
export const ENERGY_UNIT = "MWh";
export const IRRADIANCE_UNIT = "W/m²";
export const WIND_SPEED_UNIT = "m/s";

export const NOMINAL_GRID_FREQUENCY_HZ = 50.0;
export const FREQUENCY_TOLERANCE_HZ = 0.5;

export const DEFAULT_ANOMALY_THRESHOLD = 0.70;

export const BATTERY_DEFAULTS = {
  MIN_SOC_PERCENT: 10,
  MAX_SOC_PERCENT: 90,
  ROUND_TRIP_EFFICIENCY: 0.90,
} as const;

export const GRID_STRESS = {
  NORMAL_THRESHOLD: 0.50,
  WARNING_THRESHOLD: 0.75,
  CRITICAL_THRESHOLD: 0.90,
} as const;
