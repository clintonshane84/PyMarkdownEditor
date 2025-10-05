# PyMarkdownEditor

A clean, Python 3 Markdown **editor & viewer** with live preview, export to **HTML** and **PDF**, and a modular architecture that follows **SOLID** principles with **dependency injection**. Built on **PyQt6** and **python-markdown**.

> Minimal UI, fast preview, safe (atomic) saves, and easy to extend (add exporters/renderers without touching the UI).

---

## ✨ Features

* Live Markdown preview (debounced) with light/dark aware CSS
* Open / Save (`.md`) with **atomic** writes (no corrupt files)
* Export:

  * **HTML** (same CSS as preview)
  * **PDF** (Qt print stack; A4 portrait, 12.7 mm margins)
* Recent files menu
* Toggle word wrap & toggle preview pane
* Remembers window geometry and splitter layout
* **Modular SOLID design**: swappable renderers & exporters via DI

---

## 📦 Project Structure

```
pymd/
  main.py                 # CLI entrypoint
  app.py                  # App bootstrap
  di/
    container.py          # Simple DI container (wires interfaces -> implementations)
  domain/
    interfaces.py         # Small, focused interfaces (ISP)
    models.py             # Core dataclasses (Document)
  services/
    markdown_renderer.py  # Markdown -> HTML (Strategy)
    file_service.py       # Atomic file IO
    settings_service.py   # Persist UI state (QSettings)
    exporters/
      base.py             # Exporter registry
      html_exporter.py    # Export to HTML
      pdf_exporter.py     # Export to PDF (QPrinter)
  ui/
    main_window.py        # Thin PyQt window, delegates to services
  utils/
    constants.py          # CSS, HTML template, app constants
requirements.txt
```

---

## 🚀 Getting Started

### Prerequisites

* Python **3.10+**
* A working Qt runtime (installed automatically through `PyQt6`)

### Setup

```bash
# (recommended) create a virtualenv
python -m venv .venv
# Windows
. .venv/Scripts/activate
# macOS/Linux
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt
```

### Run

```bash
# from the repo root
python -m pymd.main                # launch empty
python -m pymd.main README.md      # open a file on startup
```

---

## 🧭 Usage

* **Open**: File → Open… (or toolbar)
* **Save**: File → Save / Save As…
* **Export**:

  * **HTML**: File → Export HTML…
  * **PDF**: File → Export PDF…
* **View**:

  * Toggle **Wrap** and **Preview** from the toolbar or View menu
* **Recent files**: File → Open Recent

### Keyboard shortcuts

* New: **Ctrl+N**
* Open: **Ctrl+O**
* Save: **Ctrl+S**
* Save As: **Ctrl+Shift+S**
* Re-render preview: **Ctrl+R**

---

## 🧱 Architecture (SOLID + DI)

* **Single Responsibility (SRP):** Each service has exactly one job (render, file IO, settings, export).
* **Open/Closed (OCP):** Add features by adding new classes (e.g., exporters) and registering them—no changes to existing UI code.
* **Liskov Substitution (LSP):** Any `IExporter` can replace another wherever an exporter is expected.
* **Interface Segregation (ISP):** Small, purpose-built interfaces (`IMarkdownRenderer`, `IFileService`, `ISettingsService`, `IExporter`).
* **Dependency Inversion (DIP):** The UI depends on **interfaces**; a tiny DI container wires concrete implementations.

Patterns used:

* **Strategy** for exporters (`IExporter` implementations)
* **Registry/Factory** for exporter discovery (`ExporterRegistry`)
* **Passive View** style: `MainWindow` is thin and delegates work

---

## 🧩 Extensibility

### Add a new exporter (example: DOCX)

1. Create a class that implements `IExporter`.
2. Register it in `di/container.py`.

```python
# services/exporters/docx_exporter.py
from pathlib import Path
from pymd.domain.interfaces import IExporter

class DocxExporter(IExporter):
    name = "docx"
    label = "Export DOCX…"

    def export(self, html: str, out_path: Path) -> None:
        # convert html -> docx using your lib of choice
        # e.g., docx-mailmerge, mammoth, pandoc wrapper, etc.
        ...
```

```python
# di/container.py
from pymd.services.exporters.docx_exporter import DocxExporter
...
ExporterRegistry.register(DocxExporter())
```

Done—`MainWindow` will automatically show “Export DOCX…” in the menu and toolbar.

### Swap Markdown engine

Create a new renderer that implements `IMarkdownRenderer` and set it in the container:

```python
class MarkdownItRenderer(IMarkdownRenderer):
    def to_html(self, markdown_text: str) -> str:
        # call alternative engine, return full HTML with your CSS
        ...
```

```python
# di/container.py
self.renderer = MarkdownItRenderer()
```

---

## 🛠️ Troubleshooting

* **PyQt6 platform plugin error (Linux):**
  Install missing XCB dependencies (varies by distro), e.g. `sudo apt install libxcb-xinerama0`.
* **PDF export looks different from preview:**
  The PDF uses the same HTML/CSS as the preview, rendered by Qt’s print engine. If corporate fonts differ, embed web-safe fonts or tweak `CSS_PREVIEW` in `utils/constants.py`.
* **Right-to-left or CJK text issues:**
  Ensure fonts support your glyphs; adjust the CSS `font-family`.

---

## 🧪 Testing (suggested approach)

* Unit test services by **mocking interfaces**:

  * `FileService` with a temp dir
  * `SettingsService` using an in-memory QSettings scope
  * Exporters using stub outputs
* UI tests can be done with `pytest-qt`.

---

## 📦 Packaging (optional)

Create a single-file binary with **PyInstaller**:

```bash
pip install pyinstaller
pyinstaller -n PyMarkdownEditor --onefile -w pymd/main.py
```

> Note: Fonts and platform plugins may need extra hooks; consult PyInstaller docs for your OS.

---

## 📜 License

MIT (suggested). Add your preferred license to `LICENSE`.

---

## 🤝 Contributing

* Fork & branch (`feat/...` or `fix/...`)
* Keep classes small, follow interfaces, and register new strategies in the DI container
* Submit a PR with a short description and screenshots if UI-visible

---

## 🖼️ Screenshots (optional)

Add your screenshots to `docs/` and link them here:

```
![Editor light mode](docs/screenshot-light.png)
![Editor dark mode](docs/screenshot-dark.png)
```

---

### Credits

Built with ❤️ using **PyQt6**, **python-markdown**, and **Pygments**.
