# formic-kit development guidelines

formic-kit is a set of agent skills, a few small scripts and a herdr plugin. A coordinator agent runs a task board (`.formic/board.json`) and hands each step of a task to worker agents in herdr panes. See `README.md` for the user-facing description and `docs/walkthrough.md` for an end-to-end example.

## Layout

- `skills/<id>/SKILL.md`: one skill per folder. Folder name is the skill id; every kit skill id starts with `formic-`.
- `skills/formic-board/scripts/board.py`: the only code that writes a board.
- `skills/formic-dispatch/scripts/`: `send_brief.sh` and `worker_report.py`, used by the coordinator to run one step in a worker.
- `install.sh`: install, init, doctor, uninstall.
- `agents/*.md.tmpl`: agent profile templates filled in at install time.
- `plugin/`, `herdr-plugin.toml`: the herdr plugin (actions, panes, startup hook).
- `templates/`: files copied into a project by `install.sh init`.
- `tests/`: Python `unittest` tests. Run with `python3 -m unittest discover -s tests -v`.

## Rules

- **No dependencies.** Scripts are bash, or Python 3.8+ using the standard library only. Do not add packages, package manifests, or tools a user would have to install.
- **Stay portable.** No absolute paths, user names, model ids or project-specific commands inside skills, scripts or templates. Model ids reach agent profiles only through `install.sh` flags. Project commands come from the project's `.formic/project.json`.
- **Never overwrite what the kit did not create.** `install.sh` leaves a file or link alone unless it carries the kit's marker or `--force` is given, and records what it creates so `uninstall` removes only that.
- **Idempotent.** Running `install.sh` or `init` twice changes nothing the second time.
- **Do not pipe long command output into `head`, `grep -q` or `$(...)` and rely on it.** opencode truncates output written to a pipe, and `head` can kill a writer with SIGPIPE mid-run. Write to a temporary file and read the file.
- **bash scripts** use `set -euo pipefail` (or `set -uo pipefail` where a failing command must not stop the script), quote every expansion, and pass `bash -n` and `shellcheck -S warning` with no new warnings.
- **Skills are prompts.** Write them in plain, direct English addressed to the agent that runs them: short sentences, imperative steps, tables where they help. No emojis. A skill must say exactly which files it reads and writes and how it reports.
- **Workers never read or write `.formic/board.json` and never start other agents.** Only the coordinator does either.
- **Keep existing behaviour.** A change for a new capability must leave current installs and their behaviour unchanged unless the user opts in.
- **Testing.** Do not run `install.sh install` or `uninstall` against the real `~/.config/opencode`, `~/.claude` or `~/.config/formic-kit`. Use `FORMIC_KIT_STATE_DIR` and the config-directory options with temporary directories. Do not start herdr agents from a worker.
- **Docs.** A user-facing change updates `README.md`, and `docs/walkthrough.md` where the steps change.


## Task workflow (formic-kit)

Work in this project is tracked on a task board at `.formic/board.json`. A coordinator session runs the board and hands each step of a task to a worker agent.

- **If you were started with a brief that names a task id and a task folder, you are a worker.** Do what the brief says, load the skill it names, and end with the report it asks for. Do not read or write `.formic/board.json`, and do not start other agents.
- **Otherwise you are working with the user directly.** To create a task use the `formic-task-craft` skill. To run queued tasks use `formic-coordinate`. To check finished tasks use `formic-task-review`. Change the board only with the tool in the `formic-board` skill. If the user asks you to make a change directly, make it; not everything needs a task.
- The project's check commands and workflow limits are in `.formic/project.json`.
