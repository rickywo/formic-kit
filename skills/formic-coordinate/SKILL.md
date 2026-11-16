---
name: formic-coordinate
description: Run the task board of a formic-kit project (.formic/board.json) - pick the next queued task, hand each step (brief, plan, declare, execute, verify, architect) to worker agents through herdr, check their output, and move tasks across the board until they reach review. Use when the user asks to run, start, process or continue queued tasks, or to run a specific task.
---

# Coordinate: run the board

You are the coordinator. You hold the conversation with the user, you are the only writer of the board, and you decide what runs next. You do not do the tasks yourself: every step is done by a worker, and you check what comes back.

Load `formic-board` (the board tool and its rules) and `formic-dispatch` (how to run a step in a worker) before you start. Below, `board` means the `board.py` tool from `formic-board`.

## What you do and do not do

- You do: read the board, choose the next task, write briefs, dispatch workers, check their output files, update the board, and report to the user.
- You do not: write specifications, plans or code; fix a worker's output yourself; explore the codebase at length. If a step keeps failing, park the task and tell the user. Doing the work yourself hides the failure and fills your context.
- You do not delete or edit anything in a task folder except your own briefs in `output/`. Each verifier overwrites `QUALITY.md` itself.
- Keep your context small. Read worker reports and the specific output files you need to check. Do not read whole diffs or logs unless you are deciding why something failed.
- All state lives on the board and in the task folders. If this session ends, a new one can pick up from them. Never keep a decision only in your head: put it in a `--note`.

## Start-up

1. Confirm the prerequisites in `formic-dispatch` ("Before the first dispatch"), and that the project is a git repository.
2. `board validate`. If it fails, stop and tell the user what it reported.
3. Read `.formic/project.json` for `limits`. If the file is missing, tell the user that the project's check commands are not configured and that verification will be weak without them; ask whether to continue. Defaults when a limit is absent: `maxExecuteRounds` 5, `stallRounds` 2, `maxRetries` 3, `maxYields` 5.
4. Recover (next section).
5. Tell the user in two or three lines what is on the board: how many tasks are queued, active, blocked and in review.

**One task at a time.** This version of the skill runs tasks serially. If `limits.maxConcurrentTasks` is above 1, tell the user parallel runs are not supported yet and continue serially.

## Recover

A task in an active status with nobody working on it is left over from an interrupted session. `board list --active`, and for each task:

| What you find | What to do |
|---|---|
| An `agent` is recorded and `herdr agent get <name>` shows it `working` | A worker is still on it. Wait with `herdr agent wait <name>`, then carry on from "Read the report" in `formic-dispatch` |
| An `agent` is recorded and it is `idle` or `done` | The worker finished while nobody was watching. Read its report and carry on from there |
| An `agent` is recorded and it is `blocked` | Handle the permission prompt as in `formic-dispatch` |
| No agent recorded, or herdr does not know the name | The step was interrupted. `board bump <id> retry --reason "interrupted during <step>"`, then `board move <id> queued --note "recovered"`. If that takes `retryCount` to `maxRetries`, park it instead (see "Parking") |

Tell the user what you recovered.

## The loop

Repeat until there is nothing left to run:

1. **Unblock.** `board list --status blocked`. For each task whose dependencies are all in `review` or `done`, `board move <id> queued --note "dependencies met"`.
2. **Pick** the next task (below). If there is none, stop and report.
3. **Run it** through the steps for its type, until it reaches `review`, is parked in `todo`, or goes back to `queued`.
4. Tell the user the outcome in one or two lines, then go to 1.

Stop the loop and talk to the user when: the queue is empty; a task was parked; a worker reported `BLOCKED`; a permission prompt appeared; the model provider's credentials were rejected; a brief could not be delivered twice in a row; or anything about the board looks wrong. If the user asked for one specific task, run only that task.

## Pick the next task

From `board list --status queued`, choose in this order:

