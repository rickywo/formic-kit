---
name: formic-dispatch
description: How the formic-kit coordinator runs one step of a task in a worker agent through herdr - which tier and skill each step uses, the brief template, starting the worker in a new pane, waiting, reading its report, handling permission prompts, and closing the pane. Requires running inside herdr.
metadata:
  opencode/autoinvoke: false
---

# Dispatch: run one step in a worker

This skill is for the coordinator. It covers the mechanics of handing one step of one task to a worker and getting the result back. What to dispatch and what to do with the result is in `formic-coordinate`.

A worker is a fresh agent of the runtime's tool (opencode or Claude Code) in its own herdr pane. It knows nothing about this conversation. Everything it needs must be in the brief you send or in the task folder. One worker per step; never reuse a worker for a second step.

## Which runtime

One machine-level setting chooses the tool that runs the workers: `opencode` or `claude` (Claude Code). Read it once at start-up and keep it for the whole session. Do not store it on the board.

```bash
grep '^runtime=' "${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config"
```

The line is `runtime=opencode` or `runtime=claude`. A missing file, a missing line, or any other value means `opencode`.

When the runtime is `claude`, read these lines from the same file the same way:

- `claude_dir=`: the folder the kit installed its skills and agents into (`install.sh --claude-dir`). A missing line means `~/.claude`. It can be a project's `.claude` folder. It says nothing about where Claude Code writes session transcripts.
- `claude_sonnet_model=` and `claude_haiku_model=`: the model ids you pass with `--model`. Below they are written `<claude_sonnet_model>` and `<claude_haiku_model>`.

Transcripts: Claude Code writes them under its own config folder, which `send_brief.sh` and `worker_report.py` look up as `$FORMIC_CLAUDE_DIR` if set, else `$CLAUDE_CONFIG_DIR` if set, else `~/.claude`, in `projects/*/<session-id>.jsonl`. They never use `claude_dir`. You need to set `FORMIC_CLAUDE_DIR` (for the scripts you run) only when the workers' Claude Code config folder differs from what those two lookups give from your environment.

## Which permission mode

The same file holds the user's choice of how workers are started. Read it once at start-up, with the runtime:

```bash
grep '^permissions=' "${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config"
```

The line is `permissions=auto` or it is absent. Only the exact value `auto` means auto. A missing file, a missing line, or any other value means `ask`.

| Mode | How workers start | Permission prompts |
|---|---|---|
| `ask` (the default) | With the tool's normal permission checks | A prompt appears in the worker's pane and you relay it to the user |
| `auto` | opencode with `--auto`; Claude Code with `--dangerously-skip-permissions` | The worker is not asked before it runs commands, edits files or reaches outside the project |

`auto` is a setting the user chose with `install.sh --permissions auto`. Never choose it yourself, never add either flag when the mode is `ask`, and never write the setting. If the user asks for it in conversation, tell them to run `install.sh --permissions auto`.

From then on, follow the `opencode` or the `claude` variant of every tool-specific step, and the `ask` or `auto` variant where a step has one. Where a step has no label, it is the same for both.

## Before the first dispatch

Both runtimes:

```bash
test "${HERDR_ENV:-}" = 1 && echo inside-herdr
```

**opencode:**

```bash
opencode agent list > /tmp/formic-agents.txt 2>/dev/null; grep -E '^worker-(haiku|sonnet)' /tmp/formic-agents.txt
```

Write the agent list to a file as shown. opencode cuts long output short when it is piped, which can hide the worker agents.

**claude:**

```bash
command -v claude
test -f "<claude_dir>/agents/worker-haiku.md" && test -f "<claude_dir>/agents/worker-sonnet.md" && echo agents-present
grep -E '^claude_(sonnet|haiku)_model=' "${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config"
```

Replace `<claude_dir>` with the saved folder (`~/.claude` if none is saved; let the shell expand `~` or `$HOME`). `claude` must be found, both agent files must exist, and both model lines must be there with a value.

If you are not inside herdr, or anything above is missing, stop and tell the user. Do not fall back to another way of running workers without asking.

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

Write the brief to `<task-folder>/output/brief-<step>.md`, then send that file. Use the template for the runtime, and leave out the lines that do not apply.

**opencode:**

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

**claude:**

```markdown
/formic-execute
You are a worker for formic-kit. Do one step of one task, then report.

- Task id: t-12
- Task folder: .formic/tasks/t-12_add-export-button
- Step: execute
- Round: 2 of 5                          (execute only)
- Safe point commit: 4d69bd1             (verify only)
- Also load: /formic-root-cause-fix      (execute only, when the task is a bug fix or the plan names a style)

Load the skill /formic-execute with the skill tool and follow it. Start by reading TASK.md in the task folder.

Notes from the coordinator:
<Anything the worker cannot get from the task folder: the answer to a question a previous
worker raised, which subtasks remain, what the last check failed on. Leave out if none.>

Run every shell command from the project root. Do not use `cd`; pass paths instead.
Do not read or write .formic/board.json. Do not start other agents. Do not commit.
End with a final message whose first word is DONE, BLOCKED or FAILED (execute may also use PARTIAL).
```

