# formic-kit

Skills that run a task board with a coordinator agent and worker agents, for opencode and herdr.

A coordinator session (your strongest model) owns the board at `<project>/.formic/board.json` and hands each step of a task to a worker (`worker-sonnet` or `worker-haiku`) running in its own herdr pane. Workers share context through the task folder, `.formic/tasks/<id>_<slug>/`.

Status: work in progress. Tasks run one at a time; parallel runs are not built yet.

## Install

On each machine, after installing opencode and herdr and setting up your model provider:

```bash
git clone <this repository> && cd formic-kit
./install.sh --coordinator-model <provider/model> --sonnet-model <provider/model> --haiku-model <provider/model>
herdr integration install opencode
./install.sh doctor
```

`install` links the skills into `~/.config/opencode/skills` and writes three agent profiles into `~/.config/opencode/agents`: `worker-haiku`, `worker-sonnet` and `formic-coordinator`. It leaves any file it did not create alone unless you pass `--force`. `opencode models` lists the model ids.

In each project:

```bash
<kit>/install.sh init .
```

Then fill in the check commands in `.formic/project.json`, start opencode inside herdr in the project, and ask it to create a task or run the queue. `opencode --agent formic-coordinator` starts the session on the coordinator model.

To update, `git pull`; rerun `./install.sh` only if the agent templates changed. `./install.sh uninstall` removes what install created.

## herdr plugin

The kit is also a herdr plugin (`herdr-plugin.toml`). Install it with `herdr plugin install <owner>/<repo>` once the repository is on GitHub, or from a local clone with `herdr plugin link <path>`. It adds five actions, which you can run with `herdr plugin action invoke formic.kit.<id>` or bind to keys:

| Action | What it does |
|---|---|
| `setup` | Opens a popup that asks for the three model ids, runs the installer and then the doctor |
| `init` | Sets up the board in the project of the focused pane, after asking |
| `doctor` | Shows the doctor's report for this machine and project |
| `board` | Opens a live, read-only view of the project's task board. `q` closes it |
| `coordinator` | Starts a coordinator agent beside the focused pane, one per workspace |

```toml
# ~/.config/herdr/config.toml
[[keys.command]]
key = "prefix+b"
type = "plugin_action"
command = "formic.kit.board"
description = "formic board"
```

A startup hook points the skill links at the plugin's current folder after an install or update. It does nothing until `setup` has been run once.

## Layout

| Path | What |
|---|---|
| `skills/formic-coordinate` | The run loop: pick a task, dispatch each step, check the output, update the board |
| `skills/formic-board` | Board rules, and `scripts/board.py`, the only way the board is changed |
| `skills/formic-dispatch` | Running one step in a worker through herdr, and `scripts/worker_report.py` |
| `skills/formic-brief`, `-plan`, `-declare`, `-execute`, `-quality-gate`, `-architect` | The worker step skills |
| `skills/formic-task-craft`, `-task-review`, `-board-hygiene` | Skills you call yourself: create a task, review finished tasks, audit `.formic/` |
| `skills/formic-root-cause-fix` and 23 role skills | Styles of work a worker can be told to load |
| `herdr-plugin.toml`, `plugin/` | The herdr plugin: actions, panes, the board viewer and the startup hook |
| `install.sh` | `install`, `init`, `doctor`, `uninstall` |
| `agents/*.md.tmpl` | Agent profiles, filled in with this machine's model ids at install |
| `templates/project.json` | Per-project settings: check commands, forbidden patterns, shared files, limits |
| `templates/AGENTS-section.md` | Section to add to a project's `AGENTS.md` |
| `tests/test_board.py` | Tests for `board.py`: `python3 tests/test_board.py` |

## Requirements

opencode, herdr with its opencode integration, Python 3.8+, git, and two opencode agents named `worker-haiku` and `worker-sonnet`.
