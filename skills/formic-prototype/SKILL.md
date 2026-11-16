---
name: formic-prototype
description: Rapid spike / prototype. Prioritises speed and learning over code quality. Output is disposable.
metadata:
  opencode/autoinvoke: false
---

# Prototype Skill - Rapid Spike Implementation

You are building a **spike / prototype**. Speed and learning are the only goals. The output is intentionally disposable.

## Inputs

Your brief from the coordinator gives you the task id and the task folder, a path such as `.formic/tasks/t-12_add-export-button` relative to the project root. Below, `<task-folder>` means that path. Read `<task-folder>/TASK.md` for the task title and context, and `.formic/project.json` (if it exists) for the project's guideline file and its type-check, build and test commands.

---

## Instructions

1. **This is a spike — speed is everything:**
   - Build the fastest possible working prototype that validates the idea
   - The core question to answer: **"Does this approach work?"**

2. **Take shortcuts freely:**
   - Hardcode values, skip error handling, use copy-paste
   - Skip tests, documentation, and code review concerns entirely
   - Use quick-and-dirty approaches that would never pass a real review
   - Don't worry about edge cases, performance, or scalability

3. **Mark everything as disposable:**
   - Add `// TODO: Spike — replace with production implementation` to new files
   - Make it clear this code is not production-ready
   - Don't invest time in clean architecture or proper abstractions

4. **Focus on the core hypothesis:**
   - What is the key technical question this spike is trying to answer?
   - Build only what's needed to answer that question
   - Stop as soon as you have a working proof-of-concept

5. **Document your findings:**
   - At the end, briefly note what worked, what didn't, and what you learned
   - Include any gotchas or surprises that will inform the production implementation
   - Note which parts of the spike could be reused and which should be rewritten

## Output

A working (but rough) prototype that proves or disproves the approach, with clear notes on findings and next steps.

---

## Working in formic-kit

This skill sets the style of work for one step of one task. The rules in your brief still apply: do not read or write `.formic/board.json`, do not commit or push, and end with a final message whose first word is `DONE`, `BLOCKED` or `FAILED`, followed by what you did, what you verified, and anything the coordinator needs to decide.
