/**
 * Environment-based configuration for GridPilot API Gateway
 * Zero hardcoded credentials; all values loaded from environment with safe local defaults.
 */

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
