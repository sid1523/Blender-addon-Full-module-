import random
import pytest
from canvas3d.generation.spec_executor import SpecExecutor

def _base_spec(seed: int) -> dict:
    return {
        "version": "1.0.0",
        "domain": "procedural_dungeon",
        "units": "meters",
        "seed": seed,
        "grid": {"cell_size_m": 1.0, "dimensions": {"cols": 10, "rows": 10}},
        "materials": [],
        "collections": [],
        "objects": [],
        "lighting": [
            {"type": "sun", "position": [0, 0, 10], "rotation_euler": [0, 0, 0], "intensity": 1.0, "color_rgb": [1.0, 1.0, 1.0]}
        ],
        "camera": {"position": [0, -10, 10], "rotation_euler": [0.7, 0.0, 0.0], "fov_deg": 60.0},
    }

def test_seed_sets_random_state():
    # Seed 42 should set Python's random to a deterministic state inside executor
    ex = SpecExecutor()
    spec = _base_spec(42)
    ex.execute_scene_spec(spec, request_id="determinism-42", dry_run_when_no_bpy=True)
    val = random.random()
    # Known first random after seeding with 42
    assert pytest.approx(val, rel=1e-12) == 0.6394267984578837

def test_reseeding_produces_same_random_sequence():
    ex = SpecExecutor()
    spec = _base_spec(42)
    ex.execute_scene_spec(spec, request_id="run-a", dry_run_when_no_bpy=True)
    a = random.random()
    # Re-seed to same value via another execution should reset sequence
    ex.execute_scene_spec(spec, request_id="run-b", dry_run_when_no_bpy=True)
    b = random.random()
    assert pytest.approx(a, rel=1e-12) == b

def test_different_seed_changes_random_state():
    ex = SpecExecutor()
    spec42 = _base_spec(42)
    ex.execute_scene_spec(spec42, request_id="run-42", dry_run_when_no_bpy=True)
    v42 = random.random()
    spec43 = _base_spec(43)
    ex.execute_scene_spec(spec43, request_id="run-43", dry_run_when_no_bpy=True)
    v43 = random.random()
    # Different seeds should yield different next random values with overwhelming probability
    assert v42 != v43

def test_deterministic_collection_name_dry_run():
    ex = SpecExecutor()
    spec = _base_spec(123)
    name1 = ex.execute_scene_spec(spec, request_id="det-name", dry_run_when_no_bpy=True)
    name2 = ex.execute_scene_spec(spec, request_id="det-name", dry_run_when_no_bpy=True)
    assert name1 == name2