# Changelog
All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2025-10-06

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
- **Editor helpers**: bold/italic/inline-code inserts, H1/H2/list line prefixes, wrap toggle, preview toggle, re-render.
- **Settings persistence** with `QSettings` (window geometry, splitter state, recents).
- **SOLID-friendly architecture**:
  - `domain/` interfaces & models.
  - `services/` (renderer, files, settings) and `services/exporters/` strategies.
  - `di/container.py` for dependency injection & exporter registration.
  - Thin `ui/main_window.py` (UI separated from logic).
- **Package entry points**: `python -m pymd` and `pymd/main.py`.
- **Test suite** (pytest) with positive/negative paths covering:
  - Models, Markdown renderer, file & settings services, exporter registry,
    HTML/PDF exporters, DI container, and main window behaviors.

### Notes
- **Python**: 3.10+ recommended.
- Install runtime deps: `pip install -r requirements.txt`
- Run: `python -m pymd`
- Test: `pytest --cov=pymd --cov-report=term-missing`

---

[0.1.0]: https://github.com/clintonshane84/PyMarkdownEditor/releases/tag/v0.1.0
