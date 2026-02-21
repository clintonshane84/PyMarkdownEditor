# PyMarkdownEditor

A fast, minimal **PyQt6 Markdown editor** with live preview, HTML/PDF export, and a clean, SOLID-friendly architecture.

Designed to stay small, deterministic, and easy to package.

Owner-led governance; contributions welcome (see CONTRIBUTING).

---

## 🚀 Features

### 📝 Live Preview

* Debounced, side-by-side Markdown preview while you type.
* Dark-mode friendly CSS.
* Optional Qt WebEngine rendering (automatically disabled in tests/headless runs).

### 🧠 Markdown Rendering

Powered by:

* `python-markdown`
* Extensions:

    * `extra`
    * `fenced_code`
    * `codehilite`
    * `toc`
    * `sane_lists`
    * `smarty`
* Optional:

    * `pymdown-extensions` (e.g. math/LaTeX via `arithmatex`)

### 📁 Robust File Handling

* Open/Save `.md` files
* Atomic writes via `QSaveFile`
* UTF-8 encoding
* Drag & drop support
* Recent files persisted via `QSettings`

---

## 📤 Exporters

Exporters are strategy-based and registered in an `ExporterRegistry`.

### HTML

Saves the preview HTML as-is.

### PDF (Classic)

Uses `QTextDocument` + `QPrinter` (A4, 12.7mm margins).

### PDF (WebEngine – Optional)

Uses `QWebEngineView` for closer WYSIWYG output.

Automatically disabled in:

* pytest
* headless environments
* when `PYMD_DISABLE_WEBENGINE=1`

---

## 🔌 Plugin System

PyMarkdownEditor includes a **first-class plugin architecture**.

### Discovery

Plugins are discovered via:

1. **Built-in plugins**
2. **Python entry points**

Discovery is deterministic.

### Lifecycle Contract

Recommended host wiring:

```python
plugin_manager.set_api(app_api)
plugin_manager.reload()
plugin_manager.on_app_ready()
```

Hooks (optional):

* `on_load(api)` → runs once per process
* `activate(api)` → runs when enabled
* `on_ready(api)` → runs once per activation session
* `deactivate()` → runs when disabled

### Enable / Disable

Plugin state is persisted via `IPluginStateStore`.

Built-in plugins:

* Appear in the Plugins UI
* Can be enabled/disabled
* Never crash discovery if missing

---

## 🧱 Architecture

SOLID-leaning, layered design:

* **Domain layer** (interfaces, models)
* **Services layer** (rendering, exporters, plugins, config)
* **UI layer** (thin Qt window + dialogs)
* **Dependency injection container**
* **Plugin lifecycle manager**

### Key Principles

* Clear boundaries
* No UI in core
* Strategy-based exporters
* Explicit plugin lifecycle
* Deterministic startup
* Test-safe QtWebEngine behavior

---

## 📦 Installation

### From Source

```bash
# 1) Create virtual environment
python -m venv .venv

# Windows
. .venv/Scripts/activate

# macOS / Linux
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run
python -m pymd
```

Python 3.10+ recommended.

---

### From PyPI (when published)

```bash
pip install py-markdown-editor
python -m pymd
```

Future console entry:

```bash
pymd
```

---

## 📚 Requirements

Runtime:

* `PyQt6>=6.6`
* `Markdown>=3.5`
* `Pygments>=2.17`
* `pymdown-extensions`

Optional (WebEngine PDF export):

* `PyQt6-WebEngine`

---

## ⌨ Keyboard & UI

### Core

* New / Open / Save / Save As
* Toggle wrap
* Toggle preview
* Quit

### Formatting

* **B** → Bold
* *i* → Italic
* `code`
* `# H1`
* `## H2`
* `- list`

### Insert

* Insert link
* Insert image
* Insert table
* Find / Replace
* About dialog

All actions exposed via toolbar + menus.

---

## 📁 Project Structure

```
.
├── pymd/
│   ├── app.py
│   ├── di/
│   │   └── container.py
│   ├── plugins/
│   │   ├── discovery.py
│   │   ├── manager.py
│   │   ├── state.py
│   │   └── builtin/
│   ├── services/
│   │   ├── exporters/
│   │   ├── file_service.py
│   │   ├── markdown_renderer.py
│   │   ├── settings_service.py
│   │   └── ui/
│   │       ├── main_window.py
│   │       ├── dialogs
│   │       ├── adapters
│   │       ├── ports
│   │       ├── presenters
│   │       └── commands
│   └── domain/
│       ├── interfaces.py
│       └── models.py
├── tests/
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 🧪 Testing

Install dev dependencies:

```bash
pip install -r dev-requirements.txt
```

Run:

```bash
pytest --cov=pymd --cov-report=term-missing --timeout=120
```

Includes:

* pytest
* pytest-qt
* pytest-cov
* pytest-timeout
* ruff

### QtWebEngine Safety

WebEngine is automatically disabled during pytest to prevent Chromium aborts.

---

## 🏗 Building Binaries (PyInstaller)

```bash
pip install pyinstaller

pyinstaller -n PyMarkdownEditor --windowed --onefile \
  -i NONE -s -y pymd/__main__.py
```

GitHub Actions:

* Windows / Linux / macOS builds
* Hidden imports collected
* Artifacts attached to tagged releases

---

## 🔄 CI & Releases

### CI

* Runs on push/PR
* Ruff + pytest + coverage
* Fast path for dev branches
* Full OS matrix for master PRs

### Binary Releases

Triggered by semver tag:

```
vMAJOR.MINOR.PATCH
```

Builds cross-platform binaries and attaches to GitHub Release.

### PyPI Publishing

Triggered by version tags.

* Pre-releases → TestPyPI
* Final releases → PyPI
* Version verified against `pyproject.toml`

---

## 🛠 Troubleshooting

### PDF blank

* Ensure target folder writable
* Verify Qt Print/WebEngine libraries installed

### WebEngine crashes

* Ensure matching Qt libraries
* Or disable:

  ```
  PYMD_DISABLE_WEBENGINE=1
  ```

### Missing pymdownx

```
pip install pymdown-extensions
```

---

## 🤝 Contributing

We welcome issues and PRs.

See:

* CONTRIBUTING.md
* LICENSE (Apache-2.0)

Owner-led governance means:

* Maintainer steers architecture
* Small, focused scope
* Clean, maintainable contributions

### Dev loop

```bash
ruff format .
ruff check .
pytest --cov=pymd --cov-report=term-missing --timeout=120
```

---

## 📜 License

Apache-2.0 © 2025 clintonshane84
See LICENSE.
