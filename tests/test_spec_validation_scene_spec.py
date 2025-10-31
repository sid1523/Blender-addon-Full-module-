import pytest

from canvas3d.utils.spec_validation import (
    validate_scene_spec,
    assert_valid_scene_spec,
    SpecValidationError,
)


def make_valid_spec():
    return {
        "version": "1.0.0",
        "domain": "procedural_dungeon",
        "units": "meters",
        "seed": 12345,
        "metadata": {"quality_mode": "balanced", "hardware_profile": "gpu_8gb"},
        "grid": {"cell_size_m": 2.0, "dimensions": {"cols": 20, "rows": 15}},
        "objects": [
            {
                "id": "room_a",
                "type": "room",
                "grid_cell": {"col": 3, "row": 4},
                "properties": {"width_cells": 6, "height_cells": 5},
                "material": "stone_wall",
                "collection": "geometry",
            },
            {
                "id": "corridor_1",
                "type": "corridor_segment",
                "grid_cell": {"col": 9, "row": 6},
                "properties": {"length_cells": 8, "direction": "east"},
                "material": "stone_floor",
                "collection": "geometry",
            },
            {
                "id": "door_a",
                "type": "door",
                "grid_cell": {"col": 9, "row": 6},
                "properties": {"style": "wooden"},
                "material": "wood_oak",
                "collection": "geometry",
            },
            {
                "id": "table_1",
                "type": "prop_instance",
                "position": [6.0, 10.0, 0.0],
                "rotation_euler": [0.0, 0.0, 0.5],
                "scale": [1.0, 1.0, 1.0],
                "properties": {"prop_asset": "tavern_table"},
                "material": "wood_oak",
                "collection": "props",
            },
        ],
        "lighting": [
            {
                "type": "sun",
                "position": [5.0, 5.0, 10.0],
                "rotation_euler": [0.8, 0.0, 0.0],
                "intensity": 2.5,
                "color_rgb": [1.0, 0.98, 0.9],
            },
            {
                "type": "point",
                "position": [6.0, 10.0, 2.5],
                "intensity": 75.0,
                "color_rgb": [1.0, 0.85, 0.6],
            },
        ],
        "camera": {"position": [0.0, -15.0, 7.0], "rotation_euler": [1.2, 0.0, 0.0], "fov_deg": 65.0},
        "materials": [
            {"name": "stone_wall", "pbr": {"base_color": [0.4, 0.4, 0.45], "roughness": 0.8, "metallic": 0.0}},
            {"name": "stone_floor", "pbr": {"base_color": [0.35, 0.35, 0.4], "roughness": 0.7, "metallic": 0.0}},
            {"name": "wood_oak", "pbr": {"base_color": [0.55, 0.38, 0.22], "roughness": 0.6, "metallic": 0.0}},
        ],
        "collections": [
            {"name": "geometry", "purpose": "geometry"},
            {"name": "props", "purpose": "props"},
            {"name": "lighting", "purpose": "lighting"},
            {"name": "physics", "purpose": "physics"},
        ],
        "constraints": {
            "min_path_length_cells": 12,
            "require_traversable_start_to_goal": True,
            "max_polycount": 400000,
        },
    }


def run_validate(spec):
    ok, issues = validate_scene_spec(spec, expect_version="1.0.0")
    return ok, issues


def test_valid_spec_passes():
    ok, issues = run_validate(make_valid_spec())
    assert ok is True
    assert issues == []


@pytest.mark.parametrize("missing_field", ["version", "domain", "seed", "objects", "lighting", "camera"])
def test_missing_required_fields(missing_field):
    spec = make_valid_spec()
    del spec[missing_field]
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.code == "required" and missing_field in i.message for i in issues)


def test_grid_missing_reports_required():
    spec = make_valid_spec()
    del spec["grid"]
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.grid" and i.code == "required" for i in issues)


def test_version_format_invalid():
    spec = make_valid_spec()
    spec["version"] = "1.0"
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.version" and i.code in {"format", "mismatch"} for i in issues)


def test_domain_invalid():
    spec = make_valid_spec()
    spec["domain"] = "city"
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.domain" and i.code == "enum" for i in issues)


def test_units_invalid():
    spec = make_valid_spec()
    spec["units"] = "centimeters"
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.units" and i.code == "enum" for i in issues)


def test_seed_negative():
    spec = make_valid_spec()
    spec["seed"] = -1
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.seed" and i.code == "minimum" for i in issues)


def test_grid_cell_size_out_of_range():
    spec = make_valid_spec()
    spec["grid"]["cell_size_m"] = 0.1
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.grid.cell_size_m" and i.code == "range" for i in issues)


