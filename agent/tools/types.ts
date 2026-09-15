/**
 * Tool Interfaces and Types for GridPilot Operator Copilot & IBM Bob
 */

export interface ToolParameterProperty {
  type: string;
  description: string;
  enum?: string[];
  default?: any;
}

export interface ToolParametersSchema {
  type: "object";
  properties: Record<string, ToolParameterProperty>;
  required?: string[];
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: ToolParametersSchema;
}

export interface ToolExecutionResult<T = any> {
  toolName: string;
  success: boolean;
  data?: T;
  error?: string;
  durationMs: number;
}

export interface AgentTool<TArgs = any, TResult = any> {
  definition: ToolDefinition;
  execute(args: TArgs): Promise<ToolExecutionResult<TResult>>;
}
