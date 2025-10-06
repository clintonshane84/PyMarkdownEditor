# pyinstaller.spec
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from pathlib import Path
import sys

entry = "pymd/__main__.py"
name = "PyMarkdownEditor"

# Hidden imports to ensure PyQt6 plugins and libs are included
hidden = []
hidden += collect_submodules("PyQt6")
hidden += ["PyQt6.QtPrintSupport", "markdown", "pygments"]

datas = []
# If you add non-code assets later (icons, CSS, etc), include them like:
# datas += collect_data_files("pymd", includes=["utils/*.css"])

a = Analysis(
    [entry],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=name,
    console=False,   # windowed app (no console)
    icon=None,       # drop an .ico/.icns later and set here if desired
)

# On macOS this yields an .app bundle; on Win/Linux it's a single file in dist/
coll = COLLECT(exe, strip=False, upx=False, name=name)
