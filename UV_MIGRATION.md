# UV Migration Guide

This document explains how the project has been converted to use [UV](https://github.com/astral-sh/uv) for Python package management.

## What Changed

### 1. Updated `pyproject.toml`
- Added proper project metadata (authors, license, classifiers)
- Pinned exact dependency versions from `requirements.txt`
- Organized dependencies into main and optional groups:
  - `dev`: Testing and development tools
  - `multiagent`: Multi-agent specific dependencies
- Added UV-specific configuration

### 2. New Scripts
- **`start-uv.sh`**: UV-based startup script (replaces traditional `start.sh`)
- **`run_standalone_uv.py`**: Standalone runner using UV (alternative to `run_standalone.py`)

### 3. Dependency Resolution
- Fixed version conflicts (e.g., tenacity versions between main and multiagent extras)
- Created `uv.lock` file for reproducible builds
- Maintained compatibility with existing Docker setup

## Usage

### Basic Commands
```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync all dependencies
uv sync

# Install with optional dependencies
uv sync --extra dev
uv sync --extra multiagent

# Run scripts directly
uv run scraper
uv run mcp-server

# Add/remove dependencies
uv add requests
uv remove requests

# Run Python scripts
uv run python test_setup.py
```

### Development Workflow
```bash
# Set up development environment
uv sync --extra dev

# Run tests
uv run pytest

# Run scraper
uv run scraper

# Run MCP server
uv run mcp-server
```

### Production Deployment
```bash
# Quick start (recommended)
./start-uv.sh

# Standalone mode (no Docker for Python components)
./run_standalone_uv.py
```

## Benefits of UV

1. **Speed**: 10-100x faster than pip for dependency resolution and installation
2. **Reliability**: Deterministic builds with `uv.lock`
3. **Simplicity**: Single tool for all Python package management
4. **Compatibility**: Works with existing `pyproject.toml` and pip workflows

## Migration Notes

- All existing functionality is preserved
- Docker setup remains unchanged (Elasticsearch still runs in Docker)
- Original scripts (`start.sh`, `run_standalone.py`) still work
- UV scripts are additive, not replacements

## Troubleshooting

### UV Not Found
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your shell or run:
source ~/.bashrc  # or ~/.zshrc
```

### Dependency Conflicts
```bash
# Clear UV cache and resync
uv cache clean
uv sync --refresh
```

### Lock File Issues
```bash
# Regenerate lock file
rm uv.lock
uv sync
```

## Comparison

| Feature | Traditional | UV |
|---------|-------------|-----|
| Install time | ~30-60s | ~3-5s |
| Dependency resolution | pip/pip-tools | Built-in resolver |
| Lock files | requirements.txt | uv.lock |
| Virtual environments | venv/virtualenv | Built-in |
| Package management | pip | uv add/remove |
| Script running | python -m | uv run |

## Next Steps

1. Use `./start-uv.sh` for new deployments
2. Consider removing old `requirements.txt` files after validation
3. Update CI/CD pipelines to use UV
4. Train team on UV commands and workflows
