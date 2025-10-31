# Canvas3D Material Library: CC0 PBR loader with principled fallbacks
#
# Purpose:
# - Provide a small material utility that creates Principled BSDF materials
#   using CC0-style PBR texture sets when available in the user's config directory.
# - Fallback to procedurally-set Principled parameters from spec when textures are absent.
#
# Conventions:
# - Texture directory layout under config:
#     {config_dir}/materials/{material_name}/
#         basecolor.(png|jpg)
#         metallic.(png|jpg)
#         roughness.(png|jpg)
#         normal.(png|jpg)
# - Material naming uses the spec-provided "name". ASCII-safe recommended.
#
# API:
# - ensure_pbr_material(name: str, pbr: dict | None) -> bpy.types.Material | None
#   Creates or returns an existing material with node setup (textures if found).
#
# Notes:
# - All bpy usage is guarded; the module can import without Blender.
# - This library does not ship textures; place CC0 textures into the config directory
#   as per conventions to enable automatic mapping.

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import os

try:
    import bpy  # type: ignore
except Exception:
    bpy = None

from .blender_helpers import get_config_dir

_SUPPORTED_EXTS = (".png", ".jpg", ".jpeg")

def _material_dir(name: str) -> str:
    base = get_config_dir()
    return os.path.join(base, "materials", str(name))

def _find_tex(path_dir: str, basename: str) -> Optional[str]:
    for ext in _SUPPORTED_EXTS:
        fp = os.path.join(path_dir, basename + ext)
        if os.path.isfile(fp):
            return fp
    return None

def _load_image(filepath: str):
    if bpy is None:
        return None
    try:
        return bpy.data.images.load(filepath)
    except Exception:
        # Try to reuse if already loaded
        try:
            for img in getattr(getattr(bpy, "data", None), "images", []):
                if getattr(img, "filepath", "") == filepath:
                    return img
        except Exception:
            pass
    return None

def _get_or_create_material(name: str):
    if bpy is None:
        return None
    data = getattr(bpy, "data", None)
    if data is None:
        return None
    mat = data.materials.get(name)
    if mat:
        # Ensure nodes enabled
        try:
            mat.use_nodes = True
        except Exception:
            pass
        return mat
    try:
        mat = data.materials.new(name=name)
        mat.use_nodes = True
        return mat
    except Exception:
        return None

def _get_bsdf(mat):
    try:
        nt = mat.node_tree
        if nt is None:
            return None
        for n in nt.nodes:
            if n.bl_idname == "ShaderNodeBsdfPrincipled" or n.name == "Principled BSDF":
                return n
        # Create one if missing
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        # Ensure output exists and link
        out = None
        for n in nt.nodes:
            if n.bl_idname == "ShaderNodeOutputMaterial":
                out = n
                break
        if out is None:
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            out.location = (200, 0)
        try:
            nt.links.new(bsdf.outputs.get("BSDF"), out.inputs.get("Surface"))
        except Exception:
            pass
        return bsdf
    except Exception:
        return None

def _set_bsdf_fallback(bsdf, pbr: Optional[Dict[str, Any]]) -> None:
    if bsdf is None:
        return
    # Defaults
    base = (0.8, 0.8, 0.8, 1.0)
    metallic = 0.0
    rough = 0.5
    if isinstance(pbr, dict):
        bc = pbr.get("base_color")
        if isinstance(bc, list) and len(bc) == 3:
            try:
                base = (float(bc[0]), float(bc[1]), float(bc[2]), 1.0)
            except Exception:
                pass
        m = pbr.get("metallic")
        if isinstance(m, (int, float)):
            metallic = float(m)
        r = pbr.get("roughness")
        if isinstance(r, (int, float)):
            rough = float(r)
    try:
        bsdf.inputs["Base Color"].default_value = base
    except Exception:
        pass
    try:
        bsdf.inputs["Metallic"].default_value = metallic
    except Exception:
        pass
    try:
        bsdf.inputs["Roughness"].default_value = rough
    except Exception:
        pass

def _create_tex_node(nt, image, label: str, loc: Tuple[int, int]):
    try:
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = image
        node.label = label
        node.location = loc
        return node
    except Exception:
        return None

def ensure_pbr_material(name: str, pbr: Optional[Dict[str, Any]] = None):
    """
    Ensure a material exists with Principled BSDF nodes and CC0 PBR textures if found.
    Returns the material or None when bpy isn't available.
    """
    mat = _get_or_create_material(name)
    if mat is None or getattr(mat, "node_tree", None) is None:
        return mat

    nt = mat.node_tree
    bsdf = _get_bsdf(mat)
    # Apply fallback values first
    _set_bsdf_fallback(bsdf, pbr)

    # Attempt texture binding
    mdir = _material_dir(name)
    if not os.path.isdir(mdir):
        return mat  # fallback only

    base_fp = _find_tex(mdir, "basecolor")
    met_fp = _find_tex(mdir, "metallic")
    rough_fp = _find_tex(mdir, "roughness")
    norm_fp = _find_tex(mdir, "normal")

    base_img = _load_image(base_fp) if base_fp else None
    met_img = _load_image(met_fp) if met_fp else None
    rough_img = _load_image(rough_fp) if rough_fp else None
    norm_img = _load_image(norm_fp) if norm_fp else None

    # Create and link nodes
    if base_img:
        tex_base = _create_tex_node(nt, base_img, "BaseColor", (-400, 0))
        try:
            nt.links.new(tex_base.outputs.get("Color"), bsdf.inputs.get("Base Color"))
        except Exception:
            pass
    if met_img:
        tex_met = _create_tex_node(nt, met_img, "Metallic", (-400, -150))
        try:
            nt.links.new(tex_met.outputs.get("Color"), bsdf.inputs.get("Metallic"))
        except Exception:
            pass
    if rough_img:
        tex_rough = _create_tex_node(nt, rough_img, "Roughness", (-400, -300))
        try:
            nt.links.new(tex_rough.outputs.get("Color"), bsdf.inputs.get("Roughness"))
        except Exception:
            pass
    if norm_img:
        # Normal map requires a normal map node
        try:
            nmap = nt.nodes.new("ShaderNodeNormalMap")
            nmap.location = (-200, -450)
            tex_norm = _create_tex_node(nt, norm_img, "Normal", (-400, -450))
            if tex_norm and nmap:
                nt.links.new(tex_norm.outputs.get("Color"), nmap.inputs.get("Color"))
                nt.links.new(nmap.outputs.get("Normal"), bsdf.inputs.get("Normal"))
        except Exception:
            pass

    return mat

__all__ = ["ensure_pbr_material"]