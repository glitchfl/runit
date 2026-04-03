import sys
from pathlib import Path

import click

from runit.config import CONFIG_FILENAME, generate_default_config, load_config
from runit.exceptions import RunitError
from runit.runner import execute


class RunitGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["run"] + args
        return super().parse_args(ctx, args)


@click.group(cls=RunitGroup)
def cli():
    """runit - run project commands defined in runit.yaml."""


@cli.command(hidden=True)
@click.argument("name")
def run(name):
    try:
        commands = load_config()
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
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
        click.echo("No commands defined in runit.yaml.")
        return

    click.secho("Available commands:\n", bold=True)
    for name, cmd in commands.items():
        mode_tag = f"  [{cmd.mode}]" if cmd.mode != "sequential" else ""
        if len(cmd.steps) == 1:
            click.echo(f"  {name:<16} {cmd.steps[0]}{mode_tag}")
        else:
            click.echo(f"  {name:<16} ({len(cmd.steps)} steps){mode_tag}")


@cli.command()
def init():
    path = Path.cwd() / CONFIG_FILENAME
    if path.exists():
        click.secho(f"{CONFIG_FILENAME} already exists.", fg="yellow", err=True)
        sys.exit(1)

    path.write_text(generate_default_config())
    click.secho(f"Created {CONFIG_FILENAME}", fg="green")
