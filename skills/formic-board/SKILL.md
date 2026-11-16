---
name: formic-board
description: Board protocol for the formic-kit coordinator. How to read and change .formic/board.json safely with the bundled board.py tool - schema, statuses, allowed transitions, task ids, file leases. Load before touching the board.
metadata:
  opencode/autoinvoke: false
---

# Board protocol

`.formic/board.json` is the shared state for every task in this project. This skill is for the coordinator. Workers never read or write the board; they get what they need from their brief and from `TASK.md` in their task folder.

## Rules

1. **One writer.** Only the coordinator session changes the board. Never ask a worker to do it.
2. **Every change goes through `board.py`.** Do not edit `board.json` with a file-editing tool. The tool validates the whole board before each write, keeps a backup, and writes atomically. A hand edit skips all three.
3. **The tool guards integrity; you make the decisions.** It will refuse an illegal status change or a conflicting lease. It will not tell you which task to run next or when to retry. Those rules are in `formic-coordinate`.
4. **If the tool reports an error, stop and read it.** Do not reach for `--force` to get past it. `--force` exists for repairing a board by hand and needs a `--note` saying why.

## The tool

`scripts/board.py` in this skill's folder. Python 3 standard library only. Run it from the project root (it finds `.formic/` by walking up from the current directory), or pass `--root <project>` before the command.

Below, `board` stands for `python3 <this skill's folder>/scripts/board.py`.

| Command | Use |
|---|---|
| `board list` | One summary per task: id, status, type, priority, tier, counters, dependencies with their status, lease count, agent |
| `board list --status queued` | Filter by status; repeat `--status` for several |
| `board list --active` | Tasks in an active status |
| `board list --json` | Same data as JSON, without context and history |
| `board show t-12` | One task in full |
| `board add --title "..." --context-file <file> [--type standard\|quick\|goal] [--priority high\|medium\|low] [--tier haiku\|sonnet] [--status todo\|queued\|blocked] [--parent t-5] [--depends-on t-6,t-7] [--fix-for t-3]` | Create a task. Assigns the id, creates the task folder and writes `TASK.md` into it. Prints `{"id", "status", "docsPath"}` |
| `board move t-12 planning --note "brief written"` | Change status. Checked against the transition table |
| `board set t-12 executeTier=sonnet priority=high` | Set simple fields. Add `--context-file <file>` to replace the context. Rewrites `TASK.md` |
| `board agent t-12 --name t12-plan --pane w4:p2 --session ses_... --step plan --tier sonnet` | Record the worker running the current step. `board agent t-12 --clear` removes it |
| `board bump t-12 retry --reason "plan step failed: ..."` | Add 1 to `retryCount`, `yieldCount` (`yield`) or `executeRounds` (`round`) |
| `board lease t-12 acquire` | Read `declared-files.json` from the task folder and take the leases, all or nothing. Exit code 3 and a `conflicts` list if another task holds any of the files |
| `board lease t-12 release` | Drop the task's leases |
| `board leases` | Every lease held, by file |
| `board validate` | Check the whole board. Exit 1 and a list of problems if invalid |
| `board init` | Create an empty board in a project that has none |
| `board migrate` | Convert a board written by the Formic server. Keeps the original as `board.json.v1-<timestamp>` |

Long text such as a task context goes in a file and is passed with `--context-file`; do not put it on the command line.

## Task fields

| Field | Meaning |
|---|---|
| `id` | `t-N`. Assigned by `add`, never reused |
| `title`, `context` | What the task is. `context` is the full specification you wrote at intake |
| `type` | `standard` (brief, plan, declare, execute, verify), `quick` (execute, verify), `goal` (architect, then child tasks) |
| `priority` | `high`, `medium`, `low` |
| `executeTier` | `haiku` or `sonnet`: which worker executes and verifies the task. `null` until decided |
| `status` | See below |
| `docsPath` | The task folder, `.formic/tasks/<id>_<slug>`. Never changes |
| `workflowStep` | The last step dispatched: `brief`, `plan`, `declare`, `execute`, `verify`, `architect`. Set by `board agent` |
| `dependsOn` | Task ids that must reach `review` or `done` before this one may be queued |
| `parentGoalId`, `childTaskIds` | Links between a goal and the tasks it was split into |
| `fixForTaskId` | Set when this task fixes another; fix tasks run first |
| `declaredFiles`, `leases` | Files the task declared, and the ones it currently holds. Set by `lease acquire` |
| `agent` | The worker on the current step: herdr name, pane id, opencode session id, step, tier. `null` when no step is running |
| `safePointCommit` | The git commit made just before the task first ran |
| `retryCount`, `yieldCount`, `executeRounds` | Counters. Reset when a task is queued from `todo` or `blocked` |
| `yieldReason` | Why the task was last sent back or parked |
| `history` | Every status change and counter bump, with time and note. Written by the tool |

## Statuses and transitions

Waiting: `todo`, `queued`, `blocked`. Active: `briefing`, `planning`, `declaring`, `running`, `verifying`, `architecting`. Finished: `review`, `done`.

| From | Allowed next |
|---|---|
| `todo` | `queued` |
| `blocked` | `queued` (only when every `dependsOn` task is in `review` or `done`) |
| `queued` | `briefing`, `planning`, `declaring`, `running`, `architecting` |
| `briefing` | `planning`, `queued` |
| `planning` | `declaring`, `queued` |
| `declaring` | `running`, `queued` |
| `running` | `verifying`, `queued` |
| `verifying` | `review`, `running`, `queued` |
| `architecting` | `review`, `queued` |
| `review` | `done` |
| any | `todo` (stop, park, or send back for a re-run) |

Things to know:

- `running` cannot go straight to `review`. Every executed task passes through `verifying`.
- A task goes back to `queued` from an active status when a step failed and will be retried, or when it could not get its leases.
- Moving a task out of an active status to a waiting or finished one releases its leases and clears its agent. You do not need to do either by hand.
- Moving `todo` or `blocked` to `queued` resets the counters. Moving an active task back to `queued` keeps them, so retries accumulate.

## Leases

A lease says "this task is editing this file". `exclusive` means no other task may hold the file at all. `shared` means other tasks may also hold it as shared, for files such as `package.json` that several tasks touch lightly.

`board lease <id> acquire` grants everything in the task's `declared-files.json` or nothing. If it reports conflicts, the task has not been given any lease. What to do next is in `formic-coordinate`.

## When something is wrong

- **`not valid JSON`**: the board file is damaged. Do not continue. Tell the user, and offer to restore `.formic/board.json.backup`, which is the board as it was before the last write.
- **`refusing to write an invalid board`**: your change would break a rule, or the board was already inconsistent. Run `board validate` to see every problem, and fix the cause.
- **`board is locked by another process`**: another `board.py` is mid-write. Wait a moment and retry once. If it persists, another coordinator may be running against this project; tell the user.
