---
name: formic-dispatch
description: How the formic-kit coordinator runs one step of a task in a worker agent through herdr - which tier and skill each step uses, the brief template, starting the worker in a new pane, waiting, reading its report, handling permission prompts, and closing the pane. Requires running inside herdr.
metadata:
  opencode/autoinvoke: false
---

# Dispatch: run one step in a worker

This skill is for the coordinator. It covers the mechanics of handing one step of one task to a worker and getting the result back. What to dispatch and what to do with the result is in `formic-coordinate`.

A worker is a fresh opencode agent in its own herdr pane. It knows nothing about this conversation. Everything it needs must be in the brief you send or in the task folder. One worker per step; never reuse a worker for a second step.

## Before the first dispatch

```bash
test "${HERDR_ENV:-}" = 1 && echo inside-herdr
opencode agent list | grep -E '^worker-(haiku|sonnet)'
```

If you are not inside herdr, or either worker agent is missing, stop and tell the user. Do not fall back to another way of running workers without asking.

## Step table

| Step | Board status | Skill the worker loads | Tier | Worker must produce (in the task folder) |
|---|---|---|---|---|
| brief | `briefing` | `formic-brief` | sonnet | `README.md` |
| plan | `planning` | `formic-plan` | sonnet | `PLAN.md`, `subtasks.json` |
| declare | `declaring` | `formic-declare` | haiku | `declared-files.json` |
| execute | `running` | `formic-execute` | the task's `executeTier` | code changes; `subtasks.json` updated |
| verify | `verifying` | `formic-quality-gate` | the task's `executeTier` | `QUALITY.md` |
| architect | `architecting` | `formic-architect` | sonnet | `architect-output.json` |

The worker agent for a tier is `worker-haiku` or `worker-sonnet`.

The verifier is always a new worker, never the one that executed.

## The brief

Write the brief to `<task-folder>/output/brief-<step>.md`, then send that file. Use this template, and leave out the lines that do not apply:

```markdown
You are a worker for formic-kit. Do one step of one task, then report.

- Task id: t-12
- Task folder: .formic/tasks/t-12_add-export-button
- Step: execute
- Round: 2 of 5                          (execute only)
- Safe point commit: 4d69bd1             (verify only)
- Also load: formic-root-cause-fix       (execute only, when the task is a bug fix or the plan names a style)

Load the skill `formic-execute` with the skill tool and follow it. Start by reading TASK.md in the task folder.

Notes from the coordinator:
<Anything the worker cannot get from the task folder: the answer to a question a previous
worker raised, which subtasks remain, what the last check failed on. Leave out if none.>

Run every shell command from the project root. Do not use `cd`; pass paths instead.
Do not read or write .formic/board.json. Do not start other agents. Do not commit.
End with a final message whose first word is DONE, BLOCKED or FAILED (execute may also use PARTIAL).
```

Keep the notes short and factual. Do not restate the task; `TASK.md` has it. The line about `cd` matters: a worker that changes directory inside a shell command can trigger a permission prompt for the parent folder.

## Run the step

Use the project root as the working directory for every command.

