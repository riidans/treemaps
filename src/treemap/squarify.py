from typing import List, Tuple

Rect = Tuple[float, float, float, float]

def worst(R: List[float], w: float) -> float:
    """Worst aspect ratio in row along side w"""
    if not R or w <= 0:
        return float("inf")
    s = sum(R)
    if s == 0:
        return float("inf")

    r_plus = max(R)
    r_minus = min(R)

    if r_minus <= 0:
        return float("inf")

    w_sq = w * w
    s_sq = s * s

    return max((w_sq * r_plus) / s_sq, s_sq / (w_sq * r_minus))



def _layout_row(R: List[float], indices: List[int], bounds: Rect, results: List[Rect]) -> Rect:
    """Places row R along shortest edge"""
    x, y, width, height = bounds
    s = sum(R)

    if width <= height:
        # Row spans horizontally
        row_height = s / width if width > 0 else 0.0
        cur_x = x
        for r, orig_idx in zip(R, indices):
            item_w = r / row_height if row_height > 0 else 0.0
            results[orig_idx] = (cur_x, y, item_w, row_height)
            cur_x += item_w
        return (x, y + row_height, width, max(0.0, height - row_height))
    else: 
        # Row spans vertically
        row_width = s / height if height > 0 else 0.0
        cur_y = y
        for r, orig_idx in zip(R, indices):
            item_h = r / row_width if row_width > 0 else 0.0
            results[orig_idx] = (x, cur_y, row_width, item_h)
            cur_y += item_h
        return (x + row_width, y, max(0.0, width - row_width), height)



def squarify(sizes: list[float], bounds: tuple[float, float, float]) -> list[tuple[float, float, float, float]]:
    """Squarify file sizes into rectangles"""
    bx, by, bw, bh = bounds
    n = len(sizes)
    results: List[Rect] = [(bx, by, 0.0, 0.0)] * n

    if n == 0 or bw <= 0 or bh <= 0:
        return results

    total_size = sum(s for s in sizes if s > 0)
    if total_size <= 0:
        return results

    canvas_area = bw * bh
    indexed_areas = [
        ((size / total_size) * canvas_area, idx)
        for idx, size in enumerate(sizes)
        if size > 0
    ]
    indexed_areas.sort(key=lambda item: item[0], reverse=True)

    current_bounds = bounds
    R: List[float] = []        
    indices: List[int] = []    

    for r, orig_idx in indexed_areas:
        # w is the length of the shortest side of the rem container
        w = min(current_bounds[2], current_bounds[3])

        if not R:
            R.append(r)
            indices.append(orig_idx)
            continue

        curr_worst = worst(R, w)
        cand_worst = worst(R + [r], w)

        if cand_worst <= curr_worst:
            R.append(r)
            indices.append(orig_idx)
        else:
            # Aspect ratio degrades, freeze row and slice cont
            current_bounds = _layout_row(R, indices, current_bounds, results)
            R = [r]
            indices = [orig_idx]

    if R:
        _layout_row(R, indices, current_bounds, results)

    return results
