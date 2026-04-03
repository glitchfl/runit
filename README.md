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

If you forget a required parameter, runit tells you what's missing:

```
$ runit deploy
Missing: env
Usage: runit deploy <env>
```

## Random mode

Pick a random command from a list each time you run it.

```bash
runit add tip "echo 'commit often'" "echo 'write tests'" "echo 'take a break'" --mode random

runit tip
# $ echo 'take a break'   (random pick)
```

## Global commands

By default, commands are scoped to your project. If you want a command available everywhere, add it with `-g`:

```bash
runit add -g gs "git status -sb"
runit add -g gp "git push"

# Now 'runit gs' works in any directory
```

Project commands take priority — if you have a global `build` and a project `build`, the project one wins.

```bash
runit list           # shows both global and project commands
runit list -g        # shows only global commands
```

## Removing commands

```bash
runit remove test           # remove project command
runit remove -g gs          # remove global command
```

## Where are commands stored?

You don't need to think about this, but if you're curious:

- **Git projects** — inside `.git/runit.yaml` (invisible, not tracked)
- **Other directories** — in `~/.cache/runit/`, keyed by folder
- **Global commands** — in `~/.config/runit/runit.yaml`

No files in your project directory. Nothing to `.gitignore`.

## License

MIT
