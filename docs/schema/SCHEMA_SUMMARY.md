Canvas3D Scene Spec v1.0.0 — Contract Summary
Source schema: [docs/schema/canvas3d_scene_spec.schema.json](docs/schema/canvas3d_scene_spec.schema.json:1)
Core validator: [SceneSpecValidator.validate()](canvas3d/utils/spec_validation.py:88)
Executor entrypoint: [SpecExecutor.execute_scene_spec()](canvas3d/generation/spec_executor.py:54)
Traversability API: [is_spec_traversable()](canvas3d/utils/traversability.py:212)

Top-level object
- type: object; required fields: version, domain, seed, objects, lighting, camera
- units: enum ["meters"] (default "meters")
- domain: enum ["procedural_dungeon", "film_interior"]
- Conditional requirement: when domain == "procedural_dungeon", grid is required

version
- string pattern N.N.N (e.g., "1.0.0")
- Validator may enforce exact version match when expect_version is provided

seed
- integer >= 0
- Used to seed deterministic operations in executor

metadata (optional)
- quality_mode: enum ["lite", "balanced", "high"] (default "balanced")
- hardware_profile: string
- notes: string
- dev-only flag supported by executor: metadata.force_fail (bool) to simulate failure in tests

grid (required for procedural_dungeon)
- cell_size_m: number in [0.25, 5.0]
- dimensions: object with:
  - cols: integer in [5, 200]
  - rows: integer in [5, 200]

objects (array)
- item type: object; required fields: id, type
- id: ASCII-safe string "^[a-zA-Z0-9_\-]+$"; must be unique across spec
- type: enum ["cube","plane","cylinder","corridor_segment","room","door","stair","prop_instance"]
- transforms (optional): position, rotation_euler, scale must be vec3 [x,y,z] numbers
- grid_cell (optional): object with integer col,row
- material (optional): string; collection (optional): string
- properties (optional): object; domain attributes used:
  - room: width_cells, height_cells (ints)
  - corridor_segment: length_cells (int), direction: enum ["north","south","east","west"]
  - door: properties.direction (enum as above) and optional width_m (float) or width_cells (int)

lighting (array, minItems=1)
- item type: object; required fields: type, position, intensity
- type: enum ["sun","point","area","spot"]
- position: vec3; rotation_euler: vec3 (optional)
- intensity: number in [0.0, 10000.0]
- color_rgb: [r,g,b] numbers in [0.0, 1.0] (default [1.0,1.0,1.0])

camera (object)
- required: position vec3, rotation_euler vec3
- fov_deg: number in [20.0, 120.0] (default 60.0)

materials (array, default [])
- name: string (ASCII-safe and unique enforced by validator)
- pbr (optional):
  - base_color: 3 numbers in [0.0, 1.0]
  - metallic: number in [0.0, 1.0]
  - roughness: number in [0.0, 1.0]
  - normal_tex: string

collections (array, default [])
- name: string (ASCII-safe and unique enforced by validator)
- purpose: enum ["geometry","props","lighting","physics"]

constraints (object, optional)
- min_path_length_cells: integer >= 5
- require_traversable_start_to_goal: boolean (default true)
- max_polycount: integer >= 1000

Domain-specific cross-field checks in validator
- Doors must be adjacent to a room or corridor cell (same cell or 4-neighbor)
- corridor_segment.properties.direction must be one of {"north","south","east","west"}

Traversability integration
- Default start=(0,0), goal=(cols-1,rows-1) when grid present
- check blocks from object.properties.blocked == True and forces door cells open
- Optional overrides: spec.traversable_cells and object.walkable_area rectangles
- Enforces min_path_length_cells when provided or via constraints

Executor behavior summary
- Validates spec strictly via [assert_valid_scene_spec()](canvas3d/utils/spec_validation.py:541)
- Seeds RNG with spec.seed for deterministic operations
- Builds in an isolated temp collection; atomic commit-or-rollback
- Best-effort cleanup removes only newly created data-blocks on failure
- Returns committed collection name "Canvas3D_Scene_{request_id}"

Additional validator hints (non-blocking)
- Recommend grid area >= 50 cells
- Suggest adding a fill light when only a single light present
- Warn for camera FOV > 100°

Implementation notes
- ASCII-safe checks and uniqueness for materials/collections go beyond schema to meet Blender naming constraints and test expectations
- Grid requirement for procedural_dungeon enforced both by schema and validator
- Spec and executor operate correctly outside Blender with dry-run paths; bpy import is optional in tests

References
- Validator: [SceneSpecValidator](canvas3d/utils/spec_validation.py:79)
- Executor: [SpecExecutor](canvas3d/generation/spec_executor.py:49)
- Traversability: [astar_path_length()](canvas3d/utils/traversability.py:53), [check_traversable()](canvas3d/utils/traversability.py:97), [is_spec_traversable()](canvas3d/utils/traversability.py:212)
- Schema file: [docs/schema/canvas3d_scene_spec.schema.json](docs/schema/canvas3d_scene_spec.schema.json:1)