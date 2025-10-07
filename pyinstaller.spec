# pyinstaller.spec
# Clean, minimal spec for PyMarkdownEditor (onedir)
# Generates dist/PyMarkdownEditor/ with PyQt6 runtime

from PyInstaller.utils.hooks import collect_submodules

app_name = "PyMarkdownEditor"
entrypoint = "pymd/__main__.py"

# Keep markdown/pygments helpers
hidden = []
hidden += collect_submodules("markdown")
hidden += collect_submodules("pygments")

# Only the PyQt6 components we actually use
hidden += [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtPrintSupport",
]

# Exclude heavy Qt modules that trigger missing libs on Linux runners
excludes = [
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
    # and the rest of Qt stuff we don't need...
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
        # Ask PyInstaller's PyQt6 hook to include only the essentials
        # See hook documentation for supported keys; platforms is enough for us.
        "hook-PyQt6.py": {
            "plugins": ["platforms", "printsupport"],  # keep platform plugin + print support
            "excluded_qml_plugins": "all",
        },
    },
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=blockcipher)

# GUI app (console=False). If you want console on Linux, set console=True for debugging.
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,                # <-- pass the EXE object, not a path
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=app_name,      # dist/<name>/
)
