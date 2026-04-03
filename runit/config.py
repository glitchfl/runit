from dataclasses import dataclass
from pathlib import Path

import yaml

from runit.exceptions import ConfigError, ConfigNotFoundError

CONFIG_FILENAME = "runit.yaml"

VALID_MODES = ("sequential", "random")


@dataclass
class CommandConfig:
    name: str
    steps: list[str]
    mode: str = "sequential"


def find_config() -> Path:
    path = Path.cwd() / CONFIG_FILENAME
    if not path.exists():
        raise ConfigNotFoundError(
            f"No {CONFIG_FILENAME} found in the current directory.\n"
            f"Run 'runit init' to create one."
        )
    return path


def load_config(path: Path | None = None) -> dict[str, CommandConfig]:
    if path is None:
        path = find_config()

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse {CONFIG_FILENAME}: {e}") from e

    if not isinstance(raw, dict) or "commands" not in raw:
        raise ConfigError(
            f"{CONFIG_FILENAME} must have a top-level 'commands' key."
        )

    commands_raw = raw["commands"]
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


def generate_default_config() -> str:
    return """\
# runit.yaml - define your project commands here
# Docs: https://github.com/chessitay/runit

commands:
  # Simple single command
  hello:
    run: "echo 'Hello from runit!'"

  # Sequence of commands (runs in order)
  build:
    run:
      - "echo 'Step 1: compiling...'"
      - "echo 'Step 2: done!'"

  # Random pick from a list
  tip:
    run:
      - "echo 'Tip: commit often'"
      - "echo 'Tip: write tests first'"
      - "echo 'Tip: take breaks'"
    mode: random
"""
