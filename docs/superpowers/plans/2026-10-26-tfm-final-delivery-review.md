# TFM Final Delivery Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the technical report, presentation, README and evidence package with the verified implementation so the assignment can be handed in without unsupported claims.

**Architecture:** Treat the interview brief as the delivery contract. Keep the product implementation unchanged unless review finds a concrete defect; update the written report and presentation from current, provenance-backed artifacts. Preserve known limits as findings and do not invent author history, domain approval, or institutional metadata.

**Tech Stack:** Markdown, Python/uv, pnpm/Vitest, Playwright, PowerPoint/PPTX tooling, LibreOffice/Poppler for visual review.

**Spec:** `docs/enunciado/GenAI_Interview_Instructions.docx`; current Jev design and plan under `docs/superpowers/specs/` and `docs/superpowers/plans/`.

## Global Constraints

- The live evaluation used `gpt-6-luna`; `gpt-6.1-sol` is the configured OpenAI default and has not been live-tested.
- Jev router and guard are defaults; use the 26-10 campaigns and their manifest provenance for claims.
- The final claim baseline asked for clarification in 101/110 cases; decision accuracy is scored on eight cases, so do not describe the system as a reliable claim resolver.
- Use only the synthetic golden and red-team inputs; never copy credentials or real claims into the delivery package.
- Do not assert human domain approval or personal workflow details without evidence.
- Preserve the user's pre-existing uncommitted changes in the main checkout.

## Review Focus

- Current baseline and router A/B figures must match the committed reports and manifests.
- A campaign is current only if its commit and fingerprint match the code under delivery; rerun it when they do not.
- Security results must distinguish `guard=off` from Jev guard and preserve the 3 benign controls.
- Report and slides must state missing-case denominators and claim-quality limits.
- Every referenced path must exist; every test count must match the current suite.
- The final package must include sufficient manifests and summaries to reproduce its reported metrics without secrets.

---

### Task 1: Requirements and evidence audit

**Files:**
- Read: `docs/enunciado/GenAI_Interview_Instructions.docx`
- Read: `docs/entrega/memoria.md`, `docs/evaluacion.md`, `docs/operacion.md`, `README.md`
- Read: `docs/entrega/presentacion.pptx`
- Read: current ignored evaluation manifests and summaries

- [ ] Map each brief deliverable and evaluation criterion to repository evidence.
- [ ] Verify current metrics, campaign identity, active index and model settings from artifacts.
- [ ] Compare the recorded campaign commit/fingerprint with the final branch and rerun stale campaigns on the final code.
- [ ] List inaccurate counts, broken links, placeholders and unverified claims before editing.

### Task 2: Reconcile technical report and repository documentation

**Files:**
- Modify: `docs/entrega/memoria.md`
- Modify: `docs/entrega/validacion-pendiente.md` or replace it with a final status/evidence note
- Modify: `docs/evaluacion.md`, `docs/operacion.md`, `README.md`, `docs/README.md`
- Create if useful: `docs/entrega/README.md` and sanitized reproducibility artifacts

- [ ] Update the report summary table and the README test counts from current results.
- [ ] Repair references to missing specification files and stale process-document claims.
- [ ] Make author-process wording evidence-based; remove statements that cannot be verified.
- [ ] Include a traceability matrix for requirements, implementation, validation and known limits.
- [ ] Preserve caveats, mark unverified integrations, and keep evaluation artifacts reproducible.

### Task 3: Review and update the defense presentation

**Files:**
- Modify: `docs/entrega/presentacion.pptx`

- [ ] Inspect every current slide and preserve its visual system.
- [ ] Make the implementation plan, milestones, assumptions, risks and technical rationale explicit.
- [ ] Add the current evaluation and Jev results, with denominators and claim-quality limitation.
- [ ] Render and inspect all slides; correct content, overflow and layout issues.

### Task 4: Validate and integrate the delivery changes

**Files:**
- Final review of changed report, slides, README and evidence manifest

- [ ] Run backend, frontend, OpenAPI and E2E gates; distinguish environment failures from product failures.
- [ ] Verify no credentials or ignored runtime results are staged unintentionally.
- [ ] Check links, numbers, dates, model names and `git diff --check`.
- [ ] Commit the final delivery changes on this isolated branch and fast-forward local `main`; do not push.
