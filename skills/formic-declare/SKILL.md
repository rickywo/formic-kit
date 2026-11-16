---
name: formic-declare
description: Worker step for formic-kit. Reads one task's plan and writes declared-files.json, the list of files the task will create or modify, used for file leases.
metadata:
  opencode/autoinvoke: false
---

# Declare: list the files this task will change

You are a worker on the declare step of one task. The coordinator uses your list to make sure two tasks running at the same time never edit the same file. A file you leave out is a file another task may be given.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path.

- Read `<task-folder>/README.md`, `<task-folder>/PLAN.md` and `<task-folder>/subtasks.json`.
- Read `.formic/project.json` if it exists. Its `sharedFiles` lists this project's hotspot files.

Do not read or write `.formic/board.json`.

## What to do

1. From the plan and subtasks, identify every file that will be created or modified. Check that each existing path is real; look in the repository, do not rely on the plan's spelling.
2. Classify each one:
   - **exclusive**: only this task should touch it while it runs. This is the default, and it covers new files and test files.
   - **shared**: a hotspot that several tasks may each change in a small way, such as a dependency manifest, a central type file or a route registration file. Use the `sharedFiles` list from `.formic/project.json`. If a file is not on that list, it is exclusive.
3. Write `<task-folder>/declared-files.json` in exactly this shape:

```json
{
  "exclusive": [
    "src/server/services/newService.ts",
    "test/unit/newService.test.ts"
  ],
  "shared": [
    "package.json"
  ]
}
```

## Guidelines

- Paths are relative to the project root, with no leading `./`.
- Be thorough. Include files the plan implies but does not name, such as the test file for a changed module.
- When in doubt, exclusive.
- Do not list files that will only be read.
- Write only `declared-files.json`. Do not change any other file.

## Report

End with a final message whose first word is one of:

- `DONE`, followed by the counts of exclusive and shared files, and any file you were unsure about.
- `BLOCKED`, followed by what is missing. Use this if the plan is too vague to tell which files it touches.
- `FAILED`, followed by what went wrong.
