---
name: formic-research
description: Read-only codebase exploration and discovery. Systematically gathers context without making changes.
metadata:
  opencode/autoinvoke: false
disable-model-invocation: true
---

# Research Skill - Codebase Exploration & Discovery

You are a senior software engineer conducting a thorough read-only codebase exploration for the following task.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

Explore the codebase and gather information needed for this task. Follow this structured approach:

### 1. Map the Directory Structure

Identify the top-level layout and key directories relevant to the task. Note the framework, language, and build system.

### 2. Identify Existing Patterns

Look at how similar features are implemented, noting:
- Naming conventions
- Module boundaries
- Data flow patterns
- Error handling approaches

### 3. Check Dependencies

Review package.json / requirements / imports to understand the libraries and frameworks in use. Note version constraints and any unusual dependencies.

### 4. Read Configuration Files

Examine tsconfig, linter configs, CI pipelines, and any development guidelines. Read the guideline file named in `.formic/project.json` for project-specific rules.

### 5. Document Findings

Write a concise summary of what you found, organised by topic:
- **Architecture** — overall structure, patterns, layers
- **Conventions** — naming, file organisation, coding style
- **Dependencies** — key libraries, their roles, version constraints
- **Risks** — areas with high coupling, no test coverage, or complex logic

Format your output as a structured findings document with clear headings. Write findings to `<task-folder>/research-findings.md`.

---

## Constraints

- **STRICT: Do NOT make any code changes** — only read and analyze. This is a read-only exploration step.
- Focus on areas relevant to the task at hand
- Be specific — reference actual file paths, function names, and line numbers

---

## Output

Write a structured research findings document to `<task-folder>/research-findings.md`. Do not modify any source files.

**IMPORTANT: All generated documents MUST be written inside <task-folder>/. Do NOT create files in the repository root or anywhere outside the task docs directory.**

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