def test_grid_dimensions_type_and_range():
    spec = make_valid_spec()
    spec["grid"]["dimensions"]["cols"] = "10"
    spec["grid"]["dimensions"]["rows"] = 300
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.grid.dimensions.cols" and i.code == "type" for i in issues)
    assert any(i.path == "$.grid.dimensions.rows" and i.code == "range" for i in issues)


def test_object_id_ascii_and_unique():
    spec = make_valid_spec()
    # Non-ASCII ID
    spec["objects"][0]["id"] = "room_α"
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path.startswith("$.objects[0].id") and i.code == "ascii" for i in issues)

    # Duplicate IDs
    spec = make_valid_spec()
    spec["objects"][1]["id"] = spec["objects"][0]["id"]
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.objects" and i.code == "unique" for i in issues)


def test_object_type_enum_and_transforms_types():
    spec = make_valid_spec()
    spec["objects"][0]["type"] = "sphere"
    spec["objects"][0]["position"] = [0.0, 1.0]  # bad length
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path.startswith("$.objects[0].type") and i.code == "enum" for i in issues)
    assert any(i.path.startswith("$.objects[0].position") and i.code == "type" for i in issues)


def test_object_grid_cell_types():
    spec = make_valid_spec()
    spec["objects"][0]["grid_cell"] = {"col": "1", "row": 2}
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.objects[0].grid_cell.col" and i.code == "type" for i in issues)


def test_material_names_unique_and_ranges():
    spec = make_valid_spec()
    # Duplicate material name
    spec["materials"][1]["name"] = spec["materials"][0]["name"]
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.materials" and i.code == "unique" for i in issues)

    # Out-of-range pbr values
    spec = make_valid_spec()
    spec["materials"][0]["pbr"]["base_color"] = [1.2, -0.1, 0.5]
    spec["materials"][0]["pbr"]["roughness"] = 1.5
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path.endswith(".pbr.base_color") and i.code == "range" for i in issues)
    assert any(i.path.endswith(".pbr.roughness") and i.code == "range" for i in issues)


def test_collections_ascii_unique_and_purpose_enum():
    spec = make_valid_spec()
    spec["collections"][0]["name"] = "geométry"  # non-ascii
    spec["collections"][1]["name"] = spec["collections"][0]["name"]  # duplicate
    spec["collections"][2]["purpose"] = "render"  # invalid enum
    ok, issues = run_validate(spec)
    assert ok is False
    # Name ascii + unique
    assert any(i.code == "ascii" and i.path.endswith(".name") for i in issues)
    assert any(i.code == "unique" and i.path == "$.collections" for i in issues)
    # Purpose enum
    assert any(i.code == "enum" and i.path.endswith(".purpose") for i in issues)


def test_lighting_minitems_and_ranges():
    spec = make_valid_spec()
    spec["lighting"] = []
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.lighting" and i.code == "minItems" for i in issues)

    spec = make_valid_spec()
    spec["lighting"][0]["intensity"] = 20000.0
    spec["lighting"][1]["color_rgb"] = [-0.1, 0.0, 1.1]
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path.endswith(".intensity") and i.code == "range" for i in issues)
    assert any(i.path.endswith(".color_rgb") and i.code == "range" for i in issues)


def test_camera_fov_out_of_range_and_types():
    spec = make_valid_spec()
    spec["camera"]["fov_deg"] = 10.0
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.camera.fov_deg" and i.code == "range" for i in issues)

    spec = make_valid_spec()
    spec["camera"]["rotation_euler"] = [0.0, 0.0]  # wrong length
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.camera.rotation_euler" and i.code == "type" for i in issues)


def test_constraints_checks():
    spec = make_valid_spec()
    spec["constraints"]["min_path_length_cells"] = 3
    spec["constraints"]["require_traversable_start_to_goal"] = "yes"
    spec["constraints"]["max_polycount"] = 500
    ok, issues = run_validate(spec)
    assert ok is False
    assert any(i.path == "$.constraints.min_path_length_cells" and i.code == "minimum" for i in issues)
    assert any(i.path == "$.constraints.require_traversable_start_to_goal" and i.code == "type" for i in issues)
    assert any(i.path == "$.constraints.max_polycount" and i.code == "minimum" for i in issues)


def test_assert_valid_scene_spec_raises_with_issue_listing():
    spec = make_valid_spec()
    spec["version"] = "1.0"  # invalid format
    with pytest.raises(SpecValidationError) as exc:
        assert_valid_scene_spec(spec, expect_version="1.0.0")
    msg = str(exc.value)
    # Ensure formatted, path-scoped errors are included
    assert "Scene spec validation failed:" in msg
    assert "$.version" in msg