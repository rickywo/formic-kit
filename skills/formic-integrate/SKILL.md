---
name: formic-integrate
description: Wires together parallel streams. Connects frontend to backend, verifies API contracts, and fixes integration issues.
metadata:
  opencode/autoinvoke: false
disable-model-invocation: true
---

# Integrate Skill - Wire Parallel Streams Together

You are the **integration engineer**. Both frontend and backend streams are complete. Your job is to wire them together into a working system.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

1. **Review what both streams produced:**
   - Read the frontend changes — components, views, API call shapes, event handlers
   - Read the backend changes — API routes, services, response shapes, data models
   - Read the plan's API contract for the expected interface between frontend and backend

2. **Wire frontend to backend:**
   - Connect the frontend API calls to the actual backend endpoints
   - Ensure request payloads match what the backend expects
   - Ensure response handling matches the actual backend response shapes

3. **Verify type alignment:**
   - Request/response types must match between client and server
   - Fix mismatched field names, missing fields, or type mismatches
   - Ensure error response handling is consistent

4. **Fix integration issues:**
   - Resolve CORS configuration if needed
   - Fix missing error handling at the integration boundary
   - Handle edge cases: network errors, timeouts, empty responses
   - Ensure proper loading and error states in the UI

5. **End-to-end verification:**
   - Test the full flow from UI action → API call → server processing → response → UI update
   - Verify error paths work correctly (invalid input, server errors, network failures)
   - Run the build to confirm everything compiles
   - Run tests to confirm nothing is broken

6. **Clean up integration artifacts:**
   - Remove any stubs or mock data that was used during parallel development
   - Ensure no hardcoded URLs, ports, or temporary workarounds remain

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
