import sys

import click

from runit.config import (
    CommandConfig,
    find_config,
    global_config_path,
    load_config,
    load_merged_config,
    save_config,
)
from runit.exceptions import RunitError
from runit.runner import execute, parse_captures, parse_params

class RunitHelpFormatter(click.HelpFormatter):
    def write_text(self, text):
        if text:
            self.write(text + "\n")


class RunitContext(click.Context):
    formatter_class = RunitHelpFormatter


HELP_TEXT = """Save commands, run them by name.

\b
  runit <name> [args]       Run a saved command
  runit add <name> "cmd"    Save a new command
  runit show <name>         Show command details
  runit edit <name> "cmd"   Update a command
  runit remove <name>       Remove a command
  runit reset               Clear all commands
  runit list                Show all commands
\b
Examples:
  runit add test "pytest -v"
  runit test
\b
  runit add deploy "kubectl apply -f {env}.yaml"
  runit deploy staging
\b
  runit add -g gs "git status -sb"
  runit gs
\b
Capture output as variables:
  runit add myip "@ip ifconfig en0 | grep inet" "echo {ip}"
  runit myip
"""


class RunitGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["run"] + args
        return super().parse_args(ctx, args)


@click.group(cls=RunitGroup, help=HELP_TEXT, context_settings={"max_content_width": 120})
def cli():
    pass


