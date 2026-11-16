---
name: formic-board-hygiene
description: Audit the health of a formic-kit project's .formic/ folder - board validity, task-id collisions between task folders, orphaned folders, leftover backup and corrupted board files, stale leases and agents, duplicate open tasks, and tasks ageing in review. Read-only; reports findings and proposes a cleanup.
---

# Board hygiene: audit `.formic/`

`.formic/` accumulates debris: task folders from an earlier board that reuse the same `t-N`, leftover `board.json.corrupted.*` files, leases held by tasks nobody is running. This skill finds it and reports it. It is read-only: you report and propose, and change nothing until the user agrees.

Load `formic-board` for the board commands; `board` below means its `board.py`.

## Checks

### 1. The board is valid

```bash
board validate
```

Report every problem it lists. If the board does not parse at all, stop here and tell the user; `.formic/board.json.backup` holds the board as it was before the last write.

### 2. Task folders against the board

Compare `board list --json` with the folders in `.formic/tasks/`. Folder names are `<id>_<slug>`. Report:

- **Collisions**: an id with more than one folder. For each, say which folder matches the live task's `docsPath` and which are leftovers.
- **Missing**: a task on the board whose `docsPath` folder does not exist. This matters for tasks that are not yet done.
- **Orphans**: folders whose id is not on the board. Give the count and the names.

### 3. Leftover board files and old server state

```bash
ls -la .formic/
```

Report `board.json.corrupted.*`, `board.json.v1-*`, and files and folders written by the retired Formic server that the kit does not use: `leases.json`, `logs/`, `tools/`, `plugins/`, `usage/`, `code-sessions/`, `memory.json`, `config.json`, `assistant-context.md`. Give sizes. Do not judge whether the user still wants them; list them.

### 4. Stale leases and agents

`board list --active` and `board leases`. For each active task, check whether its recorded agent is still alive: `herdr agent list` if you are inside herdr (`HERDR_ENV=1`). An active task with no live agent is stuck; it holds its leases and blocks others. Report it. Recovering it is the coordinator's job (`formic-coordinate`), not this audit's.

### 5. Duplicate or near-duplicate open tasks

Compare the titles and the `## What` sections of all `todo`, `queued`, `blocked` and `review` tasks. Report pairs that cover the same work.

### 6. Review ageing

For each task in `review`, report how long ago its `completedAt` was and whether its folder has a `QUALITY.md` with a PASS verdict. If more than about five tasks are waiting, recommend a batch with `formic-task-review`.

## Output

1. Findings, most serious first: an invalid or unreadable board; stuck active tasks and stale leases; collisions on live tasks; duplicates; then clutter (orphans, leftover files).
2. A proposed cleanup, as exact commands, for the user to approve. Archive, never delete: old task folders are the only record of past work.

   ```bash
   mkdir -p .formic/archive/<today>
   mv .formic/tasks/<orphan-folder> .formic/archive/<today>/
   ```

3. Do not run the cleanup yourself unless the user tells you to.
