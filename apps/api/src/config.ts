import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Load .env file automatically if present so variables like LLM_PROVIDER, OLLAMA_MODEL are always active
 */
function loadEnvFile(): void {
  const envPath = resolve(process.cwd(), ".env");
  if (!existsSync(envPath)) return;
  try {
    const content = readFileSync(envPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx > 0) {
        const key = trimmed.slice(0, eqIdx).trim();
        const val = trimmed.slice(eqIdx + 1).trim();
        if (!process.env[key]) {
          process.env[key] = val;
        }
      }
    }
  } catch {
    // Ignore error if unreadable
  }
}

loadEnvFile();

export interface AppConfig {
  port: number;
  host: string;
  nodeEnv: string;
  logLevel: string;
  corsOrigin: string;
  services: {
    dataUrl: string;
    forecastingUrl: string;
    renewableUrl: string;
    optimizationUrl: string;
  };
  watsonx: {
    url: string;
    apiKey?: string;
    projectId?: string;
    modelId: string;
  };
}

export function loadConfig(): AppConfig {
  return {
    port: parseInt(process.env.PORT || process.env.APP_PORT || "8000", 10),
    host: process.env.API_HOST || "0.0.0.0",
    nodeEnv: process.env.NODE_ENV || process.env.APP_ENV || "development",
    logLevel: process.env.LOG_LEVEL || "info",
    corsOrigin: process.env.CORS_ORIGIN || "*",
    services: {
      dataUrl: process.env.DATA_SERVICE_URL || "http://localhost:8001",
      forecastingUrl: process.env.FORECASTING_SERVICE_URL || "http://localhost:8002",
      renewableUrl: process.env.RENEWABLE_SERVICE_URL || "http://localhost:8003",
      optimizationUrl: process.env.OPTIMIZATION_SERVICE_URL || "http://localhost:8004",
    },
    watsonx: {
      url: process.env.WATSONX_URL || "https://us-south.ml.cloud.ibm.com",
      apiKey: process.env.WATSONX_API_KEY,
      projectId: process.env.WATSONX_PROJECT_ID,
      modelId: process.env.WATSONX_MODEL_ID || "ibm/granite-3-8b-instruct",
    },
  };
}
