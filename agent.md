# Agent Playbook: IBM Bob & Relentless Gladiators
# Bob AI Hackathon Submission Guidelines & Operational Instructions

> **File:** `agent.md`  
> **Team Name:** Relentless Gladiators  
> **Target:** Bob AI Hackathon  
> **Role:** Operational context, engineering standards, and automation guidelines for IBM Bob (BobShell) and agentic workflows.

---

## 1. Project & Mission Overview

You are working within the repository for **Team Relentless Gladiators** in the **Bob AI Hackathon**.
Your objective is to design, develop, document, and test an enterprise-grade AI solution that scores maximum points on the hackathon evaluation rubric.

### 🏆 Hackathon Evaluation Rubric (100 Points Total)
1. **Technical Implementation Quality (25 pts):**
   - Evaluators inspect actual source code in `src/`, not just documentation.
   - Code must be clean, modular, properly typed, error-handled, and tested.
2. **Innovation & Differentiation (25 pts):**
   - Solves a non-trivial problem with a differentiated approach.
   - Grounded in functional code rather than theoretical concepts.
3. **Problem Depth & Vision (15 pts):**
   - Deep understanding of the problem domain, quantifiable impact, and target persona.
   - Articulated in `docs/problem-statement.md` and `docs/solution-overview.md`.
4. **Working Demo & Functionality (15 pts):**
   - Must run reproducibly following `docs/setup-guide.md`.
   - Backed by demo artifacts (`demo/screenshots/` and `demo/demo-video-link.txt`).
5. **IBM Bob Integration (10 pts - CRITICAL):**
   - **IBM Bob must be load-bearing**, not just cosmetic or name-dropped.
   - Bob should actively execute workflows, interface via MCP servers, orchestrate tasks, or serve as the conversational command interface for the system.
6. **Documentation & Reproducibility (10 pts):**
   - Complete, clear setup instructions, architecture diagrams (Mermaid), and verified clean installs.

---

## 2. Repository Structure & Artifact Invariants

The repository structure is strictly monitored by automated GitHub Actions (`.github/workflows/validate.yml`).

```
bob-ai-hackathon-[team-name]/
├── submission.yaml          # Evaluator metadata (MUST be 100% valid YAML, no empty required fields)
├── README.md                # Human-readable front page (ZERO [placeholder] brackets allowed)
├── agent.md                 # Agent instructions & context (this file)
├── src/                     # All application source code
│   ├── .env.example         # Complete template of all required environment variables
│   └── README.md            # Explanation of src/ architecture & modules
├── docs/
│   ├── problem-statement.md # Deep-dive into problem, pain points, audience, & metrics
│   ├── solution-overview.md # Conceptual architecture, tradeoffs, and differentiation
│   ├── architecture.md      # Mermaid diagrams, component table, security & data flow
│   └── setup-guide.md       # Exact step-by-step reproduction instructions
├── demo/
│   ├── demo-video-link.txt  # Public video URL (Loom, YouTube, Box)
│   ├── live-demo-url.txt    # Deployed URL or "NOT DEPLOYED"
│   └── screenshots/         # Min 3 sequential screenshots (01-..., 02-..., 03-...)
├── presentation/
│   └── slides.pdf           # Pitch deck (Problem, Solution, Tech/Bob, Architecture, Impact)
└── .github/workflows/
    └── validate.yml         # DO NOT MODIFY: Submission validator
```

---

## 3. Strict Rules & Guardrails for Agents

### 🚫 Prohibited Actions
- **NEVER** commit `.env` or any real API keys/credentials to Git. Always use `.env.example` with dummy placeholders.
- **NEVER** leave square brackets `[...]` or unedited template text in `README.md` or docs.
- **NEVER** rename, delete, or alter the schema of `submission.yaml`.
- **NEVER** modify `.github/workflows/validate.yml`.
- **NEVER** place source code outside `src/`.

### ✅ Mandatory Quality Checks Before Any Commit
1. **Validation Check:** Verify `submission.yaml` parses without syntax errors and all `# REQUIRED` fields are non-empty.
2. **Setup Reproducibility:** Ensure any newly introduced dependency (npm, pip, docker) is documented in `docs/setup-guide.md` and added to `package.json` / `requirements.txt`.
3. **Environment Sync:** Whenever a new environment variable is referenced in code, immediately add it with an explanatory comment to `src/.env.example`.

---

## 4. IBM Bob (BobShell) Integration Architecture

To ensure the **10-point IBM Bob Integration** is fully captured, Bob must serve one or more of the following core roles:

1. **Autonomous Tool Operator via MCP:**
   - Expose backend APIs, data pipelines, or runbook triggers as a custom **MCP Server**.
   - Configure Bob via `bob mcp add` to call tools directly (e.g. log analysis, remediation triggers, watsonx querying).
2. **Agentic Orchestrator:**
   - Use Bob's headless mode (`bob run "<task>"`) in CI/CD or backend scripts to automate reasoning, triage, or code transformations.
3. **Interactive Developer / Ops Copilot:**
   - Enable operators to query system metrics, trigger deployments, or summarize incidents in natural language via BobShell.

---

## 5. Development Workflows & Commands

### Running IBM Bob Shell
- **Interactive UI:** `bob chat` (or with auto-approval for scripts: `bob chat --auto-approve`)
- **Headless Task Execution:** `bob run "Analyze logs in src/logs and trigger fix"`

### MCP Server Management in Bob
> **Note for Windows / PowerShell:** Stdio servers require a `--` separator before arguments. In PowerShell, quote the separator as ``--`` so PowerShell does not strip it:
- **Add custom stdio server:** `bob mcp add <name> <command> "--" <args...>`
  - Example: `bob mcp add project-tools node "--" ./src/mcp-server/index.js`
- **Add via raw JSON:** `bob mcp add-json <name> '<json-config>'`
- **Direct config file:** Edit [.bob/mcp.json](file:///f:/bob-ai-hackthon-Relentless-Gladiators/.bob/mcp.json) directly.
- **List servers:** `bob mcp list`
- **Remove server:** `bob mcp remove <name>`

### Verification Routine
Before pushing to GitHub, execute:
```bash
# Verify no real secrets are staged
git status

# Check for residual bracket placeholders in README
grep -n "\[" README.md

# Verify documentation existence
test -f docs/setup-guide.md
test -f demo/demo-video-link.txt
```

---

## 6. Tone & Output Format
- Deliver production-ready code with clean typing, error handling, and comments.
- Prioritize architectural clarity, security by default, and reproducible setup commands.
