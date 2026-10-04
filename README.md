# Treemaps

Treemaps is a PyQt6 filesystem visualizer. It scans a directory, aggregates file sizes, and displays the result as an interactive squarified treemap, based on Mark Bruls, Kees Huizing, and Jarke J. van Wijk's [Squarified Treemaps paper](https://classes.engineering.wustl.edu/cse557/readings/squarified-treemap.pdf).

## Usage

- Single-click selection and double-click directory navigation
- Right-click actions to open files and folders in the system file manager

## Features

- Squarified treemap layout with level-of-detail controls
- Parallel I/O-oriented directory scanning
- Symlink-loop suppression and permission-error handling
- Small-file aggregation below 4 KiB to reduce object allocation
- Top-10 directory grouping with a clickable `Other` group
- Live scan progress and file-count updates
- Current-view file count and total size summary

## Requirements

- Python 3.10+
- PyQt6 for the GUI
- `coverage` for coverage reports

## Setup

From the project root, create or use the included virtual environment and install runtime dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For development and coverage tooling:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Run the GUI

The package lives under `src`, so set `PYTHONPATH` for the current PowerShell session:

```powershell
$env:PYTHONPATH = "$PWD\src"
```

Launch with a folder chooser:

```powershell
.\.venv\Scripts\python.exe -m treemap
```

Or scan a directory directly:

```powershell
.\.venv\Scripts\python.exe -m treemap C:\Path\To\Folder
```

The window remains responsive while scanning. The progress bar is indeterminate because the final file count is not known before traversal, while the status text shows the number discovered so far.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite covers models, scanner behavior, nested empty directories, cyclic symlinks, permission errors, small-file aggregation, layout boundaries, and squarify behavior.

The real symlink test may be skipped on Windows when the process does not have symbolic-link creation privileges. A mocked cyclic-symlink regression test runs independently of that permission.

## Run coverage

The coverage configuration excludes the GUI and module entry point so the report focuses on core logic:

```powershell
.\.venv\Scripts\python.exe -m coverage erase
.\.venv\Scripts\python.exe -m coverage run -m unittest discover -s tests
.\.venv\Scripts\python.exe -m coverage report -m
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): system design, scanning pipeline, layout, rendering, and testing strategy
- [API reference](docs/API.md): models, scanner, layout, squarify, and GUI entry points

## Project layout

```text
src/treemap/          application package
tests/                unittest suite
docs/                 architecture and API documentation
requirements.txt      runtime dependencies
requirements-dev.txt  runtime plus coverage tooling
.coveragerc           coverage configuration
```
