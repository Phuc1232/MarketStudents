---
name: project-analyzer
description: >-
  Use this skill when the user asks to analyze the project codebase, inspect its architecture,
  explain technical concepts, evaluate code quality, or export a comprehensive analysis report
  and knowledge base into a .txt file.
---

# Project Deep Analyzer & Knowledge Exporter

This skill guides the agent through an end-to-end analysis of the project codebase, synthesizes technical domain knowledge, and automatically exports a structured plain-text (`.txt`) report.

## Execution Workflow (5 Steps)

### Step 1: Codebase Survey & Discovery
1. Run [scan_codebase.py](./scripts/scan_codebase.py) or inspect directories to capture file counts, line counts, and extensions.
2. Read project dependency and environment configs:
   - Dependency files: `requirements.txt`, `pyproject.toml`, or `package.json`.
   - Environment and runtime configs: `.env.example`, `.env`, `docker-compose.yml`, `alembic.ini`.
   - Application entry points: [app.py](../../../app.py), `main.py`, etc.

### Step 2: Architectural & Core Layer Analysis
1. **Foundational / Core Layer**: Inspect foundational modules (e.g., `src/Core`): database connection, ORM session factory, password hashing/security, base models, and mixins.
2. **Business Modules**: Analyze feature modules (controllers/routers, services, repositories, schemas).
3. **Data Flow**: Map data lifecycle from Request -> Router -> Dependency Injection -> Service -> ORM / Database -> Response.

### Step 3: Technical Deep-Dive & Knowledge Synthesis
1. Detail underlying technologies, libraries, and design patterns used in the codebase (e.g., Python Packages, SQLAlchemy ORM, JWT & Argon2, Asyncio, FastAPI Dependency Injection).
2. Perform line-by-line or block-level explanations for critical code segments when requested.

### Step 4: Quality Assessment & Optimization Roadmap
1. Evaluate code against [analysis_checklist.md](./references/analysis_checklist.md).
2. Identify strengths, code smells, potential vulnerabilities, and performance bottlenecks.
3. Provide actionable, prioritized recommendations.

### Step 5: Format & Export to `.txt`
1. Load layout structure from [report_template.txt](./resources/report_template.txt).
2. Populate all analysis sections with clear, concise findings.
3. Save output to `project_analysis_report.txt` at the project root (or user-specified filename) using `write_to_file`.
4. Return a concise executive summary and the path to the generated report.
