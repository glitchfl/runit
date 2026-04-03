import sys

import click

from runit.config import CommandConfig, find_config, load_config, save_config
from runit.exceptions import RunitError
from runit.runner import execute


class RunitGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["run"] + args
        return super().parse_args(ctx, args)


@click.group(cls=RunitGroup)
def cli():
    """runit - run project commands defined per project."""


@cli.command(hidden=True)
@click.argument("name")
def run(name):
    try:
        commands = load_config()
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if not commands:
        click.secho(
            "No commands defined yet. Use 'runit add' to create one.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    if name not in commands:
        click.secho(
            f"Unknown command '{name}'. Run 'runit list' to see available commands.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    exit_code = execute(commands[name])
    sys.exit(exit_code)


@cli.command("list")
def list_commands():
    try:
        commands = load_config()
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if not commands:
        click.echo("No commands defined yet. Use 'runit add' to create one.")
        return

    config_path = find_config()
    click.secho(f"Commands ({config_path}):\n", bold=True)
    for name, cmd in commands.items():
        mode_tag = f"  [{cmd.mode}]" if cmd.mode != "sequential" else ""
        if len(cmd.steps) == 1:
            click.echo(f"  {name:<16} {cmd.steps[0]}{mode_tag}")
        else:
            click.echo(f"  {name:<16} ({len(cmd.steps)} steps){mode_tag}")


@cli.command()
@click.argument("name")
@click.argument("steps", nargs=-1, required=True)
@click.option("--mode", "-m", type=click.Choice(["sequential", "random"]), default="sequential")
def add(name, steps, mode):
    try:
        commands = load_config()
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if name in commands:
        click.secho(f"Command '{name}' already exists. Remove it first to replace.", fg="yellow", err=True)
        sys.exit(1)

    commands[name] = CommandConfig(name=name, steps=list(steps), mode=mode)
    save_config(commands)
    click.secho(f"Added command '{name}'", fg="green")


@cli.command()
@click.argument("name")
def remove(name):
    try:
        commands = load_config()
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if name not in commands:
        click.secho(f"Command '{name}' not found.", fg="red", err=True)
        sys.exit(1)

    del commands[name]
    save_config(commands)
    click.secho(f"Removed command '{name}'", fg="green")
