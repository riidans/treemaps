from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class AggregateLeaf:
    """Compact representation of many small files with no useful names."""
    path: Path
    name: str
    size: int
    count: int
    is_dir: bool = False
    parent: Optional[FileNode] = None

@dataclass
class FileNode:
    """Represents a single file/directory"""
    path: Path
    name: str
    size: int = 0
    is_dir: bool = False
    parent: Optional[FileNode] = None
    children: List[FileNode | AggregateLeaf] = field(default_factory = list)
    rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def add_child(self, child: FileNode) -> None:
        child.parent = self
        self.children.append(child)

    def add_aggregate(self, aggregate: AggregateLeaf) -> None:
        aggregate.parent = self
        self.children.append(aggregate)

    def remove_child(self, child: FileNode) -> None:
        if child in self.children:
            self.children.remove(child)
            child.parent = None
