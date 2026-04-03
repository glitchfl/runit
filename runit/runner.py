import random
import subprocess

import click

from runit.config import CommandConfig


def execute(command: CommandConfig) -> int:
    """Execute a command config and return the exit code."""
    if command.mode == "random":
        return _run_step(random.choice(command.steps))

    # Sequential: run each step, stop on first failure
    for step in command.steps:
        exit_code = _run_step(step)
        if exit_code != 0:
            return exit_code
    return 0


def _run_step(step: str) -> int:
    """Run a single shell command, printing it before execution."""
    click.secho(f"$ {step}", fg="cyan")
    result = subprocess.run(step, shell=True)
    return result.returncode
