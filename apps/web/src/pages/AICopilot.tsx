import React, { useState } from "react";
import {
  Bot,
  Send,
  ShieldCheck,
  Cpu,
} from "lucide-react";
import { ApiClient } from "../services/api-client.ts";
import type { CopilotResponse } from "../services/types.ts";

export interface ChatMessage {
  id: string;
  sender: "operator" | "copilot";
  timestamp: string;
  text: string;
  copilotResponse?: CopilotResponse;
}

export const AICopilotPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "msg_welcome",
      sender: "copilot",
      timestamp: new Date().toISOString(),
      text: "GridPilot AI Operator Copilot active. I am powered by watsonx.ai / Bob MCP tools connected to SCADA telemetry, LightGBM demand forecaster, Isolation Forest anomaly detector, and the OR-Tools MILP optimizer. How can I assist with grid operations?",
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);

  const presetQueries = [
    "Check current grid demand, evaluate spike risk, and recommend battery dispatch.",
    "Are there any solar PV or wind turbine anomalies active? Diagnose root cause.",
    "Simulate what happens if 15 MW is discharged from battery BESS_SUB_01.",
    "Run mathematical optimization and report schedule feasibility.",
  ];

  const handleSendMessage = async (queryText: string) => {
    if (!queryText.trim() || isProcessing) return;

    const userMessage: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: "operator",
      timestamp: new Date().toISOString(),
      text: queryText,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText("");
    setIsProcessing(true);

    try {
      const response = await ApiClient.queryCopilot(queryText);

      const botMessage: ChatMessage = {
        id: `bot_${Date.now()}`,
        sender: "copilot",
        timestamp: new Date().toISOString(),
        text: response.explanation,
        copilotResponse: response,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err: any) {
      const errMessage: ChatMessage = {
        id: `bot_err_${Date.now()}`,
        sender: "copilot",
        timestamp: new Date().toISOString(),
        text: `⚠️ Error executing copilot query: ${err.message}`,
      };
      setMessages((prev) => [...prev, errMessage]);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-130px)] flex-col p-6 space-y-4">
      {/* Top Banner / Invariant Bar */}
      <div className="flex items-center justify-between rounded-md px-5 py-3 border border-border bg-surface shadow-sm">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-spectrum-tech/15 text-spectrum-tech border border-spectrum-tech/30">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-primary tracking-wide">
              IBM Bob Command Copilot (watsonx.ai)
            </h3>
            <span className="text-[11px] text-secondary">
              watsonx.ai with 8 Analytical MCP Tools & Dispatch Guardrails
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 rounded bg-semantic-success/15 border border-semantic-success/30 px-2.5 py-0.5 text-[11px] font-semibold text-semantic-success">
            <ShieldCheck className="h-3.5 w-3.5" /> Rule B Guardrail Active (Zero Hallucination)
          </span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === "operator" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-3xl rounded-md p-4 text-xs leading-relaxed ${
                msg.sender === "operator"
                  ? "bg-copper text-white shadow-sm rounded-br-none"
                  : "bg-surface text-primary border border-border rounded-bl-none shadow-sm"
              }`}
            >
              <div className="flex items-center justify-between gap-4 mb-2 pb-1 border-b border-border/50 text-[10px] opacity-75">
                <span className="font-semibold tracking-wider uppercase">
                  {msg.sender === "operator" ? "Grid Operator" : "GridPilot AI Copilot"}
                </span>
                <span className="font-metric">{new Date(msg.timestamp).toLocaleTimeString()}</span>
              </div>

              {/* Message Body */}
              <div className="whitespace-pre-wrap">{msg.text}</div>

              {/* Extended Structured Output Metadata for Copilot Responses */}
              {msg.copilotResponse && (
                <div className="mt-3.5 space-y-2.5 border-t border-border pt-3">
                  {/* Provider & Model Badge */}
                  {msg.copilotResponse.modelId && (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase font-bold text-secondary">Inference Engine:</span>
                      <span className="rounded bg-spectrum-tech/15 border border-spectrum-tech/30 px-2 py-0.5 text-[10px] font-metric text-spectrum-tech font-semibold flex items-center gap-1">
                        <Cpu className="h-3 w-3 text-spectrum-tech" />
                        {msg.copilotResponse.provider?.toUpperCase()} ({msg.copilotResponse.modelId})
                      </span>
                    </div>
                  )}

                  {/* Tools Called Tags */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] uppercase font-bold text-secondary">Tools:</span>
                    {msg.copilotResponse.toolsCalled.map((toolName, idx) => (
                      <span
                        key={idx}
                        className="rounded bg-surface-muted border border-border px-2 py-0.5 text-[10px] font-mono text-copper"
                      >
                        {toolName}()
                      </span>
                    ))}
                  </div>

                  {/* Actions from Optimizer */}
                  {msg.copilotResponse.recommendedActions.length > 0 && (
                    <div className="rounded-md bg-semantic-success/10 border border-semantic-success/30 p-2.5">
                      <span className="font-semibold text-semantic-success text-[11px]">
                        ✓ OR-Tools Feasible Dispatch Actions:
                      </span>
                      <ul className="mt-1 space-y-1 text-[11px] text-secondary font-metric">
                        {msg.copilotResponse.recommendedActions.map((act, idx) => (
                          <li key={idx}>
                            • {act.actionType.toUpperCase()}: {act.powerMw} MW on {act.resourceId}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Uncertainty & Limitations */}
                  {msg.copilotResponse.uncertainty && (
                    <div className="text-[11px] text-secondary italic">
                      ℹ️ {msg.copilotResponse.uncertainty}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {isProcessing && (
          <div className="flex items-center gap-2 text-secondary text-xs py-2">
            <Cpu className="h-4 w-4 animate-spin text-copper" />
            <span className="font-mono">Copilot orchestrating tools & verifying optimizer bounds...</span>
          </div>
        )}
      </div>

      {/* Preset Quick Actions */}
      <div className="flex flex-wrap gap-1.5">
        {presetQueries.map((q, idx) => (
          <button
            key={idx}
            onClick={() => handleSendMessage(q)}
            disabled={isProcessing}
            className="rounded-md bg-surface-muted hover:bg-surface border border-border px-2.5 py-1 text-[11px] text-secondary hover:text-primary transition-instant text-left disabled:opacity-50"
          >
            "{q.slice(0, 48)}..."
          </button>
        ))}
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage(inputText);
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Ask operator copilot (e.g. 'Assess demand spike and compute battery dispatch')..."
          disabled={isProcessing}
          className="flex-1 rounded-md bg-surface border border-border px-4 py-3 text-xs text-primary placeholder-tertiary focus:outline-none transition-instant font-sans shadow-sm"
        />
        <button
          type="submit"
          disabled={!inputText.trim() || isProcessing}
          className="flex items-center justify-center rounded-md bg-copper hover:bg-copper-hover px-5 text-white transition-fast active:scale-95 shadow-sm disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
};
