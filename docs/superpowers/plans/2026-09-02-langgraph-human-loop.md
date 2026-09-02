# LangGraph Human-in-the-Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pause claim workflows in LangGraph when required facts are missing, show an explicit “needs information” step in the chat, and resume the same checkpoint after the user answers.

**Architecture:** Add a checkpointer-backed claim graph with a stable `thread_id`. The graph uses `interrupt()` after deterministic rule analysis when `missing_information` is non-empty; the API serializes that interruption as a terminal `needs_input` envelope, and a follow-up request resumes it with `Command(resume=...)`. The frontend renders a dedicated clarification step and submits the values without starting a second independent workflow.

**Tech Stack:** Python, LangGraph `interrupt`/`Command`, in-memory checkpointer for local runtime, FastAPI SSE, React reducer, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-allianz-rag-design.md`

## Global Constraints

- Never calculate an indemnity from the historical 2004 manual or claim that it contains the 2025 baremo.
- Keep explicit guardrails before retrieval and preserve `session_id` for Langfuse grouping.
- A paused run must expose only serializable field labels and a stable `thread_id`; never expose secrets or local paths.
- Existing synchronous question and claim endpoints remain backwards compatible when no interruption occurs.

---

### Task 1: Model the paused claim execution

**Files:**
- Modify: `backend/src/application/models/claim.py`
- Modify: `backend/src/domain/models/claim.py`
- Test: `backend/tests/test_claim_workflow.py`

- [ ] Add a typed paused outcome carrying `thread_id`, `missing_information`, and the current evidence context.
- [ ] Write failing tests proving a paused result is distinct from a resolved `ClaimAnalysis`.
- [ ] Implement the smallest immutable model and keep existing constructors valid.
- [ ] Run the claim model/workflow tests.

### Task 2: Add a checkpointer-backed interrupt/resume graph

**Files:**
- Modify: `backend/src/infrastructure/adapters/outbound/claim_workflow/langgraph_workflow.py`
- Modify: `backend/src/application/ports/inbound/analyze_claim.py`
- Test: `backend/tests/test_claim_workflow.py`

- [ ] Write a failing test with missing facts that observes an interrupt payload and does not execute `explain`/`validate`.
- [ ] Compile the graph with a local `MemorySaver`, route `apply_rules` to a `needs_information` node, and call `interrupt({"missing_information": ...})`.
- [ ] Pass `configurable.thread_id` on initial invocation and resume with `Command(resume={"clarifications": [...]})` using the same id.
- [ ] Merge resumed clarifications into `ClaimInput` before fact extraction and return the final `ClaimExecution`.
- [ ] Verify both pause and resume tests.

### Task 3: Expose pause and resume through the envelope API/SSE

**Files:**
- Modify: `backend/src/infrastructure/adapters/inbound/api/schemas/envelope.py`
- Modify: `backend/src/infrastructure/adapters/inbound/api/routes/queries.py`
- Modify: `backend/src/infrastructure/adapters/inbound/api/schemas/claim.py`
- Test: `backend/tests/test_envelope_api.py`, `backend/tests/test_streaming_api.py`

- [ ] Add request fields `thread_id` and `resume` with validation limited to claim mode.
- [ ] Add a `needs_input` result body containing `thread_id`, `missing_information`, and a user-facing message.
- [ ] Serialize a paused workflow as `completed` SSE with `resolved_mode="clarification"` and no fabricated decision.
- [ ] Resume when `thread_id` and `resume` are supplied, preserving request/session ids.
- [ ] Verify synchronous, SSE, invalid-thread, and backwards-compatible resolved paths.

### Task 4: Render the interruption as a first-class frontend step

**Files:**
- Modify: `frontend/src/api/queries.ts`
- Modify: `frontend/src/lib/thread-state.ts`
- Modify: `frontend/src/lib/streaming-client.ts`
- Modify: `frontend/src/components/thread/assistant-message.tsx`
- Modify: `frontend/src/components/thread/thread.tsx`
- Modify: `frontend/src/routes/_index.tsx`
- Test: `frontend/tests/unit/thread-state.test.ts`, `frontend/tests/unit/assistant-message-aria-live.test.tsx`

- [ ] Add failing tests for `needs_input` state, visible “Necesita información” step, and resume payload.
- [ ] Store the paused `thread_id` and fields on the assistant message.
- [ ] Render the existing visual form as a paused workflow step, with quick “No lo sé” and free-text values.
- [ ] Submit `resume` to the same stream endpoint and display the resumed tool stages/result.
- [ ] Run frontend tests, typecheck, and build.

### Task 5: Guardrails and verification

**Files:**
- Modify: `backend/src/application/services/input_guardrails.py`
- Test: `backend/tests/test_input_guardrails.py`
- Modify: `docs/ESTADO.md`

- [ ] Ensure insults/weather are blocked before graph invocation and rendered as a clear clarification/refusal.
- [ ] Run `make check-all`, targeted pause/resume tests, and `make test-e2e`.
- [ ] Reproduce the hernia/baremo query and confirm the UI states the source limitation without an empty bubble.
- [ ] Document the checkpoint scope (local `MemorySaver`) and its production replacement requirement.

