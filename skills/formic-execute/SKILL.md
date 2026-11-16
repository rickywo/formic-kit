---
name: formic-execute
description: Worker step for formic-kit. Implements one task by working through its plan and subtasks (or, for a quick task, directly from TASK.md), updating subtasks.json as it goes.
metadata:
  opencode/autoinvoke: false
---

# Execute: implement the task

You are a worker on the execute step of one task. You write the code. A different agent will check your work afterwards against the acceptance criteria, using real command output, so a claim you cannot back with a diff or a passing command will be found.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. The brief also says which round this is, and may name another skill to load for the style of work (for example `formic-root-cause-fix` for a bug fix).

Read, in this order:

1. `<task-folder>/TASK.md`: the task title and context.
2. `.formic/project.json` if it exists, and the guideline file it names. All code you write must follow those guidelines. Its `commands` are the project's type-check, build and test commands.
3. `<task-folder>/PLAN.md`, `<task-folder>/subtasks.json` and `<task-folder>/README.md`, if they exist.
4. `<task-folder>/QUALITY.md`, if it exists. It is the report from a previous check of this task. Every failing check in it is something you must fix in this round.

If there is no `PLAN.md` or `subtasks.json`, this is a quick task: `TASK.md` is the whole specification. Implement it directly.

Do not read or write `.formic/board.json`.

## What to do

1. **Understand the code first.** Read the files you will change and their callers and tests. Match the conventions already there.
2. **Work through the subtasks in order.** In round 1, start at the first. In a later round, work only on the subtasks that are not `completed` or `skipped`, plus anything listed as failing in `QUALITY.md`.
3. **Keep `subtasks.json` current.** When you finish a subtask, set its `status` to `completed`, add `completedAt` with the current ISO 8601 time, and update the top-level `updatedAt`. Do this as you go, not at the end; if you are interrupted, the file is how the next round knows where you stopped.
4. **Stay in scope.** Change the files in `<task-folder>/declared-files.json` if it exists. If the work turns out to need a file that is not listed, make the change only if it is small and clearly required, and name the file in your report. If it needs substantial work outside the list, stop and report `BLOCKED`.
5. **Verify before you report.** Run the type check and the tests from `.formic/project.json`. Fix what your change broke. Re-read your diff (`git diff`) for unintended edits.

## Rules

- **Skipping.** Mark a subtask `skipped` only when it needs subjective human judgement or access to an external system you do not have. Writing tests, running tests, type-checking, building and linting are never skipped, even when they need setup or failed on an earlier attempt.
- **Do not commit, push, or change git history.** Leave your changes in the working tree.
- **Do not weaken a check to make it pass.** No deleting or loosening a test, and no suppressing a type error, unless the task asks for exactly that.
- **No new dependencies** unless the task context asks for one.
- If a requirement is ambiguous in a way that changes the result, do not guess. Report `BLOCKED` with the question.

## Report

End with a final message whose first word is one of:

- `DONE`, followed by: what you implemented, every file you created or changed, the checks you ran with their results, any subtask you skipped and why, and any file you touched outside the declared list. `DONE` means every subtask is `completed` or legitimately `skipped`.
- `PARTIAL`, followed by which subtasks remain and why you stopped. Use this when you made progress but ran out of room in this round.
- `BLOCKED`, followed by the question or decision you need.
- `FAILED`, followed by what went wrong and what state the working tree is in.
