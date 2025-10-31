# Canvas3D Enhancements utilities
# Deterministic summaries and heuristic enhancement prompts for director-friendly iteration.

from __future__ import annotations

from typing import Any


def _safe_get(d: dict[str, Any], key: str, default=None):
    try:
        return d.get(key, default)
    except Exception:
        return default

def _count_objects_by_type(spec: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        for o in spec.get("objects", []) or []:
            t = str((o or {}).get("type", "unknown")).lower()
            counts[t] = counts.get(t, 0) + 1
    except Exception:
        pass
    return counts

def summarize_variant(spec: dict[str, Any]) -> str:
    """
    Produce a compact, human-readable summary for a variant to show in the UI list.
    """
    domain = str(_safe_get(spec, "domain", "unknown"))
    grid = spec.get("grid")
    grid_s = ""
    try:
        if isinstance(grid, dict):
            dims = grid.get("dimensions", {}) or {}
            cols = dims.get("cols")
            rows = dims.get("rows")
            if isinstance(cols, int) and isinstance(rows, int):
                grid_s = f"grid:{cols}x{rows}"
    except Exception:
        pass
    counts = _count_objects_by_type(spec)
    # craft counts string with common types first
    order = ["room", "corridor_segment", "door", "stair", "prop_instance", "cube", "plane", "cylinder"]
    parts: list[str] = []
    for k in order:
        if k in counts:
            parts.append(f"{k}:{counts[k]}")
    # add any other types
    for k, v in counts.items():
        if k not in order:
            parts.append(f"{k}:{v}")
    objs_total = sum(counts.values())
    objs_s = f"objs:{objs_total}" + (f" ({', '.join(parts)})" if parts else "")
    # lighting
    try:
        lights = spec.get("lighting", []) or []
        lights_s = f"lights:{len(lights)}"
    except Exception:
        lights_s = "lights:?"
    # camera
    try:
        cam = spec.get("camera", {}) or {}
        fov = cam.get("fov_deg", None)
        if isinstance(fov, (int, float)):
            cam_s = f"fov:{int(round(float(fov)))}°"
        else:
            cam_s = "fov:?"
    except Exception:
        cam_s = "fov:?"
    head = domain
    if grid_s:
        head += f" | {grid_s}"
    return f"{head} | {objs_s} | {lights_s} | {cam_s}"

def generate_heuristic_enhancements(spec: dict[str, Any], controls: dict[str, Any]) -> list[str]:
    """
    Generate up to ~20 concise, actionable, director-friendly enhancement suggestions
    based on the selected spec and current controls. Deterministic and safe.
    """
    out: list[str] = []
    domain = str((controls or {}).get("domain", spec.get("domain", "procedural_dungeon")))
    size = str((controls or {}).get("size_scale", "medium"))
    density = str((controls or {}).get("complexity_density", "balanced"))
    layout = str((controls or {}).get("layout_style", "branching"))
    mood = str((controls or {}).get("mood_lighting", "neutral"))
    palette = str((controls or {}).get("materials_palette", "stone_wood"))
    cam_style = str((controls or {}).get("camera_style", "cinematic_static"))

    counts = _count_objects_by_type(spec)
    objs_total = sum(counts.values())
    try:
        lights_n = len(spec.get("lighting", []) or [])
    except Exception:
        lights_n = 0

    # Domain-agnostic suggestions
    if mood == "dramatic":
        out.append("Increase key-to-fill contrast and add subtle volumetric fog for light shafts.")
        out.append("Use motivated lighting with practicals visible in-frame to justify highlights.")
    elif mood == "warm":
        out.append("Shift light color temperature toward warm (3000–4000K) and add bounce fill near key surfaces.")
    elif mood == "cool":
        out.append("Introduce cooler rim lights and reduce fill to emphasize silhouettes.")
    else:
        out.append("Establish a consistent lighting ratio; add a gentle rim to separate the hero subject.")

    out.append("Refine material roughness/metallic values to increase micro-contrast in hero areas.")
    if palette == "marble_gold":
        out.append("Add subtle imperfections to marble (noise normal) and use tighter highlights on gold trims.")
    elif palette == "lava_obsidian":
        out.append("Introduce emissive lava seams with soft bloom and cooler fill to balance the heat.")
    elif palette == "mossy_cobble":
        out.append("Vary moss distribution using vertex weights; keep walkable areas cleaner for readability.")

    if cam_style == "handheld":
        out.append("Lower camera height slightly and add mild noise to simulate handheld energy.")
    elif cam_style == "dolly":
        out.append("Plan a motivated dolly path leading to the hero prop; keep parallax layers readable.")
    elif cam_style == "topdown":
        out.append("Ensure composition reads from above; use clear negative space and strong contour lighting.")
    else:
        out.append("Compose with rule-of-thirds; place the hero prop off-center and use leading lines.")

    # Size/density/layout guidance
    if size == "small":
        out.append("Reduce set scale; focus detail density near the hero area to save budget elsewhere.")
    elif size == "large":
        out.append("Expand negative space and add secondary vignettes for depth without clutter.")
    if density == "dense":
        out.append("Cluster detail into purposeful beats; keep traversal corridors visually simpler.")
    elif density == "sparse":
        out.append("Introduce a few mid-scale props to avoid emptiness while preserving clarity.")
    if layout == "maze":
        out.append("Add occasional landmarks and light accents to prevent disorientation.")
    elif layout == "linear":
        out.append("Use light and prop blocking to guide the eye forward; avoid backtracking cues.")

    # Domain-specific suggestions
    if domain == "procedural_dungeon":
        grid = spec.get("grid", {}) or {}
        dims = grid.get("dimensions", {}) or {}
        cols = dims.get("cols", None)
        rows = dims.get("rows", None)
        out.append("Ensure path from start to goal is traversable; avoid dead-ends near the main route.")
        out.append("Add small loops or optional rooms for exploration; gate them with keys or light cues.")
        out.append("Vary corridor widths subtly to create rhythm; widen near points of interest.")
        if isinstance(cols, int) and isinstance(rows, int) and cols * rows > 400:
            out.append("Use stronger lighting anchors and signage to maintain orientation in large maps.")
        if counts.get("door", 0) == 0:
            out.append("Introduce a few doors or thresholds to segment pacing between spaces.")
    elif domain == "film_interior":
        out.append("Add set dressing around the hero prop (books, frames, fabrics) to suggest lived-in context.")
        out.append("Shape key light with flags; avoid flat illumination on background walls.")
        if lights_n < 2:
            out.append("Add a fill practical (lamp/window) to create believable light motivation.")
        out.append("Balance color palette: pair warm key with cooler fill or vice versa for depth.")
        out.append("Consider a foreground occluder for depth layering and cinematic framing.")

    # Budget/optimization nudges
    if objs_total > 50:
        out.append("Cull hidden faces on large props and merge small meshes to reduce draw calls.")
    out.append("Add a lightweight fog volume and subtly roll off contrast with distance for scale cues.")

    # Deduplicate while preserving order, trim to max 20
    seen = set()
    final: list[str] = []
    for s in out:
        k = (s or "").strip()
        if not k:
            continue
        kl = k.lower()
        if kl in seen:
            continue
        seen.add(kl)
        final.append(k)
        if len(final) >= 20:
            break
    return final

__all__ = ["summarize_variant", "generate_heuristic_enhancements"]

# Registration stubs for Blender add-on convention
def register() -> None:
    pass

def unregister() -> None:
    pass