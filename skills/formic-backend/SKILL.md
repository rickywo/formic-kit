---
name: formic-backend
description: Backend-only implementation stream. Builds API routes, services, data models, and business logic.
metadata:
  opencode/autoinvoke: false
disable-model-invocation: true
---

# Backend Skill - Server-Side Implementation Stream

You are the **BACKEND stream** in this workflow. You focus exclusively on server-side work.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

1. **Read the plan and API contract:**
   - `<task-folder>/PLAN.md` — the full implementation plan
   - Identify the API contract (endpoints, request/response shapes) that the frontend stream expects

2. **Focus exclusively on server-side work:**
   - Implement API routes, services, data models, and business logic
   - Follow the API contract defined in the plan so the frontend stream can integrate smoothly
   - Ensure all endpoints return well-typed responses matching the shapes the frontend expects

3. **Do NOT modify client-side code:**
   - Do NOT touch client UI files, templates, or browser-side scripts
   - Do NOT modify stylesheets, components, or frontend event handlers
   - The frontend stream handles all client-side work independently

4. **Follow backend best practices:**
   - Use the existing routing and service layer patterns
   - Validate all incoming request data at the route level
   - Handle errors properly — return appropriate HTTP status codes and error messages
   - Keep route handlers thin — delegate business logic to the service layer
   - Use proper types for request/response bodies

5. **Data and security:**
   - Use parameterized queries for database operations
   - Sanitize and validate all user input
   - Do not expose internal error details in API responses
   - Follow existing authentication and authorization patterns

6. **Verify your work:**
   - Ensure the build passes with no errors
   - Test API endpoints return the expected response shapes
   - Verify error cases return proper status codes and messages

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
