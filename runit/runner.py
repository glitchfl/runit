import os
import random
import re
import subprocess
from pathlib import Path

import click

from runit.config import CommandConfig

# Matches {var} or {var:default}
PARAM_PATTERN = re.compile(r"\{(\w+)(?::([^}]*))?\}")

# Matches capture step: @varname command...
CAPTURE_PATTERN = re.compile(r"^@(\w+)\s+(.+)$", re.DOTALL)

# Matches cd command: cd [path]
CD_PATTERN = re.compile(r"^cd(?:\s+(.+))?$")


def parse_captures(steps: list[str]) -> list[str]:
    """Extract capture variable names from steps like '@varname command'.

    Returns list of variable names in order of appearance.
    """
    captures = []
    for step in steps:
        match = CAPTURE_PATTERN.match(step)
        if match:
            captures.append(match.group(1))
    return captures


def parse_params(steps: list[str]) -> dict[str, str | None]:
    """Extract all {var} and {var:default} placeholders from steps.

    Returns dict of param_name -> default_value (None if no default),
    in order of first appearance. Variables defined by capture steps
    (@varname ...) are excluded.
    """
    capture_names = set(parse_captures(steps))
    params: dict[str, str | None] = {}
    for step in steps:
        # For capture steps, only parse the command part
        capture_match = CAPTURE_PATTERN.match(step)
        text = capture_match.group(2) if capture_match else step
        for match in PARAM_PATTERN.finditer(text):
            name = match.group(1)
            default = match.group(2)
            if name not in params and name not in capture_names:
                params[name] = default
    return params


def resolve_step(step: str, resolved: dict[str, str]) -> str:
    """Replace {var} and {var:default} placeholders with resolved values."""
    def replacer(match: re.Match) -> str:
        name = match.group(1)
        if name in resolved:
            return resolved[name]
        return match.group(0)
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

    cwd: Path | None = None

    if command.mode == "random":
        exit_code, _ = _execute_step(random.choice(command.steps), resolved, cwd)
        return exit_code

    for step in command.steps:
        exit_code, cwd = _execute_step(step, resolved, cwd)
        if exit_code != 0:
            return exit_code
    return 0


def _execute_step(step: str, resolved: dict[str, str], cwd: Path | None) -> tuple[int, Path | None]:
    """Execute a single step, handling both regular and capture steps."""
    capture_match = CAPTURE_PATTERN.match(step)
    if capture_match:
        var_name = capture_match.group(1)
        command = resolve_step(capture_match.group(2), resolved)
        return _run_capture_step(var_name, command, resolved, cwd), cwd

    resolved_step = resolve_step(step, resolved)

    # Handle cd specially so directory changes persist across steps
    cd_match = CD_PATTERN.match(resolved_step.strip())
    if cd_match:
        raw_path = cd_match.group(1)
        if raw_path is None:
            new_cwd = Path.home()
        else:
            path_str = raw_path.strip().strip("\"'")
            path_str = os.path.expanduser(path_str)
            path_str = os.path.expandvars(path_str)
            p = Path(path_str)
            base = cwd or Path.cwd()
            new_cwd = (p if p.is_absolute() else base / p).resolve()

        if not new_cwd.is_dir():
            click.secho(f"cd: no such file or directory: {raw_path}", fg="red", err=True)
            return 1, cwd

        click.secho(f"$ cd {raw_path or '~'}", fg="cyan")
        return 0, new_cwd

    return _run_step(resolved_step, cwd), cwd


def _run_capture_step(var_name: str, command: str, resolved: dict[str, str], cwd: Path | None) -> int:
    """Run a command, capture its stdout, and store as a variable."""
    click.secho(f"$ @{var_name} {command}", fg="cyan")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        if result.stderr:
            click.secho(result.stderr.rstrip(), fg="red", err=True)
        return result.returncode
    value = result.stdout.strip()
    resolved[var_name] = value
    click.secho(f"  {var_name} = {value}", fg="green")
    return 0


def _run_step(step: str, cwd: Path | None) -> int:
    """Run a single shell command, printing it before execution."""
    click.secho(f"$ {step}", fg="cyan")
    result = subprocess.run(step, shell=True, cwd=cwd)
    return result.returncode
