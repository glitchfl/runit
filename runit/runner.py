import random
import re
import subprocess

import click

from runit.config import CommandConfig

# Matches {var} or {var:default}
PARAM_PATTERN = re.compile(r"\{(\w+)(?::([^}]*))?\}")


def parse_params(steps: list[str]) -> dict[str, str | None]:
    """Extract all {var} and {var:default} placeholders from steps.

    Returns dict of param_name -> default_value (None if no default),
    in order of first appearance.
    """
    params: dict[str, str | None] = {}
    for step in steps:
        for match in PARAM_PATTERN.finditer(step):
            name = match.group(1)
            default = match.group(2)
            if name not in params:
                params[name] = default
    return params


def resolve_step(step: str, resolved: dict[str, str]) -> str:
    """Replace {var} and {var:default} placeholders with resolved values."""
    def replacer(match: re.Match) -> str:
        name = match.group(1)
        return resolved[name]
    return PARAM_PATTERN.sub(replacer, step)


def execute(command: CommandConfig, positional_args: list[str] | None = None) -> int:
    """Execute a command config and return the exit code."""
    positional_args = positional_args or []

    params = parse_params(command.steps)
    param_names = list(params.keys())

    # Match positional args to params in order
    resolved: dict[str, str] = {}
    for i, name in enumerate(param_names):
        if i < len(positional_args):
            resolved[name] = positional_args[i]
        elif params[name] is not None:
            resolved[name] = params[name]

    # Check for missing required params
    missing = [name for name in param_names if name not in resolved]
    if missing:
        usage_args = " ".join(f"<{m}>" for m in param_names)
        click.secho(
            f"Missing: {', '.join(missing)}\n"
            f"Usage: runit {command.name} {usage_args}",
            fg="red",
            err=True,
        )
        return 1

    # Check for extra args
    if len(positional_args) > len(param_names):
        click.secho(
            f"Too many arguments. Expected {len(param_names)}, got {len(positional_args)}.",
            fg="red",
            err=True,
        )
        return 1

    if command.mode == "random":
        return _run_step(resolve_step(random.choice(command.steps), resolved))

    for step in command.steps:
        exit_code = _run_step(resolve_step(step, resolved))
        if exit_code != 0:
            return exit_code
    return 0


def _run_step(step: str) -> int:
    """Run a single shell command, printing it before execution."""
    click.secho(f"$ {step}", fg="cyan")
    result = subprocess.run(step, shell=True)
    return result.returncode
