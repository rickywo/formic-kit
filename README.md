# formic-kit

Skills that run a task board with a coordinator agent and worker agents, for opencode or Claude Code, and herdr.

A coordinator session (your strongest model) owns the board at `<project>/.formic/board.json` and hands each step of a task to a worker (`worker-sonnet` or `worker-haiku`) running in its own herdr pane. Workers share context through the task folder, `.formic/tasks/<id>_<slug>/`.

Status: 0.1.0, work in progress. Tasks run one at a time; parallel runs are not built yet, and goal tasks (splitting a large goal into child tasks) are written but untested.

## Requirements

- [herdr](https://herdr.dev) 0.9.5 or later, with the integration for the tool you use: `herdr integration install opencode` or `herdr integration install claude`
- [opencode](https://opencode.ai) or [Claude Code](https://claude.com/claude-code), with a model provider set up
- Python 3.8 or later, git, bash
- macOS or Linux

## Choose a runtime

The kit runs on opencode or on Claude Code. One machine-level setting, `opencode` or `claude`, chooses the tool. The same tool runs the coordinator and the workers.

- Set it with `./install.sh --runtime opencode|claude`, or answer the first question of the setup action (below).
- The choice is saved in `~/.config/formic-kit/config`, so later runs need no flag.
- The default is `opencode`. A machine that has never chosen keeps working as before.
- The model ids for the two tools are saved separately, so switching runtime does not lose the other set.

## Install

```bash
herdr plugin install rickywo/formic-kit
```

**Installing the plugin does not set anything up yet. Run the setup action next:**

```bash
herdr plugin action invoke formic.kit.setup
```

Setup asks which runtime to use (`opencode` or `claude`), then for three model ids: one for the coordinator, one for the mid-tier worker and one for the low-cost worker.

**opencode.** Model ids use opencode's `provider/model` form (`opencode models` lists them). Setup:

- links the kit's skills into `~/.config/opencode/skills`;
- writes four agent profiles into `~/.config/opencode/agents`: `formic-coordinator`, `formic-ops`, `worker-sonnet` and `worker-haiku`;
- runs a check of the installation.

**Claude Code.** Model ids have no provider prefix, unlike opencode's `provider/model`: use the ids that `claude --model` accepts. Setup:

- links the kit's skills into `<claude-dir>/skills`; `<claude-dir>` is `~/.claude` unless you pass `--claude-dir`, and it is remembered;
- writes the same four agent files into `<claude-dir>/agents`;
- runs a check of the installation.

The Claude Code agent files carry no model. The coordinator passes the saved id to Claude Code with `--model` each time it starts an agent. Workers need the mid-tier and low-cost ids; the coordinator id is optional, and without it the coordinator uses Claude Code's own default.

Either way, setup leaves any file it did not create alone. If you already have agents named `worker-sonnet` or `worker-haiku`, they are kept as they are.

## Use it in a project

From a herdr pane inside the project (a git repository):

1. `herdr plugin action invoke formic.kit.init` creates `.formic/board.json` and `.formic/project.json` and adds a short section to `AGENTS.md`. With Claude Code it also creates `CLAUDE.md` containing the line `@AGENTS.md`, because Claude Code reads `CLAUDE.md`, not `AGENTS.md`. An existing `CLAUDE.md` is left alone.
2. Fill in `.formic/project.json`: the type-check, build and test commands, and the project's guideline file. The quality gate runs these commands.
3. `herdr plugin action invoke formic.kit.coordinator` starts a coordinator agent beside the focused pane.
4. Ask the coordinator to create a task, then to run the queue. It starts workers in new panes, checks what they produce, and moves tasks to review.
5. `herdr plugin action invoke formic.kit.board` shows the board. Ask the coordinator to review the tasks waiting for you.

With opencode, the first start in a new project takes about a minute. With Claude Code, the first start in a folder asks "Do you trust this folder?" in the new pane. Answer it there yourself, then run the coordinator action again. The kit never answers it for you.

To use the skills in a project on a machine where `install` has not been run, add `--local-skills` to `./install.sh init`. It links them into `<project>/.opencode/skills`, or `<project>/.claude/skills` with Claude Code.

For a full example, from describing a feature to approving it, see [docs/walkthrough.md](docs/walkthrough.md).

## Claude Code specifics

- **Permissions.** Workers start with `--permission-mode acceptEdits` and an allow-list of the project's check commands (from `.formic/project.json`) and read-only git commands. File edits and those commands run without a prompt. Anything else shows a permission prompt in the worker's pane. The coordinator shows you the prompt and asks whether to allow it once or reject it; it never answers on its own. The kit does not use `--dangerously-skip-permissions` unless you turn on auto permissions (below).
- **Startup dialogs.** Besides the folder-trust question, Claude Code can show other one-off dialogs when it starts, such as an offer to switch model. The coordinator shows them to you and sends the key you choose.
- **Transcripts.** The dispatch scripts read the worker's session transcript from `$FORMIC_CLAUDE_DIR` if it is set, else `$CLAUDE_CONFIG_DIR` if it is set, else `~/.claude`. That is where Claude Code itself writes transcripts, which is not always the folder you gave to `install.sh --claude-dir` (for example a project's `.claude`). Set `FORMIC_CLAUDE_DIR` only when the workers' Claude Code config folder differs from what the environment already gives.
- **Your settings.** The kit never changes your Claude Code settings (`~/.claude/settings.json`). It only adds skill links and four agent files, and removes only those on uninstall.

## Formic-Ops: one assistant across projects (optional)

`formic-ops` is a primary agent you can start in any folder, with `opencode --agent formic-ops` or `claude --agent formic-ops` inside herdr. It takes in a request, works out which project it belongs to, checks the live checkout, and hands board work to that project's running coordinator with `herdr agent prompt`. It reports what each board shows.

It never writes a board, never implements project changes, and never commits or pushes unless you explicitly authorize it. If a project has no running coordinator, it asks you to start one.

With opencode it runs on the coordinator model and is written only when a coordinator model is set. An agent file of the same name that you created yourself is left alone.

## Auto permissions (optional)

By default nothing is approved for you: a permission prompt in a worker's pane is shown to you by the coordinator, and you decide. To run without prompts, opt in once per machine:

```bash
./install.sh --permissions auto
```

The choice is saved as `permissions=auto` in `~/.config/formic-kit/config`. From then on the coordinator action and the coordinator's worker starts add `--auto` with opencode and `--dangerously-skip-permissions` with Claude Code. Sessions that are already running keep the mode they started with.

In this mode the agents run shell commands, edit files and read or write outside the project without asking. Use it only on a machine and in projects where that is acceptable. The worker profiles still deny starting other agents under opencode, and startup dialogs (folder trust, and Claude Code's one-time confirmation of this mode) are still yours to answer. `./install.sh --permissions ask` turns it off.

## Actions

| Action | What it does |
|---|---|
| `formic.kit.setup` | Opens a popup that asks for the runtime and the three model ids, runs the installer and then the check |
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
# opencode (the default)
./install.sh --coordinator-model <provider/model> --sonnet-model <provider/model> --haiku-model <provider/model>
# or Claude Code (ids without a provider prefix; --coordinator-model is optional)
./install.sh --runtime claude --sonnet-model <id> --haiku-model <id> --coordinator-model <id>
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
| `agents/*.md.tmpl`, `agents/*.claude.md.tmpl` | Agent profiles for opencode (filled in with this machine's model ids at install) and for Claude Code (no model in the file) |
| `templates/project.json` | Per-project settings: check commands, forbidden patterns, shared files, limits |
| `templates/AGENTS-section.md` | Section to add to a project's `AGENTS.md` |
| `docs/walkthrough.md` | A full example, from describing a feature to approving it |
| `tests/` | Unit tests for the board tool, the installer, the plugin scripts and the worker report: `python3 -m unittest discover -s tests -v` |

## Licence

MIT. See `LICENSE`.
