# Canvas3D UI operators

import json
import logging

import bpy
from bpy_extras.io_utils import ImportHelper

from ..core.orchestrator import get_orchestrator
from ..utils.blender_helpers import append_history, read_history
from ..utils.enhancements import generate_heuristic_enhancements, summarize_variant
from ..utils.exporters import export_collection_fbx, export_collection_gltf, export_collection_usd

logger = logging.getLogger(__name__)

# Generate Scene operator
class CANVAS3D_OT_GenerateScene(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.generate_scene"
    bl_label = "Generate Scene"
    bl_description = "Generate a 3D scene from the prompt using AI"

    def execute(self, context: object) -> set[str]:
        # Get prompt from scene property
        prompt = context.scene.canvas3d_prompt.strip()
        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt first.")
            return {'CANCELLED'}

        # Initialize status
        context.scene.canvas3d_status = "Initializing..."

        # Non-blocking generation via orchestrator
        try:
            orchestrator = get_orchestrator()
            request_id = orchestrator.start_generate_scene(prompt, context)
            self.report({'INFO'}, f"Scene generation started (request {request_id}). Progress will appear in the status panel.")
            # Return immediately to keep UI responsive
            return {'FINISHED'}
        except Exception as e:
            context.scene.canvas3d_status = f"Error: {str(e)}"
            self.report({'ERROR'}, f"Generation failed to start: {str(e)}")
            return {'CANCELLED'}

# Load Scene Spec operator
class CANVAS3D_OT_LoadSpec(bpy.types.Operator, ImportHelper):  # noqa: N801
    bl_idname = "canvas3d.load_spec"
    bl_label = "Load Scene Spec"
    bl_description = "Load a JSON scene spec exported from front-end and build in Blender"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context: object) -> set[str]:
        import json

        from ..core.orchestrator import get_orchestrator

        try:
            with open(self.filepath, encoding='utf-8') as f:
                spec = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read JSON spec: {e}")
            return {'CANCELLED'}

        orchestrator = get_orchestrator()
        request_id = orchestrator.start_load_spec(spec, context)
        self.report({'INFO'}, f"Loading spec started (request {request_id}). See status panel.")
        return {'FINISHED'}

