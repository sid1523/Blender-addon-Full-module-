import pytest

from canvas3d.generation.spec_executor import SpecExecutor, SpecExecutionError
import canvas3d.generation.spec_executor as se_mod


# ----------------------------
# Fake bpy data-block managers
# ----------------------------
class _FakeObject:
    def __init__(self, name):
        self.name_full = name
        self.name = name


class _NamedBlock:
    def __init__(self, name):
        self.name = name


class _ManagerBase:
    def __init__(self):
        self._items = {}

    def __iter__(self):
        return iter(self._items.values())

    def get(self, name):
        return self._items.get(name)

    def _add(self, name, obj):
        self._items[name] = obj

    def remove(self, item, do_unlink=True):
        name = getattr(item, "name", None) or getattr(item, "name_full", None)
        if not isinstance(name, str):
            raise TypeError("Invalid data-block passed to remove()")
        if name in self._items:
            del self._items[name]


class _ObjectsManager(_ManagerBase):
    def new(self, name, *args, **kwargs):
        obj = _FakeObject(name)
        self._add(name, obj)
        return obj


class _MaterialsManager(_ManagerBase):
    def new(self, name):
        m = _NamedBlock(name)
        self._add(name, m)
        return m


class _ImagesManager(_ManagerBase):
    pass


class _MeshesManager(_ManagerBase):
    def new(self, name):
        m = _NamedBlock(name)
        self._add(name, m)
        return m


class _CollectionsManager(_ManagerBase):
    def new(self, name):
        c = _NamedBlock(name)
        self._add(name, c)
        return c


class _WorldsManager(_ManagerBase):
    pass


class _DataContainer:
    def __init__(self):
        self.objects = _ObjectsManager()
        self.materials = _MaterialsManager()
        self.images = _ImagesManager()
        self.meshes = _MeshesManager()
        self.collections = _CollectionsManager()
        self.worlds = _WorldsManager()


class _FakeBpy:
    """
    Minimal bpy stub with data-block managers used by SpecExecutor.
    """
    def __init__(self):
        self.data = _DataContainer()


# ----------------------------
# Spec helpers
# ----------------------------
def make_min_valid_spec(force_fail=False):
    return {
        "version": "1.0.0",
        "domain": "procedural_dungeon",
        "units": "meters",
        "seed": 42,
        "metadata": {"quality_mode": "balanced", "hardware_profile": "gpu_8gb", "force_fail": bool(force_fail)},
        "grid": {"cell_size_m": 2.0, "dimensions": {"cols": 10, "rows": 10}},
        "objects": [
            {
                "id": "room_a",
                "type": "room",
                "grid_cell": {"col": 1, "row": 1},
                "properties": {"width_cells": 4, "height_cells": 3},
                "material": "stone_wall",
                "collection": "geometry",
            }
        ],
        "lighting": [
            {
                "type": "sun",
                "position": [0.0, 0.0, 10.0],
                "rotation_euler": [0.0, 0.0, 0.0],
                "intensity": 1.0,
                "color_rgb": [1.0, 1.0, 1.0],
            }
        ],
        "camera": {"position": [0.0, -5.0, 2.0], "rotation_euler": [1.0, 0.0, 0.0], "fov_deg": 60.0},
        "materials": [{"name": "stone_wall"}],
        "collections": [{"name": "geometry", "purpose": "geometry"}],
        "constraints": {"min_path_length_cells": 5, "require_traversable_start_to_goal": True, "max_polycount": 1000},
    }


# ----------------------------
# Tests
# ----------------------------
def test_atomic_cleanup_on_failure(monkeypatch):
    # Arrange fake bpy with pre-existing items that must persist
    fake_bpy = _FakeBpy()
    fake_bpy.data.objects.new("KeepObj")
    fake_bpy.data.materials.new("KeepMat")
    fake_bpy.data.collections.new("KeepCol")

    # Inject stub bpy into module under test
    monkeypatch.setattr(se_mod, "bpy", fake_bpy, raising=True)

    spec = make_min_valid_spec(force_fail=True)
    executor = SpecExecutor()

    # Act: execute and expect failure with cleanup
    with pytest.raises(SpecExecutionError):
        executor.execute_scene_spec(
            spec,
            request_id="exec-fail",
            expect_version="1.0.0",
            dry_run_when_no_bpy=False,
            cleanup_on_failure=True,
        )

    # Assert: newly created data-blocks removed; pre-existing remain
    obj_names = set(o.name_full for o in fake_bpy.data.objects)
    mat_names = set(getattr(m, "name", "") for m in fake_bpy.data.materials)
    col_names = set(getattr(c, "name", "") for c in fake_bpy.data.collections)

    assert "KeepObj" in obj_names
    assert "KeepMat" in mat_names
    assert "KeepCol" in col_names

    # New items should be gone
    assert "Obj_room_a" not in obj_names
    assert "stone_wall" not in mat_names
    # Temp collection should be removed
    assert not any(n.startswith("Canvas3D_Temp_") for n in col_names)


def test_success_commit_and_deterministic_names(monkeypatch):
    # Fresh fake bpy
    fake_bpy = _FakeBpy()

    # Inject stub bpy into module under test
    monkeypatch.setattr(se_mod, "bpy", fake_bpy, raising=True)

    spec = make_min_valid_spec(force_fail=False)
    executor = SpecExecutor()

    # Act: execute successfully
    commit_name = executor.execute_scene_spec(
        spec,
        request_id="abc123",
        expect_version="1.0.0",
        dry_run_when_no_bpy=False,
        cleanup_on_failure=True,
    )

    # Assert: committed collection exists and is named deterministically
    assert commit_name == "Canvas3D_Scene_abc123"
    col_names = set(getattr(c, "name", "") for c in fake_bpy.data.collections)
    assert commit_name in col_names

    # Object deterministic name should exist
    obj_names = set(o.name_full for o in fake_bpy.data.objects)
    assert "Obj_room_a" in obj_names

    # Material deterministic name should exist
    mat_names = set(getattr(m, "name", "") for m in fake_bpy.data.materials)
    assert "stone_wall" in mat_names