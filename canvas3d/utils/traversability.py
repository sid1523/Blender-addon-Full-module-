# Canvas3D Traversability Utilities
# Tier 2.2 requirement: automated traversal validation (A*).
#
# This module provides:
# - Lightweight grid A* implementation with Manhattan heuristic
# - Helpers to check traversability and minimum path length constraints
# - Optional extraction stubs from a scene spec (will be improved as domain rules evolve)
#
# Public API:
# - astar_path_length(cols, rows, blocked, start, goal) -> Optional[int]
# - check_traversable(cols, rows, blocked, start, goal, min_len=None) -> tuple[bool, Optional[int]]
# - is_spec_traversable(spec, start=None, goal=None, min_len=None) -> tuple[bool, Optional[int], dict]
#
# Notes:
# - Coordinates are integer grid cells in [0..cols-1] x [0..rows-1]
# - Movement is 4-connected (N,E,S,W)
# - blocked is a set of (col,row) cells that cannot be traversed
# - For MVP, spec extraction uses conservative defaults; will be enhanced to encode
#   rooms, corridors, and doors semantics from the schema contract.

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Set, Tuple, List, Dict
import heapq


@dataclass(frozen=True)
class Cell:
    c: int
    r: int

    def as_tuple(self) -> Tuple[int, int]:
        return (self.c, self.r)


def _in_bounds(c: int, r: int, cols: int, rows: int) -> bool:
    return 0 <= c < cols and 0 <= r < rows


def _neighbors_4(c: int, r: int, cols: int, rows: int) -> Iterable[Tuple[int, int]]:
    # 4-connected grid
    cand = ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1))
    for cc, rr in cand:
        if _in_bounds(cc, rr, cols, rows):
            yield (cc, rr)


def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar_path_length(
    cols: int,
    rows: int,
    blocked: Set[Tuple[int, int]],
    start: Tuple[int, int],
    goal: Tuple[int, int],
) -> Optional[int]:
    """
    Compute shortest path length from start to goal using A* on a 4-connected grid.
    Returns the number of steps (edges) or None if no path exists.
    """
    if not _in_bounds(start[0], start[1], cols, rows):
        return None
    if not _in_bounds(goal[0], goal[1], cols, rows):
        return None
    if start in blocked or goal in blocked:
        return None

    open_heap: List[Tuple[int, Tuple[int, int]]] = []
    heapq.heappush(open_heap, (0, start))
    g_score: Dict[Tuple[int, int], int] = {start: 0}
    closed: Set[Tuple[int, int]] = set()

    while open_heap:
        _, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        if cur == goal:
            return g_score[cur]
        closed.add(cur)

        for nb in _neighbors_4(cur[0], cur[1], cols, rows):
            if nb in blocked:
                continue
            tentative = g_score[cur] + 1
            prev = g_score.get(nb)
            if prev is None or tentative < prev:
                g_score[nb] = tentative
                f = tentative + _manhattan(nb, goal)
                heapq.heappush(open_heap, (f, nb))

    return None


def check_traversable(
    cols: int,
    rows: int,
    blocked: Set[Tuple[int, int]],
    start: Tuple[int, int],
    goal: Tuple[int, int],
    min_len: Optional[int] = None,
) -> Tuple[bool, Optional[int]]:
    """
    Return (ok, path_len). ok is True if a path exists and satisfies min_len (if provided).
    """
    length = astar_path_length(cols, rows, blocked, start, goal)
    if length is None:
        return False, None
    if min_len is not None and length < int(min_len):
        return False, length
    return True, length


# -----------------------------
# Spec integration (MVP stubs)
# -----------------------------
def _extract_grid_dims(spec: dict) -> Tuple[int, int]:
    grid = spec.get("grid") or {}
    dims = grid.get("dimensions") or {}
    cols = int(dims.get("cols", 0))
    rows = int(dims.get("rows", 0))
    return cols, rows


