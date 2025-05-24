# GitHub Actions Workflows

This directory contains the CI/CD workflows for the RPI Weather Display project.

## Workflows

### ci.yml - Main CI/CD Pipeline
The main workflow that handles testing, building, and deployment. It has been optimized to skip unnecessary steps based on which files were changed:

- **Changes Detection**: Uses `dorny/paths-filter` to detect what type of files changed
- **Code Changes**: Runs full pipeline (lint, typecheck, tests, build, deploy)
- **Docs-only Changes**: Skips all code-related steps
- **Docker Changes**: Ensures build step runs even if no code changed
- **Workflow Changes**: Runs full pipeline to validate workflow changes

#### Path Filters:
- **code**: `src/**`, `tests/**`, `pyproject.toml`, `poetry.lock`
- **docs**: `**.md`, `docs/**`, `config.example.yaml`, `.gitignore`, `LICENSE`
- **docker**: `Dockerfile`, `deploy/**`
- **workflows**: `.github/workflows/**`

### docs.yml - Documentation Check
A lightweight workflow specifically for pull requests that only modify documentation:

- Runs only when docs/config files are changed in PRs
- Checks for broken markdown links
- Validates YAML syntax for config files
- Provides quick feedback without running the full test suite
- Saves CI resources and time

## Benefits

1. **Faster Feedback**: Documentation changes get validated in seconds instead of minutes
2. **Resource Efficiency**: Saves CI minutes by not running unnecessary jobs
3. **Clear Notifications**: Different messages for code vs docs deployments
4. **Smart Dependencies**: Jobs only run when their inputs actually changed

## How It Works

1. The `changes` job runs first to detect what files changed
2. Each subsequent job checks the outputs to decide if it should run
3. For docs-only changes, most jobs are skipped automatically
4. The deploy job provides appropriate notifications based on what ran

## Manual Runs

You can still force a full run using workflow_dispatch, which will execute all steps regardless of changes.