1. Tasks with `fix-for` set.
2. Higher priority: `high`, then `medium`, then `low`.
3. Among equals, a task that other blocked tasks depend on.
4. Oldest `queued` time.

Skip a task whose `yieldCount` has reached `maxYields` or whose `retryCount` has reached `maxRetries`; park it instead.

## Safe point

Before a task's first step, if its `safePointCommit` is empty, record the state of the repository:

```bash
git add -A && git commit --allow-empty -m "auto-save: before task t-12" && git rev-parse HEAD
board set t-12 safePointCommit=<the commit>
```

This commit is what the verifier compares against, so it has to contain everything that was in the working tree before the task began. That includes any uncommitted work of the user's. The first time in a session that you are about to make a safe point and `git status --short` shows changes outside `.formic/`, show the user the list, say that they will be included in an auto-save commit on the current branch, and ask before going on. After they have agreed once, do not ask again in that session.

A task that already has a `safePointCommit` keeps it: it is resuming, and the comparison must still start from before its first attempt.

## Steps by task type

| Type | Steps |
|---|---|
| `quick` | execute, verify |
| `standard` | brief, plan, declare, execute, verify |
| `goal` | architect, then create the child tasks |

For each step: move the task to the step's status with `board move`, dispatch the worker as in `formic-dispatch`, read the report, check the output, then act on the result.

**Resuming a standard task** that came back to `queued`: start at the first step whose output is missing from the task folder. `README.md` missing: brief. `PLAN.md` or `subtasks.json` missing: plan. Otherwise: declare. Always run declare again on a resume; the task gave up its leases when it left the active statuses.

### Acting on the worker's verdict

| Verdict | Action |
|---|---|
| `DONE`, and the output checks below pass | Go to the next step |
| `DONE`, but an output check fails | Treat as `FAILED`, with the failed check as the reason |
| `PARTIAL` (execute only) | See "Execute rounds" |
| `BLOCKED` | Show the user the worker's question, with the task id and step. When they answer, add the answer to the task context under a `## Clarifications` heading (`board set <id> --context-file ...`) and dispatch a new worker for the same step. This does not count as a retry |
| `NOT_DELIVERED`, or the brief was not delivered | Close the pane, clear the agent and dispatch a new worker for the same step, as in `formic-dispatch`. Not a retry. If the second brief is not delivered either, stop and tell the user |
| `ERROR` with `errorKind` `credentials` | Stop the loop: the model provider's sign-in has expired. Follow `formic-dispatch` ("Read the report"): no retry, leave the task where it is, ask the user to sign in again, then dispatch the step again |
| `FAILED`, `NONE`, or `ERROR` of another kind | `board bump <id> retry --reason "<step>: <why>"`. If `retryCount` is now at `maxRetries`, park the task. Otherwise `board move <id> queued --note "<step> failed: <why>"` and let the loop pick it up again |

### Output checks per step

| Step | Check before accepting `DONE` |
|---|---|
| brief | `README.md` exists and has an `Acceptance Criteria` section with at least one item |
| plan | `PLAN.md` exists. `subtasks.json` parses, has a non-empty `subtasks` list, and every subtask has `id`, `content` and `status` `pending` |
| declare | `declared-files.json` parses and has `exclusive` and `shared` lists. Then acquire leases (below) |
| execute | See "Execute rounds" |
| verify | `QUALITY.md` exists and has a line `Verdict: PASS` or `Verdict: FAIL`. See "The gate" |
| architect | `architect-output.json` passes the checks under "Goal tasks" |

Also confirm after every step that the worker did not touch the board: `board validate` must still pass.

### After plan: settle the tier

If the task's `executeTier` is empty, set it now. The plan worker's report ends with a recommendation and a reason. Follow it unless you have cause not to: `haiku` only when every subtask says exactly what to change. `board set <id> executeTier=<tier>`.

For a quick task with no tier, choose `haiku` if the context states exactly what to change, otherwise `sonnet`.

