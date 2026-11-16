# formic-kit

Skills that run a task board with a coordinator agent and worker agents, for opencode and herdr.

A coordinator session (your strongest model) owns the board at `<project>/.formic/board.json` and hands each step of a task to a worker (`worker-sonnet` or `worker-haiku`) running in its own herdr pane. Workers share context through the task folder, `.formic/tasks/<id>_<slug>/`.

Status: 0.1.0, work in progress. Tasks run one at a time; parallel runs are not built yet, and goal tasks (splitting a large goal into child tasks) are written but untested.

## Requirements

- [herdr](https://herdr.dev) 0.9.5 or later, with its opencode integration: `herdr integration install opencode`
- [opencode](https://opencode.ai), with a model provider set up
- Python 3.8 or later, git, bash
- macOS or Linux

## Install

```bash
herdr plugin install rickywo/formic-kit
```

**Installing the plugin does not set anything up yet. Run the setup action next:**

```bash
herdr plugin action invoke formic.kit.setup
```

Setup asks for three model ids in opencode's `provider/model` form (`opencode models` lists them): one for the coordinator, one for the mid-tier worker and one for the low-cost worker. It then:

- links the kit's skills into `~/.config/opencode/skills`;
- writes three agent profiles into `~/.config/opencode/agents`: `formic-coordinator`, `worker-sonnet` and `worker-haiku`;
- runs a check of the installation.

It leaves any file it did not create alone. If you already have agents named `worker-sonnet` or `worker-haiku`, they are kept as they are.

## Use it in a project

From a herdr pane inside the project (a git repository):

1. `herdr plugin action invoke formic.kit.init` creates `.formic/board.json` and `.formic/project.json` and adds a short section to `AGENTS.md`.
2. Fill in `.formic/project.json`: the type-check, build and test commands, and the project's guideline file. The quality gate runs these commands.
3. `herdr plugin action invoke formic.kit.coordinator` starts a coordinator agent beside the focused pane.
4. Ask the coordinator to create a task, then to run the queue. It starts workers in new panes, checks what they produce, and moves tasks to review.
5. `herdr plugin action invoke formic.kit.board` shows the board. Ask the coordinator to review the tasks waiting for you.

The first opencode start in a new project takes about a minute.

For a full example, from describing a feature to approving it, see [docs/walkthrough.md](docs/walkthrough.md).

## Actions

| Action | What it does |
|---|---|
| `formic.kit.setup` | Opens a popup that asks for the three model ids, runs the installer and then the check |
| `formic.kit.init` | Sets up the board in the project of the focused pane, after asking |
| `formic.kit.doctor` | Shows the check for this machine and project |
| `formic.kit.board` | Opens a live, read-only view of the project's task board. `q` closes it |
| `formic.kit.coordinator` | Starts a coordinator agent beside the focused pane, one per workspace |

To bind one to a key:

```toml
# ~/.config/herdr/config.toml
[[keys.command]]
key = "prefix+b"
type = "plugin_action"
command = "formic.kit.board"
description = "formic board"
```

## Update and remove

`herdr plugin update` fetches the latest version. herdr puts each version in a new folder; the kit points its skill links at the new one the next time you run any of its actions or herdr starts.

To remove it, run `install.sh uninstall` from the plugin folder first, then unregister the plugin:

```bash
bash "$(herdr plugin list --plugin formic.kit --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["plugins"][0]["plugin_root"])')/install.sh" uninstall
herdr plugin uninstall formic.kit
```

Projects and their `.formic` folders are not touched.

## Without the plugin

The same installer works from a clone:

```bash
git clone https://github.com/rickywo/formic-kit && cd formic-kit
./install.sh --coordinator-model <provider/model> --sonnet-model <provider/model> --haiku-model <provider/model>
./install.sh doctor
./install.sh init <project>
```

For development, `herdr plugin link <path-to-clone>` registers the clone as the plugin, so edits take effect at once.

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
| `docs/walkthrough.md` | A full example, from describing a feature to approving it |
| `tests/test_board.py` | Tests for `board.py`: `python3 tests/test_board.py` |

## Licence

MIT. See `LICENSE`.
