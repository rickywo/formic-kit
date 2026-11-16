## Task workflow (formic-kit)

Work in this project is tracked on a task board at `.formic/board.json`. A coordinator session runs the board and hands each step of a task to a worker agent.

- **If you were started with a brief that names a task id and a task folder, you are a worker.** Do what the brief says, load the skill it names, and end with the report it asks for. Do not read or write `.formic/board.json`, and do not start other agents.
- **Otherwise you are working with the user directly.** To create a task use the `formic-task-craft` skill. To run queued tasks use `formic-coordinate`. To check finished tasks use `formic-task-review`. Change the board only with the tool in the `formic-board` skill. If the user asks you to make a change directly, make it; not everything needs a task.
- The project's check commands and workflow limits are in `.formic/project.json`.
