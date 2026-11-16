---
name: formic-unit-test
description: Generates and improves unit tests until a configurable coverage threshold is met
metadata:
  opencode/autoinvoke: false
---

# Unit Test Generation

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

## Objective

Generate or improve unit tests for all files modified during the execute stage of this task. Iterate until the configured coverage threshold is reached.

## Coverage Target

Use the coverage target given in your brief. If the brief gives none, use `limits.coverageThreshold` from `.formic/project.json`; if that is not set either, use 80% and say in your report that you used the default. Below, "the target" means that number.

## Instructions

1. **Identify modified files**: Review the git diff or task execution logs to determine which source files were created or modified during the execute stage.

2. **Write or update tests**: For each modified file:
   - Create or update the corresponding test file
   - Cover all public functions, methods, and edge cases
   - Use the project's existing test framework and patterns
   - Follow the test file naming convention used in the project

3. **Run the test suite**: Execute the project's test runner to measure current coverage.

4. **Check coverage**: If coverage is below the target, identify untested code paths and add more tests.

5. **Iterate**: Repeat steps 3–4 until coverage meets or exceeds the target, or until all reasonable test cases have been covered.

6. **Commit tests**: Once the threshold is met, the tests are complete.

## Notes

- Do not modify production source files during this stage — only add or update test files.
- If a file has no testable logic (e.g., pure configuration, type definitions), note this and move on.
- Use the project's existing mock/stub patterns for external dependencies.
- If coverage tooling is not configured, set it up following the project's conventions.

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
