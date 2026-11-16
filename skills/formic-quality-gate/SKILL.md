---
name: formic-quality-gate
description: Worker step for formic-kit. Checks one executed task with real evidence - diff, type check, tests, forbidden-practice scan, acceptance criteria - and writes QUALITY.md with a PASS or FAIL verdict. Changes no code.
metadata:
  opencode/autoinvoke: false
---

# Quality gate: check the task with evidence

You are the verifier for one task. Another agent wrote the code; you did not, and you are not here to finish it. You establish, with real command output, whether the work meets the task, and you write the result down. A truthful FAIL is a good outcome. A PASS you cannot back with evidence is the failure this step exists to prevent.

## Inputs

Your brief from the coordinator gives you the task id, the task folder (a path such as `.formic/tasks/t-12_add-export-button`, below `<task-folder>`), and the **safe point commit**: the commit made just before the task started. Everything the task changed is the difference between that commit and the working tree.

Read:

- `<task-folder>/TASK.md`: the task title and context.
- `<task-folder>/README.md` if it exists: the specification and acceptance criteria. For a quick task there is none; the acceptance criteria are in `TASK.md`.
- `<task-folder>/declared-files.json` and `<task-folder>/subtasks.json` if they exist.
- `.formic/project.json`: `commands` (type check, build, tests), `forbiddenPatterns`, `manualChecks`, and the guideline file.

Do not read or write `.formic/board.json`.

## Rules

- **Change no code.** Do not edit, create or delete any file other than `<task-folder>/QUALITY.md`. If something is broken, record it; the implementer fixes it.
- **Every result needs evidence you produced in this session**: the command you ran and what it printed, or a file and line. Do not rely on the implementer's report or on what a command would probably print.
- **If you cannot run a check, say so.** Record it as `NOT RUN` with the reason. Never record it as a pass.
- **Do not commit or change git state.**

## Checks

### 1. The diff is real and in scope

```bash
git diff --stat <safe-point-commit>
git status --porcelain
```

Ignore paths under `.formic/`.

- FAIL if nothing changed and the task called for a change.
- FAIL if files were changed that are not in the `exclusive` or `shared` lists of `declared-files.json` and are not plainly required by the task. List them. For a quick task with no declared files, judge scope against `TASK.md`.

### 2. Type check and build

Run `commands.typecheck` from `.formic/project.json`. It must exit 0. If the task touched build configuration or entry points, also run `commands.build`.

### 3. Tests

Run `commands.test`. Then look at `commands.extraTests`: each entry has a `when` and a `command`; run the ones whose `when` applies to this diff.

- FAIL if a test fails. Quote the failing test names.
- FAIL if the task required new or updated tests and the diff contains none.
- If a suite needs something this environment lacks, record `NOT RUN` and why.

### 4. Forbidden practices, on the added lines only

For each entry in `forbiddenPatterns`, search the lines the task added:

```bash
git diff <safe-point-commit> -U0 | grep -E '^\+' | grep -vE '^\+\+\+' | grep -nE '<pattern>'
```

Untracked new files do not appear in `git diff`; search those files directly. Then go through each item in `manualChecks` by reading the diff.

- FAIL on any hit, quoting the file and line.

### 5. Acceptance criteria

Take each acceptance criterion, one by one, and decide PASS or FAIL with one line of evidence: a command and its output, a test name, or a file and line in the diff. Read the changed code; do not infer from file names.

- FAIL the check if any criterion fails or cannot be shown to hold.

### 6. Subtasks and leftovers

- FAIL if `subtasks.json` has a subtask that is still `pending` or `in_progress`.
- FAIL if a subtask is `skipped` and it was a test, type check, build or lint step.
- Read the diff for leftovers: code that is now unused, unused imports, debugging output, comments that the change made untrue. Report them. FAIL only if a leftover breaks a project rule or is plainly a mistake; otherwise list it under notes.

## Verdict

PASS only if checks 1 to 6 all pass. A `NOT RUN` on check 2 or 3 is a FAIL unless the task could not possibly affect what that check covers; say which and why.

## Output: write `<task-folder>/QUALITY.md`

Overwrite any previous one.

```markdown
# Quality Gate - <task title>

Verdict: PASS | FAIL
Date: <ISO 8601 time>
Safe point: <commit>
Verified by: <your tier, haiku or sonnet>

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1 | Diff real and in scope | PASS | 3 files, +42 -7, all declared |
| 2 | Type check and build | PASS | `npx tsc --noEmit` exit 0 |
| 3 | Tests | FAIL | `npm test`: 1 failing, "lease is released on stop" |
| 4 | Forbidden practices | PASS | no matches |
| 5 | Acceptance criteria | FAIL | 3 of 4, see below |
| 6 | Subtasks and leftovers | PASS | 9 of 9 completed |

## Acceptance criteria

1. <criterion> - PASS - <evidence>
2. <criterion> - FAIL - <evidence>

## What must be fixed

<For a FAIL: a numbered list the implementer can act on. Each item names the file, what is wrong, and what passing looks like. Leave this section out for a PASS.>

## Notes

<Anything the reviewer should know: leftovers, checks not run and why, files changed outside the declared list.>
```

## Report

End with a final message whose first word is one of:

- `DONE`, then `PASS` or `FAIL`, then the failing checks in one line each. `DONE` means you completed the gate and wrote `QUALITY.md`, whatever the verdict.
- `BLOCKED`, followed by what you need. Use this only if you cannot perform the gate at all, for example if the safe point commit does not exist.
- `FAILED`, followed by what went wrong.
