# Architecture

## Overview

Treemaps is a filesystem treemap viewer. It scans a directory into a lightweight tree, computes rectangles for visible items, and renders those rectangles in a PyQt6 GUI.

The main pipeline is:

```text
filesystem
    -> scanner.py
    -> FileNode tree + AggregateLeaf rollups
    -> layout.py / squarify.py
    -> LayoutItem rectangles
    -> gui.py / QPainter
```

## Package structure

```text
src/treemap/
├── __main__.py   # python -m treemap entry point
├── gui.py        # PyQt6 window, interaction, rendering
├── layout.py     # breadth-first layout and level-of-detail decisions
├── models.py     # FileNode and compact aggregate leaf models
├── scanner.py    # parallel filesystem traversal and size aggregation
└── squarify.py   # rectangle packing algorithm
```

## Scanning

`scanner.scan_filesystem()` validates the target, traverses directories, and calculates aggregate directory sizes.

Directory scanning uses a bounded `ThreadPoolExecutor`. A coordinator maintains a queue of directories while worker threads perform `os.scandir()` and metadata reads. The coordinator owns tree mutation, so `FileNode` parent and child relationships are not modified concurrently.

The worker count is selected dynamically:

```python
min(32, (os.cpu_count() or 4) * 4)
```

Symlinks are skipped before directory checks, preventing cyclic links from entering the traversal. Permission, missing-file, and general OS errors are treated as unreadable entries or empty directories rather than aborting the scan.

### Small-file aggregation

Files smaller than 4,096 bytes are not allocated as individual `FileNode` objects. Each directory receives at most one `AggregateLeaf` containing:

- total size of rolled-up files;
- number of rolled-up files;
- the containing directory path.

The aggregate leaf participates in directory size calculations and layout, but is rendered as a neutral-gray compact item named `Other files (N)`.

## Models

`FileNode` represents directories and individually retained files. Directories own their children and set child parent pointers when adding entries.

`AggregateLeaf` is a compact leaf for many small files. It intentionally has no individual filenames because those names were discarded during scanning.

## Layout

`layout.compute_layout()` uses a queue to process the tree breadth-first. Each directory's active children are passed to `squarify()` and assigned rectangles.

Level of detail is controlled by:

- `max_depth`, which limits subdivision depth;
- rectangle dimensions, including the GUI's 24-pixel minimum for subdivision;
- zero-size filtering.

Directories that are not subdivided remain visible as a single rectangle, preserving the treemap's visual density while avoiding excessive deep traversal during painting.

Folder headers reserve space above top-level child treemaps so the main folder label does not cover the largest child rectangle.

## Rendering and navigation

`TreemapCanvas` paints `LayoutItem` rectangles with `QPainter`.

Colors are stable by top-level directory, so drilling down preserves visual context. Aggregate leaves remain neutral gray.

The GUI provides:

- full current path in the toolbar;
- a clickable color legend;
- single-click selection and path display;
- double-click directory drill-down;
- right-click file-manager actions;
- a Back button;
- nested folder labels only when useful;
- a bottom summary of file count and total size;
- an asynchronous scan progress indicator.

Large directories are grouped for display into the ten largest top-level directories plus a clickable `Other` directory containing the remainder.

## Testing and coverage

Tests use the standard library `unittest` runner:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Coverage focuses on scanner, models, layout, and squarify. GUI and the module entry point are excluded in `.coveragerc` because GUI behavior is better validated with smoke tests or manual interaction.

```powershell
.\.venv\Scripts\python.exe -m coverage run -m unittest discover -s tests
.\.venv\Scripts\python.exe -m coverage report -m
```
