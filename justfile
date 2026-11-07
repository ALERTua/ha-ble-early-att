# https://github.com/casey/just
set dotenv-load

# Set shell for Windows OSs:
[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

# Set shell for non-Windows OSs:
[unix]
set shell := ["sh", "-c"]

# Format the code, fix what ruff can fix, and check the types
lint:
    uv run ruff format .
    uv run ruff check --fix
    uv run pre-commit run ty --all-files

# Run all pre-commit hooks on all files
pre:
    uv run pre-commit run --all-files

# Update the versions of the pre-commit hooks
pre-update:
    uv run pre-commit autoupdate

# Install the project and all dependency groups
install:
    uv sync --all-groups

# Upgrade all dependencies
upgrade:
    uv sync --all-groups --upgrade

# Run the tests
test:
    uv run pytest

# Run the tests with a coverage report, and fail below 95 percent
cov:
    uv run pytest --cov=custom_components/ble_early_att --cov-report=term-missing --cov-fail-under=95

# Set the version in pyproject.toml and manifest.json
version VERSION:
    uv run script/update_version.py {{VERSION}}
    uv lock

# Show available commands
help:
    @just --list
