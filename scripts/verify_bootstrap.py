import sys
from pathlib import Path

required_dirs = [
    "apps/web",
    "apps/api",
    "services/data",
    "services/forecasting",
    "services/renewable",
    "services/optimization",
    "agent/provider",
    "agent/tools",
    "agent/prompts",
    "agent/orchestration",
    "agent/policies",
    "shared/contracts",
    "shared/types",
    "shared/constants",
    "shared/errors",
    "database/schema",
    "database/migrations",
    "database/seed",
    "ml/datasets",
    "ml/models",
    "ml/experiments",
    "tests/integration",
    "tests/e2e",
    "docs",
    "scripts",
]

required_files = [
    "AGENTS.md",
    "CONTRIBUTING.md",
    ".env.example",
    ".gitignore",
    "README.md",
]

base_dir = Path(__file__).resolve().parent.parent

all_passed = True

print("=== Checking Module Directories ===")
for d in required_dirs:
    readme_path = base_dir / d / "README.md"
    if readme_path.exists():
        print(f"[OK] {d:<25} -> README.md exists ({readme_path.stat().st_size} bytes)")
    else:
        print(f"[FAIL] {d:<25} -> MISSING README.md")
        all_passed = False

print("\n=== Checking Governance Files ===")
for f in required_files:
    file_path = base_dir / f
    if file_path.exists():
        print(f"[OK] {f:<25} -> Exists ({file_path.stat().st_size} bytes)")
    else:
        print(f"[FAIL] {f:<25} -> MISSING")
        all_passed = False

# Verify AGENTS.md retains reference to agent.md
agents_content = (base_dir / "AGENTS.md").read_text(encoding="utf-8")
if "agent.md" in agents_content:
    print("\n[OK] AGENTS.md correctly references agent.md")
else:
    print("\n[FAIL] AGENTS.md missing reference to agent.md")
    all_passed = False

if all_passed:
    print("\n[SUCCESS] Verification PASSED: All modules and boundary documentation are in place!")
    sys.exit(0)
else:
    print("\n[FAILURE] Verification FAILED!")
    sys.exit(1)

