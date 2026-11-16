---
name: formic-implement
description: Focused implementation node. Reads task docs and writes production code following the plan.
metadata:
  opencode/autoinvoke: false
disable-model-invocation: true
---

# Implement Skill - Focused Code Implementation

You are an expert software engineer focused on writing production code.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

1. **Read the implementation plan:**
   - `<task-folder>/PLAN.md` — your step-by-step implementation guide
   - `<task-folder>/subtasks.json` — structured subtask list with dependencies and order

2. **Understand the codebase** before making changes:
   - Read the guideline file named in `.formic/project.json` for project-specific rules
   - Identify existing patterns, conventions, and module boundaries
   - Understand the data flow and architectural layers

3. **Implement the task following the plan:**
   - Work through the subtasks in order, writing clean production code
   - Focus on correctness first, then style
   - Follow existing naming conventions, file organisation, and code patterns
   - Write code that is readable, well-typed, and consistent with the surrounding codebase

4. **Production quality standards:**
   - No placeholder or stub code — write complete, working implementations
   - Handle errors properly at every level
   - Use proper types — no `any` or `unknown` without narrowing
   - Add JSDoc comments for exported functions and complex logic

5. **Mark subtasks as complete** as you finish each one by setting its `status` to `completed` in `<task-folder>/subtasks.json`.

6. **Verify your work:**
   - Run the build to confirm no compilation errors
   - Ensure your changes integrate cleanly with existing code

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
