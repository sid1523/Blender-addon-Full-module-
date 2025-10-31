import importlib
import pytest

from canvas3d.generation.scene_builder import SceneBuilder, SceneExecutionError
import canvas3d.generation.scene_builder as sb_mod


class _FakeObject:
    def __init__(self, name):
        # Blender uses name_full for unique identifier in objects diff
        self.name_full = name
        self.name = name


class _ManagerBase:
    def __init__(self):
        self._items = {}

    def __iter__(self):
        # Iterate values like Blender's bpy.data.collections
        return iter(self._items.values())

    def get(self, name):
        return self._items.get(name)

    def _add(self, name, obj):
        self._items[name] = obj

    def _remove_by_name(self, name):
        if name in self._items:
            del self._items[name]

    def remove(self, item, do_unlink=True):  # do_unlink is accepted to mirror Blender API
        # Most bpy.data.remove signatures accept data-block object; we simulate lookup by its .name/.name_full
        name = getattr(item, "name", None) or getattr(item, "name_full", None)
        if not isinstance(name, str):
            raise TypeError("Invalid data-block passed to remove()")
        self._remove_by_name(name)


class _ObjectsManager(_ManagerBase):
    def new(self, name):
        obj = _FakeObject(name)
        self._add(name, obj)
        return obj

    def remove(self, item, do_unlink=True):
        super().remove(item, do_unlink=do_unlink)


class _NamedBlock:
    def __init__(self, name):
        self.name = name


class _MaterialsManager(_ManagerBase):
    def new(self, name):
        m = _NamedBlock(name)
        self._add(name, m)
        return m


class _ImagesManager(_ManagerBase):
    pass


class _MeshesManager(_ManagerBase):
    pass


class _CollectionsManager(_ManagerBase):
    pass


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


class _OpsObjectNS:
    def __init__(self, data: _DataContainer):
        self._data = data

    def camera_add(self, *args, **kwargs):
        # Create a deterministic new object
        base = "TmpObj"
        idx = 1
        name = f"{base}{idx}"
        while self._data.objects.get(name) is not None:
            idx += 1
            name = f"{base}{idx}"
        self._data.objects.new(name)
        return {"FINISHED"}


class _OpsNS:
    def __init__(self, data: _DataContainer):
        self.object = _OpsObjectNS(data)
        # Forbidden namespaces (wm, render, etc.) are not needed for this test


class _FakeBpy:
    """
    Minimal bpy stub with data-block managers and ops namespace.
    """
    def __init__(self):
        self.data = _DataContainer()
        self.ops = _OpsNS(self.data)


def test_scene_builder_cleanup_removes_new_datablocks(monkeypatch):
    # Arrange fake bpy with some pre-existing data-blocks
    fake_bpy = _FakeBpy()
    # Pre-existing entries that must remain after cleanup
    fake_bpy.data.objects.new("KeepObj")
    fake_bpy.data.materials.new("KeepMat")
    fake_bpy.data.images._add("KeepImg", _NamedBlock("KeepImg"))
    fake_bpy.data.meshes._add("KeepMesh", _NamedBlock("KeepMesh"))
    fake_bpy.data.collections._add("KeepCol", _NamedBlock("KeepCol"))
    fake_bpy.data.worlds._add("KeepWorld", _NamedBlock("KeepWorld"))

    # Monkeypatch the scene_builder module's bpy to our fake
    monkeypatch.setattr(sb_mod, "bpy", fake_bpy, raising=True)

    builder = SceneBuilder()

    # The code will create a new object and a new material, then raise to trigger cleanup
    code = """
bpy.ops.object.camera_add()
m = bpy.data.materials.new(name="TmpMat")
raise Exception("boom")
"""

    # Act
    with pytest.raises(SceneExecutionError):
        builder.execute_scene_code(
            code,
            request_id="test-cleanup",
            timeout_sec=5.0,
            dry_run_when_no_bpy=False,
            cleanup_on_failure=True,
        )

    # Assert: Newly created data-blocks are removed, pre-existing remain
    # Objects
    obj_names = set(o.name_full for o in fake_bpy.data.objects)
    assert "KeepObj" in obj_names
    assert not any(n.startswith("TmpObj") for n in obj_names)

    # Materials
    mat_names = set(getattr(m, "name", "") for m in fake_bpy.data.materials)
    assert "KeepMat" in mat_names
    assert "TmpMat" not in mat_names

    # Other data-block categories should keep pre-existing; we didn't create new ones here
    img_names = set(getattr(i, "name", "") for i in fake_bpy.data.images)
    mesh_names = set(getattr(me, "name", "") for me in fake_bpy.data.meshes)
    col_names = set(getattr(c, "name", "") for c in fake_bpy.data.collections)
    world_names = set(getattr(w, "name", "") for w in fake_bpy.data.worlds)

    assert "KeepImg" in img_names
    assert "KeepMesh" in mesh_names
    assert "KeepCol" in col_names
    assert "KeepWorld" in world_names