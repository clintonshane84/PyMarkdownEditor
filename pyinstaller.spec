# pyinstaller.spec
from PyInstaller.utils.hooks import collect_submodules

app_name = "PyMarkdownEditor"
entrypoint = "pymd/__main__.py"

# Hidden imports used by markdown/pygments
hidden = []
hidden += collect_submodules("markdown")
hidden += collect_submodules("pygments")

# Keep only Qt modules we actually use
hidden += [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtPrintSupport",
]

excludes = [
    # Exclude heavy/unused Qt modules that drag plugins with external deps
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtSpatialAudio",
    "PyQt6.QtNfc",
    "PyQt6.QtSerialPort",
    "PyQt6.QtSensors",
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtSvg",
    "PyQt6.QtSvgWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtQuick3D",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
]

blockcipher = None

a = Analysis(
    [entrypoint],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={
        # Keep only platform + printsupport plugins
        "hook-PyQt6.py": {"plugins": ["platforms", "printsupport"], "excluded_qml_plugins": "all"},
    },
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=blockcipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app
)

# IMPORTANT: Only pass TOC objects to COLLECT; NO STRINGS/PATHS
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=app_name,  # keyword only, this sets dist/<name>/
)
