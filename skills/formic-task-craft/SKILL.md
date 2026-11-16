---
name: formic-task-craft
description: Author a task for a formic-kit board (.formic/board.json) - duplicate check, type and tier recommendation, a structured context, then add it to the board after the user confirms. Use whenever the user wants to create or refine a task in a project that has a .formic/ folder.
---

# Task craft: write a task and put it on the board

A well-written task is the highest-leverage thing in this workflow. Every later step, the brief, the plan, the code and the check, works from the context you write here. A vague context produces a chain of fix tasks. Follow each step.

You are the coordinator when you use this skill. Load `formic-board` for the board commands; `board` below means its `board.py`.

## Step 1: Duplicate check (do this first)

Before drafting, find out whether the work already exists or was already done:

1. Open tasks: `board list --status todo --status queued --status blocked --status review`, plus anything active.
2. Past task folders: list `.formic/tasks/` and look for two or three keywords from the request.
3. Recent commits: `git log --oneline -30`, same keywords.

If a similar task is **open**, propose updating or re-running it instead of creating a new one. If similar work was **already completed**, check in the code whether the request is still needed, and tell the user what you found before creating anything.

## Step 2: Recommend a type and a tier

Type:

| Type | When | What happens |
|---|---|---|
| `quick` | One or two files, no design decisions: typos, comments, configuration | Execute, then verify |
| `standard` | Two to ten files, needs a plan: features, investigated bug fixes, refactors | Brief, plan, declare, execute, verify |
| `goal` | Ten or more files, or cuts across modules | An architect splits it into 3 to 8 child tasks |

Between two types, pick the larger.

Execute tier, the model that implements and verifies:

| Tier | When |
|---|---|
| `haiku` | The work is mechanical and the context states exactly what to change |
| `sonnet` | It needs judgement: debugging, design choices inside the task, changes across several files |

For a `standard` task the tier can be left unset; the plan step recommends one and you decide then. For a `quick` task set it now, since there is no plan step. A `goal` has no tier; its children do.

State both recommendations with a one-line reason each.

## Step 3: Write the context

Every context has these five sections:

```
## Why
<The problem or motivation, one to three sentences. For a bug: the observed symptom and how to reproduce it.>

## What
<Concrete requirements, numbered. Each one can be checked on its own.>

## Files
<Best-guess files to modify, and files only read. Name real paths; look them up.>

## Acceptance criteria
<Numbered statements that are plainly true or false. "Works correctly" is not a criterion.
"GET /api/tasks/:id returns 404 for an unknown id" is.>

## Verification
<Which of the project's checks apply, by name from .formic/project.json: type check, tests,
any extra test suite. Add any task-specific command that shows the change works.>
```

Look in the codebase before writing `## Files`; do not guess paths.

For a `goal`, the context describes the outcome and the boundaries. The architect writes the five sections for each child.

## Step 4: Extra rules for bug-fix tasks

If the task fixes a bug, the context must also require:

- **Reproduce first**: show the failure before changing code.
- **Root cause, not symptom**: state the mechanism, not just what was observed.
- **Sibling scan**: look for the same defect at other call sites.
- **Regression test**: add a test that fails without the fix.

Say in the context that it is a bug fix, so the coordinator dispatches it with `formic-root-cause-fix`. If it fixes a defect introduced by another task on the board, note that task's id; it becomes `--fix-for`, and fix tasks run first.

## Step 5: Confirm, then add

Show the user the title, type, tier, priority and full context, and ask for confirmation or changes. Do not add the task before they agree.

- Title starts with a verb: Add, Implement, Fix, Update, Refactor.
- Priority is `high` only when the problem blocks other queued tasks or damages data. Otherwise `medium`; `low` for nice-to-have.

When confirmed, write the context to a temporary file and run:

```bash
board add --title "<title>" --context-file <file> --type <type> --priority <priority> [--tier <tier>] [--fix-for t-N]
```

The task is created in `todo`. Tell the user its id. Ask whether to queue it now (`board move <id> queued`); do not queue it unasked.

To refine an existing task that is still in `todo`: `board set <id> --context-file <file>` and, if needed, `title=...`, `priority=...`, `executeTier=...`.
