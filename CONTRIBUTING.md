# Contributing To MokaMusic

Thanks for helping improve MokaMusic.

## Docker Development (Recommended for a Consistent Environment)

Install Docker Desktop (using Linux containers), or Docker Engine with Compose
on Linux. Clone this repository and run commands from its root.

### VS Code with a Browser Desktop

1. Install VS Code and its **Dev Containers** extension.
2. Open the repository and choose **Dev Containers: Reopen in Container** from
   the command palette. The first build installs Python 3.11, dependencies,
   FFmpeg, and a lightweight desktop; subsequent opens reuse them.
3. In the container terminal, run `python main.py`.
4. In VS Code's **Ports** panel, open port **6080** in your browser. Click
   **Connect** and use the local development password `vscode`.

The editor and app share your checked-out source files. Restart the app after
editing Python code. Rebuild the container after changing dependencies.
The desktop uses the maintained
[desktop-lite feature](https://github.com/devcontainers/features/tree/main/src/desktop-lite).
Keep the forwarded desktop port local/private; the example password is for
local development only. Use sample audio files inside the workspace when
testing metadata edits, since changes to mounted files persist on the host.

### Terminal and Automated Tests

```sh
docker compose build dev
docker compose run --rm dev
```

Inside the shell:

```sh
ruff check app tests tools
ruff format app tests tools --check
xvfb-run -a python -m unittest discover -s tests -p "test*.py"
```

Or run tests directly from the host:

```sh
docker compose run --rm -T dev xvfb-run -a python -m unittest discover -s tests -p "test*.py"
```

Xvfb provides an invisible display for Tk tests. For an interactive visible
window, use the VS Code browser desktop above. Both setups use silent dummy
audio: UI and metadata work are supported, but listening to playback and
testing Windows taskbar controls or building the Windows executable require
the native Windows setup below. Linux may skip Windows-only tests.

The container runs as a non-root user and mounts only this repository. On
Linux, VS Code adjusts the user ID for bind mounts; for plain Compose, if your
host UID is not 1000, pass `--user "$(id -u):$(id -g)"` to `docker compose run`.

### Published Development Image

The **Development Container** workflow builds and tests the image on pull
requests. Successful runs on `main` publish it to GitHub Packages as
`ghcr.io/andrewmtz23/moka-music-dev:latest`, plus an immutable-by-convention
`sha-<commit>` tag. It contains tools and dependencies, not source code or music.

After the first publication, the repository owner should check the package's
visibility and make it public so contributors can pull without signing in.
For example, from a cloned repository in PowerShell:

```powershell
docker pull ghcr.io/andrewmtz23/moka-music-dev:latest
docker run --rm -it --init --env SDL_AUDIODRIVER=dummy --mount "type=bind,source=$PWD,target=/workspace" ghcr.io/andrewmtz23/moka-music-dev:latest
```

The published image provides the terminal environment. Dev Containers adds the
browser desktop when opening the project in VS Code. The development image is
separate from the Windows application available in Releases.

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

After the release workflow is merged into `main`, a successful `Python CI` run on `main` creates a release automatically when `app/constants.py` has a new `VERSION`.

You can also publish a GitHub Release manually by pushing a version tag from `main`:

```powershell
git tag v2.3.6
git push origin v2.3.6
```

The `GitHub Release` workflow builds the Windows zip and attaches it to the release.
