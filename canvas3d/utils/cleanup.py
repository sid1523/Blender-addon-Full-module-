# Shared cleanup utilities for Canvas3D
# Provide atomic build cleanup by removing only newly created datablocks after a failure.
# Used by SpecExecutor and SceneBuilder.

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def snapshot_datablocks(bpy_module) -> dict[str, set[str]]:
    """
    Snapshot existing datablock names. This allows targeted cleanup of only new items
    created during an execution attempt.

    Returns a dict mapping category -> set of names.
    Categories: collections, objects, meshes, materials, lights, cameras
    """
    snap: dict[str, set[str]] = {
        "collections": set(),
        "objects": set(),
        "meshes": set(),
        "materials": set(),
        "lights": set(),
        "cameras": set(),
    }
    try:
        data = getattr(bpy_module, "data", None)
        if data is None:
            return snap

        # Collections
        try:
            for c in getattr(data, "collections", []):
                nm = getattr(c, "name", None)
                if isinstance(nm, str):
                    snap["collections"].add(nm)
        except Exception:
            pass

        # Objects
        try:
            for o in getattr(data, "objects", []):
                nm = getattr(o, "name", None)
                if isinstance(nm, str):
                    snap["objects"].add(nm)
        except Exception:
            pass

        # Meshes
        try:
            for me in getattr(data, "meshes", []):
                nm = getattr(me, "name", None)
                if isinstance(nm, str):
                    snap["meshes"].add(nm)
        except Exception:
            pass

        # Materials
        try:
            for m in getattr(data, "materials", []):
                nm = getattr(m, "name", None)
                if isinstance(nm, str):
                    snap["materials"].add(nm)
        except Exception:
            pass

        # Lights
        try:
            for lt in getattr(data, "lights", []):
                nm = getattr(lt, "name", None)
                if isinstance(nm, str):
                    snap["lights"].add(nm)
        except Exception:
            pass

        # Cameras
        try:
            for cam in getattr(data, "cameras", []):
                nm = getattr(cam, "name", None)
                if isinstance(nm, str):
                    snap["cameras"].add(nm)
        except Exception:
            pass

    except Exception as ex:
        logger.debug(f"snapshot_datablocks: error during snapshot: {ex}")

    return snap


def _safe_remove_collection(data, col) -> None:
    try:
        if hasattr(data.collections, "remove"):
            try:
                data.collections.remove(col, do_unlink=True)
            except TypeError:
                data.collections.remove(col)
    except Exception:
        pass


def _safe_unlink_object_from_all_collections(obj) -> None:
    try:
        # Unlink object from any collections it belongs to
        for col in list(getattr(obj, "users_collection", []) or []):
            try:
                if hasattr(col, "objects") and hasattr(col.objects, "unlink"):
                    col.objects.unlink(obj)
            except Exception:
                pass
    except Exception:
        pass


def _safe_remove_object(data, obj_name: str) -> None:
    try:
        obj = data.objects.get(obj_name)
        if obj is None:
            return
        _safe_unlink_object_from_all_collections(obj)
        if hasattr(data.objects, "remove"):
            try:
                data.objects.remove(obj, do_unlink=True)
            except TypeError:
                data.objects.remove(obj)
    except Exception:
        pass


