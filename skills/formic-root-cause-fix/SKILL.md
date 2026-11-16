---
name: formic-root-cause-fix
description: Execution style for formic-kit bug-fix tasks - reproduce, find the root cause, scan for siblings, add a regression test. Loaded by a worker on the execute step when the task fixes a defect.
metadata:
  opencode/autoinvoke: false
---

# Root-cause fix: bug-fix protocol

You are a worker on the execute step of a task that fixes a defect. Load and follow `formic-execute` for the general rules (inputs, subtasks, scope, report). This skill adds the order of work for a bug fix, so that one fix task means one fixed bug and not a patch over the symptom.

Below, `<task-folder>` is the task folder named in your brief.

## Phase 1: Reproduce, before changing any code

1. Restate the observed symptom from `TASK.md` in one sentence.
2. Reproduce it: run the failing command, call the function, or write a minimal script that shows the wrong behaviour. Keep the output.
3. If you cannot reproduce it, stop. Look at the git history of the affected file (`git log -p --follow -- <file>`) and at recent commits to see whether it was already fixed or the description is off. Do not fix what you cannot observe; report `BLOCKED` with what you found.

## Phase 2: Root cause

4. Trace from symptom to cause and write it as a causal chain: "X happens because function A does B, which leaves state C, so when D runs it E."
5. Separate the **defect** (the wrong code) from the **trigger** (the conditions that expose it). The fix must remove the defect, not avoid the trigger.
6. Ask whether the defect could have damaged stored state, such as data files or persisted configuration. If so, check whether existing state is already damaged and needs repair, and say so in your report.

## Phase 3: Sibling scan

7. Search for the same defect pattern elsewhere in the codebase. If the bug was a missing check before an operation, look at every other place that performs that kind of operation.
8. Fix siblings that are inside this task's declared files. List the others in your report so they can become their own task; do not fix them here.

## Phase 4: Fix and regression test

9. Make the smallest change that removes the defect. No refactoring alongside it.
10. Add a regression test that **fails without the fix and passes with it**, in the project's existing test setup. Confirm the first half: run the test against the unfixed code (for example with `git stash`, or by reverting your fix temporarily) and keep the failing output. If no test harness can express the bug, write a reproduction script and keep its output before and after.
11. Re-run the reproduction from Phase 1 and confirm the behaviour is now correct.

## Phase 5: Record

12. Write `<task-folder>/output/root-cause.md` with four headings:
    - **Root cause**: the causal chain from step 4.
    - **Fix**: the files and lines changed, and why this removes the defect.
    - **Regression test**: its name and location, and the output showing it fails without the fix.
    - **Siblings**: other occurrences found, and what was done with each.

The verifier and the reviewer read this file. Then finish with the report described in `formic-execute`, and include the root cause in one sentence.
