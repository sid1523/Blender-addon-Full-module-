# Canvas3D Scene Spec Validator (v1.0.0)
# Validates deterministic JSON scene specs for the "procedural_dungeon" MVP domain.
#
# Contract highlights (see roadmap):
# - Units in meters, right-handed Blender coordinates.
# - Deterministic: all randomness must be driven by a provided seed.
# - All names ASCII-safe; object IDs unique; collection/material names unique.
# - Strict schema with actionable, path-scoped errors.
#
# Public API:
# - validate_scene_spec(spec: dict) -> tuple[bool, list[ValidationIssue]]
# - assert_valid_scene_spec(spec: dict) -> None  (raises SpecValidationError on errors)
#
# Integration:
# - Orchestrator should call assert_valid_scene_spec() before execution.
# - Traversability checks (A*) will be added/integrated in a follow-up module.

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ASCII_SAFE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")

ALLOWED_DOMAINS = {"procedural_dungeon", "film_interior"}
UNITS_ALLOWED = {"meters"}

OBJECT_TYPES = {
    "cube",
    "plane",
    "cylinder",
    "corridor_segment",
    "room",
    "door",
    "stair",
    "prop_instance",
}

LIGHT_TYPES = {"sun", "point", "area", "spot"}
QUALITY_MODES = {"lite", "balanced", "high"}
COLLECTION_PURPOSE = {"geometry", "props", "lighting", "physics"}


class SpecValidationError(Exception):
    """Raised when a scene spec fails validation with actionable details."""
    pass


@dataclass
class ValidationIssue:
    path: str
    message: str
    code: str = "invalid"

    def __str__(self) -> str:
        return f"{self.path}: {self.message} ({self.code})"



