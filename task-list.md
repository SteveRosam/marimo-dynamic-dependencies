# Marimo Dynamic Dependencies - Task List

## Goal

Enable users of the Quix Marimo dashboard to install new packages at runtime, then quickly begin using them.

## Architecture

### Two Repositories

1. **marimo-quix-plugin** (`C:\DataDrive\Code\marimo-quix-plugin\`)
   - Base image: `ghcr.io/quixio/marimo-base`
   - Abstracts complexity away from Quix Cloud users
   - Contains: nginx, auth proxy, supervisor config, startup scripts
   - Branch `task/venv` has the fixes we're testing

2. **marimo-dynamic-dependencies** (this repo)
   - User-facing deployment code
   - `marimo/` folder uses the base image
   - Simple Dockerfile that just copies `main.py`, `icon.png`, `requirements.txt`

### How Marimo Runs

```
Container Start
    └── /app/start.sh
        └── supervisord (runs 4 processes)
            ├── nginx (port 8080) - reverse proxy
            ├── auth_proxy (port 8082) - Quix PAT authentication
            ├── marimo (port 8081) - via /app/start_marimo.sh
            └── file_watcher - watches for file changes
```

## State Directory

Quix Cloud mounts persistent state at `./state/` relative to WORKDIR.
- WORKDIR = `/app`
- State directory = `/app/state/` (or `./state/`)
- Venv location = `/app/state/venv`

Reference: https://quix.io/docs/deploy/state-management.html

## Key Learnings

### Venv Detection Issue (2026-02-10)

**Problem:** Marimo showed "If you set up a virtual environment, marimo can install these packages for you" instead of an Install button.

**Investigation:**
1. Logs showed venv WAS being created: "Using existing virtual environment from /app/state/venv"
2. Packages WERE installed in venv: "Requirement already satisfied: numpy in ./state/venv/lib/python3.13/site-packages"
3. But marimo still didn't detect the venv

**Root Cause:**
The startup script used `exec marimo ...` after `source activate`. While this modifies PATH, the marimo command (from the base Docker image `ghcr.io/marimo-team/marimo:latest`) might invoke system Python internally, not the venv Python.

Marimo checks `sys.prefix != sys.base_prefix` to detect a venv. This only works if marimo runs with the venv's Python interpreter.

**Solution:**
Changed from:
```bash
source "$VENV_DIR/bin/activate"
exec marimo edit /app ...
```

To:
```bash
exec "$VENV_DIR/bin/python" -m marimo edit /app ...
```

This explicitly uses the venv's Python interpreter, guaranteeing `sys.prefix` points to the venv.

### Testing Branch Builds

The base image builds via GitHub Actions:
- Only builds on push to `main`, PRs to main, or manual dispatch
- Tags: `latest` (main only) and SHA hash
- Registry: `ghcr.io/quixio/marimo-base`

To test changes without merging to main:
1. Push branch and create PR (or use workflow_dispatch)
2. Get the SHA tag from build output (e.g., `096b448`)
3. Update `marimo/dockerfile`: `FROM ghcr.io/quixio/marimo-base:096b448`

## Current Test Setup

**Base image:** `ghcr.io/quixio/marimo-base:096b448` (from branch `task/venv`)

**Changes in test image:**
- Uses `exec "$VENV_DIR/bin/python" -m marimo` instead of `exec marimo`

**Quix deployment:**
- State temporarily disabled (venv recreated on each restart)
- Testing with `marimo/` deployment

## Tasks

### Task 1: Enable Package Installation - COMPLETE
- [x] Venv is created at `/app/state/venv`
- [x] Packages install into venv
- [x] Marimo detects venv and shows "Install" button
- [x] Packages available immediately after install (no restart needed!)

### Task 2: Restart After Installation - NOT NEEDED
Marimo can use packages immediately after pip install. No restart required!

### Task 3: Trigger Restart from UI
- [x] `/redeploy` endpoint exists in auth_proxy.py
- [x] nginx routes `/redeploy` to auth_proxy
- [ ] User notification for restart status

## Current Status

**Implemented:**
- [x] Supervisor runs nginx, auth_proxy, marimo, file_watcher
- [x] start_marimo.sh creates venv at `/app/state/venv`
- [x] `/redeploy` endpoint calls Quix API for container restart
- [x] nginx routes `/redeploy` to auth_proxy
- [x] Fix: Use venv Python explicitly to run marimo

**Tested & Verified (2026-02-10):**
- [x] Marimo shows Install button for missing packages
- [x] Clicking Install successfully installs packages via pip
- [x] Packages available immediately (no restart needed!)
- [x] Tested with: cowsay package - "cow says 'Installed at runtime!'"

**Remaining:**
- [ ] Re-enable state and verify package persistence across restarts
- [ ] Merge `task/venv` branch to main in marimo-quix-plugin
- [ ] Update marimo/dockerfile back to `FROM ghcr.io/quixio/marimo-base:latest`

## Answered Questions

1. **Does marimo need a restart after pip install?** NO! Packages are available immediately after installation. No restart required.

## Known Issues

### State Directory Causes Startup Failure (2026-02-10)
**Problem:** When state is enabled, the container fails to start (502 Bad Gateway). This happens even with 10GB state allocation.

**Observations:**
- Works fine with state disabled
- Fails with state enabled regardless of size (tested 1GB and 10GB)
- The startup script blocks on `pip install -r requirements.txt` before starting marimo
- With bloated requirements.txt (16 packages including pydantic_ai), pip takes many minutes

**Current Status:** Investigating. Reduced requirements.txt to just 4 packages (marimo, numpy, plotly, quixlake) to rule out size issues.

## Open Questions

1. Should we still provide a restart option for edge cases?
2. Do packages persist across container restarts (when state is enabled)? **← Blocked by state issue**
3. Why does enabling state cause startup failure?

## Next Steps

1. **Re-enable state** in Quix deployment
2. **Install a package** via marimo UI
3. **Restart the deployment** and verify the package is still available
4. **Merge** `task/venv` branch to main in marimo-quix-plugin
5. **Update** marimo/dockerfile to use `:latest` tag
