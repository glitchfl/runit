import subprocess
from pathlib import Path

import click


def prune(resolved: dict[str, str]) -> int:
    click.secho("$ git fetch -p", fg="cyan")
    result = subprocess.run(["git", "fetch", "-p"])
    if result.returncode != 0:
        return result.returncode

    result = subprocess.run(
        ["git", "branch", "-vv"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return result.returncode

    pruned = 0
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if ": gone]" in stripped:
            branch = stripped.split()[0].lstrip("* ")
            click.secho(f"$ git branch -D {branch}", fg="cyan")
            subprocess.run(["git", "branch", "-D", branch])
            pruned += 1

    if pruned == 0:
        click.echo("No stale branches to prune.")
    return 0


def loc(resolved: dict[str, str]) -> int:
    ext = resolved.get("ext", "py")
    exclude = {".git", "node_modules", "__pycache__", "venv", ".venv", "env"}

    counts: list[tuple[int, str]] = []
    total = 0
    for path in sorted(Path(".").rglob(f"*.{ext}")):
        if any(part in exclude for part in path.parts):
            continue
        try:
            lines = len(path.read_text(errors="replace").splitlines())
            counts.append((lines, str(path)))
            total += lines
        except (OSError, PermissionError):
            continue

    counts.sort()
    for line_count, name in counts:
        click.echo(f"{line_count:>8} {name}")
    if counts:
        click.echo(f"{total:>8} total")
    else:
        click.echo(f"No .{ext} files found.")
    return 0


def heatmap(resolved: dict[str, str]) -> int:
    result = subprocess.run(
        ["git", "log", "--pretty=format:", "--name-only"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        click.secho("Failed to read git history.", fg="red", err=True)
        return result.returncode

    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        name = line.strip()
        if name:
            counts[name] = counts.get(name, 0) + 1

    sorted_files = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20]
    for name, count in sorted_files:
        click.echo(f"{count:>4} {name}")
    return 0
