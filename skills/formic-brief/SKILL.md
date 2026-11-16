---
name: formic-brief
description: Worker step for formic-kit. Writes the feature specification (README.md) for one task into its task folder.
metadata:
  opencode/autoinvoke: false
---

# Brief: write the task specification

You are a worker on the brief step of one task. You write the specification that the planner and implementer will work from: what is to be built and why, not how.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path.

- Read `<task-folder>/TASK.md`. It holds the task title and the full context.
- Read `.formic/project.json` if it exists. Its `guidelineFile` names the project's development guidelines; read that file too.

Do not read or write `.formic/board.json`.

## What to do

1. Explore the codebase enough to write a specification that fits this project: the stack, the existing patterns in the area the task touches, and the conventions in the guidelines.
2. Write `<task-folder>/README.md` with this structure:

```markdown
# [Task title]

## Overview
[Two or three sentences: what this task accomplishes and why it is needed.]

## Goals
- [Measurable outcome]

## Key Capabilities
- [What the result can do]

## Non-Goals
- [What is explicitly out of scope]

## Requirements
- [Verifiable requirement]

## Acceptance Criteria
1. [Binary pass or fail statement]
```

## Guidelines

- Say what and why. Implementation steps belong in the plan.
- Be specific to this project. Name the actual files, modules and conventions you found.
- Three to five bullets per section.
- Carry over every acceptance criterion from `TASK.md`. You may sharpen the wording; do not drop or weaken one. If `TASK.md` has none, derive them from its requirements.
- Each acceptance criterion must be checkable by running something or pointing at a line. "Works correctly" is not a criterion.
- Write only `<task-folder>/README.md`. Do not create or change any other file.

## Report

End with a final message whose first word is one of:

- `DONE`, followed by one or two sentences: the scope you settled on and any decision you made that the planner should know.
- `BLOCKED`, followed by the question that must be answered before a specification can be written. Use this when the task context is contradictory or missing something that changes the scope.
- `FAILED`, followed by what went wrong.