def _extract_blocked_from_spec(spec: dict) -> Set[Tuple[int, int]]:
    """
    Derive blocked cells from the spec.
    Defaults to an empty set unless objects explicitly mark blocking.
    Enhancements:
    - Any object with properties.blocked == True will force-block its grid_cell.
    - Explicit 'traversable_cells' (on spec or per-object) are honored as open cells.
    - 'walkable_area' rectangles (per-object) are honored as open cells.
    - Doors are considered traversable (their cells are forced open).
    """
    cols, rows = _extract_grid_dims(spec)
    blocked: Set[Tuple[int, int]] = set()
    forced_open: Set[Tuple[int, int]] = set()

    # Spec-level explicit traversable cells (optional)
    try:
        for cell in spec.get("traversable_cells", []) or []:
            if isinstance(cell, (list, tuple)) and len(cell) == 2:
                c, r = int(cell[0]), int(cell[1])
                if 0 <= c < cols and 0 <= r < rows:
                    forced_open.add((c, r))
    except Exception:
        pass

    objs = spec.get("objects") or []
    for o in objs:
        try:
            # Force-blocked cells
            props = o.get("properties") or {}
            if bool(props.get("blocked", False)):
                gc = o.get("grid_cell")
                if isinstance(gc, dict):
                    col = gc.get("col")
                    row = gc.get("row")
                    if isinstance(col, int) and isinstance(row, int):
                        if 0 <= col < cols and 0 <= row < rows:
                            blocked.add((col, row))

            # Doors: force-open the door cell
            if str(o.get("type", "")).lower() == "door":
                gc = o.get("grid_cell", {}) or {}
                col = gc.get("col")
                row = gc.get("row")
                if isinstance(col, int) and isinstance(row, int):
                    if 0 <= col < cols and 0 <= row < rows:
                        forced_open.add((col, row))

            # Object-level explicit traversable cells
            for cell in o.get("traversable_cells", []) or []:
                if isinstance(cell, (list, tuple)) and len(cell) == 2:
                    c, r = int(cell[0]), int(cell[1])
                    if 0 <= c < cols and 0 <= r < rows:
                        forced_open.add((c, r))

            # Object-level walkable area (rectangular)
            wa = o.get("walkable_area")
            if isinstance(wa, dict):
                if str(wa.get("type", "")).lower() == "rectangle":
                    b = wa.get("bounds", {}) or {}
                    min_col = int(b.get("min_col", 0))
                    max_col = int(b.get("max_col", 0))
                    min_row = int(b.get("min_row", 0))
                    max_row = int(b.get("max_row", 0))
                    for c in range(min_col, max_col):
                        for r in range(min_row, max_row):
                            if 0 <= c < cols and 0 <= r < rows:
                                forced_open.add((c, r))
        except Exception:
            continue

    # Ensure explicit traversable cells are not blocked
    blocked.difference_update(forced_open)
    return blocked


def _default_start_goal(spec: dict, cols: int, rows: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """
    Default start/goal are the grid corners to align with unit tests:
    start = (0,0), goal = (cols-1, rows-1) when grid is valid.
    """
    start = (0, 0) if cols > 0 and rows > 0 else (0, 0)
    goal = (max(0, cols - 1), max(0, rows - 1)) if cols > 0 and rows > 0 else (0, 0)
    return start, goal


def is_spec_traversable(
    spec: dict,
    start: Optional[Tuple[int, int]] = None,
    goal: Optional[Tuple[int, int]] = None,
    min_len: Optional[int] = None,
) -> Tuple[bool, Optional[int], Dict[str, object]]:
    """
    Validate traversability for a scene spec on its grid.
    Returns (ok, path_len, info)
      info = {
        "cols": int,
        "rows": int,
        "start": (c,r),
        "goal": (c,r),
        "blocked_count": int
      }
    """
    cols, rows = _extract_grid_dims(spec)
    blocked = _extract_blocked_from_spec(spec)

    # Determine start/goal
    s, g = _default_start_goal(spec, cols, rows)
    if start is not None:
        s = start
    if goal is not None:
        g = goal

    # Honor constraints.min_path_length_cells if min_len not provided
    if min_len is None:
        try:
            cons = spec.get("constraints", {}) or {}
            mpl = cons.get("min_path_length_cells", None)
            if isinstance(mpl, int) and mpl >= 0:
                min_len = mpl
        except Exception:
            pass

    ok, plen = check_traversable(cols, rows, blocked, s, g, min_len=min_len)
    info = {"cols": cols, "rows": rows, "start": s, "goal": g, "blocked_count": len(blocked)}
    return ok, plen, info


__all__ = [
    "Cell",
    "astar_path_length",
    "check_traversable",
    "is_spec_traversable",
]