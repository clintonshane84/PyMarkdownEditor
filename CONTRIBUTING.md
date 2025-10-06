# Contributions Guide

Thanks for your interest in contributing to **PyMarkdownEditor**!  
This project is open source and welcomes bug reports, ideas, and code contributions.

> **Governance:** The project is **owner-led**. The initial Code Owner is **YOU** (replace with your name/handle).  
> Additional Code Owners may be added over time. **All merges require Code Owner approval.**

---

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Governance & Decision Making](#governance--decision-making)
- [Before You Start](#before-you-start)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Issue Reporting](#issue-reporting)
- [Proposing Changes](#proposing-changes)
- [Branching & Commits](#branching--commits)
- [Testing & Quality Gates](#testing--quality-gates)
- [Documentation](#documentation)
- [Pull Request Checklist](#pull-request-checklist)
- [Review & Merge Process](#review--merge-process)
- [Security](#security)
- [Releases](#releases)
- [License & Ownership](#license--ownership)
- [Contact](#contact)

---

## Code of Conduct
We follow the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).  
By participating, you agree to uphold this code. If you observe unacceptable behavior, please report it privately (see [Security](#security)).

---

## Governance & Decision Making
- **Code Owners**: Approve/merge PRs, set roadmap, cut releases.
- **Maintainers**: Triage issues, review PRs, help with releases (as delegated).
- **Contributors**: Everyone submitting issues/PRs.

> A PR **must** be approved by a Code Owner to be merged.

---

## Before You Start
- For **non-trivial changes**, please open an **issue** first to discuss direction.
- For **small fixes** (docs, typos, trivial refactors), you can go straight to a PR.
- If your change impacts public API, UX, or architecture, an approved issue or design sketch is required.

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
````

Run tests & coverage:

```bash
pytest --cov=pymd --cov-report=term-missing
```

Run the app:

```bash
python -m pymd
```

Recommended (optional):

* Lint/format via `ruff` or `black` + `ruff` (`pip install ruff black`).

---

## Project Structure

```
pymd/
  __init__.py
  __main__.py
  main.py
  app.py
  di/
  domain/
  services/
    exporters/
  ui/
  utils/
tests/
```

* **SOLID-friendly** design with interfaces in `domain/` and DI in `di/`.
* Export strategies (HTML/PDF) live in `services/exporters/` (Open/Closed Principle).
* Qt UI in `ui/` is thin; business logic lives in services.

---

## Issue Reporting

Please include:

* Expected vs actual behavior
* Steps to reproduce
* Environment (OS, Python, PyQt, commit SHA)
* Logs/screenshots if relevant
* For feature requests: Why it’s needed, alternatives considered, scope

Use labels if available (bug, feature, docs, help wanted).

---

## Proposing Changes

1. **Discuss** substantial work in an issue first.
2. **Design**: brief plan if touching architecture, DI, or interfaces.
3. **Scope**: keep PRs small, focused, and reviewable.
4. **Tests**: add unit tests (positive & negative paths).
5. **Docs**: update README/CONTRIBUTIONS/CHANGELOG if user-visible changes.

---

## Branching & Commits

* Branch from `main`:

  * `feat/<short-topic>`
  * `fix/<short-topic>`
  * `docs/<short-topic>`
  * `chore/<short-topic>`
* Commit style (suggested):

  * `feat: add pdf exporter margins`
  * `fix: handle QSaveFile commit failure`
  * `test: add negative path for exporter`
* **DCO sign-off** required (or CLA if requested):

  ```bash
  git commit -s -m "feat: add exporter"
  ```

  This appends: `Signed-off-by: Your Name <email>`

---

## Testing & Quality Gates

* Use **pytest**; keep tests deterministic and fast.
* Cover both **happy paths** and **failure modes** (e.g., IO errors, Qt print errors, missing exporters).
* Target **≥90% coverage** for new/changed code; don’t regress overall coverage.
* Avoid GUI modal interactions in tests—call internal helpers or monkeypatch dialogs.

**Run:**

```bash
pytest -q
pytest --cov=pymd --cov-report=term-missing
```

---

## Documentation

* Public behaviors, CLI flags, or UI changes → update **README.md**.
* Architectural or design updates → add short notes to **CONTRIBUTIONS.md** or a `/docs` page.
* Add docstrings to public classes/interfaces.

---

## Pull Request Checklist

* [ ] Issue linked (if needed) and description explains **why** & **what**
* [ ] Small, focused changes; unrelated refactors split out
* [ ] Tests added/updated (positive + negative)
* [ ] `pytest` passes locally
* [ ] Coverage maintained or improved
* [ ] Docs updated (README/CHANGELOG) if user-visible
* [ ] Commits signed off with **DCO** (`-s`)
* [ ] No secrets, PII, or license-incompatible code included

---

## Review & Merge Process

* A Code Owner reviews for:

  * Architectural fit (SOLID, DI, interfaces)
  * Safety (error handling, UI blocking, thread affinity in Qt)
  * Tests & coverage
  * Maintainability (naming, size, clarity)
* Address feedback with follow-up commits (keep them tidy).
* **Squash merge** preferred; Code Owner presses the button.

---

## Security

If you believe you’ve found a security issue:

* **Do not** open a public issue.
* DM the Code Owner on Github, username: **clintonshane84**.
* We will acknowledge within 72 hours and work on a fix depending on availability. This is not guarenteed and serves as a general guideline only.

---

## Releases

* Version set in `pymd/__init__.py`.
* Update `CHANGELOG.md` (Keep a Changelog style recommended).
* Tag release: `vX.Y.Z`.
* Prepare binaries (optional: PyInstaller), publish GitHub Release.

---

## License & Ownership

* Licensed under **Apache-2.0** (see `LICENSE`).
* Contributions are accepted under the same license.
* The Code Owner retains repository administrative control; new Code Owners may be added over time.

---

## Contact

* General: open an issue
* Security: **TBC**
* Current Code Owner: **Clinton Wright / @clintonshane84**

Thanks again for helping make PyMarkdownEditor better! 🎉