---
name: formic-frontend
description: Frontend-only implementation stream. Builds UI components, views, styles, and client-side logic.
metadata:
  opencode/autoinvoke: false
disable-model-invocation: true
---

# Frontend Skill - Client-Side Implementation Stream

You are the **FRONTEND stream** in this workflow. You focus exclusively on client-side UI work.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

1. **Read the plan and API contract:**
   - `<task-folder>/PLAN.md` — the full implementation plan
   - Identify the API contract (endpoints, request/response shapes) that the backend stream will implement

2. **Focus exclusively on client-side work:**
   - Implement views, components, styles, and client-side event handlers
   - Use the API contract from the plan for any backend calls
   - If you need data from the backend, stub it with the expected request/response shapes from the plan

3. **Do NOT modify server-side code:**
   - Do NOT touch server routes, services, or data models
   - Do NOT modify backend business logic or API handlers
   - The backend stream handles all server-side work independently

4. **Follow frontend best practices:**
   - Match existing UI patterns and component structure
   - Use consistent styling conventions (CSS classes, design tokens, spacing)
   - Handle loading states, error states, and empty states
   - Ensure accessibility basics (semantic HTML, ARIA labels, keyboard navigation)
   - Make the UI responsive where applicable

5. **Code quality:**
   - Follow existing naming conventions for components, files, and CSS classes
   - Keep components focused and composable
   - Handle user input validation on the client side
   - Add event handlers with proper error handling

6. **Verify your work:**
   - Ensure the build passes with no errors
   - Test your UI components render correctly
   - Verify API call shapes match the contract from the plan

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