@cli.command(hidden=True)
@click.argument("name")
@click.argument("extra_args", nargs=-1)
def run(name, extra_args):
    try:
        commands = load_merged_config()
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if not commands:
        click.secho(
            "No commands defined yet. Run 'runit add <name> \"command\"' to create one.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    if name not in commands:
        click.secho(f"Unknown command '{name}'.", fg="red", err=True)
        click.echo("Run 'runit list' to see available commands.")
        sys.exit(1)

    exit_code = execute(commands[name], list(extra_args))
    sys.exit(exit_code)


@cli.command("list")
@click.option("--global", "-g", "is_global", is_flag=True, help="Show only global commands.")
def list_commands(is_global):
    """Show all saved commands for this project and globally."""
    try:
        if is_global:
            commands = load_config(global_config_path())
            label = f"Global ({global_config_path()})"
        else:
            project_cmds = load_config()
            global_cmds = load_config(global_config_path())
            label = None
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if is_global:
        if not commands:
            click.echo("No global commands yet. Add one with 'runit add -g <name> \"command\"'.")
            return
        click.secho(f"{label}:\n", bold=True)
        _print_commands(commands)
        return

    if not project_cmds and not global_cmds:
        click.echo("No commands yet. Add one with 'runit add <name> \"command\"'.")
        return

    if global_cmds:
        click.secho(f"Global ({global_config_path()}):\n", bold=True)
        _print_commands(global_cmds)
        click.echo()

    if project_cmds:
        click.secho(f"Project ({find_config()}):\n", bold=True)
        _print_commands(project_cmds)
    elif global_cmds:
        click.echo("No project commands. Add one with 'runit add <name> \"command\"'.")


@cli.command()
@click.argument("name")
def show(name):
    """Show full details of a command.

    \b
    runit show <name>
    """
    try:
        commands = load_merged_config()
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if name not in commands:
        click.secho(f"Unknown command '{name}'.", fg="red", err=True)
        click.echo("Run 'runit list' to see available commands.")
        sys.exit(1)

    cmd = commands[name]

    # Check where it lives
    project_cmds = load_config()
    if name in project_cmds:
        source = f"project ({find_config()})"
    else:
        source = f"global ({global_config_path()})"

    click.secho(f"{name}", bold=True)
    click.echo(f"  source:  {source}")
    click.echo(f"  mode:    {cmd.mode}")

    params = parse_params(cmd.steps)
    if params:
        parts = []
        for param_name, default in params.items():
            if default is not None:
                parts.append(f"{param_name} (default: {default})")
            else:
                parts.append(f"{param_name} (required)")
        click.echo(f"  params:  {', '.join(parts)}")

    captures = parse_captures(cmd.steps)
    if captures:
        click.echo(f"  captures: {', '.join(captures)}")

    click.echo(f"  steps:")
    for i, step in enumerate(cmd.steps, 1):
        click.echo(f"    {i}. {step}")


def _format_params(cmd: CommandConfig) -> str:
    """Format parameter info for display."""
    params = parse_params(cmd.steps)
    if not params:
        return ""
    parts = []
    for name, default in params.items():
        if default is not None:
            parts.append(f"[{name}={default}]")
        else:
            parts.append(f"<{name}>")
    return "  " + " ".join(parts)


def _print_commands(commands: dict[str, CommandConfig]) -> None:
    for name, cmd in commands.items():
        mode_tag = f"  [{cmd.mode}]" if cmd.mode != "sequential" else ""
        param_info = _format_params(cmd)
        if len(cmd.steps) == 1:
            click.echo(f"  {name:<16} {cmd.steps[0]}{mode_tag}")
        else:
            click.echo(f"  {name:<16} ({len(cmd.steps)} steps){mode_tag}")
        if param_info:
            click.echo(f"  {'':<16}{param_info}")


@cli.command()
@click.argument("name")
@click.argument("steps", nargs=-1, required=True)
@click.option("--mode", "-m", type=click.Choice(["sequential", "random"]), default="sequential",
              help="Run steps in order (default) or pick one at random.")
@click.option("--global", "-g", "is_global", is_flag=True, help="Save as a global command (available everywhere).")
def add(name, steps, mode, is_global):
    """Save a new command.

    \b
    runit add <name> "command"
    runit add <name> "step1" "step2" "step3"
    runit add <name> "echo {var}" --mode random
    runit add -g <name> "command"

    \b
    Parameters:
      Use {var} for required values, {var:default} for optional ones.
      Pass them positionally when running: runit <name> value1 value2
    \b
    Captures:
      Use @varname to capture a command's output as a variable.
      Reference it in later steps with {varname}.
    """
    try:
        path = global_config_path() if is_global else find_config()
        commands = load_config(path)
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if name in commands:
        scope = "global" if is_global else "project"
        click.secho(
            f"'{name}' already exists in {scope} commands. Remove it first with 'runit remove {'-g ' if is_global else ''}{name}'.",
            fg="yellow",
            err=True,
        )
        sys.exit(1)

    commands[name] = CommandConfig(name=name, steps=list(steps), mode=mode)
    save_config(commands, path)
    scope = "global" if is_global else "project"
    click.secho(f"Added {scope} command '{name}'", fg="green")


@cli.command()
@click.argument("name")
@click.argument("steps", nargs=-1)
@click.option("--mode", "-m", type=click.Choice(["sequential", "random"]), default=None,
              help="Change mode to sequential or random.")
@click.option("--global", "-g", "is_global", is_flag=True, help="Edit a global command.")
def edit(name, steps, mode, is_global):
    """Update an existing command.

    \b
    runit edit <name> "new-cmd"              Replace steps
    runit edit <name> "step1" "step2"        Replace with new steps
    runit edit <name> --mode random          Change mode only
    runit edit <name> "new-cmd" -m random    Replace steps and mode
    runit edit -g <name> "new-cmd"           Edit a global command
    """
    try:
        path = global_config_path() if is_global else find_config()
        commands = load_config(path)
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if name not in commands:
        scope = "global" if is_global else "project"
        click.secho(f"'{name}' not found in {scope} commands.", fg="red", err=True)
        sys.exit(1)

    if not steps and mode is None:
        click.secho("Nothing to update. Provide new steps or --mode.", fg="yellow", err=True)
        sys.exit(1)

    cmd = commands[name]
    if steps:
        cmd.steps = list(steps)
    if mode is not None:
        cmd.mode = mode

    save_config(commands, path)

    changes = []
    if steps:
        changes.append("steps")
    if mode is not None:
        changes.append("mode")
    click.secho(f"Updated '{name}' ({', '.join(changes)})", fg="green")


@cli.command()
@click.argument("name")
@click.option("--global", "-g", "is_global", is_flag=True, help="Remove a global command.")
def remove(name, is_global):
    """Remove a saved command.

    \b
    runit remove <name>
    runit remove -g <name>
    """
    try:
        path = global_config_path() if is_global else find_config()
        commands = load_config(path)
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if name not in commands:
        scope = "global" if is_global else "project"
        click.secho(f"'{name}' not found in {scope} commands.", fg="red", err=True)
        sys.exit(1)

    del commands[name]
    save_config(commands, path)
    scope = "global" if is_global else "project"
    click.secho(f"Removed {scope} command '{name}'", fg="green")


@cli.command()
@click.option("--global", "-g", "is_global", is_flag=True, help="Clear global commands.")
@click.option("--all", "-a", "reset_all", is_flag=True, help="Clear both project and global commands.")
def reset(is_global, reset_all):
    """Clear all saved commands.

    \b
    runit reset          Clear project commands
    runit reset -g       Clear global commands
    runit reset -a       Clear both project and global commands
    """
    targets = []

    if reset_all:
        targets.append(("project", find_config()))
        targets.append(("global", global_config_path()))
    elif is_global:
        targets.append(("global", global_config_path()))
    else:
        targets.append(("project", find_config()))

    for scope, path in targets:
        if path.exists():
            path.unlink()
            click.secho(f"Cleared all {scope} commands.", fg="green")
        else:
            click.echo(f"No {scope} commands to clear.")
