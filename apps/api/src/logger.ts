/**
 * Structured JSON Logger for GridPilot API Gateway
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

export class Logger {
  private minLevel: number;

  constructor(level: LogLevel = "info") {
    this.minLevel = LEVEL_PRIORITY[level] ?? 1;
  }

  private log(level: LogLevel, message: string, meta?: Record<string, any>): void {
    if (LEVEL_PRIORITY[level] < this.minLevel) return;

    const entry = {
      timestamp: new Date().toISOString(),
      level: level.toUpperCase(),
      message,
      ...meta,
    };

    const out = JSON.stringify(entry);
    if (level === "error") {
      process.stderr.write(out + "\n");
    } else {
      process.stdout.write(out + "\n");
    }
  }

  debug(message: string, meta?: Record<string, any>): void {
    this.log("debug", message, meta);
  }

  info(message: string, meta?: Record<string, any>): void {
    this.log("info", message, meta);
  }

  warn(message: string, meta?: Record<string, any>): void {
    this.log("warn", message, meta);
  }

  error(message: string, meta?: Record<string, any>): void {
    this.log("error", message, meta);
  }
}

export const logger = new Logger(
  (process.env.LOG_LEVEL?.toLowerCase() as LogLevel) || "info"
);