# Variants: Generate 15–20 options
class CANVAS3D_OT_GenerateVariants(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.generate_variants"
    bl_label = "Generate Variants"
    bl_description = "Generate 15–20 high-quality scene variants from the prompt and controls"

    def execute(self, context: object) -> set[str]:  # noqa: C901
        # Gather prompt and controls from scene properties
        prompt = (getattr(context.scene, "canvas3d_prompt", "") or "").strip()
        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt first.")
            return {'CANCELLED'}

        # Controls (Enum/String props defined in panels register())
        controls = {
            "domain": getattr(context.scene, "canvas3d_domain", "procedural_dungeon"),
            "size_scale": getattr(context.scene, "canvas3d_size_scale", "medium"),
            "complexity_density": getattr(context.scene, "canvas3d_complexity_density", "balanced"),
            "layout_style": getattr(context.scene, "canvas3d_layout_style", "branching"),
            "mood_lighting": getattr(context.scene, "canvas3d_mood_lighting", "neutral"),
            "materials_palette": getattr(context.scene, "canvas3d_materials_palette", "stone_wood"),
            "camera_style": getattr(context.scene, "canvas3d_camera_style", "cinematic_static"),
        }

        # Non-blocking generation via orchestrator singleton
        try:
            orchestrator = get_orchestrator()
            request_id = orchestrator.start_generate_variants(prompt, controls, context)
            # Store current request in scene properties for selection flow
            try:
                context.scene.canvas3d_selected_request = request_id
                # Reset selected index
                context.scene.canvas3d_selected_variant_index = 0
                # Clear variants list UI
                coll = getattr(context.scene, "canvas3d_variants", None)
                if coll is not None and hasattr(coll, "clear"):
                    coll.clear()
                    context.scene.canvas3d_variants_index = 0
            except Exception as ex:
                logger.debug(f"Variants UI reset failed: {ex}")

            # Auto-refresh variants list when bundle becomes ready (poll every 0.5s and stop after loading)
            try:
                import bpy as _bpy
                if hasattr(_bpy, "app") and hasattr(_bpy.app, "timers"):
                    scn = context.scene
                    def _refresh_variants() -> float | None:
                        try:
                            orchestrator_local = get_orchestrator()
                            variants_local = orchestrator_local.get_variants_snapshot(request_id)
                            if variants_local:
                                coll_local = getattr(scn, "canvas3d_variants", None)
                                if coll_local is not None and hasattr(coll_local, "clear"):
                                    coll_local.clear()
                                    for idx, spec in enumerate(variants_local):
                                        item = coll_local.add()
                                        item.index = idx
                                        try:
                                            item.summary = summarize_variant(spec)
                                        except Exception:
                                            item.summary = f"Variant {idx}"
                                    scn.canvas3d_variants_index = 0
                                    scn.canvas3d_selected_variant_index = 0
                                return None  # stop timer after loading
                        except Exception as ex:
                            logger.debug(f"Variants auto-refresh poll failed: {ex}")
                        return 0.5  # keep polling until ready
                    _bpy.app.timers.register(_refresh_variants, first_interval=0.5)
            except Exception as ex:
                logger.debug(f"Variants auto-refresh scheduling failed: {ex}")

            self.report({'INFO'}, f"Variants generation started (request {request_id}). Status will update in the panel.")
            return {'FINISHED'}
        except Exception as e:
            try:
                context.scene.canvas3d_status = f"Error: {str(e)}"
            except Exception as ex:
                logger.debug(f"Variants start: status set failed: {ex}")
            self.report({'ERROR'}, f"Variants generation failed to start: {str(e)}")
            return {'CANCELLED'}


# Variants: Select one and execute deterministically
class CANVAS3D_OT_SelectVariant(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.select_variant"
    bl_label = "Select Variant"
    bl_description = "Execute the selected variant deterministically and persist selection to history"

    def execute(self, context: object) -> set[str]:
        # Acquire request id and selected index from scene properties
        request_id = getattr(context.scene, "canvas3d_selected_request", "") or ""
        if not request_id:
            self.report({'WARNING'}, "No active variants request. Generate variants first.")
            return {'CANCELLED'}
        # Prefer UI list active index if available; fallback to numeric property
        try:
            index = int(getattr(context.scene, "canvas3d_variants_index", getattr(context.scene, "canvas3d_selected_variant_index", 0)))
        except Exception:
            try:
                index = int(getattr(context.scene, "canvas3d_selected_variant_index", 0))
            except Exception:
                index = 0
        try:
            orchestrator = get_orchestrator()
            ok = orchestrator.select_and_execute_variant(request_id, index, context)
            if ok:
                self.report({'INFO'}, f"Variant {index} executed for request {request_id}.")
                return {'FINISHED'}
            self.report({'WARNING'}, "Variant selection failed. Check status.")
            return {'CANCELLED'}
        except Exception as e:
            try:
                context.scene.canvas3d_status = f"Error: {str(e)}"
            except Exception as ex:
                logger.debug(f"SelectVariant: status set failed: {ex}")
            self.report({'ERROR'}, f"Variant execution failed: {str(e)}")
            return {'CANCELLED'}


# Heuristic enhancements operator
class CANVAS3D_OT_ApplyEnhancements(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.apply_enhancements"
    bl_label = "Apply Enhancements"
    bl_description = "Generate heuristic enhancement suggestions for the selected variant and store them in history"

    def execute(self, context: object) -> set[str]:
        # Acquire request id and selected index from scene properties
        request_id = getattr(context.scene, "canvas3d_selected_request", "") or ""
        if not request_id:
            self.report({'WARNING'}, "No active variants request. Generate variants first.")
            return {'CANCELLED'}
        try:
            index = int(getattr(context.scene, "canvas3d_selected_variant_index", 0))
        except Exception:
            index = 0

        # Controls (Enum/String props defined in panels register())
        controls = {
            "domain": getattr(context.scene, "canvas3d_domain", "procedural_dungeon"),
            "size_scale": getattr(context.scene, "canvas3d_size_scale", "medium"),
            "complexity_density": getattr(context.scene, "canvas3d_complexity_density", "balanced"),
            "layout_style": getattr(context.scene, "canvas3d_layout_style", "branching"),
            "mood_lighting": getattr(context.scene, "canvas3d_mood_lighting", "neutral"),
            "materials_palette": getattr(context.scene, "canvas3d_materials_palette", "stone_wood"),
            "camera_style": getattr(context.scene, "canvas3d_camera_style", "cinematic_static"),
        }

        try:
            orchestrator = get_orchestrator()
            spec = orchestrator.get_variant_spec(request_id, index)
            if not spec:
                self.report({'WARNING'}, "Selected variant not available. Generate variants again.")
                return {'CANCELLED'}

            suggestions = generate_heuristic_enhancements(spec, controls)
            # Store to scene property for display
            try:
                context.scene.canvas3d_last_enhancements = "\n".join(suggestions)
            except Exception as ex:
                logger.debug(f"ApplyEnhancements: set last enhancements failed: {ex}")

            # Persist to history
            try:
                append_history({
                    "type": "enhancements_heuristics",
                    "request_id": request_id,
                    "index": index,
                    "count": len(suggestions),
                    "controls": controls,
                })
            except Exception as ex:
                logger.debug(f"ApplyEnhancements: append_history failed: {ex}")

            self.report({'INFO'}, f"Generated {len(suggestions)} heuristic suggestions.")
            return {'FINISHED'}
        except Exception as e:
            try:
                context.scene.canvas3d_status = f"Error: {str(e)}"
            except Exception as ex:
                logger.debug(f"ApplyEnhancements: status set failed: {ex}")
            self.report({'ERROR'}, f"Heuristic enhancements failed: {str(e)}")
            return {'CANCELLED'}


# Provider 'More Ideas' operator
class CANVAS3D_OT_MoreIdeas(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.more_ideas"
    bl_label = "More Ideas"
    bl_description = "Request additional enhancement suggestions from the provider for the selected variant"

    def execute(self, context: object) -> set[str]:
        request_id = getattr(context.scene, "canvas3d_selected_request", "") or ""
        if not request_id:
            self.report({'WARNING'}, "No active variants request. Generate variants first.")
            return {'CANCELLED'}
        try:
            index = int(getattr(context.scene, "canvas3d_selected_variant_index", 0))
        except Exception:
            index = 0

        prompt = (getattr(context.scene, "canvas3d_prompt", "") or "").strip()
        if not prompt:
            self.report({'WARNING'}, "Please enter a prompt first.")
            return {'CANCELLED'}

        controls = {
            "domain": getattr(context.scene, "canvas3d_domain", "procedural_dungeon"),
            "size_scale": getattr(context.scene, "canvas3d_size_scale", "medium"),
            "complexity_density": getattr(context.scene, "canvas3d_complexity_density", "balanced"),
            "layout_style": getattr(context.scene, "canvas3d_layout_style", "branching"),
            "mood_lighting": getattr(context.scene, "canvas3d_mood_lighting", "neutral"),
            "materials_palette": getattr(context.scene, "canvas3d_materials_palette", "stone_wood"),
            "camera_style": getattr(context.scene, "canvas3d_camera_style", "cinematic_static"),
        }

        try:
            orchestrator = get_orchestrator()
            spec = orchestrator.get_variant_spec(request_id, index)
            if not spec:
                self.report({'WARNING'}, "Selected variant not available. Generate variants again.")
                return {'CANCELLED'}

            ideas = orchestrator.llm.get_enhancement_ideas(
                prompt=prompt,
                selected_spec=spec,
                controls=controls,
                request_id=request_id,
                count=12,
            )
            # Store to scene property for display
            try:
                context.scene.canvas3d_last_enhancements = "\n".join(ideas)
            except Exception as ex:
                logger.debug(f"MoreIdeas: set last enhancements failed: {ex}")

            # Persist to history
            try:
                append_history({
                    "type": "enhancements_provider",
                    "request_id": request_id,
                    "index": index,
                    "count": len(ideas),
                    "controls": controls,
                })
            except Exception as ex:
                logger.debug(f"MoreIdeas: append_history failed: {ex}")

            self.report({'INFO'}, f"Received {len(ideas)} provider ideas.")
            return {'FINISHED'}
        except Exception as e:
            try:
                context.scene.canvas3d_status = f"Error: {str(e)}"
            except Exception as ex:
                logger.debug(f"MoreIdeas: status set failed: {ex}")
            self.report({'ERROR'}, f"Provider ideas failed: {str(e)}")
            return {'CANCELLED'}


# Variants refresh operator
class CANVAS3D_OT_RefreshVariantsList(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.refresh_variants_list"
    bl_label = "Refresh Variants"
    bl_description = "Refresh the variants list with human-readable summaries for the current request"

    def execute(self, context: object) -> set[str]:
        request_id = getattr(context.scene, "canvas3d_selected_request", "") or ""
        if not request_id:
            self.report({'WARNING'}, "No active variants request. Generate variants first.")
            return {'CANCELLED'}

        try:
            orchestrator = get_orchestrator()
            variants = orchestrator.get_variants_snapshot(request_id)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to retrieve variants: {str(e)}")
            return {'CANCELLED'}

        # Populate the collection property with summaries
        try:
            coll = getattr(context.scene, "canvas3d_variants", None)
            if coll is not None and hasattr(coll, "clear"):
                coll.clear()
                for idx, spec in enumerate(variants):
                    item = coll.add()
                    item.index = idx
                    try:
                        item.summary = summarize_variant(spec)
                    except Exception:
                        item.summary = f"Variant {idx}"
                # Sync UI list index into selected variant index
                idx_active = int(getattr(context.scene, "canvas3d_variants_index", 0))
                context.scene.canvas3d_selected_variant_index = idx_active
        except Exception as ex:
            logger.debug(f"RefreshVariantsList: populate UI failed: {ex}")

        self.report({'INFO'}, f"Loaded {len(variants)} variants.")
        return {'FINISHED'}

# Variants: Clear bundles operator
class CANVAS3D_OT_ClearVariants(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.clear_variants"
    bl_label = "Clear Variants"
    bl_description = "Clear stored variants for the current request id. If none set, clears all bundles."

    def execute(self, context: object) -> set[str]:
        try:
            orchestrator = get_orchestrator()
            rid = str(getattr(context.scene, "canvas3d_selected_request", "") or "")
            if rid:
                _ = orchestrator.clear_variants(rid)
                self.report({'INFO'}, f"Cleared variants for request {rid}.")
            else:
                count = orchestrator.clear_variants(None)
                self.report({'INFO'}, f"Cleared {count} variants bundles.")
            # Clear UI list and reset indices
            try:
                coll = getattr(context.scene, "canvas3d_variants", None)
                if coll is not None and hasattr(coll, "clear"):
                    coll.clear()
                    context.scene.canvas3d_variants_index = 0
                    context.scene.canvas3d_selected_variant_index = 0
            except Exception as ex:
                logger.debug(f"ClearVariants: clear UI list failed: {ex}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Clear variants failed: {str(e)}")
            return {'CANCELLED'}

# Registration
def register() -> None:
    bpy.utils.register_class(CANVAS3D_OT_GenerateScene)
    bpy.utils.register_class(CANVAS3D_OT_LoadSpec)
    bpy.utils.register_class(CANVAS3D_OT_GenerateVariants)
    bpy.utils.register_class(CANVAS3D_OT_SelectVariant)
    bpy.utils.register_class(CANVAS3D_OT_ApplyEnhancements)
    bpy.utils.register_class(CANVAS3D_OT_MoreIdeas)
    bpy.utils.register_class(CANVAS3D_OT_RefreshVariantsList)
    bpy.utils.register_class(CANVAS3D_OT_ClearVariants)
    # Local Iteration, History, and Export operators
    bpy.utils.register_class(CANVAS3D_OT_LoadOverridesFromSelection)
    bpy.utils.register_class(CANVAS3D_OT_RegenerateLocal)
    bpy.utils.register_class(CANVAS3D_OT_HistoryRefresh)
    bpy.utils.register_class(CANVAS3D_OT_HistoryRevert)
    bpy.utils.register_class(CANVAS3D_OT_ExportLastScene)

def unregister() -> None:
    bpy.utils.unregister_class(CANVAS3D_OT_ExportLastScene)
    bpy.utils.unregister_class(CANVAS3D_OT_HistoryRevert)
    bpy.utils.unregister_class(CANVAS3D_OT_HistoryRefresh)
    bpy.utils.unregister_class(CANVAS3D_OT_RegenerateLocal)
    bpy.utils.unregister_class(CANVAS3D_OT_LoadOverridesFromSelection)
    bpy.utils.unregister_class(CANVAS3D_OT_ClearVariants)
    bpy.utils.unregister_class(CANVAS3D_OT_RefreshVariantsList)
    bpy.utils.unregister_class(CANVAS3D_OT_MoreIdeas)
    bpy.utils.unregister_class(CANVAS3D_OT_ApplyEnhancements)
    bpy.utils.unregister_class(CANVAS3D_OT_SelectVariant)
    bpy.utils.unregister_class(CANVAS3D_OT_GenerateVariants)
    bpy.utils.unregister_class(CANVAS3D_OT_LoadSpec)
    bpy.utils.unregister_class(CANVAS3D_OT_GenerateScene)
# --- Local Iteration, History, and Export Operators ---



def _clone_spec(spec: dict) -> dict:
    try:
        return json.loads(json.dumps(spec))
    except Exception:
        return dict(spec)

def _apply_local_overrides(spec: dict, scene: object) -> dict:  # noqa: C901
    """
    Apply local override properties from the scene onto a cloned spec.
    This avoids another LLM call and enables rapid iteration.
    """
    out = _clone_spec(spec)

    # Camera FOV override
    try:
        fov = float(getattr(scene, "canvas3d_edit_fov_deg", 0.0) or 0.0)
        if fov > 0:
            cam = out.get("camera", {}) or {}
            cam["fov_deg"] = fov
            out["camera"] = cam
    except Exception as ex:
        logger.debug(f"_apply_local_overrides: camera override failed: {ex}")

    # Lighting intensity scale
    try:
        scale = float(getattr(scene, "canvas3d_edit_light_intensity_scale", 1.0) or 1.0)
        if scale != 1.0 and isinstance(out.get("lighting"), list):
            new_lights = []
            for light in out.get("lighting", []) or []:
                if isinstance(light, dict):
                    try:
                        val = float(light.get("intensity", 0.0))
                        light["intensity"] = max(0.0, val * scale)
                    except Exception as ex:
                        logger.debug(f"_apply_local_overrides: lighting overrides failed: {ex}")
                new_lights.append(light)
            out["lighting"] = new_lights
    except Exception as ex:
        logger.debug(f"_apply_local_overrides: light intensity adjust failed: {ex}")

    # Materials roughness/metallic overrides (global nudges)
    try:
        r_ovr = getattr(scene, "canvas3d_edit_material_roughness", None)
        m_ovr = getattr(scene, "canvas3d_edit_material_metallic", None)
        mats = out.get("materials", []) or []
        if mats and (r_ovr is not None or m_ovr is not None):
            new_mats = []
            for m in mats:
                if not isinstance(m, dict):
                    new_mats.append(m)
                    continue
                pbr = m.get("pbr", {}) or {}
                if isinstance(r_ovr, (int, float)):
                    try:
                        pbr["roughness"] = float(r_ovr)
                    except Exception as ex:
                        logger.debug(f"_apply_local_overrides: roughness override failed: {ex}")
                if isinstance(m_ovr, (int, float)):
                    try:
                        pbr["metallic"] = float(m_ovr)
                    except Exception as ex:
                        logger.debug(f"_apply_local_overrides: metallic override failed: {ex}")
                m["pbr"] = pbr
                new_mats.append(m)
            out["materials"] = new_mats
    except Exception as ex:
        logger.debug(f"_apply_local_overrides: materials overrides failed: {ex}")

    # Density (increase/decrease) simple heuristic:
    # - For procedural_dungeon: adjust corridor length_cells +/- 1 and duplicate/trim small props
    try:
        density = str(getattr(scene, "canvas3d_edit_density", "unchanged") or "unchanged").lower()
        domain = str(out.get("domain", "procedural_dungeon"))
        if density in {"increase", "decrease"} and isinstance(out.get("objects"), list):
            objs = out.get("objects", []) or []
            new_objs = []
            for o in objs:
                if not isinstance(o, dict):
                    new_objs.append(o)
                    continue
                t = str(o.get("type", "")).lower()
                props = o.get("properties", {}) or {}
                if domain == "procedural_dungeon":
                    if t == "corridor_segment":
                        try:
                            length_cells = int(props.get("length_cells", 1))
                            props["length_cells"] = max(1, (length_cells + (1 if density == "increase" else -1)))
                            o["properties"] = props
                        except Exception as ex:
                            logger.debug(f"_apply_local_overrides: corridor length adjust failed: {ex}")
                    elif t == "prop_instance" and density == "increase":
                        # duplicate a few small props with slight offsets (soft heuristic)
                        new_objs.append(o)
                        try:
                            dup = _clone_spec(o)
                            pos = list(dup.get("position", [0.0, 0.0, 0.0]))
                            if isinstance(pos, list) and len(pos) == 3:
                                pos[0] = float(pos[0]) + 0.5
                                pos[1] = float(pos[1]) + 0.2
                                dup["position"] = pos
                            dup["id"] = str(dup.get("id", "prop")) + "_dup"
                            new_objs.append(dup)
                            continue
                        except Exception as ex:
                            logger.debug(f"_apply_local_overrides: prop duplicate heuristic failed: {ex}")
                new_objs.append(o)
            # For decrease: trim last few prop_instance entries
            if density == "decrease":
                trimmed = []
                removed = 0
                for o in new_objs:
                    if removed < 2 and isinstance(o, dict) and str(o.get("type", "")).lower() == "prop_instance":
                        removed += 1
                        continue
                    trimmed.append(o)
                new_objs = trimmed
            out["objects"] = new_objs
    except Exception as ex:
        logger.debug(f"_apply_local_overrides: density heuristic failed: {ex}")

    return out

class CANVAS3D_OT_LoadOverridesFromSelection(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.load_overrides"
    bl_label = "Load Overrides from Selection"
    bl_description = "Load baseline values from the selected variant into the local overrides"

    def execute(self, context: object) -> set[str]:  # noqa: C901
        request_id = getattr(context.scene, "canvas3d_selected_request", "") or ""
        if not request_id:
            self.report({'WARNING'}, "No active variants request.")
            return {'CANCELLED'}
        try:
            idx = int(getattr(context.scene, "canvas3d_selected_variant_index", 0))
        except Exception:
            idx = 0
        try:
            orchestrator = get_orchestrator()
            spec = orchestrator.get_variant_spec(request_id, idx)
            if not spec:
                self.report({'WARNING'}, "Selected variant not available.")
                return {'CANCELLED'}

            # Load approximate baseline overrides from spec
            try:
                cam = spec.get("camera", {}) or {}
                fov = float(cam.get("fov_deg", 60.0))
                context.scene.canvas3d_edit_fov_deg = fov
            except Exception as ex:
                logger.debug(f"LoadOverridesFromSelection: camera baseline failed: {ex}")
            try:
                lights = spec.get("lighting", []) or []
                if lights:
                    avg = 0.0
                    cnt = 0
                    for light in lights:
                        try:
                            avg += float(light.get("intensity", 0.0))
                            cnt += 1
                        except Exception as ex:
                            logger.debug(f"LoadOverridesFromSelection: intensity accumulation failed: {ex}")
                    if cnt > 0 and avg > 0.0:
                        # Set scale to 1.0 baseline; user can change
                        context.scene.canvas3d_edit_light_intensity_scale = 1.0
            except Exception as ex:
                logger.debug(f"LoadOverridesFromSelection: light scale set failed: {ex}")
            try:
                mats = spec.get("materials", []) or []
                if mats:
                    pbr = mats[0].get("pbr", {}) or {}
                    r = float(pbr.get("roughness", 0.5))
                    m = float(pbr.get("metallic", 0.0))
                    context.scene.canvas3d_edit_material_roughness = r
                    context.scene.canvas3d_edit_material_metallic = m
            except Exception as ex:
                logger.debug(f"LoadOverridesFromSelection: material baseline failed: {ex}")
            self.report({'INFO'}, "Overrides loaded from selection.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Load overrides failed: {str(e)}")
            return {'CANCELLED'}

class CANVAS3D_OT_RegenerateLocal(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.regenerate_local"
    bl_label = "Regenerate Locally"
    bl_description = "Regenerate the scene locally with overrides, without calling the LLM"

    def execute(self, context: object) -> set[str]:
        request_id = getattr(context.scene, "canvas3d_selected_request", "") or ""
        try:
            idx = int(getattr(context.scene, "canvas3d_selected_variant_index", 0))
        except Exception:
            idx = 0
        orchestrator = get_orchestrator()
        spec = None
        try:
            spec = orchestrator.get_variant_spec(request_id, idx)
        except Exception:
            spec = None
        if not spec:
            self.report({'WARNING'}, "No selected variant. Generate variants and select one first.")
            return {'CANCELLED'}
        try:
            local_spec = _apply_local_overrides(spec, context.scene)
            ok = orchestrator.execute_spec(local_spec, context, label="local_regen")
            if ok:
                self.report({'INFO'}, "Local regeneration complete.")
                return {'FINISHED'}
            self.report({'WARNING'}, "Local regeneration failed.")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Local regeneration error: {str(e)}")
            return {'CANCELLED'}

class CANVAS3D_OT_HistoryRefresh(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.history_refresh"
    bl_label = "Refresh History"
    bl_description = "Load recent generation history entries for comparison/revert"

    def execute(self, context: object) -> set[str]:
        try:
            entries = read_history(limit=50)
        except Exception as e:
            self.report({'ERROR'}, f"History read failed: {str(e)}")
            return {'CANCELLED'}
        # Populate scene collection canvas3d_history if available
        try:
            coll = getattr(context.scene, "canvas3d_history", None)
            if coll is not None and hasattr(coll, "clear"):
                coll.clear()
                for i, e in enumerate(entries):
                    item = coll.add()
                    item.index = i
                    # Minimal summary
                    typ = str(e.get("type", ""))
                    dom = str((e.get("spec", {}) or {}).get("domain", ""))
                    cnt = e.get("count", None)
                    idx = e.get("index", None)
                    req = str(e.get("request_id", "") or "")
                    summary = typ
                    if dom:
                        summary += f" | {dom}"
                    if isinstance(cnt, int):
                        summary += f" | count={cnt}"
                    if isinstance(idx, int):
                        summary += f" | index={idx}"
                    if req:
                        summary += f" | {req}"
                    item.summary = summary
            self.report({'INFO'}, "History loaded.")
            return {'FINISHED'}
        except Exception:
            # Non-fatal: still succeed
            self.report({'INFO'}, "History loaded (no UI list available).")
            return {'FINISHED'}

class CANVAS3D_OT_HistoryRevert(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.history_revert"
    bl_label = "Revert to History Entry"
    bl_description = "Execute a stored spec from history for comparison/revert"

    def execute(self, context: object) -> set[str]:
        try:
            entries = read_history(limit=200)
        except Exception as e:
            self.report({'ERROR'}, f"History read failed: {str(e)}")
            return {'CANCELLED'}
        idx = 0
        try:
            idx = int(getattr(context.scene, "canvas3d_history_index", 0))
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(entries):
            self.report({'WARNING'}, "Invalid history index.")
            return {'CANCELLED'}
        entry = entries[idx]
        spec = entry.get("spec")
        if not isinstance(spec, dict):
            self.report({'WARNING'}, "Selected history entry has no spec.")
            return {'CANCELLED'}
        try:
            orchestrator = get_orchestrator()
            ok = orchestrator.execute_spec(_clone_spec(spec), context, label="history_revert")
            if ok:
                self.report({'INFO'}, "Reverted to history entry.")
                return {'FINISHED'}
            self.report({'WARNING'}, "History revert failed.")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"History revert error: {str(e)}")
            return {'CANCELLED'}

class CANVAS3D_OT_ExportLastScene(bpy.types.Operator):  # noqa: N801
    bl_idname = "canvas3d.export_last_scene"
    bl_label = "Export Last Scene"
    bl_description = "Export the last committed scene collection to glTF/FBX/USD with optional collisions"

    def execute(self, context: object) -> set[str]:
        # Resolve last committed collection name
        try:
            col = str(getattr(context.scene, "canvas3d_last_collection", "") or "")
            if not col:
                col = str(context.scene.get("canvas3d_last_collection", "") or "")
        except Exception:
            col = ""
        if not col:
            self.report({'WARNING'}, "No last committed collection found. Generate a scene first.")
            return {'CANCELLED'}

        fmt = str(getattr(context.scene, "canvas3d_export_format", "gltf") or "gltf").lower()
        path = str(getattr(context.scene, "canvas3d_export_path", "") or "")
        collisions = bool(getattr(context.scene, "canvas3d_export_collision", False))

        if not path:
            self.report({'WARNING'}, "Please set an export file path.")
            return {'CANCELLED'}

        try:
            if fmt == "gltf":
                export_collection_gltf(col, path, generate_collisions=collisions)
            elif fmt == "fbx":
                export_collection_fbx(col, path, generate_collisions=collisions)
            elif fmt == "usd":
                export_collection_usd(col, path, generate_collisions=collisions)
            else:
                self.report({'WARNING'}, f"Unsupported format: {fmt}")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {col} to {path} ({fmt}).")
        return {'FINISHED'}