def _is_vec3(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 3:
        return False
    return all(isinstance(x, (int, float)) for x in value)





def _require(cond: bool, issues: list[ValidationIssue], path: str, msg: str, code: str = "invalid") -> None:
    if not cond:
        issues.append(ValidationIssue(path=path, message=msg, code=code))


def _type_of(value: Any) -> str:
    return type(value).__name__


class SceneSpecValidator:
    """Validator for Canvas3D scene specs (domain=procedural_dungeon)."""

    def __init__(self, expect_version: str | None = None) -> None:
        self.expect_version = expect_version  # if set, require exact match

    # -----------------
    # Top-level checks
    # -----------------
    def validate(self, spec: dict[str, Any]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        # Type
        _require(isinstance(spec, dict), issues, path="$", msg=f"Spec must be an object, got: {_type_of(spec)}", code="type")

        if not isinstance(spec, dict):
            return issues  # nothing else to do

        # Required keys
        required_keys = ["version", "domain", "seed", "objects", "lighting", "camera"]
        for k in required_keys:
            _require(k in spec, issues, path="$", msg=f"Missing required field: {k}", code="required")

        # version
        version = spec.get("version")
        if version is not None:
            _require(isinstance(version, str), issues, "$.version", f"version must be string, got: {_type_of(version)}", "type")
            if isinstance(version, str):
                _require(bool(VERSION_PATTERN.match(version)), issues, "$.version", "version must match N.N.N", "format")
                if self.expect_version is not None:
                    _require(version == self.expect_version, issues, "$.version", f"expected version {self.expect_version}", "mismatch")

        # domain
        domain = spec.get("domain")
        if domain is not None:
            _require(isinstance(domain, str), issues, "$.domain", f"domain must be string, got: {_type_of(domain)}", "type")
            if isinstance(domain, str):
                _require(domain in ALLOWED_DOMAINS, issues, "$.domain", f"domain must be one of {sorted(ALLOWED_DOMAINS)}", "enum")

        # units (optional, default 'meters')
        units = spec.get("units", "meters")
        _require(units in UNITS_ALLOWED, issues, "$.units", "units must be 'meters'", "enum")

        # seed
        seed = spec.get("seed")
        if seed is not None:
            _require(isinstance(seed, int), issues, "$.seed", f"seed must be integer, got: {_type_of(seed)}", "type")
            if isinstance(seed, int):
                _require(seed >= 0, issues, "$.seed", "seed must be >= 0", "minimum")

        # metadata (optional)
        if "metadata" in spec:
            self._validate_metadata(spec["metadata"], issues)

        # grid
        if "grid" in spec:
            self._validate_grid(spec["grid"], issues)
        else:
            # Grid is required for procedural_dungeon domain, optional otherwise
            if domain == "procedural_dungeon":
                issues.append(ValidationIssue("$.grid", "grid is required for procedural_dungeon domain", "required"))

        # materials (optional, default [])
        if "materials" in spec:
            self._validate_materials(spec["materials"], issues)

        # collections (optional, default [])
        if "collections" in spec:
            self._validate_collections(spec["collections"], issues)

        # objects
        if "objects" in spec:
            self._validate_objects(spec["objects"], issues)
        # lighting
        if "lighting" in spec:
            self._validate_lighting(spec["lighting"], issues)
        # camera
        if "camera" in spec:
            self._validate_camera(spec["camera"], issues)

        # constraints (optional)
        if "constraints" in spec:
            self._validate_constraints(spec["constraints"], issues)

        # Domain-specific traversability placeholder; actual check handled in traversability module.
        cons = spec.get("constraints", {}) or {}
        require_trav = cons.get("require_traversable_start_to_goal", True)

        # Cross-field constraints (non-trivial semantics that require multiple fields)
        try:
            objs = spec.get("objects", []) or []
            # Build occupancy for adjacency checks
            room_cells: set[tuple[int, int]] = set()
            corridor_cells: set[tuple[int, int]] = set()
            for i, o in enumerate(objs):
                try:
                    otype = str(o.get("type", "")).lower()
                    gc = o.get("grid_cell", {}) or {}
                    col = gc.get("col", None)
                    row = gc.get("row", None)
                    if isinstance(col, int) and isinstance(row, int):
                        if otype == "room":
                            room_cells.add((col, row))
                        if otype == "corridor_segment":
                            corridor_cells.add((col, row))
                except Exception:
                    continue

            def _neighbors(c: int, r: int) -> list[tuple[int, int]]:
                return [(c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)]

            # Doors must be adjacent to a room or corridor
            for i, o in enumerate(objs):
                try:
                    if str(o.get("type", "")).lower() != "door":
                        continue
                    gc = o.get("grid_cell", {}) or {}
                    col = gc.get("col", None)
                    row = gc.get("row", None)
                    if not (isinstance(col, int) and isinstance(row, int)):
                        # grid_cell validity already checked elsewhere
                        continue
                    # Accept co-located door on the same cell as a room or corridor start, or adjacency
                    same_cell_ok = ((col, row) in room_cells) or ((col, row) in corridor_cells)
                    adj = _neighbors(col, row)
                    adjacent_ok = any((a in room_cells or a in corridor_cells) for a in adj)
                    if not (same_cell_ok or adjacent_ok):
                        issues.append(ValidationIssue(
                            path=f"$.objects[{i}]",
                            message="Door must be adjacent to a room or corridor cell",
                            code="cross_constraint",
                        ))
                except Exception:
                    continue

            # Corridor direction must be valid and supported
            for i, o in enumerate(objs):
                try:
                    if str(o.get("type", "")).lower() != "corridor_segment":
                        continue
                    props = o.get("properties", {}) or {}
                    direction = str(props.get("direction", "") or "").lower()
                    if direction not in {"north", "south", "east", "west"}:
                        issues.append(ValidationIssue(
                            path=f"$.objects[{i}].properties.direction",
                            message="corridor_segment.properties.direction must be one of {'north','south','east','west'}",
                            code="enum",
                        ))
                except Exception:
                    continue
        except Exception:
            # Cross-field validation is best-effort; do not fail validation routine on its own errors
            pass

        return issues

    # -----------------
    # Section validators
    # -----------------
    def _validate_metadata(self, meta: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(meta, dict), issues, "$.metadata", f"metadata must be object, got: {_type_of(meta)}", "type")
        if not isinstance(meta, dict):
            return
        qm = meta.get("quality_mode", "balanced")
        if qm is not None:
            _require(isinstance(qm, str), issues, "$.metadata.quality_mode", f"quality_mode must be string, got: {_type_of(qm)}", "type")
            if isinstance(qm, str):
                _require(qm in QUALITY_MODES, issues, "$.metadata.quality_mode", f"quality_mode must be one of {sorted(QUALITY_MODES)}", "enum")
        hp = meta.get("hardware_profile", None)
        if hp is not None:
            _require(isinstance(hp, str), issues, "$.metadata.hardware_profile", f"hardware_profile must be string, got: {_type_of(hp)}", "type")
        notes = meta.get("notes", None)
        if notes is not None:
            _require(isinstance(notes, str), issues, "$.metadata.notes", f"notes must be string, got: {_type_of(notes)}", "type")

    def _validate_grid(self, grid: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(grid, dict), issues, "$.grid", f"grid must be object, got: {_type_of(grid)}", "type")
        if not isinstance(grid, dict):
            return
        _require("cell_size_m" in grid, issues, "$.grid", "Missing required field: cell_size_m", "required")
        _require("dimensions" in grid, issues, "$.grid", "Missing required field: dimensions", "required")

        cs = grid.get("cell_size_m")
        if cs is not None:
            _require(isinstance(cs, (int, float)), issues, "$.grid.cell_size_m", f"cell_size_m must be number, got: {_type_of(cs)}", "type")
            if isinstance(cs, (int, float)):
                _require(0.25 <= float(cs) <= 5.0, issues, "$.grid.cell_size_m", "cell_size_m must be in [0.25, 5.0]", "range")

        dims = grid.get("dimensions")
        _require(isinstance(dims, dict), issues, "$.grid.dimensions", f"dimensions must be object, got: {_type_of(dims)}", "type")
        if isinstance(dims, dict):
            cols = dims.get("cols")
            rows = dims.get("rows")
            _require(isinstance(cols, int), issues, "$.grid.dimensions.cols", f"cols must be integer, got: {_type_of(cols)}", "type")
            _require(isinstance(rows, int), issues, "$.grid.dimensions.rows", f"rows must be integer, got: {_type_of(rows)}", "type")
            if isinstance(cols, int):
                _require(5 <= cols <= 200, issues, "$.grid.dimensions.cols", "cols must be in [5, 200]", "range")
            if isinstance(rows, int):
                _require(5 <= rows <= 200, issues, "$.grid.dimensions.rows", "rows must be in [5, 200]", "range")

    def _validate_materials(self, materials: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(materials, list), issues, "$.materials", f"materials must be array, got: {_type_of(materials)}", "type")
        if not isinstance(materials, list):
            return
        names: list[str] = []
        for i, m in enumerate(materials):
            p = f"$.materials[{i}]"
            _require(isinstance(m, dict), issues, p, f"material must be object, got: {_type_of(m)}", "type")
            if not isinstance(m, dict):
                continue
            name = m.get("name")
            _require(isinstance(name, str) and name.strip(), issues, f"{p}.name", "material.name must be non-empty string", "required")
            if isinstance(name, str) and name.strip():
                # ASCII-safe check
                _require(bool(ASCII_SAFE_PATTERN.match(name)), issues, f"{p}.name", "material.name must be ASCII-safe [a-zA-Z0-9_\\-]", "ascii")
                names.append(name)
            pbr = m.get("pbr", None)
            if pbr is not None:
                _require(isinstance(pbr, dict), issues, f"{p}.pbr", f"pbr must be object, got: {_type_of(pbr)}", "type")
                if isinstance(pbr, dict):
                    bc = pbr.get("base_color", None)
                    if bc is not None:
                        _require(isinstance(bc, list) and len(bc) == 3 and all(isinstance(x, (int, float)) for x in bc), issues, f"{p}.pbr.base_color", "base_color must be [r,g,b] numbers", "type")
                        if isinstance(bc, list) and len(bc) == 3 and all(isinstance(x, (int, float)) for x in bc):
                            _require(all(0.0 <= float(x) <= 1.0 for x in bc), issues, f"{p}.pbr.base_color", "base_color components must be in [0,1]", "range")
                    for fld in ("metallic", "roughness"):
                        val = pbr.get(fld, None)
                        if val is not None:
                            _require(isinstance(val, (int, float)), issues, f"{p}.pbr.{fld}", f"{fld} must be number", "type")
                            if isinstance(val, (int, float)):
                                _require(0.0 <= float(val) <= 1.0, issues, f"{p}.pbr.{fld}", f"{fld} must be in [0,1]", "range")
                    nt = pbr.get("normal_tex", None)
                    if nt is not None:
                        _require(isinstance(nt, str), issues, f"{p}.pbr.normal_tex", "normal_tex must be string (path/identifier)", "type")
        # Duplicate material names not allowed
        try:
            if names and len(names) != len(set(names)):
                issues.append(ValidationIssue("$.materials", "material names must be unique", "unique"))
        except Exception:
            pass

    def _validate_collections(self, collections: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(collections, list), issues, "$.collections", f"collections must be array, got: {_type_of(collections)}", "type")
        if not isinstance(collections, list):
            return
        names: list[str] = []
        for i, c in enumerate(collections):
            p = f"$.collections[{i}]"
            _require(isinstance(c, dict), issues, p, f"collection must be object, got: {_type_of(c)}", "type")
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            _require(isinstance(name, str) and name.strip(), issues, f"{p}.name", "collection.name must be non-empty string", "required")
            if isinstance(name, str) and name.strip():
                # ASCII-safe check
                _require(bool(ASCII_SAFE_PATTERN.match(name)), issues, f"{p}.name", "collection.name must be ASCII-safe [a-zA-Z0-9_\\-]", "ascii")
                names.append(name)
            purpose = c.get("purpose", None)
            if purpose is not None:
                _require(isinstance(purpose, str), issues, f"{p}.purpose", f"purpose must be string, got: {_type_of(purpose)}", "type")
                if isinstance(purpose, str):
                    _require(purpose in COLLECTION_PURPOSE, issues, f"{p}.purpose", f"purpose must be one of {sorted(COLLECTION_PURPOSE)}", "enum")
        # Duplicate collection names not allowed
        try:
            if names and len(names) != len(set(names)):
                issues.append(ValidationIssue("$.collections", "collection names must be unique", "unique"))
        except Exception:
            pass

    def _validate_objects(self, objects: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(objects, list), issues, "$.objects", f"objects must be array, got: {_type_of(objects)}", "type")
        if not isinstance(objects, list):
            return
        ids: list[str] = []
        seen: set[str] = set()
        for i, o in enumerate(objects):
            p = f"$.objects[{i}]"
            _require(isinstance(o, dict), issues, p, f"object must be object, got: {_type_of(o)}", "type")
            if not isinstance(o, dict):
                continue
            oid = o.get("id")
            _require(isinstance(oid, str) and oid.strip(), issues, f"{p}.id", "object.id must be non-empty string", "required")
            if isinstance(oid, str) and oid.strip():
                # ASCII-safe id
                _require(bool(ASCII_SAFE_PATTERN.match(oid)), issues, f"{p}.id", "object.id must be ASCII-safe [a-zA-Z0-9_\\-]", "ascii")
                # Inline uniqueness detection to fail fast
                if bool(ASCII_SAFE_PATTERN.match(oid)):
                    if oid in seen:
                        issues.append(ValidationIssue("$.objects", "object ids must be unique", "unique"))
                    else:
                        seen.add(oid)
                ids.append(oid)

            otype = o.get("type")
            _require(isinstance(otype, str), issues, f"{p}.type", f"object.type must be string, got: {_type_of(otype)}", "type")
            if isinstance(otype, str):
                _require(otype in OBJECT_TYPES, issues, f"{p}.type", f"object.type must be one of {sorted(OBJECT_TYPES)}", "enum")

            # Optional transforms
            pos = o.get("position", None)
            if pos is not None:
                _require(_is_vec3(pos), issues, f"{p}.position", "position must be [x,y,z] numbers", "type")
            rot = o.get("rotation_euler", None)
            if rot is not None:
                _require(_is_vec3(rot), issues, f"{p}.rotation_euler", "rotation_euler must be [rx,ry,rz] numbers", "type")
            scale = o.get("scale", None)
            if scale is not None:
                _require(_is_vec3(scale), issues, f"{p}.scale", "scale must be [sx,sy,sz] numbers", "type")

            # grid_cell (optional but recommended for dungeon domain)
            gc = o.get("grid_cell", None)
            if gc is not None:
                _require(isinstance(gc, dict), issues, f"{p}.grid_cell", f"grid_cell must be object, got: {_type_of(gc)}", "type")
                if isinstance(gc, dict):
                    col = gc.get("col")
                    row = gc.get("row")
                    _require(isinstance(col, int), issues, f"{p}.grid_cell.col", f"grid_cell.col must be integer, got: {_type_of(col)}", "type")
                    _require(isinstance(row, int), issues, f"{p}.grid_cell.row", f"grid_cell.row must be integer, got: {_type_of(row)}", "type")

            # material (optional)
            mat = o.get("material", None)
            if mat is not None:
                _require(isinstance(mat, str), issues, f"{p}.material", f"material must be string, got: {_type_of(mat)}", "type")

            # collection (optional)
            coln = o.get("collection", None)
            if coln is not None:
                _require(isinstance(coln, str), issues, f"{p}.collection", f"collection must be string, got: {_type_of(coln)}", "type")

            # properties (optional)
            props = o.get("properties", None)
            if props is not None:
                _require(isinstance(props, dict), issues, f"{p}.properties", f"properties must be object, got: {_type_of(props)}", "type")

        # Object id uniqueness across spec
        try:
            if ids and len(ids) != len(set(ids)):
                issues.append(ValidationIssue("$.objects", "object ids must be unique", "unique"))
        except Exception:
            pass

    def _validate_lighting(self, lights: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(lights, list), issues, "$.lighting", f"lighting must be array, got: {_type_of(lights)}", "type")
        if not isinstance(lights, list):
            return
        _require(len(lights) >= 1, issues, "$.lighting", "lighting must contain at least one light", "minItems")
        for i, L in enumerate(lights):
            p = f"$.lighting[{i}]"
            _require(isinstance(L, dict), issues, p, f"light must be object, got: {_type_of(L)}", "type")
            if not isinstance(L, dict):
                continue
            ltype = L.get("type")
            _require(isinstance(ltype, str), issues, f"{p}.type", f"type must be string, got: {_type_of(ltype)}", "type")
            if isinstance(ltype, str):
                _require(ltype in LIGHT_TYPES, issues, f"{p}.type", f"type must be one of {sorted(LIGHT_TYPES)}", "enum")
            pos = L.get("position")
            _require(_is_vec3(pos), issues, f"{p}.position", "position must be [x,y,z] numbers", "type")
            rot = L.get("rotation_euler", None)
            if rot is not None:
                _require(_is_vec3(rot), issues, f"{p}.rotation_euler", "rotation_euler must be [rx,ry,rz] numbers", "type")
            intensity = L.get("intensity")
            _require(isinstance(intensity, (int, float)), issues, f"{p}.intensity", f"intensity must be number, got: {_type_of(intensity)}", "type")
            if isinstance(intensity, (int, float)):
                _require(0.0 <= float(intensity) <= 10000.0, issues, f"{p}.intensity", "intensity must be in [0, 10000]", "range")
            color = L.get("color_rgb", [1.0, 1.0, 1.0])
            _require(isinstance(color, list) and len(color) == 3 and all(isinstance(x, (int, float)) for x in color), issues, f"{p}.color_rgb", "color_rgb must be [r,g,b] numbers", "type")
            if isinstance(color, list) and len(color) == 3 and all(isinstance(x, (int, float)) for x in color):
                _require(all(0.0 <= float(x) <= 1.0 for x in color), issues, f"{p}.color_rgb", "color_rgb components must be in [0,1]", "range")

    def _validate_camera(self, cam: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(cam, dict), issues, "$.camera", f"camera must be object, got: {_type_of(cam)}", "type")
        if not isinstance(cam, dict):
            return
        pos = cam.get("position")
        rot = cam.get("rotation_euler")
        _require(_is_vec3(pos), issues, "$.camera.position", "position must be [x,y,z] numbers", "type")
        _require(_is_vec3(rot), issues, "$.camera.rotation_euler", "rotation_euler must be [rx,ry,rz] numbers", "type")
        fov = cam.get("fov_deg", 60.0)
        _require(isinstance(fov, (int, float)), issues, "$.camera.fov_deg", f"fov_deg must be number, got: {_type_of(fov)}", "type")
        if isinstance(fov, (int, float)):
            _require(20.0 <= float(fov) <= 120.0, issues, "$.camera.fov_deg", "fov_deg must be in [20, 120]", "range")

    def _validate_constraints(self, cons: Any, issues: list[ValidationIssue]) -> None:
        _require(isinstance(cons, dict), issues, "$.constraints", f"constraints must be object, got: {_type_of(cons)}", "type")
        if not isinstance(cons, dict):
            return
        mpl = cons.get("min_path_length_cells", None)
        if mpl is not None:
            _require(isinstance(mpl, int), issues, "$.constraints.min_path_length_cells", f"min_path_length_cells must be integer, got: {_type_of(mpl)}", "type")
            if isinstance(mpl, int):
                _require(mpl >= 5, issues, "$.constraints.min_path_length_cells", "min_path_length_cells must be >= 5", "minimum")
        rtg = cons.get("require_traversable_start_to_goal", True)
        _require(isinstance(rtg, bool), issues, "$.constraints.require_traversable_start_to_goal", f"require_traversable_start_to_goal must be boolean, got: {_type_of(rtg)}", "type")
        mp = cons.get("max_polycount", None)
        if mp is not None:
            _require(isinstance(mp, int), issues, "$.constraints.max_polycount", f"max_polycount must be integer, got: {_type_of(mp)}", "type")
            if isinstance(mp, int):
                _require(mp >= 1000, issues, "$.constraints.max_polycount", "max_polycount must be >= 1000", "minimum")

    def _validate_best_practices(self, spec: dict[str, Any]) -> list[ValidationIssue]:
        """
        Non-blocking semantic validation producing hints/warnings:
        - Recommend minimum grid area (cols*rows >= 50) to avoid cramped layouts.
        - Suggest adding a fill light when only a single light is present.
        - Warn when camera FOV is extremely wide (>100°).
        Returns a list of ValidationIssue entries with code 'hint' or 'warning'.
        """
        hints: list[ValidationIssue] = []
        # Grid size recommendation
        try:
            grid = spec.get("grid", {}) or {}
            dims = grid.get("dimensions", {}) or {}
            cols = int(dims.get("cols", 0))
            rows = int(dims.get("rows", 0))
            if cols > 0 and rows > 0 and (cols * rows) < 50:
                hints.append(ValidationIssue(
                    path="$.grid.dimensions",
                    message="Recommended minimum 50 cells (e.g., 10x5). Small grids may feel cramped.",
                    code="warning",
                ))
        except Exception:
            pass
        # Lighting composition suggestion
        try:
            lights = spec.get("lighting", []) or []
            if isinstance(lights, list) and len(lights) == 1:
                hints.append(ValidationIssue(
                    path="$.lighting",
                    message="Single light source may create harsh shadows. Consider adding a fill light.",
                    code="hint",
                ))
        except Exception:
            pass
        # Camera FOV hint
        try:
            camera = spec.get("camera", {}) or {}
            fov = camera.get("fov_deg", 60.0)
            if isinstance(fov, (int, float)) and float(fov) > 100.0:
                hints.append(ValidationIssue(
                    path="$.camera.fov_deg",
                    message="Very wide FOV (>100°) can distort perspective. Typical: 50–70°.",
                    code="hint",
                ))
        except Exception:
            pass
        return hints

# -----------------
# Public API
# -----------------
def validate_scene_spec(spec: dict[str, Any], expect_version: str | None = None) -> tuple[bool, list[ValidationIssue]]:
    """
    Validate a scene spec dict against the Canvas3D v1.0.0 contract.

    Returns:
        (ok, issues)
    """
    validator = SceneSpecValidator(expect_version=expect_version)
    issues = validator.validate(spec)
    return (len(issues) == 0, issues)


def assert_valid_scene_spec(spec: dict[str, Any], expect_version: str | None = None) -> None:
    """
    Validate and raise SpecValidationError with actionable, path-scoped messages if invalid.
    """
    ok, issues = validate_scene_spec(spec, expect_version=expect_version)
    if not ok:
        # Format issues for readability
        lines = [f"- {str(i)}" for i in issues]
        msg = "Scene spec validation failed:\n" + "\n".join(lines)
        raise SpecValidationError(msg)


__all__ = [
    "SpecValidationError",
    "ValidationIssue",
    "SceneSpecValidator",
    "validate_scene_spec",
    "assert_valid_scene_spec",
]


# Registration stubs (Blender add-on convention)
def register() -> None:
    pass


def unregister() -> None:
    pass