---
name: formic-plan
description: Worker step for formic-kit. Writes the implementation plan (PLAN.md) and the subtask list (subtasks.json) for one task from its specification.
metadata:
  opencode/autoinvoke: false
disable-model-invocation: true
---

# Plan: write the implementation plan and subtasks

You are a worker on the plan step of one task. You turn the specification into a plan a different agent can follow without having seen your reasoning.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path.

- Read `<task-folder>/TASK.md` for the task title and context.
- Read `<task-folder>/README.md`, the specification written in the brief step.
- Read `.formic/project.json` if it exists, and the guideline file it names. Its `commands` are the project's type-check, build and test commands.

Do not read or write `.formic/board.json`.

## What to do

### 1. Read the code the task touches

Find the files, functions and tests involved. The plan must use real names from this codebase.

### 2. Write `<task-folder>/PLAN.md`

```markdown
# [Task title] - Implementation Plan

## Status
**PENDING** - Plan created, implementation to begin.

## Context
[One or two sentences summarising the task from README.md.]

## Implementation Overview

### Phase 1: [First logical grouping]
[What this phase accomplishes, and in which files.]

### Phase 2: [Second logical grouping]
[...]

## Key Milestones
- [Milestone]

## Success Criteria
- [Measurable outcome, matching the acceptance criteria in README.md]
```

### 3. Write `<task-folder>/subtasks.json`

This is the list the implementer works through and ticks off. Use exactly this shape:

```json
{
  "version": "1.0",
  "taskId": "t-12",
  "title": "The task title",
  "createdAt": "2026-01-01T00:00:00.000Z",
  "updatedAt": "2026-01-01T00:00:00.000Z",
  "subtasks": [
    { "id": "1", "content": "Specific action, naming the file and function", "status": "pending" },
    { "id": "2", "content": "Another specific action", "status": "pending" }
  ]
}
```

- Use the real task id and title, and the current time in ISO 8601.
- Every subtask starts as `pending`. The other values, set later by the implementer, are `in_progress`, `completed` and `skipped`.
- Five to fifteen subtasks. Each is one action that can be checked.
- Order them so that each depends only on earlier ones.
- Include subtasks for writing or updating tests.
- End with subtasks that run the project's checks, using the commands from `.formic/project.json`.

## Guidelines

- Name actual files, functions and paths.
- If the specification leaves a design choice open, make it, and state it in PLAN.md so the implementer does not have to guess.
- Stay inside the scope in README.md. Its Non-Goals are not to be planned.
- Write only `PLAN.md` and `subtasks.json` in the task folder. Do not write any code and do not change any other file.

## Report

End with a final message whose first word is one of:

- `DONE`, followed by: the number of subtasks, the design decisions you made, and your view of the execute tier. Say `haiku` if every subtask states exactly what to change and needs no design judgement, otherwise `sonnet`, with one sentence of reason. The coordinator decides; this is your recommendation.
- `BLOCKED`, followed by the question that must be answered before a plan can be written.
- `FAILED`, followed by what went wrong.