**1. Make a pane.** With no worker pane open, split the coordinator's pane to the right. With one already open, split that worker pane downward.

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
```

Read the new pane id from `.result.pane.pane_id`. Never guess a pane id.

**2. Start the worker.** Name it `<task id without the dash>-<step>`, for example `t12-plan`. For a repeat of the same step add the attempt: `t12-execute-2`.

```bash
herdr agent start t12-plan --kind opencode --pane <pane-id> -- --agent worker-sonnet
```

If it returns `agent_not_ready`, read the pane (`herdr agent read t12-plan --source visible`) to see why before doing anything else.

A successful return is not proof that opencode has finished starting. The first time opencode runs in a project it installs its own support files, which can take a minute, and herdr reports the agent `idle` before the screen is up. Confirm before you prompt:

```bash
herdr agent read t12-plan --source visible --lines 45 | grep -i "worker-sonnet"
```

The input box shows the agent's name (for example `Worker-Sonnet`) once it is ready. If the pane is still blank, wait ten seconds and look again, for up to two minutes. A name other than the worker you asked for means the profile did not load: close the pane and tell the user.

**3. Record it on the board**, so that a restarted coordinator can find the worker:

```bash
board agent t-12 --name t12-plan --pane <pane-id> --step plan --tier sonnet
```

**4. Send the brief and wait.**

```bash
herdr agent prompt t12-plan "$(cat .formic/tasks/t-12_add-export-button/output/brief-plan.md)" --wait --timeout 1800000
```

The command blocks until the worker stops. Give your shell tool a timeout longer than the `--timeout` value. Use 30 minutes (1800000) for brief, plan, declare, verify and architect, and 60 minutes for execute, unless `.formic/project.json` says otherwise.

Read `.result.agent.agent_status` from the response:

| Result | Meaning | What to do |
|---|---|---|
| `idle` or `done` | The worker's turn ended | Go to step 5 |
| `blocked` | Usually a permission dialog is showing | Read the pane first. If it shows "Permission required", see "Permission prompts" below. herdr sometimes reports `blocked` for a moment while a worker is running a long command: if there is no dialog, wait again with `herdr agent wait <name> --timeout <ms>` |
| error `timeout` | Your wait ran out; the worker may still be working | Do not send the brief again. `herdr agent get <name>`; if it is `working`, wait again with `herdr agent wait <name> --timeout <ms>` |
| error `agent_prompt_stalled` | herdr saw no activity after sending | Do not resend blindly. Read the pane. If it is blank, opencode was still starting and the prompt was lost: wait for the input box, then send the brief once more. If the brief is visible in the pane, it arrived: wait with `herdr agent wait <name>` |

**5. Read the report.**

```bash
python3 <this skill's folder>/scripts/worker_report.py t12-plan
```

It prints JSON: `verdict` (`DONE`, `PARTIAL`, `BLOCKED`, `FAILED`, or `NONE` if the message did not start with one of those), `message` (the worker's exact final message), `agent`, `model` and `sessionId`.

Check that `agent` is the worker you asked for. If it is not, the step ran under the wrong profile; treat it as failed and tell the user.

herdr reports a worker that finished and a worker that stopped to ask a question the same way, as `idle`. The verdict is the only way to tell them apart, so always read it.

**6. Check the output yourself.** A `DONE` verdict is the worker's claim. Confirm that the files in the step table exist in the task folder and are well-formed: JSON files parse and have the expected keys, Markdown files are not empty. `formic-coordinate` lists the checks per step.

**7. Close the pane and clear the agent.**

```bash
herdr pane close <pane-id>
board agent t-12 --clear
```

Close only panes you created in this session. Close the pane whatever the verdict was, once you have read the report. Leave it open only if you are about to show it to the user.

## Permission prompts

`blocked` means opencode is showing a "Permission required" dialog in the worker's pane, usually because the worker tried to touch something outside the project.

1. Read it: `herdr agent read <name> --source visible --lines 30`.
2. Show the user what is being asked, and for which task and step. Ask whether to allow once or reject. Do not offer "allow always".
3. Never answer a permission dialog on your own judgement, even when it looks harmless.
4. Send the answer. The dialog's options are in a row, `Allow once`, `Allow always`, `Reject`, with the first selected:
   - Allow once: `herdr agent send-keys <name> enter`
   - Reject: `herdr agent send-keys <name> right right` then `herdr agent send-keys <name> enter`

   Before pressing enter, read the pane again and confirm the option you want is the highlighted one. Dialog layouts can change between opencode versions.
5. Wait for the worker to settle: `herdr agent wait <name> --timeout <ms>`, then continue from step 5 above. After a rejection the worker's turn often ends with no final message, which reads as verdict `NONE`.

## If herdr or the worker misbehaves

- **The pane closed or the agent vanished** (`agent_not_found`): the step did not finish. Clear the agent on the board and treat the step as failed.
- **The worker is still `working` long after it should be done**: read the pane. If it is looping, interrupt with `herdr agent send-keys <name> esc`, read the report, and treat the step as failed.
- **Do not** run `herdr server stop`, close panes or tabs you did not create, or create new workspaces or tabs unless the user asks.
