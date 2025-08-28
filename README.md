# linear-project-updates

CLI tool for fetching and displaying Linear project updates via GraphQL API. Shows the latest update for each project, sorted by priority, with configurable filtering and output formats.

## Installation

Requires [UV](https://docs.astral.sh/uv/) and a Linear API key.

```bash
uv tool install .
```

## Configuration

Set your Linear API key using either method:

**Environment variable:**
```bash
export LINEAR_API_KEY='lin_api_your_key_here'
```

**Config file:**
```bash
mkdir -p ~/.config/linear-project-updates
echo 'lin_api_your_key_here' > ~/.config/linear-project-updates/config
```

Get your API key from Linear Settings → API → Personal API keys.

## Usage

```bash
linear-updates                    # All projects by priority
linear-updates -p                 # In-progress/paused projects only
linear-updates -u                 # Include timestamps
linear-updates -b                 # Bold headers instead of ##
linear-updates -w 2               # Updates from last 2 weeks
linear-updates -w 1               # Updates from last week only
linear-updates -p -u -b -w 1      # Combined flags
```

### Command Options

- `-p, --in-progress-only`: Filter to active/paused projects (excludes backlog)
- `-u, --include-updated`: Add timestamps to project headers
- `-b, --bold-headers`: Use **bold** instead of ## markdown headers
- `-w, --weeks-back N`: Only show updates from the last N weeks


## Project Filtering

The tool automatically filters projects based on Linear status:

**Included by -p flag:**
- In Progress (started state)
- Planned (planned state)
- Paused (planned state)

**Excluded by -p flag:**
- Backlog (backlog state)


## Development

```bash
# Local development
uv run python linear_updates.py --help
uv sync                           # Install dependencies
uv tool install --force .        # Reinstall after changes
```

## API

Uses Linear GraphQL API at `https://api.linear.app/graphql`. Fetches project updates with status, priority, and content data.

Documentation: https://linear.app/developers/graphql