def cleanup_new_datablocks(pre_snapshot: dict[str, set[str]], temp_collection_name: str | None, bpy_module) -> None:
    """
    Remove only newly created datablocks by comparing current bpy.data against the pre-snapshot.

    Parameters:
      - pre_snapshot: result from snapshot_datablocks()
      - temp_collection_name: optional name of the temporary collection to remove
      - bpy_module: the bpy module

    Behavior:
      - If temp_collection_name provided, attempts to remove the temp collection and any objects inside it.
      - Removes objects, meshes, materials, lights, and cameras created after the snapshot.
      - Ignores errors to remain robust across Blender versions and stubbed environments.
    """
    try:
        data = getattr(bpy_module, "data", None)
        if data is None:
            return

        # Remove objects under the temp collection first (if provided)
        if isinstance(temp_collection_name, str) and temp_collection_name:
            try:
                temp_col = data.collections.get(temp_collection_name)
                if temp_col:
                    # Unlink and remove objects in the temp collection
                    try:
                        obj_names = [getattr(o, "name", None) for o in getattr(temp_col, "objects", [])]
                    except Exception:
                        obj_names = []

                    for nm in obj_names:
                        if isinstance(nm, str) and nm:
                            _safe_remove_object(data, nm)

                    # Finally remove the temp collection
                    _safe_remove_collection(data, temp_col)
            except Exception:
                pass

        # Objects: remove any created after snapshot
        try:
            pre_objs = set(pre_snapshot.get("objects", set()))
            cur_objs = set()
            for o in getattr(data, "objects", []):
                nm = getattr(o, "name", None)
                if isinstance(nm, str):
                    cur_objs.add(nm)
            for nm in (cur_objs - pre_objs):
                _safe_remove_object(data, nm)
        except Exception:
            pass

        # Meshes
        try:
            pre_meshes = set(pre_snapshot.get("meshes", set()))
            cur_meshes = set()
            for me in getattr(data, "meshes", []):
                nm = getattr(me, "name", None)
                if isinstance(nm, str):
                    cur_meshes.add(nm)
            for nm in (cur_meshes - pre_meshes):
                me = data.meshes.get(nm)
                if me and hasattr(data.meshes, "remove"):
                    try:
                        data.meshes.remove(me)
                    except Exception:
                        pass
        except Exception:
            pass

        # Materials
        try:
            pre_mats = set(pre_snapshot.get("materials", set()))
            cur_mats = set()
            for m in getattr(data, "materials", []):
                nm = getattr(m, "name", None)
                if isinstance(nm, str):
                    cur_mats.add(nm)
            for nm in (cur_mats - pre_mats):
                mat = data.materials.get(nm)
                if mat and hasattr(data.materials, "remove"):
                    try:
                        data.materials.remove(mat)
                    except Exception:
                        pass
        except Exception:
            pass

        # Lights
        try:
            pre_lights = set(pre_snapshot.get("lights", set()))
            cur_lights = set()
            for lt in getattr(data, "lights", []):
                nm = getattr(lt, "name", None)
                if isinstance(nm, str):
                    cur_lights.add(nm)
            for nm in (cur_lights - pre_lights):
                lt = data.lights.get(nm)
                if lt and hasattr(data.lights, "remove"):
                    try:
                        data.lights.remove(lt)
                    except Exception:
                        pass
        except Exception:
            pass

        # Cameras
        try:
            pre_cams = set(pre_snapshot.get("cameras", set()))
            cur_cams = set()
            for cam in getattr(data, "cameras", []):
                nm = getattr(cam, "name", None)
                if isinstance(nm, str):
                    cur_cams.add(nm)
            for nm in (cur_cams - pre_cams):
                cam_db = data.cameras.get(nm)
                if cam_db and hasattr(data.cameras, "remove"):
                    try:
                        data.cameras.remove(cam_db)
                    except Exception:
                        pass
        except Exception:
            pass

        # Collections (post): remove any collections created after snapshot, including collision collections
        try:
            pre_cols = set(pre_snapshot.get("collections", set()))
            cur_cols = set()
            for c in getattr(data, "collections", []):
                nm = getattr(c, "name", None)
                if isinstance(nm, str):
                    cur_cols.add(nm)
            for nm in (cur_cols - pre_cols):
                col = data.collections.get(nm)
                if col:
                    _safe_remove_collection(data, col)
        except Exception:
            pass

        logger.info("Canvas3D cleanup: removed newly created datablocks after failure.")
    except Exception as ex:
        logger.debug(f"cleanup_new_datablocks: encountered error during cleanup: {ex}")