# Advanced usage

Power-user patterns and real-world workflows for runit. For basics, see the [README](README.md).

## Table of contents

- [Capture chains](#capture-chains)
- [CD steps](#cd-steps)
- [Mixing captures with parameters](#mixing-captures-with-parameters)
- [Overriding built-in commands](#overriding-built-in-commands)
- [Global vs project strategies](#global-vs-project-strategies)
- [Real-world recipes](#real-world-recipes)
- [Tips & tricks](#tips--tricks)

## Capture chains

A captured variable is available to all subsequent steps - including other captures. This lets you build data pipelines entirely within runit.

![Capture chains](assets/capture-chain.gif)

```bash
runit add pipeline \
  "@branch git rev-parse --abbrev-ref HEAD" \
  "@msg echo Deploying {branch}" \
  "echo {msg} at $(date +%H:%M)"

runit pipeline
# $ @branch git rev-parse --abbrev-ref HEAD
#   branch = main
# $ @msg echo Deploying main
#   msg = Deploying main
# $ echo Deploying main at 14:32
# Deploying main at 14:32
```

Each capture feeds into the next. Step 2 uses `{branch}` from step 1, and step 3 uses `{msg}` from step 2.

## CD steps

A `cd` step changes the working directory for all subsequent steps. Paths can be relative, absolute, or use `~` and environment variables.

![CD steps](assets/cd-steps.gif)

```bash
runit add frontend \
  "cd src/frontend" \
  "echo Building in $(pwd)..." \
  "cd .." \
  "echo Back to $(pwd)"

runit frontend
# $ cd src/frontend
# $ echo Building in /path/to/project/src/frontend...
# Building in /path/to/project/src/frontend...
# $ cd ..
# $ echo Back to /path/to/project/src...
# Back to /path/to/project/src...
```

Relative paths resolve from the current step's directory, not the original working directory. `cd` with no arguments goes to `$HOME`.

## Mixing captures with parameters

Parameters (`{var}`) come from positional arguments. Captures (`@var`) come from step output. They coexist in the same command - runit knows which is which.

![Mixing captures with parameters](assets/capture-params.gif)

```bash
runit add release \
  "@rev git rev-parse --short HEAD" \
  "echo Tagging {rev} as {tag}"

runit release v1.0
# $ @rev git rev-parse --short HEAD
#   rev = a1b2c3d
# $ echo Tagging a1b2c3d as v1.0
# Tagging a1b2c3d as v1.0

runit show release
# release
#   source:  project (.git/runit.yaml)
#   mode:    sequential
#   params:  tag (required)
#   captures: rev
#   steps:
#     1. @rev git rev-parse --short HEAD
#     2. echo Tagging {rev} as {tag}
```

`runit show` makes it clear which variables are params and which are captures.

## Overriding built-in commands

You can't edit or remove built-ins, but you can shadow them by adding a command with the same name.

```bash
# Override the built-in 'loc' to count TypeScript by default
runit add loc "echo Counting .ts files..."

# Now 'runit loc' runs your version, not the built-in
runit loc
# $ echo Counting .ts files...
# Counting .ts files...

# Remove your override to restore the built-in
runit remove loc
```

This works at both project and global scope. Project overrides take priority over global overrides, which take priority over built-ins.

## Global vs project strategies

Commands resolve in this order: **project > global > built-in**. Use this to your advantage.

**Global for universal shortcuts:**

```bash
runit add -g gs "git status -sb"
runit add -g gp "git push"
runit add -g gl "git log --oneline -10"
```

**Project for build/test/deploy:**

```bash
runit add test "pytest -v"
runit add build "docker build -t myapp ."
runit add deploy "kubectl apply -f k8s/{env}.yaml"
```

**Project overrides for special cases:**

```bash
# Global 'test' runs pytest everywhere
runit add -g test "pytest -v"

# But this frontend project uses jest
runit add test "npx jest --coverage"

# 'runit test' now runs jest here, pytest everywhere else
```

The same command name can exist in both scopes. `runit show <name>` tells you which one is active.

## Real-world recipes

![Real-world workflow](assets/workflow.gif)

**Git release tagging:**

```bash
runit add tag \
  "@rev git rev-parse --short HEAD" \
  "echo Creating {version} at {rev}" \
  "git tag -a {version} -m 'Release {version}'"

runit tag v2.0
```

**Push with configurable remote:**

```bash
runit add push \
  "echo Pushing to {remote:origin}..." \
  "git push {remote:origin} HEAD"

runit push              # pushes to origin (default)
runit push upstream     # pushes to upstream
```

**Docker build and push:**

```bash
runit add docker \
  "@hash docker build -q -t myapp:{tag:latest} ." \
  "echo Built {hash}" \
  "docker push myapp:{tag:latest}"

runit docker            # builds and pushes :latest
runit docker v2.0       # builds and pushes :v2.0
```

**Monorepo service deploy:**

```bash
runit add svc \
  "cd services/{name}" \
  "echo Building {name}..." \
  "echo Deploying {name} to {env:staging}"

runit svc auth prod     # deploys auth service to prod
runit svc api           # deploys api service to staging
```

## Tips & tricks

**Auto-run your only command.** If your project has exactly one saved command, skip typing the name:

```bash
runit config single_command run
runit    # runs the only project command automatically
```

**Debug with show.** Not sure what a command does? `runit show` reveals everything - source, mode, params, captures, and all steps.

```bash
runit show deploy
```

**Defaults with special characters.** Default values can contain spaces, commas, anything except `}`:

```bash
runit add notify "echo {msg:Build succeeded, all tests passed!}"
runit notify                    # uses the full default
runit notify "Deploy failed"    # overrides it
```

**Reuse captured variables.** A capture can appear in multiple later steps:

```bash
runit add info "@branch git branch --show-current" "echo Branch: {branch}" "echo Deploying {branch} now"
```
