# API Reference

The package is available under `treemap` when `src` is on `PYTHONPATH`.

## `treemap.models`

### `FileNode`

```python
FileNode(
    path: Path,
    name: str,
    size: int = 0,
    is_dir: bool = False,
    parent: FileNode | None = None,
    children: list[FileNode | AggregateLeaf],
)
```

Represents a directory or retained file.

Important attributes:

- `path`: filesystem path;
- `name`: display name;
- `size`: file size or aggregated directory size in bytes;
- `is_dir`: whether the node is a directory;
- `parent`: parent directory, if any;
- `children`: directory entries.

Methods:

- `add_child(child)`: attaches a `FileNode` and sets its parent;
- `add_aggregate(aggregate)`: attaches an `AggregateLeaf` and sets its parent;
- `remove_child(child)`: removes a child and clears its parent.

### `AggregateLeaf`

```python
AggregateLeaf(
    path: Path,
    name: str,
    size: int,
    count: int,
    is_dir: bool = False,
    parent: FileNode | None = None,
)
```

Compact representation of multiple small files. `count` is the number of files represented by the leaf. It is not expandable because individual filenames are intentionally not retained.

## `treemap.scanner`

### `scan_filesystem`

```python
scan_filesystem(
    root_path: Path,
    on_progress: Callable[[Path, int], None] | None = None,
    progress_interval: int = 500,
) -> FileNode
```

Scans an existing filesystem path and returns the root `FileNode`.

Raises `FileNotFoundError` if the target does not exist. Unreadable entries are skipped or represented with zero size where appropriate.

The progress callback receives the scan root and the number of discovered files after directory work completes. The final count includes files rolled into aggregate leaves. `progress_interval` is retained for API compatibility; progress is currently reported after each completed directory.

### `scan_directory_dfs`

```python
scan_directory_dfs(
    root_path: Path,
    on_progress: Callable[[Path, int], None] | None = None,
    progress_interval: int = 500,
) -> FileNode
```

Performs the directory traversal and builds the tree. Despite the historical function name, traversal dispatch is now queue-based and uses parallel directory workers.

### `aggregate_sizes_post_order`

```python
aggregate_sizes_post_order(root: FileNode) -> int
```

Calculates directory sizes from child sizes using post-order traversal and returns the root size.

### `SMALL_FILE_THRESHOLD`

```python
SMALL_FILE_THRESHOLD = 4096
```

Files strictly smaller than this number of bytes are rolled into an `AggregateLeaf`.

## `treemap.squarify`

### `squarify`

```python
squarify(
    sizes: list[float],
    bounds: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]
```

Packs positive sizes into rectangles within `(x, y, width, height)`. Results preserve the input index positions. Non-positive sizes receive zero-sized rectangles at the bounds origin.

### `worst`

```python
worst(R: list[float], w: float) -> float
```

Returns the worst aspect-ratio score for a candidate row along side length `w`. Empty, invalid, or zero-minimum rows return infinity.

## `treemap.layout`

### `LayoutItem`

```python
LayoutItem(
    node: FileNode | AggregateLeaf,
    rect: tuple[float, float, float, float],
    depth: int,
)
```

Immutable GUI-facing pairing of a model entry and its rectangle.

### `compute_layout`

```python
compute_layout(
    root: FileNode,
    bounds: tuple[float, float, float, float],
    min_size: float = 0.0,
    max_depth: int = 5,
    padding: float = 1.0,
) -> list[LayoutItem]
```

Computes visible rectangles using breadth-first traversal.

Parameters:

- `root`: directory tree root;
- `bounds`: canvas rectangle;
- `min_size`: minimum width and height required to subdivide a directory; the GUI passes `24.0`;
- `max_depth`: maximum subdivision depth;
- `padding`: inset applied before laying out a subdivided directory.

Returns an empty list for invalid bounds or zero-sized roots.

## `treemap.gui`

### `main`

```python
main(argv: list[str] | None = None) -> int
```

Starts the PyQt6 application. With no path argument it opens a folder chooser; with a path argument it begins scanning that directory.

Run from the project root:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m treemap [PATH]
```

### `prepare_display_root`

```python
prepare_display_root(root: FileNode) -> FileNode
```

Prepares the GUI view by retaining the ten largest top-level directories and grouping the remaining directories under a clickable `Other` directory.
