---
name: coding-define-to-plan
description: Standard workflow for coding agents before writing any code - "Define Business → Plan". Phase 1 defines the business (problem, users, business rules, scope, acceptance criteria); Phase 2 produces a technical plan as a separate file the user can read and control (codebase survey, design, file layout, task breakdown, test strategy, risks); implementation then writes each feature into its own file. Use this skill whenever the user asks to build a new feature, app, module, API, integration, refactor or migration, or gives a request that is non-trivial or ambiguous, e.g. "build feature X", "implement this", "design this system", "write a spec/plan first", "plan before coding", "làm tính năng X", "xây hệ thống Y", "lên kế hoạch trước khi code". Use it BEFORE writing any implementation code. Skip only for trivial fixes (typo, one-line bug, rename) where requirements are already unambiguous.
---

# Coding: Define Business → Plan

A two-phase workflow that **must run before writing code** for any non-trivial request. Goal: build the right thing, in the right place, the right way, instead of coding fast and redoing it later.

```
[Triage] → [Phase 1: DEFINE] → GATE A → [Phase 2: PLAN → write 02-plan.md] → GATE B (user reads/edits/approves the file) → Implement
```

**Hard rule: do not write implementation code (do not modify source files) until Gate B is passed**, unless the user explicitly says "skip the plan, just do it". You may read code, run read-only commands, and create spec/plan documents.

## Principles

1. **Business first, technology second.** Understand *why* and *for whom* before choosing *how*.
2. **Don't guess what you can read.** For questions about code, structure, or conventions, survey the repo yourself. Only ask the user what the repo cannot answer (intent, priorities, business rules).
3. **Ask few, ask batched.** At most 5 questions per turn, each with a proposed default so the user can just say "ok".
4. **Surface assumptions.** Mark anything uncertain as `[ASSUMPTION]`; high-risk assumptions must be asked, not decided silently.
5. **Smallest thing that works.** Prefer the simplest solution that satisfies the acceptance criteria; state what is *deliberately not done*.
6. **Follow existing repo conventions** (structure, naming, libraries, test style) instead of importing your own habits.
7. **Every task must be verifiable.** A task with no way to verify it is not yet a task.
8. **The plan is a separate file, controlled by the user.** The technical plan is always written to a file the user can read, edit, and approve. That file is the single source of truth for implementation; never keep the "real plan" only in your head or in chat.
9. **Each feature is coded into its own file.** Implementation code is split by feature/responsibility into separate files that are easy to read, review, and change independently. Do not pile multiple features into one large file.
10. **Use the user's language** for documents; keep technical terms and code identifiers in English.

---

## Step 0: Triage

Classify the request to choose the depth:

| Size | Signals | Depth |
|------|---------|-------|
| **Small** | Touches 1-2 files, behavior is clear | Define in 3-5 lines in chat; plan is a short file (3-5 tasks) |
| **Medium** | One feature, a few modules | Short Define; plan file of 1-2 pages |
| **Large** | New system, architecture change, migration, touches data/money/security | Both documents in full, with phased release |

**Phase 2 always produces a separate plan file, at every size**, so the user can read and control it (see Phase 2). Size only decides how long the file is. For **Small** requests keep the plan file tight (a few dozen lines) and don't impose heavy ceremony.

Also determine: new project or existing repo, runtime environment, and who approves.

---

## Phase 1: DEFINE (business definition)

Goal: a **Business Definition** that someone who never reads the code can use to understand what must be built and when it counts as done.

### 1.1 What to clarify

