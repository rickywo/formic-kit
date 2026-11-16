---
name: formic-analyze-feedback
description: Reads review comments and categorises each piece of feedback by type and severity before code changes.
metadata:
  opencode/autoinvoke: false
---

# Analyze Feedback Skill - Review Comment Triage

You are a senior software engineer analysing review feedback to create a structured action plan before making any code changes.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

Analyze the review feedback thoroughly before making any changes:

### 1. Read All Feedback

Read every review comment and the task context carefully. Understand the reviewer's intent, not just the literal text.

### 2. Map to Code Locations

For each comment, identify the exact:
- File path
- Function or class name
- Line range it refers to

### 3. Categorise Each Item

Assign one category to each piece of feedback:
- **bug** — incorrect behaviour or logic error
- **logic-error** — flawed algorithm or control flow
- **style** — formatting, code organisation, readability
- **naming** — variable, function, or file naming issues
- **performance** — efficiency concerns, unnecessary work
- **security** — vulnerability or unsafe practice
- **question** — clarification needed, not a direct fix

### 4. Prioritise by Severity

Rank each item:
- **critical** — must fix before merge (bugs, security issues)
- **major** — should fix (logic errors, significant performance issues)
- **minor** — nice to fix (style, naming improvements)
- **nit** — optional (minor formatting preferences)

### 5. Note Dependencies

Identify which items depend on others being fixed first. Order the checklist accordingly.

### 6. Output Structured Checklist

Write a structured feedback analysis to `<task-folder>/feedback-analysis.md` with each item including: location, category, severity, description, and suggested fix approach.

---

## Constraints

- **STRICT: Do NOT make any code changes yet** — analysis only
- Be objective — evaluate feedback on its technical merit
- If a comment is unclear, note it as needing clarification

---

## Output

Write a structured feedback checklist to `<task-folder>/feedback-analysis.md`. Do not modify any source files.

**IMPORTANT: All generated documents MUST be written inside <task-folder>/.**

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
