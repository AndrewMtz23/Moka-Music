# Contributing To MokaMusic

Thanks for helping improve MokaMusic.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Feature Workflow

1. Create a focused feature branch.
2. Keep functional changes separate from formatting-only changes.
3. Run lint, format, and tests before opening a pull request.
4. Push the branch and wait for GitHub Actions to pass.
5. Merge only after CI is green.

## Local Checks

```powershell
.\.venv\Scripts\ruff.exe check app tests tools
.\.venv\Scripts\ruff.exe format app tests tools --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Optional deeper diagnostics:

```powershell
.\.venv\Scripts\pylint.exe app tests tools --exit-zero
.\.venv\Scripts\pip-audit.exe -r requirements.txt
```

Pylint is intentionally optional for now. Ruff and the unit tests are the main required checks.

## Release Checklist

Before publishing a release:

```powershell
.\.venv\Scripts\ruff.exe check app tests tools
.\.venv\Scripts\ruff.exe format app tests tools --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
.\.venv\Scripts\pyinstaller.exe MokaMusic.spec --noconfirm --clean
```

Package Windows builds by zipping the full `dist/MokaMusic` folder, not only `MokaMusic.exe`.

The `Windows Release Build` workflow can also generate the zip from GitHub Actions through `Run workflow`.

To publish a GitHub Release automatically, push a version tag from `main`:

```powershell
git tag v2.2.0
git push origin v2.2.0
```

The `GitHub Release` workflow builds the Windows zip and attaches it to the release.