| Item | Core questions |
|------|----------------|
| **Context & problem** | Where is the pain? How is it done today (manually/other tools)? Why now? |
| **Users & roles** | Who uses it (actors/roles)? Who is indirectly affected? What are the permissions? |
| **Desired outcome** | What does success look like and how is it measured? |
| **Main business flow** | Step by step, what do users/system do (happy path), as user stories or a short sequence. |
| **Business rules** | Formulas, conditions, states, limits, rounding, time zones, currency, regulations. |
| **Edge cases & errors** | Empty/duplicate data, concurrency (races), cancellation midway, wrong permissions, external system failures. |
| **Scope** | **In scope / Out of scope** (explicitly list what is deliberately not done). |
| **Non-functional constraints** | Performance, scale, security, privacy, audit log, accessibility, i18n, compatibility. |
| **Integrations & dependencies** | Related systems/APIs/teams; legacy data that must stay compatible. |
| **Glossary** | Easily misunderstood domain terms, each defined with one meaning. |

### 1.2 How to gather

1. Read everything the user provided (request, files, links, tickets) and fill in what can be inferred.
2. If a repo exists: skim the README, docs, and relevant code to understand current behavior (see 2.1) before asking.
3. Ask only for what's missing, prioritized by impact: business rules > scope > edge cases > non-functional.
4. If the user says "you decide", pick a reasonable default, mark it `[ASSUMPTION]`, and state it in the document.

### 1.3 Acceptance criteria (mandatory)

Write them so they can be verified, preferably Given/When/Then:

```
AC-1: Given an unauthenticated visitor, When they open /orders, Then they are redirected to the login page (302).
AC-2: Given an order over 10,000,000 VND, When paying, Then OTP verification is required.
```

Every business rule and every important edge case must have at least one matching AC. Vague criteria like "fast" or "user-friendly" must be quantified or dropped.

### 1.4 Phase 1 output

