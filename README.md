# runit

Stop typing the same long commands over and over. `runit` lets you save commands with short names and run them instantly.

```
runit add build "cargo build --release"
runit build
```

That's it. No config files to manage, no setup step. Just add a command and run it.

## Install

```bash
pip install -e .
```

Requires Python 3.10+.

## Quick start

```bash
# Save a command
runit add test "pytest -v --tb=short"

# Run it
runit test

# See what you've got
runit list
```

## Multiple steps

Commands can be a sequence. They run in order, stopping if any step fails.

```bash
runit add deploy "npm run build" "npm test" "rsync -av dist/ server:/var/www/"

runit deploy
# $ npm run build
# $ npm test
# $ rsync -av dist/ server:/var/www/
```

## Parameters

Some commands are almost the same every time, just with a different value here and there. Use `{var}` placeholders and pass values positionally - just type the values after the command name, in order.

```bash
runit add deploy "kubectl apply -f k8s/{env}.yaml" "echo 'deployed to {env}'"

runit deploy staging
# $ kubectl apply -f k8s/staging.yaml
# $ echo 'deployed to staging'

runit deploy prod
# $ kubectl apply -f k8s/prod.yaml
# $ echo 'deployed to prod'
```

Multiple parameters just go in order:

```bash
runit add ssh "ssh {user}@{host}"

runit ssh admin 192.168.1.10
# $ ssh admin@192.168.1.10
```

You can set defaults with `{var:default}` - if you don't pass it, the default kicks in.

```bash
runit add push "docker push myapp:{tag:latest}"

runit push              # uses tag=latest
runit push v2.0         # uses tag=v2.0
```

Strings with spaces work fine in quotes:

```bash
runit add greet "echo {message}"

runit greet "hello world"
# $ echo hello world
```

If you forget a required parameter, runit tells you what's missing:

```
$ runit deploy
Missing: env
Usage: runit deploy <env>
```

## Capture output as variables

Sometimes a later step needs the output of an earlier one. Prefix a step with `@varname` to capture its stdout into a variable, then use `{varname}` in any step that follows.

```bash
runit add whoami "@user whoami" "echo Hello, {user}"

runit whoami
# $ @user whoami
#   user = itayfliess
# $ echo Hello, itayfliess
# Hello, itayfliess
```

A more practical example — grab your local IP and use it:

```bash
runit add myip "@ip ifconfig en0 | grep 'inet ' | awk '{print \$2}'" "echo {ip}"

runit myip
# $ @ip ifconfig en0 | grep 'inet ' | awk '{print $2}'
#   ip = 192.168.1.5
# $ echo 192.168.1.5
# 192.168.1.5
```

Captures can be combined with regular parameters:

```bash
runit add deploy "@host cat config/{env}.txt" "scp build.tar {host}:/app/"

runit deploy staging
```

If a capture step fails, execution stops — same as any other step.

## Random mode

Pick a random command from a list each time you run it.

```bash
runit add tip "echo 'commit often'" "echo 'write tests'" "echo 'take a break'" --mode random

runit tip
# $ echo 'take a break'   (random pick)
```

## Built-in commands

runit ships with a set of built-in git/dev commands ready to use out of the box. They show up under "Built-in" in `runit list` and work in any project.

| Command | Description |
|---------|-------------|
| `runit prune` | Delete local branches whose remote has been deleted |
| `runit untrack <path>` | Remove a file from git tracking (without touching `.gitignore`) |
| `runit loc [ext]` | Count lines of code by file type (default: `.py`) |
| `runit heatmap` | Show the 20 most frequently changed files in git history |

```bash
runit prune
# Fetches remote and deletes any local branches marked as gone

runit untrack src/secret.txt
# $ git rm --cached -r src/secret.txt

runit loc
# Counts all .py files

runit loc ts
# Counts all .ts files

runit heatmap
#  11 runit/cli.py
#   4 runit/runner.py
#   ...
```

Built-in commands can't be removed or edited, but you can override any of them by adding a project or global command with the same name.

## Global commands

By default, commands are scoped to your project. If you want a command available everywhere, add it with `-g`:

```bash
runit add -g gs "git status -sb"
runit add -g gp "git push"

# Now 'runit gs' works in any directory
```

Project commands take priority - if you have a global `build` and a project `build`, the project one wins.

```bash
runit list           # shows both global and project commands
runit list -g        # shows only global commands
```

## Inspecting commands

Use `show` to see the full details of a command - where it's stored, its mode, parameters, and every step.

```bash
runit show deploy
# deploy
#   source:  project (.git/runit.yaml)
#   mode:    sequential
#   params:  env (required), tag (default: latest)
#   steps:
#     1. kubectl apply -f k8s/{env}.yaml
#     2. echo 'tag: {tag:latest}'

runit show myip
# myip
#   source:  project (.git/runit.yaml)
#   mode:    sequential
#   captures: ip
#   steps:
#     1. @ip ifconfig en0 | grep 'inet ' | awk '{print $2}'
#     2. echo {ip}
```

## Editing commands

Update a command without having to remove and re-add it.

```bash
# Replace the steps
runit edit deploy "new-step-1" "new-step-2"

# Change just the mode
runit edit deploy --mode random

# Update both steps and mode
runit edit deploy "new-cmd" --mode sequential

# Edit a global command
runit edit -g gs "git status -sb --porcelain"
```

## Renaming commands

```bash
runit rename test t          # rename project command
runit rename -g gs gst       # rename global command
```

## Removing commands

```bash
runit remove test           # remove project command
runit remove -g gs          # remove global command
```

## Resetting

Clear all commands at once.

```bash
runit reset          # clear project commands
runit reset -g       # clear global commands
runit reset -a       # clear both project and global
```

## Where are commands stored?

You don't need to think about this, but if you're curious:

- **Git projects** - inside `.git/runit.yaml` (invisible, not tracked)
- **Other directories** - in `~/.cache/runit/`, keyed by folder
- **Global commands** - in `~/.config/runit/runit.yaml`

No files in your project directory. Nothing to `.gitignore`.

## All commands

| Command | Description |
|---------|-------------|
| `runit <name> [args]` | Run a saved command |
| `runit add <name> "cmd" ...` | Save a new command |
| `runit edit <name> "cmd" ...` | Update an existing command |
| `runit show <name>` | Show full command details |
| `runit rename <old> <new>` | Rename a command |
| `runit remove <name>` | Remove a command |
| `runit reset` | Clear all commands |
| `runit list` | List all commands (built-in, global, project) |

Add `-g` to `add`, `edit`, `rename`, `remove`, `list`, or `reset` to target global commands.

### Step syntax

| Syntax | Meaning |
|--------|---------|
| `{var}` | Required parameter — pass positionally when running |
| `{var:default}` | Optional parameter with a default value |
| `@varname cmd` | Capture step — runs `cmd`, stores stdout as `varname` |

## Credit

Credit to @Eyalcfish for the idea and its based on his pulse project.


## Disclaimer

AI was used to generate almost all of this tool.