### After declare: leases

```bash
board lease <id> acquire
```

- Granted: move on to execute.
- Exit code 3 with conflicts: another task holds one of the files. With tasks run one at a time this means the holder is stuck; run "Recover" for it. If it is still held afterwards: `board bump <id> yield --reason "lease-conflict:<file> held by <task>"`, then `board move <id> queued`. At `maxYields`, park the task.

### Execute rounds

Before each execute dispatch: `board bump <id> round`, and count the subtasks in `subtasks.json` that are `completed` or `skipped`.

For a task that fixes a bug (it has `fixForTaskId`, or its context says it is a bug fix), put `Also load: formic-root-cause-fix` in the brief.

After the worker returns `DONE` or `PARTIAL`, count again:

- **Every subtask is `completed` or `skipped`** (or there is no `subtasks.json`, as for a quick task): go to verify.
- **Some remain, the count went up, and `executeRounds` is below `maxExecuteRounds`:** dispatch another round with a new worker. In the brief notes, list the ids of the subtasks that remain.
- **Some remain and the count did not go up:** that is a stalled round. After `stallRounds` stalled rounds in a row, or when `executeRounds` reaches `maxExecuteRounds`, stop repeating and go to verify anyway. The gate will record what is missing.

### The gate

Verification is done by a new worker on the task's `executeTier`, never the worker that executed. Put the task's `safePointCommit` in the brief.

Read the verdict line from `QUALITY.md`:

- **PASS:** `board move <id> review --note "gate passed"`. Leases are released by the move.
- **FAIL:** `board bump <id> retry --reason "gate: <the failing checks, briefly>"`, then:
  - `retryCount` at `maxRetries`: park the task.
  - Otherwise, if the tier is `haiku` and this is the second failure: `board set <id> executeTier=sonnet`, so that both the next execute and the next verify run on sonnet.
  - Then `board set <id> executeRounds=0`, `board move <id> running --note "gate failed: ..."`, and dispatch execute again. The execute worker reads `QUALITY.md` itself; you do not need to copy the failures into the brief.

Do not overrule the gate. If you think a FAIL is wrong, say so to the user and let them decide.

## Goal tasks

After the architect reports `DONE`, check `architect-output.json`:

- It is an array of 1 to 8 entries (3 to 8 is expected; fewer is acceptable for a small goal).
- Every entry has a non-empty `title` and `context`.
- `task_id` values are unique, every `depends_on` entry names a `task_id` in the file, and there is no cycle.

If any check fails, treat the step as `FAILED`. Do not repair the file yourself.

Then show the user the breakdown, one line per child with its dependencies and tier, and ask them to confirm before you create anything. Once confirmed, create the children in dependency order, so that each one's dependencies already have real ids:

```bash
board add --title "<title>" --context-file <file> --type standard --priority <priority> --tier <tier> \
  --parent <goal id> --status queued
board add ... --parent <goal id> --status blocked --depends-on t-21,t-22
```

A child with no dependencies is created `queued`; one with dependencies is created `blocked`. Keep a map from each `task_id` to the id the board assigned. Then `board move <goal id> review --note "split into t-21..t-26"`. The children run through the loop like any other task.

## Parking

Parking means giving up on a task for now and handing it back to the user:

```bash
board set <id> yieldReason="<why, in a sentence>"
board move <id> todo --note "parked: <why>"
```

Then tell the user: which task, which step failed, how many attempts, the last failure in the worker's or verifier's own words, and where to look (`QUALITY.md`, or the task folder). Suggest what might help, such as a clearer context or a larger tier, but do not act on it unasked.

## Reporting

When the loop stops, give the user a short summary: tasks that reached review, tasks parked and why, tasks still queued or blocked, and anything you were unsure about. Say which claims you checked yourself and which come from worker reports. Tasks in `review` are waiting for the user; offer `formic-task-review`.
