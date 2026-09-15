import type { ValidationResult } from "../types/index.ts";


export interface WeatherLocation {
  latitude: number;
  longitude: number;
  zoneId: string;
}

export interface WeatherData {
  timestamp: string;
  location: WeatherLocation;
  ghiWm2: number;
  temperatureCelsius: number;
  windSpeedMs: number;
  cloudCoverPercent: number;
  dniWm2?: number;
  dhiWm2?: number;
  windDirectionDegrees?: number;
  relativeHumidityPercent?: number;
  isForecast: boolean;
}

export function validateWeatherData(data: unknown): ValidationResult<WeatherData> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.timestamp !== "string" || isNaN(Date.parse(d.timestamp))) {
    errors.push("timestamp must be a valid ISO timestamp");
  }

  if (!d.location || typeof d.location !== "object") {
    errors.push("location must be an object");
  } else {
    if (
      typeof d.location.latitude !== "number" ||
      d.location.latitude < -90 ||
      d.location.latitude > 90
    ) {
      errors.push("location.latitude must be a number between -90 and 90");
    }
    if (
      typeof d.location.longitude !== "number" ||
      d.location.longitude < -180 ||
      d.location.longitude > 180
    ) {
      errors.push("location.longitude must be a number between -180 and 180");
    }
    if (typeof d.location.zoneId !== "string" || d.location.zoneId.trim().length === 0) {
      errors.push("location.zoneId must be a non-empty string");
    }
  }

  if (typeof d.ghiWm2 !== "number" || d.ghiWm2 < 0) {
    errors.push("ghiWm2 must be a non-negative number");
  }

  if (typeof d.temperatureCelsius !== "number") {
    errors.push("temperatureCelsius must be a number");
  }

  if (typeof d.windSpeedMs !== "number" || d.windSpeedMs < 0) {
    errors.push("windSpeedMs must be a non-negative number");
  }

  if (
    typeof d.cloudCoverPercent !== "number" ||
    d.cloudCoverPercent < 0 ||
    d.cloudCoverPercent > 100
  ) {
    errors.push("cloudCoverPercent must be a number between 0 and 100");
  }

  if (d.dniWm2 !== undefined && (typeof d.dniWm2 !== "number" || d.dniWm2 < 0)) {
    errors.push("dniWm2 must be a non-negative number");
  }

  if (d.dhiWm2 !== undefined && (typeof d.dhiWm2 !== "number" || d.dhiWm2 < 0)) {
    errors.push("dhiWm2 must be a non-negative number");
  }

  if (
    d.windDirectionDegrees !== undefined &&
    (typeof d.windDirectionDegrees !== "number" ||
      d.windDirectionDegrees < 0 ||
      d.windDirectionDegrees > 360)
  ) {
    errors.push("windDirectionDegrees must be a number between 0 and 360");
  }

  if (
    d.relativeHumidityPercent !== undefined &&
    (typeof d.relativeHumidityPercent !== "number" ||
      d.relativeHumidityPercent < 0 ||
      d.relativeHumidityPercent > 100)
  ) {
    errors.push("relativeHumidityPercent must be a number between 0 and 100");
  }

  if (typeof d.isForecast !== "boolean") {
    errors.push("isForecast must be a boolean");
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as WeatherData };
}
