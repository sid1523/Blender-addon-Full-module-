# Canvas3D Exporters: One-click export presets (glTF/FBX/USD) with optional collision mesh generation
#
# Notes:
# - Guard all bpy usage so module can import in test/CI environments without Blender.
# - Exports the last committed collection (or a named collection) out to target formats.
# - Collision meshes are generated into a sibling "{name}_Collision" collection by duplicating
#   render meshes and applying simple modifiers suitable for game engines.
#
# Limitations (MVP):
# - Collision generation uses Decimate + Triangulate as a light heuristic.
# - If a collection name is not found, functions raise RuntimeError.
# - USD export requires Blender with USD support.
#
# Public API:
# - export_collection_gltf(collection_name: str, filepath: str, generate_collisions: bool = False) -> None
# - export_collection_fbx(collection_name: str, filepath: str, generate_collisions: bool = False) -> None
# - export_collection_usd(collection_name: str, filepath: str, generate_collisions: bool = False) -> None

from __future__ import annotations
from typing import Optional

try:
    import bpy  # type: ignore
except Exception:
    bpy = None  # Allows offline import

def _get_collection(name: str):
    if bpy is None:
        raise RuntimeError("bpy not available; exporters require Blender runtime.")
    col = getattr(getattr(bpy, "data", None), "collections", None)
    if col is None:
        raise RuntimeError("bpy.data.collections unavailable")
    found = col.get(name)
    if found is None:
        raise RuntimeError(f"Collection '{name}' not found")
    return found

def _ensure_collection(name: str):
    data = getattr(bpy, "data", None)
    if data is None:
        raise RuntimeError("bpy.data unavailable")
    col = data.collections.get(name)
    if col:
        return col
    return data.collections.new(name)

def _link_object_to_collection(obj, col) -> None:
    try:
        if hasattr(col, "objects") and hasattr(col.objects, "link"):
            col.objects.link(obj)
    except Exception:
        pass

def _duplicate_object(obj):
    data = getattr(bpy, "data", None)
    if data is None:
        return None
    try:
        dup = obj.copy()
        if getattr(obj, "data", None) is not None:
            dup.data = obj.data.copy()
        return dup
    except Exception:
        return None

def _is_mesh_object(obj) -> bool:
    try:
        return getattr(obj, "type", "") == "MESH"
    except Exception:
        return False

def generate_collision_meshes(collection_name: str) -> str:
    """
    Duplicate all mesh objects in the given collection into a sibling collision collection
    and apply simple modifiers (Triangulate + Decimate). Returns the collision collection name.
    """
    if bpy is None:
        raise RuntimeError("bpy unavailable")
    src_col = _get_collection(collection_name)
    coll_name = f"{collection_name}_Collision"
    dst_col = _ensure_collection(coll_name)

    # Optionally clear existing content
    try:
        # Remove existing objects in collision collection
        for o in list(getattr(dst_col, "objects", [])):
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except TypeError:
                bpy.data.objects.remove(o)
    except Exception:
        pass

    # Duplicate mesh objects
    for obj in list(getattr(src_col, "objects", [])):
        if not _is_mesh_object(obj):
            continue
        dup = _duplicate_object(obj)
        if dup is None:
            continue
        dup.name = f"{obj.name}_COL"

        # Place into collision collection
        _link_object_to_collection(dup, dst_col)

        # Apply lightweight collision-friendly modifiers
        try:
            # Triangulate
            tri = dup.modifiers.new(name="Triangulate", type="TRIANGULATE")
            tri.keep_custom_normals = True
        except Exception:
            pass
        try:
            # Decimate (collapse) to reduce complexity; ratio conservative
            dec = dup.modifiers.new(name="Decimate", type="DECIMATE")
            dec.ratio = 0.5
            dec.use_collapse_triangulate = True
        except Exception:
            pass

        # Disable rendering flags (optional)
        try:
            dup.hide_render = True
        except Exception:
            pass

    return coll_name

def _deselect_all():
    try:
        bpy.ops.object.select_all(action='DESELECT')
    except Exception:
        pass

def _select_collection_objects(col) -> None:
    # Switch to object mode if needed
    try:
        if getattr(bpy.context, "mode", "") != "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass
    _deselect_all()
    try:
        for obj in getattr(col, "objects", []):
            try:
                obj.select_set(True)
            except Exception:
                pass
        # Set active
        if getattr(col, "objects", []) and hasattr(bpy.context, "view_layer"):
            bpy.context.view_layer.objects.active = col.objects[0]
    except Exception:
        pass

def export_collection_gltf(collection_name: str, filepath: str, generate_collisions: bool = False) -> None:
    if bpy is None:
        raise RuntimeError("bpy unavailable")
    col = _get_collection(collection_name)
    if generate_collisions:
        try:
            generate_collision_meshes(collection_name)
        except Exception:
            # Non-fatal
            pass
    _select_collection_objects(col)
    # Export active selection as glTF (embedded by default)
    try:
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format='GLB',  # single file binary
            use_selection=True,
            export_apply=True,
            export_texcoords=True,
            export_normals=True,
            export_tangents=False,
            export_materials='EXPORT',
            export_colors=True,
        )
    except Exception as ex:
        raise RuntimeError(f"glTF export failed: {ex}")

def export_collection_fbx(collection_name: str, filepath: str, generate_collisions: bool = False) -> None:
    if bpy is None:
        raise RuntimeError("bpy unavailable")
    col = _get_collection(collection_name)
    if generate_collisions:
        try:
            generate_collision_meshes(collection_name)
        except Exception:
            pass
    _select_collection_objects(col)
    try:
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_selection=True,
            apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',
            add_leaf_bones=False,
            bake_space_transform=False,
            path_mode='AUTO',
            embed_textures=False,
            use_mesh_modifiers=True,
        )
    except Exception as ex:
        raise RuntimeError(f"FBX export failed: {ex}")

def export_collection_usd(collection_name: str, filepath: str, generate_collisions: bool = False) -> None:
    if bpy is None:
        raise RuntimeError("bpy unavailable")
    col = _get_collection(collection_name)
    if generate_collisions:
        try:
            generate_collision_meshes(collection_name)
        except Exception:
            pass
    _select_collection_objects(col)
    # USD export operator name may vary depending on Blender build
    try:
        bpy.ops.wm.usd_export(
            filepath=filepath,
            selected_objects_only=True,
            export_textures=True,
            export_animation=False,
        )
    except Exception as ex:
        raise RuntimeError(f"USD export failed: {ex}")

__all__ = [
    "generate_collision_meshes",
    "export_collection_gltf",
    "export_collection_fbx",
    "export_collection_usd",
]