Save to `docs/specs/<feature-name>/01-business-definition.md` (or present in chat for Small/Medium requests when the user doesn't need a file):

```markdown
# Business Definition: [Name]
**Status:** Draft | **Updated:** [date]

## 1. Context & problem
## 2. Users & roles
## 3. Desired outcome (success measures)
## 4. Main business flow
## 5. Business rules
## 6. Edge cases & error handling
## 7. Scope (In / Out)
## 8. Non-functional constraints
## 9. Integrations & dependencies
## 10. Glossary
## 11. Acceptance criteria (AC-1, AC-2, ...)
## 12. Assumptions & open questions
```

---

## GATE A: Define → Plan

Move to Phase 2 only when:

- [ ] Problem and desired outcome are clear and can be summed up in one sentence.
- [ ] In/out of scope is settled.
- [ ] Main business rules have no remaining ambiguity.
- [ ] Verifiable acceptance criteria exist.
- [ ] High-risk assumptions have been confirmed by the user.

Not met: state exactly what is missing and ask. Met: summarize the Definition (≤ 10 lines) and ask the user to confirm before continuing. For Small requests, confirmation may be implicit if the request is already clear.

---

## Phase 2: PLAN (technical plan)

Goal: a plan that another person (or the agent in a later session) can execute step by step without guessing, **written to its own file so the user can read and control it**.

**Phase 2 output rules:**
- The result of Phase 2 is **one standalone Markdown file**: `docs/specs/<feature-name>/02-plan.md` (if the repo already has another documentation folder such as `docs/`, `plans/`, `.claude/plans/`, follow that convention). Do not paste the whole plan into chat instead of writing the file.
- Only **create documentation files**; do not touch source code yet. Phase 2 ends when the plan file is written.
- In chat, send only: the **file path** + a summary of ≤ 10 lines (approach, number of tasks, the 2-3 biggest risks, open questions).
- The plan file must **stand alone**: the user can open it by itself and understand it without chat history.
- Write it to be **easy to review and hand-edit**: clear headings, numbered tasks, a `- [ ]` checkbox on every task, and decisions the user must make in a dedicated section "Decisions needed from you".

### 2.1 Codebase survey (mandatory if a repo exists)

Before designing, investigate and briefly record:

- **Structure & stack**: language, framework, build/test/lint commands, how to run locally.
- **Touchpoints**: files/modules/DB tables/endpoints that will be affected (with concrete paths).
- **Existing patterns to imitate**: a similar feature already in the repo, naming conventions, error handling, logging, tests.
- **Dependencies & blast radius**: who calls the code you'll change, whether the change breaks compatibility.
- **Current state**: do tests pass today? Are there pre-existing failures to distinguish from ones you cause?

Use targeted search and reading, not blanket reading. If the repo is empty, choose a stack based on the Phase 1 constraints and state why.

### 2.2 Solution design

Include the relevant parts (drop what doesn't apply):

- **Approach overview** (3-6 sentences) and **rejected alternatives** with reasons.
- **File layout (mandatory)**: map each feature/responsibility to **its own file** with a concrete path, stating *new* or *modified*. Split by layer where sensible (route/controller, service/business logic, repository/data, model/schema, validator, util, test). Follow the repo's directory conventions.
- **Architecture/components**: new/changed modules, each part's responsibility, data flow (text diagram or mermaid if helpful).
- **Data model**: tables/fields/indexes/constraints, **migration** (up and down), handling of existing data.
- **API/interface**: endpoints, request/response, error codes, versioning, backward compatibility.
- **Business rules → where implemented**: where each Phase 1 rule lives (explicit mapping).
- **Non-functional**: security (authn/authz, input validation, secrets), performance, observability (logs/metrics), config/feature flags.

### 2.3 Task breakdown

Split into **small, relatively independent tasks in dependency order**, each small enough to finish and verify in one working session. Format:

```
- [ ] T1. [Short title, starts with a verb]
  - Work: concrete description
  - Files: `path/to/file_a.ext` (new) | `path/to/file_b.ext` (modified)
  - Depends on: (none) | T-x
  - Verify: command/test/observable behavior that proves it's done
  - Covers: AC-1, AC-3
```

Checkboxes let the user see progress and strike out, delete, or reorder tasks directly in the file.

Task rules:
- Every task has a concrete **Verify**; if it doesn't, rewrite it.
- Every AC is covered by at least one task; include an AC → Task → Test traceability table.
- Put risky/uncertain tasks early (a spike, or a thin vertical slice that runs end to end first), then widen.
- Each task should leave the repo with a green build/tests; separate refactors from behavior changes.

### 2.4 Test strategy

- Test pyramid: unit tests for business rules, integration tests for DB/API, e2e for the main flow.
- List the main test cases, mapped to ACs and edge cases.
- Test data, mocks/stubs for external systems, the command to run tests.
- For bug fixes/refactors: first write a test that reproduces the bug or characterizes current behavior.

### 2.5 Rollout & rollback

- Release order, feature flags, when migrations run, rollback plan.
- Backward compatibility and how legacy data/customers are migrated.
- Config changes, environment variables, documentation to update.

### 2.6 Risks

Table: `Risk | Likelihood | Impact | Mitigation / early detection`. Always consider: data loss/corruption, security, performance under load, third-party dependencies, compatibility breaks.

### 2.7 Phase 2 output: the `02-plan.md` file

Write the file with this structure (drop sections that don't apply, but keep those marked ★):

```markdown
# Technical Plan: [Name]
**Based on:** 01-business-definition.md
**Status:** Draft | Approved | In progress | Done
**Last updated:** [date]

## ★ 0. Decisions needed from you
(Points the agent cannot decide alone, each with a proposed default. The user edits them right here.)
- [ ] Q1: ... → Proposed: ...

## 1. Approach summary
## 2. Codebase survey results
## 3. Design (architecture, data, API, security)
## 4. Map of features & business rules → implementation files
(Table: Feature/Rule | File | New/Modified | File's responsibility)
## 5. Task list (T1..Tn)
## 6. Traceability: AC → Task → Test
## 7. Test strategy
## 8. Rollout & rollback
## 9. Risks
## 10. Out of scope / later
## 11. Open questions
## ★ 12. Change log
(Record every time the plan changes: date, who, what, why. Also used when the agent must adjust the plan during implementation.)
```

---

## GATE B: User approves the plan file

1. After writing `02-plan.md`, **stop**. In chat, report only: the file path, a summary of ≤ 10 lines, and invite the user to open the file and edit it directly if needed (especially "Decisions needed from you" and the task list).
2. Wait for explicit confirmation ("approved", "go ahead"...) or change requests. Silence is not approval.
3. When the user returns, **re-read `02-plan.md` from the top** before doing anything, since they may have edited it by hand. The user's edits in the file **win** over the agent's memory. If edits conflict with the Definition or with each other, ask instead of choosing.
4. When the user requests changes verbally, update the file (don't just answer in chat), record it in the Change log, then briefly report what changed.
5. Once approved, set **Status** in the file to `Approved` and only then begin writing code.

**Only start writing code after Gate B.** For Small requests, still create a short plan file; you may proceed immediately if the user already said "go ahead" in the same request, but the plan file must still exist for them to check against.

## After approval: implementation

- **`02-plan.md` is the source of truth.** Follow that file, not memory or chat drafts.
- Work through tasks in order; after each task run its **Verify** step, then tick `- [x]` for that task in the plan file and set Status to `In progress`.
- If you discover something that invalidates the Definition or Plan (misunderstood business rule, infeasible design): **stop, update the plan file (with a Change log entry), tell the user,** and wait for agreement instead of quietly drifting.
- Do not add, remove, or reorder tasks relative to the approved file without permission. Changes outside the approved scope must be asked first.
- When finished, check every AC, set Status to `Done`, and report: what was achieved, which tests ran, what remains.

## Coding rule: one file per feature

During implementation (after Gate B), the agent **writes each feature's code into its own file**, exactly as mapped in section 4 of the plan file:

1. **Split by feature/responsibility.** One file = one feature or one clear responsibility (e.g. `order_service`, `order_validator`, `order_repository`, `order_routes`); never merge unrelated features into one file.
2. **Create files with real file writes** (create/edit files in the repo), not by pasting code into chat. In chat, only list the files created/modified with a one-line description each.
3. **Use the approved paths.** File names and locations follow the plan; if a file outside the plan is needed, update section 4 and the Change log first and tell the user.
4. **Keep files readable.** If a file grows too long or takes on multiple responsibilities, split it further (guideline: a file should be readable in one sitting, a few hundred lines at most). When modifying an existing file, keep changes small and focused.
5. **Give each file a short header** (a one- or two-line comment/docstring stating the file's purpose and related ACs, e.g. `AC-2`) so readers can trace back to the business requirement.
6. **Tests go in their own files too**, placed alongside the source file per convention (e.g. `order_service` ↔ `order_service.test`).
7. **Explicit imports/dependencies** between files; avoid circular dependencies. Shared functions/classes live in their own file rather than being copied.
8. **Follow task order**; after each task, every file should be in a runnable state before ticking `[x]` in the plan.
9. **Final report** includes a table: `File | New/Modified | Feature | Related AC/Test`, so the user can read and control each file.

## Common situations

- **One-line, very vague request** ("build me a booking system"): offer 2-3 concrete interpretations with a proposed default; don't fire 10 questions at once.
- **User already has a spec/PRD/ticket**: read it, check it against Gate A, ask only for what's missing, then go straight to Phase 2.
- **Bug fix**: Define = expected vs actual behavior + reproduction steps; Plan = root cause, scope of fix, regression tests.
- **Refactor/migration**: Define = why, which behavior must stay the same, a "no behavior change" criterion; Plan emphasizes characterization tests first and small reversible steps.
- **User wants to skip the plan**: respect it, but state the main risk in 1-2 sentences and still record the assumptions in a minimal plan file.
- **User wants a single file** (small script, demo): comply, but still divide it into clearly labeled sections by feature with header comments, and note it in the plan.
- **Multi-session project**: record status (which tasks are done, what's in progress, decisions made) in `02-plan.md` so a later session can resume just by reading the file, with no context lost.