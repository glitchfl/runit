import random
import re
import subprocess

import click

from runit.config import CommandConfig

# Matches {var} or {var:default}
PARAM_PATTERN = re.compile(r"\{(\w+)(?::([^}]*))?\}")


def parse_params(steps: list[str]) -> dict[str, str | None]:
    params: dict[str, str | None] = {}
    for step in steps:
        for match in PARAM_PATTERN.finditer(step):
            name = match.group(1)
            default = match.group(2)
            if name not in params:
                params[name] = default
    return params


def resolve_step(step: str, args: dict[str, str]) -> str:
    """Replace {var} and {var:default} placeholders with provided values."""
    def replacer(match: re.Match) -> str:
        name = match.group(1)
        return args[name]
    return PARAM_PATTERN.sub(replacer, step)


def execute(command: CommandConfig, args: dict[str, str] | None = None) -> int:
    args = args or {}

    # Validate all required params are provided
    params = parse_params(command.steps)
    missing = []
    for name, default in params.items():
        if name not in args:
            if default is not None:
                args[name] = default
            else:
                missing.append(name)

    if missing:
        click.secho(
            f"Missing required args: {', '.join(missing)}\n"
            f"Usage: runit {command.name} {' '.join(f'{m}=<value>' for m in missing)}",
            fg="red",
            err=True,
        )
        return 1

    if command.mode == "random":
        return _run_step(resolve_step(random.choice(command.steps), args))

    for step in command.steps:
        exit_code = _run_step(resolve_step(step, args))
        if exit_code != 0:
            return exit_code
    return 0


def _run_step(step: str) -> int:
    """Run a single shell command, printing it before execution."""
    click.secho(f"$ {step}", fg="cyan")
    result = subprocess.run(step, shell=True)
    return result.returncode
