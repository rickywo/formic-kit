---
name: formic-task-review
description: Evidence-based review of tasks in the review status of a formic-kit board (.formic/board.json). Checks that the work landed against the acceptance criteria and gives an APPROVE or RE-RUN verdict per task; the user decides. Supports a batch over the whole review column.
---

# Task review: verdicts for the review column

Tasks pile up in review when approving one means investigating it. This skill does the investigation and gives the user a verdict with evidence, so that they only have to confirm.

You are the coordinator when you use this skill. Load `formic-board` for the board commands; `board` below means its `board.py`. You recommend; the user decides. Do not move a task to `done` or send it back until they say so.

**Usage:** one task ("review t-12") or the whole column ("review everything in review").

## Per task

### 1. Load the task

- `board show <id>`: note `docsPath`, `safePointCommit`, `type`, `executeTier`, and the last few `history` entries.
- In the task folder: `TASK.md`, `README.md` (acceptance criteria), `PLAN.md`, `subtasks.json`, `declared-files.json`, `QUALITY.md`, and `output/root-cause.md` for a bug fix.
- A goal task has no code of its own. Review it by checking that its children exist on the board and cover the goal; report the children's statuses.

### 2. Find the actual changes

```bash
git diff --stat <safePointCommit>
git status --porcelain
```

Ignore paths under `.formic/`. If later tasks have run since, the diff from this task's safe point includes their work too: narrow it to this task's `declared-files.json`, and say in your verdict that you did. If `safePointCommit` is missing (an older task), find the window with `git log --oneline | grep "before task <id>"`.

Read the diff itself, not only the stat.

### 3. Check against the acceptance criteria

`QUALITY.md` is the verifier's report. Use it as a guide to where to look, not as the answer: it was written by a worker, and you are the second check.

- Is its verdict PASS, and is it for the current state of the code? Compare its date with the task's last `running` entry in `history`.
- Spot-check its evidence. Rerun the type check and the tests from `.formic/project.json` on the current tree. Open the file and line cited for at least the criteria that matter most.
- For each acceptance criterion, record PASS or FAIL with your own one line of evidence.
- The diff is not empty for a task that called for a change.
- For a task that produced something other than code, open what it produced and confirm it matches the request.

### 4. Verdict

- **APPROVE**: every criterion passes. Say so plainly, with the evidence table.
- **RE-RUN**: at least one criterion fails. Quote the failing criteria and the evidence, and the likely cause if you can tell. Draft the text to append to the task context so the next run does not repeat the mistake.
- If the problem is a defect in work that otherwise landed, recommend a new fix task (via `formic-task-craft`, with `--fix-for <id>`) instead of a re-run.

Then say which parts you verified yourself and which you took from `QUALITY.md`.

### 5. Act on the user's decision

- Approve: `board move <id> done --note "approved by user"`.
- Re-run: append the feedback under a `## Review feedback` heading in the context and clear the safe point, so the next run is compared against the repository as it is now (`board set <id> safePointCommit= --context-file <file>`). Then `board move <id> todo --note "re-run: <reason>"`. Ask whether to queue it.

## Batch

1. `board list --status review`, oldest `completedAt` first.
2. Run the per-task procedure on each.
3. Give the summary table first, details after:

| Task | Title | Verdict | Blocking issue |
|------|-------|---------|----------------|
| t-1  | Merge per-step logs | APPROVE | none |
| t-2  | ... | RE-RUN | criterion 3: no regression test |

4. End with a one-line list of actions for the user to confirm, for example "Approve t-1 and t-3; re-run t-2 with the feedback above".
