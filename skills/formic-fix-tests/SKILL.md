---
name: formic-fix-tests
description: Updates existing tests affected by code changes. Fixes broken assertions, updates mocks, and adds migration-specific tests.
metadata:
  opencode/autoinvoke: false
disable-model-invocation: true
---

# Fix Tests Skill - Update Tests After Code Changes

You are a testing specialist. Your job is to update all existing tests that were broken or affected by recent code changes.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

1. **Identify affected tests:**
   - Review the recent code changes to understand what was modified
   - If an impact analysis report exists, use it to find affected test files
   - Search for test files that import or reference the modified modules, types, or APIs
   - Check for tests that use mock data matching old schemas or interfaces

2. **Fix broken assertions:**
   - Update expected values to match the new behaviour
   - Fix type shapes in assertions to match updated interfaces
   - Correct any hardcoded values that no longer apply

3. **Update mocks and fixtures:**
   - Replace old mock objects with versions matching the new system
   - Update factory functions and test data builders
   - Fix test fixtures that reference old schemas, field names, or API shapes
   - Ensure mock return values match the new function signatures

4. **Add new test cases:**
   - Write tests for changed functionality, especially boundary conditions
   - Add regression tests that would have caught the bug if applicable
   - Test backwards-compatibility shims if any exist
   - Cover new code paths introduced by the changes

5. **Run and verify:**
   - Execute the full test suite
   - Confirm all updated and new tests pass
   - Check that test coverage has not decreased
   - Ensure no unrelated tests were broken by the changes

6. **Quality standards:**
   - Use descriptive test names that explain what's being tested
   - Keep tests independent — no shared mutable state between tests
   - Assert precisely — test specific values, not just truthiness
   - Follow the project's existing test conventions and framework patterns

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
