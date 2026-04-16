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
    """Return the path to the global config (platform-aware)."""
    from runit.settings import base_config_dir

    config_dir = base_config_dir()
    return config_dir / CONFIG_FILENAME


def _get_folder_mode_path(directory: Path) -> Path:
    """Return the central config path for a directory in folder mode."""
    from runit.settings import base_config_dir

    resolved = directory.resolve()
    key = hashlib.sha256(str(resolved).encode()).hexdigest()[:16]
    folder_name = f"{resolved.name}_{key}"
    projects_dir = base_config_dir() / "projects" / folder_name
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir / CONFIG_FILENAME


def _update_folder_index(directory: Path) -> None:
    """Update the folder index with a directory entry."""
    from runit.settings import base_config_dir

    resolved = directory.resolve()
    key = hashlib.sha256(str(resolved).encode()).hexdigest()[:16]
    hash_name = f"{resolved.name}_{key}"

    projects_dir = base_config_dir() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    index_path = projects_dir / "index.yaml"

    index = {}
    if index_path.exists():
        raw = yaml.safe_load(index_path.read_text())
        if isinstance(raw, dict):
            index = raw

    index[str(resolved)] = hash_name
    index_path.write_text(yaml.dump(index, default_flow_style=False, sort_keys=False))


def load_folder_index() -> dict[str, str]:
    """Return {folder_path: hash_name} for all tracked folders."""
    from runit.settings import base_config_dir

    index_path = base_config_dir() / "projects" / "index.yaml"
    if not index_path.exists():
        return {}
    raw = yaml.safe_load(index_path.read_text())
    return raw if isinstance(raw, dict) else {}


def find_config() -> Path:
    """Find or create the config path for the current directory.

    In repo mode (default):
      - Git repo: .git/runit.yaml
      - Non-git: ~/.cache/runit/<dir>_<hash>/runit.yaml

    In folder mode:
      - All directories: <config_dir>/projects/<name>_<hash>/runit.yaml
    """
    from runit.settings import get_storage_mode

    cwd = Path.cwd()

    if get_storage_mode() == "folder":
        return _get_folder_mode_path(cwd)

    git_dir = _find_git_root(cwd)
    if git_dir is not None:
        return git_dir / CONFIG_FILENAME

    return _get_cache_path(cwd)


def builtin_commands() -> dict[str, CommandConfig]:
    """Return built-in commands that ship with runit."""
    from runit.builtins import loc, prune

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
        "glog": CommandConfig(
            name="glog",
            steps=["git log --graph --format='%C(auto)%h%Creset%x09%C(cyan)%an%Creset%x09%C(green)%ad%Creset%x09%s%x09%C(auto)%d%Creset'"],
        ),
    }


def load_disabled_builtins(path: Path | None = None) -> set[str]:
    """Return the set of disabled builtin command names from a config file."""
    if path is None:
        path = find_config()
    if not path.exists():
        return set()
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return set()
    if not isinstance(raw, dict):
        return set()
    disabled = raw.get("disabled_builtins", [])
    if isinstance(disabled, list):
        return {str(name) for name in disabled}
    return set()


def save_disabled_builtins(names: set[str], path: Path | None = None) -> None:
    """Write the disabled_builtins list into a config file."""
    if path is None:
        path = find_config()

    raw: dict = {}
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    if names:
        raw["disabled_builtins"] = sorted(names)
    else:
        raw.pop("disabled_builtins", None)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(raw, default_flow_style=False, sort_keys=False))


def load_merged_config() -> dict[str, CommandConfig]:
    """Load built-in, global, and project commands.

    Priority: project > global > built-in.
    Builtins listed in disabled_builtins (global or project) are excluded.
    """
    builtins = builtin_commands()
    global_cmds = load_config(global_config_path())
    project_cmds = load_config()

    disabled = (
        load_disabled_builtins(global_config_path())
        | load_disabled_builtins()
    )
    filtered_builtins = {k: v for k, v in builtins.items() if k not in disabled}

    return {**filtered_builtins, **global_cmds, **project_cmds}


def parse_commands_dict(raw: dict | None) -> dict[str, CommandConfig]:
    """Validate a raw {'commands': {...}} mapping into CommandConfig objects."""
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


def load_config(path: Path | None = None) -> dict[str, CommandConfig]:
    if path is None:
        path = find_config()

    if not path.exists():
        return {}

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse config: {e}") from e

    return parse_commands_dict(raw)


def serialize_commands_dict(commands: dict[str, CommandConfig]) -> dict[str, dict | str]:
    """Inverse of parse_commands_dict: convert CommandConfigs to YAML-ready entries."""
    data: dict[str, dict | str] = {}
    for name, cmd in commands.items():
        if len(cmd.steps) == 1 and cmd.mode == "sequential":
            data[name] = cmd.steps[0]
        else:
            entry: dict = {"run": cmd.steps[0] if len(cmd.steps) == 1 else cmd.steps}
            if cmd.mode != "sequential":
                entry["mode"] = cmd.mode
            data[name] = entry
    return data


def save_config(commands: dict[str, CommandConfig], path: Path | None = None) -> None:
    if path is None:
        path = find_config()

    output: dict = {"commands": serialize_commands_dict(commands)}

    # In folder mode, store the folder path and update the index
    from runit.settings import get_storage_mode

    if get_storage_mode() == "folder" and path != global_config_path():
        cwd = Path.cwd().resolve()
        output["folder"] = str(cwd)
        _update_folder_index(cwd)

    path.write_text(yaml.dump(output, default_flow_style=False, sort_keys=False))
