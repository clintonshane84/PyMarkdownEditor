# Contributions Guide

Thanks for your interest in contributing to **PyMarkdownEditor**!
This project is open source and welcomes issues and PRs.

> **Governance:** The project is **owner-led**. The initial Code Owner is **YOU** (replace below).
> Additional Code Owners may be added over time. **All merges require Code Owner approval.**

- License: **Apache-2.0** (`LICENSE`)
- Code Owners: see `.github/CODEOWNERS`
- PR Template: `.github/pull_request_template.md`

---

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Governance & Decision Making](#governance--decision-making)
- [Status Checks (CI)](#status-checks-ci)
- [Before You Start](#before-you-start)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Branching & Commits](#branching--commits)
- [Testing & Quality Gates](#testing--quality-gates)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Security](#security)
- [Releases](#releases)
- [License & Ownership](#license--ownership)
- [Contact](#contact)

---

## Code of Conduct
We follow the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating, you agree to uphold this code.

---

## Governance & Decision Making
- **Code Owners**: approve/merge PRs, set roadmap, cut releases.
- **Maintainers**: triage issues, review PRs (as delegated).
- **Contributors**: everyone submitting issues/PRs.

> A PR **must** be approved by a Code Owner to be merged.

---

## Status Checks (CI)

All PRs must pass automated checks (see `.github/workflows/`):

1. **Ruff Format (check)** — `ruff format --check .`
2. **Ruff Lint** — `ruff check .` (imports, pyflakes, pycodestyle, bugbear, pyupgrade)
3. **Tests** — `pytest` (Qt runs headless: `QT_QPA_PLATFORM=offscreen`)
   Coverage is reported to the console.
4. **(Optional) Pre-commit Autofix** — for PR branches **within this repo**, a bot may push formatting fixes

**Workflows:**
- CI: `.github/workflows/ci.yml` (runs on push & PR to `main`/`develop`)
- Autofix: `.github/workflows/pre-commit-autofix.yml` (optional; formatting only)
- Release binaries: `.github/workflows/release-binaries.yml` (on tag `v*.*.*`)

**Local pre-commit (recommended):**
```bash
pip install -r dev-requirements.txt
pre-commit install
pre-commit run --all-files
````

If CI fails on formatting only, either:

* run `pre-commit` locally and push, or
* wait for the **autofix** workflow to push a formatting commit (repo branches only).

---

## Before You Start

* For **non-trivial changes**, please open an **issue** to discuss direction.
* For **small fixes** (docs, typos, trivial refactors), you may open a PR directly.
* For API/UX/architectural changes, please include a brief design sketch in the issue.

---

## Development Setup

```bash
python -m venv .venv
# Windows:
. .venv/Scripts/activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
pip install -r dev-requirements.txt
```

Run the app:

```bash
python -m pymd
```

Run tests:

```bash
pytest --cov=pymd --cov-report=term-missing
```

**Optional tools:** `ruff`, `black`, `pyinstaller`.

---

## Project Structure

```
pymd/
  __init__.py
  __main__.py
  main.py
  app.py
  di/
    container.py
  domain/
    interfaces.py
    models.py
  services/
    markdown_renderer.py
    file_service.py
    settings_service.py
    exporters/
      base.py
      html_exporter.py
      pdf_exporter.py
  ui/
    main_window.py
  utils/
    constants.py
tests/
```

* **SOLID & DI**: interfaces in `domain/`, wiring in `di/container.py`
* **Exporters** follow the strategy pattern and a registry (Open/Closed Principle)
* UI in `ui/` is thin and delegates to services

---

## Branching & Commits

* Branch from `main`:
  `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `chore/<short-name>`
* Commit style (suggested):

  * `feat: add pdf exporter margins`
  * `fix: handle QSaveFile commit failure`
  * `test: negative path for QTextDocument.print`
* **DCO sign-off** required (or CLA if requested):

  ```bash
  git commit -s -m "feat: add exporter"
  ```

  This adds: `Signed-off-by: Your Name <email>`

---

## Testing & Quality Gates

* Use **pytest**; keep tests deterministic & fast.
* Include **positive + negative** paths (I/O failures, print errors, unknown exporters, etc.).
* Target **≥90% coverage** for new/changed code; don’t regress overall.
* Avoid modal dialogs in tests; use internal helpers or monkeypatch.

Run:

```bash
pytest -q
pytest --cov=pymd --cov-report=term-missing
```

---

## Documentation

* User-visible changes → update **README.md** and **CHANGELOG.md**.
* Architectural changes → brief notes in **CONTRIBUTIONS.md** or `docs/`.
* Add docstrings for public classes/interfaces.

---

## Pull Request Process

1. Use the PR template (`.github/pull_request_template.md`).
2. Link the related issue if applicable; explain **why** + **what**.
3. Keep PRs small & focused.
4. Add/update tests and docs.
5. Ensure **CI is green** (format/lint/tests).
6. A **Code Owner** reviews and merges (squash preferred).

**Reviewers look for:**

* SOLID/DI alignment, exporter strategy consistency
* Good error handling (Qt threading/printing/IO edge cases)
* Tests cover happy and failure paths
* Maintainable code (naming, small units, clarity)

---

## Security

If you suspect a security issue:

* **Do not** open a public issue.
* Send Github DM to the current Code Owner.
* I’ll acknowledge within 72 hours and work on a fix, not guarenteed, but its best effort.

---

## Releases

* Version is set in `pymd/__init__.py` (follow **SemVer**).
* Update `CHANGELOG.md`.
* Create a tag `vX.Y.Z` and push:

```bash
git tag v0.1.0
git push origin v0.1.0
```
* The **Release binaries workflow** builds PyInstaller artifacts for Windows/macOS/Linux and attaches them to the GitHub Release. See `docs/RELEASING.md`.

---

## License & Ownership

* Licensed under **Apache-2.0** (`LICENSE`).
* Contributions are accepted under the same license.
* The Code Owner retains repository administrative control; new Code Owners may be added over time.

---

## Contact

* General: open an issue
* Security: Send a DM to the Current Code Owner
* Current Code Owner: **Clinton Wright / @clintonshane84**
