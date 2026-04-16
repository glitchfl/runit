import base64
import binascii
import sys

import click
import yaml

from runit.config import (
    CommandConfig,
    builtin_commands,
    find_config,
    global_config_path,
    load_config,
    load_disabled_builtins,
    load_merged_config,
    parse_commands_dict,
    save_config,
    save_disabled_builtins,
    serialize_commands_dict,
)
from runit.exceptions import RunitError
from runit.runner import execute, parse_captures, parse_params

SHARE_PREFIX = "runit:v1:"

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
  runit rename <old> <new>  Rename a command
  runit remove <name>       Remove a command
  runit reset               Clear all commands
  runit list                Show all commands
  runit config <key> [val]  View or change settings
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
\b
Share commands:
  runit export flutter-pc flutter-mobile     Print a code; copy + send
  runit import runit:v1:eyJjb21tYW5kcyI6...  Asks: local or global?
"""


class RunitGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args:
            from runit.settings import load_settings

            if load_settings().get("single_command") == "run":
                project_cmds = load_config()
                if len(project_cmds) == 1:
                    args = ["run", next(iter(project_cmds))]
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

    all_builtins = builtin_commands()
    disabled = (
        load_disabled_builtins(global_config_path())
        | load_disabled_builtins()
    )
    builtins = {k: v for k, v in all_builtins.items() if k not in disabled}
    sections = []

    if builtins:
        sections.append(("Built-in", builtins))
    if global_cmds:
        sections.append((f"Global ({global_config_path()})", global_cmds))
    if project_cmds:
        sections.append((f"Project ({find_config()})", project_cmds))

    for i, (label, cmds) in enumerate(sections):
        if i > 0:
            click.echo()
        click.secho(f"{label}:\n", bold=True)
        _print_commands(cmds)


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
    global_cmds = load_config(global_config_path())
    if name in project_cmds:
        source = f"project ({find_config()})"
    elif name in global_cmds:
        source = f"global ({global_config_path()})"
    else:
        source = "built-in"

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
        if name in builtin_commands():
            click.secho(
                f"'{name}' is a built-in command. Use 'runit add {name} \"...\"' to override it.",
                fg="yellow",
                err=True,
            )
        else:
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

    builtins = builtin_commands()

    if name not in commands:
        if name in builtins:
            disabled = load_disabled_builtins(path)
            if name in disabled:
                click.secho(f"Built-in '{name}' is already disabled.", fg="yellow", err=True)
                sys.exit(1)
            disabled.add(name)
            save_disabled_builtins(disabled, path)
            scope = "globally" if is_global else "for this project"
            click.secho(f"Disabled built-in command '{name}' {scope}.", fg="green")
            return
        else:
            scope = "global" if is_global else "project"
            click.secho(f"'{name}' not found in {scope} commands.", fg="red", err=True)
        sys.exit(1)

    del commands[name]
    save_config(commands, path)
    scope = "global" if is_global else "project"
    click.secho(f"Removed {scope} command '{name}'", fg="green")


@cli.command()
@click.argument("old_name")
@click.argument("new_name")
@click.option("--global", "-g", "is_global", is_flag=True, help="Rename a global command.")
def rename(old_name, new_name, is_global):
    """Rename a saved command.

    \b
    runit rename <old> <new>
    runit rename -g <old> <new>
    """
    try:
        path = global_config_path() if is_global else find_config()
        commands = load_config(path)
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if old_name not in commands:
        if old_name in builtin_commands():
            click.secho(
                f"'{old_name}' is a built-in command and cannot be renamed.",
                fg="yellow",
                err=True,
            )
        else:
            scope = "global" if is_global else "project"
            click.secho(f"'{old_name}' not found in {scope} commands.", fg="red", err=True)
        sys.exit(1)

    if new_name in commands:
        scope = "global" if is_global else "project"
        click.secho(f"'{new_name}' already exists in {scope} commands.", fg="yellow", err=True)
        sys.exit(1)

    cmd = commands.pop(old_name)
    cmd.name = new_name
    commands[new_name] = cmd
    save_config(commands, path)
    scope = "global" if is_global else "project"
    click.secho(f"Renamed {scope} command '{old_name}' → '{new_name}'", fg="green")


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


@cli.command("config")
@click.argument("key")
@click.argument("value", required=False)
def config_cmd(key, value):
    """View or change runit settings.

    \b
    runit config storage_mode           Show current storage mode
    runit config storage_mode folder    Switch to folder-specific storage
    runit config storage_mode repo      Switch to repo-specific storage
    \b
    runit config single_command         Show current single-command behavior
    runit config single_command run     Auto-run when only one project command exists
    runit config single_command ignore  Do nothing (default)
    """
    from runit.settings import (
        VALID_SINGLE_COMMAND,
        VALID_STORAGE_MODES,
        load_settings,
        save_settings,
    )

    settings = load_settings()

    if value is None:
        if key not in settings:
            click.secho(f"Unknown setting '{key}'.", fg="red", err=True)
            sys.exit(1)
        click.echo(f"{key} = {settings[key]}")
        return

    if key == "storage_mode":
        if value not in VALID_STORAGE_MODES:
            click.secho(
                f"Invalid mode '{value}'. Must be one of: {', '.join(VALID_STORAGE_MODES)}",
                fg="red",
                err=True,
            )
            sys.exit(1)

        old_mode = settings.get("storage_mode", "repo")
        if old_mode == value:
            click.echo(f"Storage mode is already '{value}'.")
            return

        settings["storage_mode"] = value
        save_settings(settings)
        click.secho(f"Storage mode set to '{value}'.", fg="green")
    elif key == "single_command":
        if value not in VALID_SINGLE_COMMAND:
            click.secho(
                f"Invalid value '{value}'. Must be one of: {', '.join(VALID_SINGLE_COMMAND)}",
                fg="red",
                err=True,
            )
            sys.exit(1)

        if settings.get("single_command", "ignore") == value:
            click.echo(f"single_command is already '{value}'.")
            return

        settings["single_command"] = value
        save_settings(settings)
        click.secho(f"single_command set to '{value}'.", fg="green")
    else:
        click.secho(f"Unknown setting '{key}'.", fg="red", err=True)
        sys.exit(1)


@cli.command("export")
@click.argument("names", nargs=-1)
@click.option("-g", "--global", "is_global", is_flag=True,
              help="Look up names in global commands only.")
@click.option("-N", "--no-names", is_flag=True,
              help="Strip command names from the share code; importer will be asked to name them.")
def export_cmd(names, is_global, no_names):
    """Export commands as a copy-pasteable share code.

    \b
    runit export                              Export every saved command
    runit export flutter-pc flutter-mobile    Export selected commands
    runit export -g my-alias                  Look up name in global only
    runit export -N flutter-pc flutter-mobile Strip names; importer picks new ones
    \b
    Pipe straight to your clipboard:
      runit export flutter-pc flutter-mobile | pbcopy
    """
    try:
        if is_global:
            source = load_config(global_config_path())
        else:
            source = {**load_config(global_config_path()), **load_config()}
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if names:
        unknown = [n for n in names if n not in source]
        if unknown:
            scope = "global" if is_global else "your saved"
            click.secho(
                f"Not found in {scope} commands: {', '.join(unknown)}",
                fg="red",
                err=True,
            )
            sys.exit(1)
        selected = {n: source[n] for n in names}
    else:
        if not source:
            click.secho("No commands to export.", fg="yellow", err=True)
            sys.exit(1)
        selected = source

    serialized = serialize_commands_dict(selected)
    if no_names:
        anonymous = {f"cmd{i + 1}": entry for i, entry in enumerate(serialized.values())}
        payload = {"anonymous": True, "commands": anonymous}
    else:
        payload = {"commands": serialized}
    yaml_text = yaml.dump(payload, default_flow_style=False, sort_keys=False)
    encoded = base64.urlsafe_b64encode(yaml_text.encode("utf-8")).decode("ascii")

    click.echo(SHARE_PREFIX + encoded)
    suffix = ", names stripped" if no_names else ""
    click.secho(
        f"Share with: runit import <code>  ({len(selected)} command(s){suffix})",
        fg="green",
        err=True,
    )


@cli.command("import")
@click.argument("code", required=False)
@click.option("-g", "--global", "is_global", is_flag=True,
              help="Save imported commands globally.")
@click.option("-l", "--local", "is_local", is_flag=True,
              help="Save imported commands to this project.")
@click.option("--force", is_flag=True, help="Overwrite existing commands with the same name.")
def import_cmd(code, is_global, is_local, force):
    """Import commands from a share code.

    \b
    runit import <code>           Asks whether to save locally or globally
    runit import <code> -l        Save to this project
    runit import <code> -g        Save globally
    runit import <code> --force   Overwrite existing commands of the same name
    \b
    If the code includes names, you'll be asked whether to rename any.
    If it was exported with -N (no names), you'll be prompted to name each one.
    \b
    Read the code from stdin:
      pbpaste | runit import -l
    """
    if is_global and is_local:
        click.secho("Pass either --global or --local, not both.", fg="red", err=True)
        sys.exit(1)

    code_from_stdin = code is None
    if code_from_stdin:
        code = sys.stdin.read()
        try:
            sys.stdin = open("/dev/tty", "r")
        except OSError:
            pass
    code = code.strip()

    if not code.startswith(SHARE_PREFIX):
        click.secho(
            f"Not a valid runit share code (expected '{SHARE_PREFIX}' prefix).",
            fg="red",
            err=True,
        )
        sys.exit(1)

    encoded = code[len(SHARE_PREFIX):]
    try:
        yaml_bytes = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except (binascii.Error, ValueError):
        click.secho("Share code is corrupted (base64 decode failed).", fg="red", err=True)
        sys.exit(1)

    try:
        raw = yaml.safe_load(yaml_bytes.decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        click.secho(f"Share code is corrupted ({e}).", fg="red", err=True)
        sys.exit(1)

    is_anonymous = isinstance(raw, dict) and bool(raw.get("anonymous", False))

    try:
        incoming = parse_commands_dict(raw)
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    if not incoming:
        click.secho("Share code contains no commands.", fg="yellow", err=True)
        sys.exit(1)

    is_tty = sys.stdin is not None and sys.stdin.isatty()

    incoming = _resolve_import_names(incoming, is_anonymous, is_tty)

    if is_global:
        scope, dest = "global", global_config_path()
    elif is_local:
        scope, dest = "project", find_config()
    else:
        if not is_tty:
            click.secho(
                "Pass -l (local) or -g (global) when running non-interactively.",
                fg="red",
                err=True,
            )
            sys.exit(1)
        choice = click.prompt(
            "Save to",
            type=click.Choice(["local", "global"]),
            default="local",
        )
        if choice == "global":
            scope, dest = "global", global_config_path()
        else:
            scope, dest = "project", find_config()

    try:
        existing = load_config(dest)
    except RunitError as e:
        click.secho(str(e), fg="red", err=True)
        sys.exit(1)

    imported = []
    skipped = []
    for name, cmd in incoming.items():
        if name in existing and not force:
            skipped.append(name)
            continue
        cmd.name = name
        existing[name] = cmd
        imported.append(name)

    if imported:
        save_config(existing, dest)

    if skipped:
        click.secho(
            f"Skipped (already exist, pass --force to overwrite): {', '.join(skipped)}",
            fg="yellow",
        )

    if imported:
        click.secho(
            f"Imported {len(imported)} command(s) into {scope}: {', '.join(imported)}",
            fg="green",
        )
    elif not skipped:
        click.echo("Nothing imported.")


def _show_steps(cmd: CommandConfig) -> None:
    for step in cmd.steps:
        click.echo(f"  {step}")


def _prompt_unique_name(prompt_text: str, taken: dict, default: str | None = None) -> str:
    while True:
        new_name = click.prompt(prompt_text, default=default, type=str).strip()
        if not new_name:
            click.secho("Name cannot be empty.", fg="yellow", err=True)
            continue
        if new_name != default and new_name in taken:
            click.secho(f"'{new_name}' is already used in this import.", fg="yellow", err=True)
            continue
        return new_name


def _resolve_import_names(
    incoming: dict[str, CommandConfig],
    is_anonymous: bool,
    is_tty: bool,
) -> dict[str, CommandConfig]:
    if is_anonymous:
        if not is_tty:
            click.secho(
                "Anonymous share code: a TTY is required to name the commands.",
                fg="red",
                err=True,
            )
            sys.exit(1)
        click.echo(f"Naming {len(incoming)} command(s) from the share code:")
        named: dict[str, CommandConfig] = {}
        for i, cmd in enumerate(incoming.values(), 1):
            click.echo()
            click.secho(f"Command {i} of {len(incoming)}:", bold=True)
            _show_steps(cmd)
            new_name = _prompt_unique_name("Name", named)
            cmd.name = new_name
            named[new_name] = cmd
        click.echo()
        return named

    if not is_tty:
        return incoming

    click.echo(f"Importing: {', '.join(incoming.keys())}")
    if not click.confirm("Rename any of these?", default=False):
        return incoming

    renamed: dict[str, CommandConfig] = {}
    for original, cmd in incoming.items():
        click.echo()
        click.secho(original, bold=True)
        _show_steps(cmd)
        new_name = _prompt_unique_name("Name", renamed, default=original)
        cmd.name = new_name
        renamed[new_name] = cmd
    click.echo()
    return renamed
