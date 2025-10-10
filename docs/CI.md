# Continuous Integration (CI)

## Workflows

- **CI** — `.github/workflows/ci.yml`
  - Runs on push/PR to `master` and `development`
  - Steps:
    - `ruff format --check .` (style)
    - `ruff check .` (lint)
    - `pytest` with `QT_QPA_PLATFORM=offscreen`

- **Pre-commit autofix** — `.github/workflows/pre-commit-autofix.yml` (optional)
  - Runs on PRs from branches **within this repo**
  - Applies pre-commit (ruff) fixes and pushes them back

- **Build & Release Binaries** — `.github/workflows/release-binaries.yml`
  - Runs on tag push `v*.*.*`
  - Builds PyInstaller binaries and attaches them to the GitHub Release
  - Generates a fresh copy of CHANGELOG.md file using python app `git-changelog`
  - Commits and pushes up the updated CHANGELOG.md file

## Local equivalents

```bash
# Style & lint
ruff format .
ruff check .

# Tests
pytest --cov=pymd --cov-report=term-missing

# Pre-commit
pre-commit install
pre-commit run --all-files
````

Set headless Qt if needed:

```bash
export QT_QPA_PLATFORM=offscreen    # macOS/Linux
setx QT_QPA_PLATFORM offscreen      # Windows (PowerShell: $env:QT_QPA_PLATFORM="offscreen")
```
