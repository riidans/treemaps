from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
from collections import deque

from treemap.models import FileNode
from treemap.squarify import squarify, Rect

FOLDER_HEADER_HEIGHT = 24.0

@dataclass(frozen = True)
class LayoutItem:
    """Used by GUI painter"""
    node: FileNode
    rect: Rect
    depth: int

def compute_layout(root: FileNode, bounds: Rect, min_size: float = 0.0, max_depth: int = 5, padding: float = 1.0) -> List[LayoutItem]:
    """BFS and LoD culling over FileNode tree using a FIFO queue"""
    bx, by, bw, bh = bounds
    if bw <= 0.0 or bh <= 0.0 or root.size <= 0:
        return []

    if not root.is_dir or not root.children:
        return [LayoutItem(node=root, rect=bounds, depth=0)]

    visible_items: List[LayoutItem] = []

    queue: deque[Tuple[FileNode, Rect, int]] = deque([(root, bounds, 0)])

    while queue:
        parent, container_bounds, depth = queue.popleft()
        
        active_children = [child for child in parent.children if child.size > 0]
        
        # Zero-byte children
        if not active_children:
            visible_items.append(LayoutItem(node=parent, rect=container_bounds, depth=depth))
            continue
        child_sizes = [float(child.size) for child in active_children]
        computed_rects = squarify(child_sizes, container_bounds)

        for child, child_rect in zip(active_children, computed_rects):
            cx, cy, cw, ch = child_rect
            if cw <= 0.0 or ch <= 0.0:
                continue

            can_subdivide = (
                child.is_dir
                and (depth + 1) < max_depth
                and cw >= min_size
                and ch >= min_size
                and any(grandchild.size > 0 for grandchild in child.children)
            )

            if can_subdivide:
                if padding > 0.0 and cw > (2.0 * padding) and ch > (2.0 * padding):
                    header_height = (
                        FOLDER_HEADER_HEIGHT
                        if depth == 0 and ch > (2.0 * padding + FOLDER_HEADER_HEIGHT)
                        else 0.0
                    )
                    sub_bounds = (
                        cx + padding,
                        cy + padding + header_height,
                        cw - (2.0 * padding),
                        ch - (2.0 * padding) - header_height,
                    )
                else:
                    sub_bounds = child_rect

                # Enqueue subdir
                queue.append((child, sub_bounds, depth + 1))
            else:
                visible_items.append(
                    LayoutItem(node=child, rect=child_rect, depth=depth + 1)
                )

    return visible_items
