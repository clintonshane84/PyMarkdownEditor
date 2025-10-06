# Releasing

This project ships **binary releases** for Windows, macOS, and Linux via GitHub Actions using **PyInstaller**.

## Prereqs
- Version bumped in `pymd/__init__.py` (SemVer).
- `CHANGELOG.md` updated.

## Steps
1. Tag and push:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
````

2. The workflow `.github/workflows/release-binaries.yml` will:

   * Build on `ubuntu-latest`, `windows-latest`, `macos-latest`
   * Produce:

     * `PyMarkdownEditor-windows-x86_64.exe`
     * `PyMarkdownEditor-macos-universal.zip` (contains `.app`)
     * `PyMarkdownEditor-linux-x86_64`
   * Create/update a GitHub Release for the tag and upload the artifacts

> If you need code signing, add platform-specific signing steps before packaging.

## Local Build (optional)

```bash
pip install -r requirements.txt
pip install -r build-requirements.txt
pyinstaller pyinstaller.spec
```

Artifacts appear in `dist/`.
