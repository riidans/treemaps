import os
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from treemap.models import AggregateLeaf, FileNode

ProgressCallback = Optional[Callable[[Path, int], None]]
SMALL_FILE_THRESHOLD = 4096


@dataclass
class _DirectoryResult:
    files: list[tuple[Path, str, int]]
    directories: list[tuple[Path, str]]
    small_file_size: int = 0
    small_file_count: int = 0
    file_count: int = 0


def _scan_one_directory(directory_path: Path) -> _DirectoryResult:
    result = _DirectoryResult(files=[], directories=[])
    try:
        with os.scandir(directory_path) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        result.directories.append((Path(entry.path), entry.name))
                        continue

                    result.file_count += 1
                    try:
                        file_size = entry.stat(follow_symlinks=False).st_size
                    except (PermissionError, FileNotFoundError, OSError):
                        file_size = 0

                    if file_size < SMALL_FILE_THRESHOLD:
                        result.small_file_size += file_size
                        result.small_file_count += 1
                    else:
                        result.files.append((Path(entry.path), entry.name, file_size))
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return result

def scan_directory_dfs(root_path: Path, on_progress: ProgressCallback = None, progress_interval: int = 500) -> FileNode:
    """Runs through filesystem using a DFS stack, returns root of tree model"""
    root_path = root_path.resolve()
    root_node = FileNode(
        path = root_path,
        name = root_path.name or str(root_path),
        is_dir = True
    )

    if not root_path.is_dir():
        try:
            stat = root_path.stat(follow_symlinks=False)
            root_node.is_dir = False
            root_node.size = stat.st_size
        except (PermissionError, FileNotFoundError, OSError):
            root_node.size = 0
        return root_node

    pending: deque[tuple[Path, FileNode]] = deque([(root_path, root_node)])
    in_flight = {}
    total_files_discovered = 0
    max_workers = min(32, (os.cpu_count() or 4) * 4)

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="treemap-scan") as executor:
        while pending or in_flight:
            while pending and len(in_flight) < max_workers:
                directory_path, parent_node = pending.popleft()
                future = executor.submit(_scan_one_directory, directory_path)
                in_flight[future] = (directory_path, parent_node)

            completed, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in completed:
                directory_path, parent_node = in_flight.pop(future)
                try:
                    result = future.result()
                except (PermissionError, FileNotFoundError, OSError):
                    continue

                for file_path, file_name, file_size in result.files:
                    parent_node.add_child(
                        FileNode(
                            path=file_path,
                            name=file_name,
                            size=file_size,
                            is_dir=False,
                        )
                    )

                if result.small_file_count:
                    parent_node.add_aggregate(
                        AggregateLeaf(
                            path=directory_path,
                            name=f"Other files ({result.small_file_count})",
                            size=result.small_file_size,
                            count=result.small_file_count,
                        )
                    )

                for child_path, child_name in result.directories:
                    child_node = FileNode(
                        path=child_path,
                        name=child_name,
                        is_dir=True,
                    )
                    parent_node.add_child(child_node)
                    pending.append((child_path, child_node))

                total_files_discovered += result.file_count
                if on_progress:
                    on_progress(root_path, total_files_discovered)

    return root_node

def aggregate_sizes_post_order(root: FileNode) -> int:
    """Calculates dir size using post-order traversal"""
    if not root.is_dir:
        return root.size
    
    stack: list[tuple[FileNode, bool]] = [(root, False)]

    while stack:
        node, children_processed = stack.pop()
        if children_processed:
            node.size = sum(child.size for child in node.children)
        else:
            stack.append((node, True))
            for child in reversed(node.children):
                if child.is_dir:
                    stack.append((child, False))

    return root.size

def scan_filesystem(root_path: Path, on_progress: ProgressCallback = None, progress_interval: int = 500) -> FileNode:
    path = Path(root_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Target path does not exist: {path}")

    root_node = scan_directory_dfs(
        root_path = path,
        on_progress = on_progress,
        progress_interval = progress_interval
    )
    
    aggregate_sizes_post_order(root_node)
    return root_node

