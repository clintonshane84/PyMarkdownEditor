# Changelog
All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.3]
### Fixed
- Follow-up fix to `__main__.py`: ensure absolute import `from pymd.main import main`, exiting via `raise SystemExit(main())` for consistency across frozen builds.

### Packaging
- No functional changes besides entrypoint correctness for Windows EXE.

---

## [0.3.2]
### Fixed
- Switched `pymd/__main__.py` from a relative import to an absolute import to avoid `ImportError: attempted relative import with no known parent package` in frozen executables.

---

## [0.3.1]
### Fixed
- Corrected Linux package artifact path (`linux-x86_64`) in release workflow.

### Packaging
- Refined PyInstaller outputs and artifact naming for Linux/macOS/Windows.

---

## [0.3.0]
### Changed
- Reworked PyInstaller build steps across Linux, macOS, and Windows to standardize output layout and names.

### CI/CD
- Stabilized release workflow and artifact upload behavior.

---

## [0.2.2]
### CI/CD
- Simplified CI strategy: quick 1-job checks for non-`master` branches, full matrix only where needed.
- Improved Windows packaging step in release workflow.

---

## [0.2.1]
### Maintenance
- Merges from `development` with incremental workflow and docs improvements.

---

## [0.2.0]
### Added
- **Continuous Integration**: format checking via Ruff, unit test execution, and required system libraries for Linux runners.
- **Docs**: updated `README.md`, `CONTRIBUTING.md`, and CI docs.
- **Developer experience**: `pytest-timeout` for more reliable CI runs.

### Changed
- Codebase formatting to Ruff standards; broad stylistic updates.
- Python versions used in CI updated.
- Tests adjusted for headless CI (e.g., handling modal dialogs, timeouts).

### Removed
- Deprecated `main.py` (superseded by modular entry via `pymd/main.py` and package `__main__`).

---

## [0.1.0]
### Added
- **PyQt6 Markdown editor** with split view: plain-text editor + live preview.
- **Debounced rendering** for smooth typing.
- **Markdown rendering** via `python-markdown` with extensions:
  - `extra`, `fenced_code`, `codehilite` (Pygments), `toc`, `sane_lists`, `smarty`.
- **Minimal, dark-mode aware CSS** for preview.
- **File operations**:
  - Open/Save `.md` (atomic saves via `QSaveFile`, UTF-8).
  - Recent files menu (persisted).
  - Drag-and-drop to open files.
- **Exporters**:
  - **HTML** exporter (saves preview HTML as-is).
  - **PDF** exporter (QPrinter, A4, 12.7 mm margins) mirroring preview.
- **Editor helpers**: bold/italic/inline-code inserts, H1/H2/list prefixes, wrap toggle, preview toggle, re-render.
- **Settings persistence** with `QSettings` (window geometry, splitter state, recents).
- **SOLID-friendly architecture**:
  - `domain/` interfaces & models.
  - `services/` (renderer, files, settings) + `services/exporters/` strategies.
  - `di/container.py` for dependency injection & exporter registration.
  - Thin `ui/main_window.py` (UI separated from logic).
- **Package entry points**: `python -m pymd` and `pymd/main.py`.
- **Test suite** (pytest) with positive/negative paths covering:
  - Models, Markdown renderer, file & settings services, exporter registry, HTML/PDF exporters, DI container, and main window behaviors.

### Notes
- **Python**: 3.10+ recommended.
- Install: `pip install -r requirements.txt`
- Run: `python -m pymd`
- Test: `pytest --cov=pymd --cov-report=term-missing`

---

[0.3.3]: https://github.com/clintonshane84/PyMarkdownEditor/releases/tag/v0.3.3
[0.3.2]: https://github.com/clintonshane84/PyMarkdownEditor/releases/tag/v0.3.2
[0.3.1]: https://github.com/clintonshane84/PyMarkdownEditor/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/clintonshane84/PyMarkdownEditor/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/clintonshane84/PyMarkdownEditor/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/clintonshane84/PyMarkdownEditor/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/clintonshane84/PyMarkdownEditor/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/clintonshane84/PyMarkdownEditor/releases/tag/v0.1.0