The Claude Code skills of the steps are hidden from model invocation, so the Skill tool refuses them unless the user's message names them. A worker's brief is its user message. Line 1 of the brief is therefore `/` followed by the step's skill id from the step table (`/formic-brief`, `/formic-plan`, `/formic-declare`, `/formic-execute`, `/formic-quality-gate`, `/formic-architect`), as a separate word, and an "Also load" skill is written the same way, `/<skill id>`. The skill line names the same skill with the slash. Do not put the slash word inside backticks. Without these slash words the worker cannot load its skill.

Keep the notes short and factual. Do not restate the task; `TASK.md` has it. The line about `cd` matters: a worker that changes directory inside a shell command can trigger a permission prompt for the parent folder.

## Run the step

Use the project root as the working directory for every command.

**1. Make a pane.** With no worker pane open, split the coordinator's pane to the right. With one already open, split that worker pane downward.

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
```

Read the new pane id from `.result.pane.pane_id`. Never guess a pane id.

**2. Start the worker.** Name it `<task id without the dash>-<step>`, for example `t12-plan`. For a repeat of the same step add the attempt: `t12-execute-2`.

**opencode:**

```bash
herdr agent start t12-plan --kind opencode --pane <pane-id> -- --agent worker-sonnet
```

In `auto` mode add `--auto` at the end:

```bash
herdr agent start t12-plan --kind opencode --pane <pane-id> -- --agent worker-sonnet --auto
```

`--auto` approves every permission the agent profile does not deny. The worker profiles still deny starting other agents.

If it returns `agent_not_ready`, read the pane (`herdr agent read t12-plan --source visible`) to see why before doing anything else.

**claude:**

In `auto` mode, skip the allow-list and start the worker like this:

```bash
herdr agent start t12-plan --kind claude --pane <pane-id> -- --agent worker-sonnet --model <claude_sonnet_model> --dangerously-skip-permissions
```

Use `<claude_haiku_model>` with `worker-haiku`. Do not pass `--permission-mode` or `--allowedTools` with it. The first time, Claude Code can show a dialog asking the user to accept this mode; treat it as a startup dialog (see "Confirm it is ready"). Then go to "Confirm it is ready".

In `ask` mode, first get the allow-list. Run this in the project root:

```bash
python3 <this skill's folder>/scripts/allowed_tools.py
```

It prints one line: the project's check commands (from `commands` in `.formic/project.json`) and a few read-only git commands, each already in single quotes and separated by spaces. Paste that line unchanged where `<entries>` is below. Run it again for each worker; `.formic/project.json` may have changed.

```bash
herdr agent start t12-plan --kind claude --pane <pane-id> -- --agent worker-sonnet --permission-mode acceptEdits --model <claude_sonnet_model> --allowedTools <entries>
```

Use `<claude_haiku_model>` with `worker-haiku`. Put `--allowedTools` last.

Why these flags:

- `--model` is passed on the command line because model aliases and the model in the agent file are not reliable.
- `--permission-mode acceptEdits` is passed on the command line because the permission mode set in the agent file is not applied.
- `--allowedTools` lets the project's check commands and read-only git commands run without a prompt.

Never use `--dangerously-skip-permissions` in `ask` mode. Anything outside the allow-list and file edits will show a permission prompt in the worker's pane. You relay that prompt to the user (see "Permission prompts").

If `herdr agent start` returns `agent_not_ready`, read the pane (`herdr agent read t12-plan --source visible`). It usually means a startup dialog is showing. See "Confirm it is ready" below.

**Confirm it is ready.** A successful return from `herdr agent start` is not proof that the tool has finished starting.

**opencode:** The first time opencode runs in a project it installs its own support files, which can take a minute, and herdr reports the agent `idle` before the screen is up. Confirm before you prompt:

```bash
herdr agent read t12-plan --source visible --lines 45 | grep -i "worker-sonnet"
```

The input box shows the agent's name (for example `Worker-Sonnet`) once it is ready. If the pane is still blank, wait ten seconds and look again, for up to two minutes. A name other than the worker you asked for means the profile did not load: close the pane and tell the user.

**claude:** Read the pane:

```bash
herdr agent read t12-plan --source visible --lines 45
```

A ready Claude Code screen shows a rule line containing the agent name (for example `──── worker-sonnet ─`) above the `❯` input prompt. If you do not see it yet, wait ten seconds and read again, for up to two minutes.

Claude Code can show a startup dialog instead:

- The first start in a folder shows "Do you trust this folder?" with numbered options. herdr reports the agent `blocked`, and `agent start` may return `agent_not_ready`.
- Other one-off dialogs can appear at start, for example an offer to switch to a newer model.

When you see any dialog, show it to the user exactly as it appears, say which task and step it is for, and ask what to answer. Never answer a startup dialog yourself, not even the trust dialog. Send the key the user chooses (see "Permission prompts" for how to send keys), then read the pane again.

A model name in the rule line that is not the agent you asked for, or a different agent name, means the wrong profile loaded: close the pane and tell the user.

**3. Record it on the board**, so that a restarted coordinator can find the worker:

```bash
board agent t-12 --name t12-plan --pane <pane-id> --step plan --tier sonnet
```

**4. Send the brief and wait.** Use the scripts, not `herdr agent prompt` directly. The scripts send the brief, check within a minute that it arrived, then wait until the worker stops. A brief can be lost without herdr noticing: the worker then sits idle while a plain `herdr agent prompt --wait` keeps waiting until its timeout. The delivery check depends on the tool herdr reports for the agent:

- **opencode:** a worker gets a session as soon as it receives its first message, so "no session after 60 seconds" means not delivered.
- **Claude Code:** herdr reports a session immediately at start, so the session cannot be the signal. The check is that the session transcript has a `user` entry with the brief (a string or a list of text parts; entries marked `isMeta` do not count). If the brief is not there after half the delivery window, the script looks at the pane on every poll. It presses Enter, once, only when herdr reports the agent `idle`, no dialog is showing, and the brief (or a `[Pasted text` placeholder) is in the input area after the last `❯` line, not in the scrollback above. It sends no other key and never answers a dialog.

Use 30 minutes (1800000) for brief, plan, declare, verify and architect, and 60 minutes for execute, unless `.formic/project.json` says otherwise.

**opencode:** Run the script in the foreground:

```bash
bash <this skill's folder>/scripts/send_brief.sh t12-plan .formic/tasks/t-12_add-export-button/output/brief-plan.md 1800000
```

Give your shell tool a timeout longer than the last argument.

**claude:** Claude Code's shell tool stops a command after at most 10 minutes, so never run `send_brief.sh` in the foreground and never give a command a longer timeout than 540000 ms (9 minutes). Start it in the background with `async_brief.sh`, which keeps its output in a file in the task folder:

```bash
bash <this skill's folder>/scripts/async_brief.sh start t12-plan .formic/tasks/t-12_add-export-button/output/brief-plan.md 1800000 .formic/tasks/t-12_add-export-button/output/result-plan.json
```

It prints `started` and returns at once. The last argument before the file is the overall limit (the same 30 or 60 minutes as above); `send_brief.sh` enforces it, so the loop below always ends. For a repeat of a step, name the file like the brief (`result-execute-2.json`). Then wait in steps, with a shell tool timeout of 540000 ms:

```bash
bash <this skill's folder>/scripts/async_brief.sh wait .formic/tasks/t-12_add-export-button/output/result-plan.json 480
```

Each call waits at most 480 seconds (it never accepts more than 540) and prints one of two things:

- `still running` (exit code 0): the worker has not stopped yet. This is normal and not an error. Run the same `wait` command again, and keep doing so until it prints JSON.
- One line of JSON that starts with `{`: the final result of `send_brief.sh`. The exit code is the one `send_brief.sh` gives: 0 the worker stopped, 3 the brief was not delivered, 1 usage or herdr error. A JSON line with `"delivered": false` and the reason `send_brief.sh stopped without a result` (exit code 1) means the background run died; treat it as a failed attempt and read the pane.

The result, the error output and the exit code are kept next to the result file (`.err`, `.code`, `.pid`). If you are restarted while a worker is running, do not run `start` again: run `wait` on the same result file. `start` refuses while a run for that file is alive.

It prints one line of JSON. If `delivered` is `false` (exit code 3), the brief never arrived:

1. Read the pane (`herdr agent read <name> --source visible`) in case it shows why, close the pane and clear the agent on the board.
2. Dispatch the step once more with a new worker and a new name. This does not count as a retry.
3. If the second brief is not delivered either, stop and tell the user. Something is wrong with herdr or the agent tool on this machine, and more attempts will not help.

If `delivered` is `true`, read `status`. (Claude Code: wherever the table or "Permission prompts" says `herdr agent wait <name> --timeout <ms>`, use at most 540000 ms and run it again if it times out.)

| Result | Meaning | What to do |
|---|---|---|
| `idle` or `done` | The worker's turn ended | Go to step 5 |
| `blocked` | Usually a dialog is showing | Read the pane first. opencode: if it shows "Permission required", see "Permission prompts" below. Claude Code: a numbered permission dialog is handled under "Permission prompts" below; a startup dialog is handled as in "Confirm it is ready". herdr sometimes reports `blocked` for a moment while a worker is running a long command: if there is no dialog, wait again with `herdr agent wait <name> --timeout <ms>` |
| `status` `timeout` | The wait ran out; `agentStatus` says what the worker is doing, usually `working` | Do not send the brief again. `herdr agent get <name>`; if it is still `working`, wait again with `herdr agent wait <name> --timeout <ms>` (Claude Code: use a timeout of at most 540000 ms and repeat it, as for `async_brief.sh wait`) |
| error `agent_prompt_stalled` | herdr saw no activity after sending | Do not resend blindly. Read the pane. opencode: if it is blank, opencode was still starting and the prompt was lost: wait for the input box, then send the brief once more. Claude Code: the script already handles a brief left unsubmitted in the input box, so after a `delivered: false` read the pane before you retry. For both: if the brief is visible in the pane, it arrived: wait with `herdr agent wait <name>` |

**5. Read the report.**

```bash
python3 <this skill's folder>/scripts/worker_report.py t12-plan
```

The script works for both runtimes: it finds the tool from herdr. It prints JSON: `verdict`, `message` (the worker's exact final message), `agent`, `model`, `sessionId`, `error` and `errorKind`.

| `verdict` | Meaning |
|---|---|
| `DONE`, `PARTIAL`, `BLOCKED`, `FAILED` | The first word of the worker's final message |
| `NONE` | The message did not start with one of those words |
| `ERROR` | The turn ended with an error instead of a message. `error` holds the error text |
| `NOT_DELIVERED` | The worker never received its brief: no session (opencode), or no transcript, or no prompt in it (Claude Code). Handle it as in step 4 |

**If `errorKind` is `credentials`, stop the run.** The model provider rejected the sign-in, for example "The security token included in the request is expired", "Could not load credentials from any providers", or any other message saying the sign-in, token or credentials are expired, invalid or missing. This is not the task's fault, and every new worker will fail the same way until the user signs in again. Do not count a retry and do not dispatch anything else:

1. Close the pane and clear the agent on the board. Leave the task in its current status.
2. Tell the user that the provider's credentials have expired or are missing, quote the error, and ask them to sign in again with whatever their Claude Code or opencode setup uses. Do not name or change their settings.
3. When they say they have, dispatch the same step again with a new worker.

If your own requests start failing in the same way, you cannot do anything about it; the user will see the error in your pane.

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

In `auto` mode workers should not show permission prompts. If one appears anyway, or a startup dialog does, handle it exactly as below: the mode changes how workers start, not who answers a dialog.

`blocked` means a dialog is showing in the worker's pane, usually because the worker tried to touch something outside the project or outside the allow-list. The dialog depends on the runtime. A startup dialog (for example "Do you trust this folder?") is not a permission prompt, but the same rules apply: see "Confirm it is ready".

1. Read it: `herdr agent read <name> --source visible --lines 30`.
2. Show the user what is being asked, and for which task and step. Ask whether to allow once or reject. Do not offer "allow always" (opencode) or option 2 (Claude Code).
3. Never answer a permission dialog on your own judgement, even when it looks harmless.
4. Send the answer.

   **opencode:** The dialog shows "Permission required". Its options are in a row, `Allow once`, `Allow always`, `Reject`, with the first selected:
   - Allow once: `herdr agent send-keys <name> enter`
   - Reject: `herdr agent send-keys <name> right right` then `herdr agent send-keys <name> enter`

   Before pressing enter, read the pane again and confirm the option you want is the highlighted one. Dialog layouts can change between opencode versions.

   **claude:** The dialog is a numbered list, with `Esc` to cancel. For a file write it reads `1. Yes`, `2. Yes, and switch to accept edits ...`, `3. No`. Never offer option 2: it changes the permission mode for the rest of the session, which is the "allow always" of Claude Code.
   - Allow once: confirm in the pane that option 1 is highlighted, then `herdr agent send-keys <name> enter`
   - Reject: `herdr agent send-keys <name> esc`

   Read the pane again before pressing anything and check the layout, because dialogs change between Claude Code versions.
5. Wait for the worker to settle: `herdr agent wait <name> --timeout <ms>`, then continue from step 5 above. After a rejection the worker's turn often ends with no final message, which reads as verdict `NONE`.

## If herdr or the worker misbehaves

- **The pane closed or the agent vanished** (`agent_not_found`): the step did not finish. Clear the agent on the board and treat the step as failed.
- **The worker is still `working` long after it should be done**: read the pane. If it is looping, interrupt with `herdr agent send-keys <name> esc`, read the report, and treat the step as failed.
- **Do not** run `herdr server stop`, close panes or tabs you did not create, or create new workspaces or tabs unless the user asks.
