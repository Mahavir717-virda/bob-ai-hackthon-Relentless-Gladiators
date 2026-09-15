import { createApiServer } from "./server.ts";
import { loadConfig } from "./config.ts";
import { logger } from "./logger.ts";

const config = loadConfig();
const server = createApiServer({ config });

server.listen(config.port, config.host, () => {
  logger.info(`GridPilot API Gateway running at http://${config.host}:${config.port}`, {
    port: config.port,
    host: config.host,
    environment: config.nodeEnv,
  });
});

process.on("SIGINT", () => {
  logger.info("Gracefully shutting down API Gateway...");
  server.close(() => {
    process.exit(0);
  });
});
