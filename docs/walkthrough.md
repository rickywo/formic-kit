# Walkthrough: from idea to approved task

This guide follows one feature through formic-kit, from describing it to approving the result. The project is a made-up TypeScript API called `notes-api`; any git repository works the same way.

## Before you start (once per machine)

```bash
herdr plugin install rickywo/formic-kit
herdr plugin action invoke formic.kit.setup
```

Setup first asks which runtime to use: `opencode` or `claude` (Claude Code). One tool runs the coordinator and the workers; `opencode` is the default. Then it asks for three model ids: one for the coordinator, one for the mid-tier worker and one for the low-cost worker.

- **opencode:** ids use the `provider/model` form, and `opencode models` lists them.
- **Claude Code:** ids have no provider prefix; use the ids that `claude --model` accepts. The coordinator id is optional.

The two sets are saved separately. On later runs, press Enter to keep the saved values. Setup ends with a check of the installation, which should finish with "All required checks passed."

## 1. Set up the project (once per project)

In herdr, go to a pane inside the project, for example `~/code/notes-api`, and run:

```bash
herdr plugin action invoke formic.kit.init
```

Answer `y`. This creates `.formic/board.json` and `.formic/project.json`, and adds a short section to `AGENTS.md`. With Claude Code it also creates a `CLAUDE.md` containing `@AGENTS.md`, because Claude Code reads that file instead of `AGENTS.md`.

Then fill in `.formic/project.json`. The quality gate runs these commands to check every task, so this step matters:

```json
"guidelineFile": "AGENTS.md",
"commands": {
  "typecheck": "npx tsc --noEmit",
  "build": "npm run build",
  "test": "npm test"
},
"forbiddenPatterns": [
  { "pattern": "console\\.log\\(", "why": "Use the logger" }
],
"sharedFiles": ["package.json", "src/routes/index.ts"]
```

| Field | What it is for |
|---|---|
| `guidelineFile` | The project's coding rules. Every worker reads it |
| `commands` | Type check, build and tests, run by the quality gate. `extraTests` can list suites that only apply to some changes |
| `forbiddenPatterns` | Regular expressions the gate searches for in the lines a task added |
| `manualChecks` | Rules the gate checks by reading the diff, such as "no new dependencies" |
| `sharedFiles` | Files that several tasks may each change a little, such as a dependency manifest |
| `limits` | Execute rounds, retries and similar caps. The defaults are fine to start with |

## 2. Start the coordinator

```bash
herdr plugin action invoke formic.kit.coordinator
```

A new pane opens beside the focused one, running the coordinator agent of your runtime (opencode or Claude Code) on your strongest model. You talk to this pane from now on. There is one coordinator per herdr workspace; running the action again focuses the existing one.

With Claude Code, the first start in a project shows "Do you trust this folder?" in the new pane, and the action reports that Claude Code did not become ready. Answer the question in that pane yourself, then run the action again. The kit never answers it for you.

## 3. Describe the work

Type what you want, for example:

> I want a search endpoint. GET /notes/search?q=... should return notes whose title or body contains the text, case-insensitive, at most 20 results.

The coordinator:

- checks the board, past task folders and recent commits for duplicate work;
- recommends a task type, here **standard**, because it touches a route, a service and tests;
- drafts the task with five sections: Why, What, Files, Acceptance criteria and Verification. An acceptance criterion is a plain true-or-false statement, such as "`?q=` with an empty string returns 400".

It shows you the draft and asks you to confirm. Correct anything that is wrong now, because every later step works from this text. Then:

> Looks good, add it and queue it.

The task gets an id such as `t-1` and the status `queued`.

## 4. Run it

> Run the queue.

The first time in a session, the coordinator lists any uncommitted files and asks before including them in an "auto-save: before task t-1" commit. The quality gate later compares the task's changes against that commit.

The coordinator then runs the task's steps. Each step is done by a fresh worker in a new pane, which opens beside you and closes when it is done:

| Step | Worker | What it writes in `.formic/tasks/t-1_add-search-endpoint/` |
|---|---|---|
| brief | sonnet | `README.md`: the specification |
| plan | sonnet | `PLAN.md` and `subtasks.json`, plus a recommended tier for the code |
| declare | haiku | `declared-files.json`: the files the task will touch |
| execute | the task's tier | the code changes, ticking off `subtasks.json` as it goes |
| verify | a new worker on the same tier | `QUALITY.md`: a PASS or FAIL verdict with evidence |

The coordinator checks each step's output before moving on. You can watch any worker's pane while it works. To see the whole board:

```bash
herdr plugin action invoke formic.kit.board
```

`q` closes the board view.

## 5. When it needs you

The coordinator stops and asks you in three situations:

- **A worker has a question.** For example: "Should search include archived notes?" Your answer is added to the task, and a new worker carries on. This does not count as a retry.
- **A worker hits a permission prompt**, such as reading a file outside the project. The coordinator shows the request and asks whether to allow it once or reject it. It never answers a permission prompt on its own. With Claude Code, workers already run file edits, the project's check commands and read-only git commands without a prompt, so a prompt means something else was requested. The coordinator shows you the dialog in the same way, you choose to allow it once or reject it, and it sends the matching key. It never picks "allow always" (opencode) or Claude Code's second option, "Yes, and switch to accept edits".
- **A task fails the gate three times.** The coordinator gives up on it for now, puts it back in `todo` with the reason, and tells you which checks failed. Before that, a task on the haiku tier that fails twice is moved up to sonnet.

## 6. Review

When the gate passes, the task moves to `review` and the coordinator tells you. Then:

> Review t-1.

The coordinator rechecks the work against the acceptance criteria and reruns the type check and tests itself. It gives a verdict, **APPROVE**, or **RE-RUN** with the reason, and says which parts it checked itself and which it took from `QUALITY.md`. You decide:

> Approve it.

The task moves to `done`. The changes are in your working tree, uncommitted. Commit them yourself when you are happy with them.

If you say re-run instead, the feedback is added to the task and the task goes back to `todo`. Ask the coordinator to queue it again when you are ready.

## Other things to say to the coordinator

| You say | What happens |
|---|---|
| "Fix the typo in the README heading" | It suggests a **quick** task: execute and verify only, with no brief or plan |
| "Build user accounts: signup, login, password reset" | It suggests a **goal**. An architect splits it into 3 to 8 tasks with dependencies, and you confirm before they are created. This path has not been tested yet |
| "Review everything in review" | A verdict table for every task waiting for you |
| "Check the board's health" | An audit of `.formic/`: stuck tasks, duplicates and leftover files. It changes nothing until you agree |

## Things to know

- **One task at a time.** Parallel runs are not built yet.
- **Nothing is committed for you** apart from the "auto-save: before task" commit at the start of each task.
- **If you close the coordinator mid-task**, start it again and say "run the queue". It finds the interrupted task and picks it up.
- **With opencode, the first start in a new project takes about a minute.** This applies to opencode only.
- **With Claude Code, the first start in a folder asks "Do you trust this folder?".** Answer it in the pane yourself. The kit does not change your Claude Code settings.
- **Never edit `.formic/board.json` by hand.** Ask the coordinator, which changes the board only through the kit's board tool.
