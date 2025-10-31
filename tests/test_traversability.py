import pytest

from canvas3d.utils.traversability import (
    astar_path_length,
    check_traversable,
    is_spec_traversable,
)


def test_astar_simple_path():
    cols, rows = 5, 4
    blocked = set()
    start = (0, 0)
    goal = (4, 3)
    # Manhattan shortest path length for 4-connected grid
    expected = (4 - 0) + (3 - 0)
    length = astar_path_length(cols, rows, blocked, start, goal)
    assert length == expected


def test_astar_no_path_due_to_blocked_barrier():
    cols, rows = 5, 5
    # Create a vertical barrier at col=2 (except at the goal)
    blocked = {(2, r) for r in range(rows)}
    start = (0, 2)
    goal = (4, 2)
    assert astar_path_length(cols, rows, blocked, start, goal) is None


def test_check_traversable_min_length():
    cols, rows = 3, 3
    blocked = set()
    start = (0, 0)
    goal = (2, 2)
    ok, length = check_traversable(cols, rows, blocked, start, goal, min_len=3)
    assert ok is True and isinstance(length, int)
    ok2, length2 = check_traversable(cols, rows, blocked, start, goal, min_len=10)
    assert ok2 is False and isinstance(length2, int)


def _make_min_spec():
    return {
        "version": "1.0.0",
        "domain": "procedural_dungeon",
        "units": "meters",
        "seed": 123,
        "grid": {"cell_size_m": 2.0, "dimensions": {"cols": 6, "rows": 5}},
        "objects": [
            {
                "id": "room_a",
                "type": "room",
                "grid_cell": {"col": 1, "row": 1},
                "properties": {"width_cells": 3, "height_cells": 3},
                "collection": "geometry",
            }
        ],
        "lighting": [
            {
                "type": "sun",
                "position": [0.0, 0.0, 5.0],
                "rotation_euler": [0.0, 0.0, 0.0],
                "intensity": 2.0,
                "color_rgb": [1.0, 1.0, 1.0],
            }
        ],
        "camera": {"position": [0.0, -5.0, 2.0], "rotation_euler": [1.0, 0.0, 0.0], "fov_deg": 60.0},
        "materials": [{"name": "stone_wall"}],
        "collections": [{"name": "geometry", "purpose": "geometry"}],
        "constraints": {"min_path_length_cells": 5, "require_traversable_start_to_goal": True, "max_polycount": 1000},
    }


def test_is_spec_traversable_ok_and_min_len_enforced():
    spec = _make_min_spec()
    ok, plen, info = is_spec_traversable(spec, min_len=2)
    assert ok is True
    assert isinstance(plen, int)
    assert info["cols"] == 6 and info["rows"] == 5

    # Make minimum higher than shortest path to force failure
    ok2, plen2, _ = is_spec_traversable(spec, min_len=999)
    assert ok2 is False
    assert isinstance(plen2, int)


def test_is_spec_traversable_blocked_start_or_goal():
    # Block the default start (0,0) via an object with properties.blocked=true
    spec = _make_min_spec()
    spec["objects"].append(
        {
            "id": "block_start",
            "type": "cube",
            "grid_cell": {"col": 0, "row": 0},
            "properties": {"blocked": True},
            "collection": "geometry",
        }
    )
    ok, plen, info = is_spec_traversable(spec, min_len=0)
    assert ok is False
    assert plen is None

    # Alternatively block the default goal (cols-1, rows-1)
    spec = _make_min_spec()
    cols, rows = spec["grid"]["dimensions"]["cols"], spec["grid"]["dimensions"]["rows"]
    spec["objects"].append(
        {
            "id": "block_goal",
            "type": "cube",
            "grid_cell": {"col": cols - 1, "row": rows - 1},
            "properties": {"blocked": True},
            "collection": "geometry",
        }
    )
    ok2, plen2, _ = is_spec_traversable(spec, min_len=0)
    assert ok2 is False
    assert plen2 is None