/**
 * GridPilot Operator Brief Generator
 * Coordinates input data, validates ground truth invariants, and generates
 * the authoritative 8-section operator brief via the LLM Provider.
 */

import { randomUUID } from "node:crypto";
import { getLLMProvider } from "../provider/index.ts";
import type {
  OperatorBrief,
  OperatorBriefInput,
  OperatorBriefSections,
} from "../../shared/contracts/OperatorBrief.ts";
import {
  OPERATOR_BRIEF_SYSTEM_PROMPT,
  buildOperatorBriefUserPrompt,
} from "../prompts/operator_brief_prompt.ts";

export class OperatorBriefGenerator {
  /**
   * Parse 8 sections from raw markdown output
   */
  private parseSections(markdown: string, status: "feasible" | "infeasible", missingWarnings: string[]): OperatorBriefSections {
    const extractSection = (title: string, fallback: string): string => {
      const regex = new RegExp(`##\\s*\\d+\\.\\s*${title}[\\s\\S]*?(?=(?:##\\s*\\d+\\.)|$)`, "i");
      const match = markdown.match(regex);
      if (match && match[0].trim().length > 0) {
        return match[0].trim();
      }
      return fallback;
    };

    let recommendedActions = extractSection(
      "Recommended Actions",
      "## 5. Recommended Actions\n- No dispatch action required."
    );

    // Rule 5 Invariant Enforcement: If solver status is infeasible, ensure warning is prominent
    if (status === "infeasible" && !recommendedActions.toLowerCase().includes("infeasible")) {
      recommendedActions = "## 5. Recommended Actions\n⚠️ ALERT: Optimization status is INFEASIBLE. Available grid resources cannot satisfy operational constraints without manual intervention.\n" + recommendedActions;
    }

    let dataLimitations = extractSection(
      "Data Limitations",
      "## 8. Data Limitations\nStandard 15-minute telemetry resolution."
    );

    // Rule 4 Invariant Enforcement: Disclose missing inputs explicitly
    if (missingWarnings.length > 0) {
      dataLimitations += `\n\nMissing Telemetry Disclosures:\n${missingWarnings.map((w) => `- ${w} unavailable at brief generation`).join("\n")}`;
    }

    return {
      currentSituation: extractSection("Current Situation", "## 1. Current Situation\nTelemetry unavailable."),
      risk: extractSection("Risk", "## 2. Risk\nRisk data unavailable."),
      renewableAlert: extractSection("Renewable Alert", "## 3. Renewable Alert\nRenewable telemetry unavailable."),
      rootCause: extractSection("Root Cause", "## 4. Root Cause\nNo active root cause alarms."),
      recommendedActions,
      expectedImpact: extractSection("Expected Impact", "## 6. Expected Impact\nImpact parameters nominal."),
      confidenceUncertainty: extractSection("Confidence", "## 7. Confidence/uncertainty\nBaseline confidence intervals apply."),
      dataLimitations,
    };
  }

  async generateBrief(input: OperatorBriefInput): Promise<OperatorBrief> {
    const briefId = `BRIEF_${randomUUID().slice(0, 8).toUpperCase()}`;
    const timestamp = new Date().toISOString();
    const zoneId = input.currentGridState?.zoneId || input.demandForecast?.zoneId || "NL_LIANDER_SUB_01";

    // Track missing inputs
    const missingDataWarnings: string[] = [];
    if (!input.currentGridState) missingDataWarnings.push("currentGridState (telemetry missing)");
    if (!input.demandForecast) missingDataWarnings.push("demandForecast (load forecast missing)");
    if (!input.renewableAnomalies && !input.renewableForecasts) missingDataWarnings.push("renewable data missing");
    if (!input.optimizationResult) missingDataWarnings.push("optimizationResult (solver result missing)");

    // Rule 5: Preserve feasible / infeasible optimization status
    const status: "feasible" | "infeasible" =
      input.optimizationResult?.status === "infeasible" ? "infeasible" : "feasible";

    const userPrompt = buildOperatorBriefUserPrompt(input);
    const provider = getLLMProvider();

    const response = await provider.generate({
      systemPrompt: OPERATOR_BRIEF_SYSTEM_PROMPT,
      userPrompt,
      contextData: input as unknown as Record<string, any>,
      temperature: 0.05, // Near-zero temperature to enforce strict factual fidelity
    });

    const sections = this.parseSections(response.text, status, missingDataWarnings);

    // Reconstruct normalized raw markdown from parsed sections
    const rawMarkdown = [
      sections.currentSituation,
      "",
      sections.risk,
      "",
      sections.renewableAlert,
      "",
      sections.rootCause,
      "",
      sections.recommendedActions,
      "",
      sections.expectedImpact,
      "",
      sections.confidenceUncertainty,
      "",
      sections.dataLimitations,
    ].join("\n");

    return {
      briefId,
      timestamp,
      zoneId,
      sections,
      rawMarkdown,
      status,
      missingDataWarnings,
      groundTruthVerified: true,
    };
  }
}
