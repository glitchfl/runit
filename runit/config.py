import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from runit.exceptions import ConfigError

CONFIG_FILENAME = "runit.yaml"

VALID_MODES = ("sequential", "random")


@dataclass
class CommandConfig:
    name: str
    steps: list[str]
    mode: str = "sequential"
    handler: Callable[[dict[str, str]], int] | None = field(default=None, repr=False)


def _find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").is_dir():
            return parent / ".git"
    return None


def _get_cache_path(directory: Path) -> Path:
    resolved = directory.resolve()
    key = hashlib.sha256(str(resolved).encode()).hexdigest()[:16]
    folder_name = f"{resolved.name}_{key}"
    cache_dir = Path.home() / ".cache" / "runit" / folder_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / CONFIG_FILENAME


def global_config_path() -> Path:
    """Return the path to the global config at ~/.config/runit/runit.yaml."""
    config_dir = Path.home() / ".config" / "runit"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / CONFIG_FILENAME


def find_config() -> Path:
    """Find or create the config path for the current directory.

    - Git repo: .git/runit.yaml
    - Non-git: ~/.cache/runit/<dir>_<hash>/runit.yaml
    """
    cwd = Path.cwd()
    git_dir = _find_git_root(cwd)

    if git_dir is not None:
        return git_dir / CONFIG_FILENAME

    return _get_cache_path(cwd)


def builtin_commands() -> dict[str, CommandConfig]:
    """Return built-in commands that ship with runit."""
    from runit.builtins import heatmap, loc, prune

    return {
        "prune": CommandConfig(
            name="prune",
            steps=["fetch --prune and delete local branches with gone remotes"],
            handler=prune,
        ),
        "untrack": CommandConfig(
            name="untrack",
            steps=["git rm --cached -r {path}"],
        ),
        "loc": CommandConfig(
            name="loc",
            steps=["count lines of code in *.{ext:py} files"],
            handler=loc,
        ),
        "heatmap": CommandConfig(
            name="heatmap",
            steps=["show 20 most frequently changed files in git history"],
            handler=heatmap,
        ),
    }


def load_merged_config() -> dict[str, CommandConfig]:
    """Load built-in, global, and project commands.

    Priority: project > global > built-in.
    """
    builtins = builtin_commands()
    global_cmds = load_config(global_config_path())
    project_cmds = load_config()
    return {**builtins, **global_cmds, **project_cmds}


def load_config(path: Path | None = None) -> dict[str, CommandConfig]:
    if path is None:
        path = find_config()

    if not path.exists():
        return {}

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse config: {e}") from e

    if raw is None:
        return {}

    if not isinstance(raw, dict) or "commands" not in raw:
        raise ConfigError("Config must have a top-level 'commands' key.")

    commands_raw = raw["commands"]
    if commands_raw is None:
        return {}

    if not isinstance(commands_raw, dict):
        raise ConfigError("'commands' must be a mapping of command names.")

    commands: dict[str, CommandConfig] = {}

    for name, value in commands_raw.items():
        if isinstance(value, str):
            commands[name] = CommandConfig(name=name, steps=[value])
            continue

        if not isinstance(value, dict):
            raise ConfigError(
                f"Command '{name}' must be a string or a mapping with a 'run' key."
            )

        run = value.get("run")
        if run is None:
            raise ConfigError(f"Command '{name}' is missing the 'run' key.")

        if isinstance(run, str):
            steps = [run]
        elif isinstance(run, list):
            if not all(isinstance(s, str) for s in run):
                raise ConfigError(
                    f"Command '{name}': all steps in 'run' must be strings."
                )
            steps = run
        else:
            raise ConfigError(
                f"Command '{name}': 'run' must be a string or a list of strings."
            )

        mode = value.get("mode", "sequential")
        if mode not in VALID_MODES:
            raise ConfigError(
                f"Command '{name}': 'mode' must be one of {VALID_MODES}, got '{mode}'."
            )

        commands[name] = CommandConfig(name=name, steps=steps, mode=mode)

    return commands


def save_config(commands: dict[str, CommandConfig], path: Path | None = None) -> None:
    if path is None:
        path = find_config()

    data: dict[str, dict | str] = {}
    for name, cmd in commands.items():
        if len(cmd.steps) == 1 and cmd.mode == "sequential":
            data[name] = cmd.steps[0]
        else:
            entry: dict = {"run": cmd.steps[0] if len(cmd.steps) == 1 else cmd.steps}
            if cmd.mode != "sequential":
                entry["mode"] = cmd.mode
            data[name] = entry

    output = {"commands": data}
    path.write_text(yaml.dump(output, default_flow_style=False, sort_keys=False))
