# Canvas3D: Complete Problem Breakdown, Fixes, and Execution Plan

Executive Summary
Canvas3D will shift from LLM-to-Python generation to a schema-validated JSON spec executed by a deterministic Blender builder. The MVP will focus on Procedural Dungeons to maximize reliability and user value. The product will ship with real Anthropic integration, an iteration workflow with variations and local parameter editing, export pipelines for major engines, robust error handling, telemetry, and stable concurrency. Each item below includes scope, implementation steps, acceptance criteria, dependencies, timeline, and impact.

Core Architecture
1. Prompt intake in Blender UI produces a request containing user intent, chosen domain, hardware profile, and quality mode.
2. Anthropic model generates a strict JSON scene spec conforming to a published schema and version.
3. A deterministic Blender executor validates the spec, performs guarded construction in an isolated collection, and either atomically commits or rolls back.
4. Iteration workflow enables local parameter edits without additional LLM calls, variation generation, and history tracking.
5. Export subsystem produces glTF, FBX, and USD outputs with organized collections, colliders, and PBR material mappings.
6. Concurrency subsystem manages a bounded request queue with cancelation and per-request state.
7. Telemetry logs generation outcomes, durations, validation results, and export stats, with privacy controls.

Scene Spec Schema (authoritative contract)
Use meters for all linear units and right-handed Blender coordinates. All randomness must be seeded. All names must be unique and ASCII-safe.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Canvas3D Scene Spec",
  "type": "object",
  "required": ["version", "domain", "seed", "objects", "lighting", "camera"],
  "properties": {
    "version": { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$" },
    "domain": { "type": "string", "enum": ["procedural_dungeon"] },
    "units": { "type": "string", "enum": ["meters"], "default": "meters" },
    "seed": { "type": "integer", "minimum": 0 },
    "metadata": {
      "type": "object",
      "properties": {
        "quality_mode": { "type": "string", "enum": ["lite", "balanced", "high"], "default": "balanced" },
        "hardware_profile": { "type": "string" },
        "notes": { "type": "string" }
      }
    },
    "grid": {
      "type": "object",
      "required": ["cell_size_m", "dimensions"],
      "properties": {
        "cell_size_m": { "type": "number", "minimum": 0.25, "maximum": 5.0 },
        "dimensions": {
          "type": "object",
          "required": ["cols", "rows"],
          "properties": {
            "cols": { "type": "integer", "minimum": 5, "maximum": 200 },
            "rows": { "type": "integer", "minimum": 5, "maximum": 200 }
          }
        }
      }
    },
    "objects": {
      "type": "array",
      "items": { "$ref": "#/definitions/object" }
    },
    "lighting": {
      "type": "array",
      "items": { "$ref": "#/definitions/light" },
      "minItems": 1
    },
    "camera": { "$ref": "#/definitions/camera" },
    "materials": {
      "type": "array",
      "items": { "$ref": "#/definitions/material" },
      "default": []
    },
    "collections": {
      "type": "array",
      "items": { "$ref": "#/definitions/collection" },
      "default": []
    },
    "constraints": {
      "type": "object",
      "properties": {
        "min_path_length_cells": { "type": "integer", "minimum": 5 },
        "require_traversable_start_to_goal": { "type": "boolean", "default": true },
        "max_polycount": { "type": "integer", "minimum": 1000 }
      }
    }
  },
  "definitions": {
    "vec3": {
      "type": "array",
      "items": { "type": "number" },
      "minItems": 3,
      "maxItems": 3
    },
    "object": {
      "type": "object",
      "required": ["id", "type"],
      "properties": {
        "id": { "type": "string", "pattern": "^[a-zA-Z0-9_\\-]+$" },
        "type": {
          "type": "string",
          "enum": [
            "cube",
            "plane",
            "cylinder",
            "corridor_segment",
            "room",
            "door",
            "stair",
            "prop_instance"
          ]
        },
        "position": { "$ref": "#/definitions/vec3" },
        "rotation_euler": { "$ref": "#/definitions/vec3" },
        "scale": { "$ref": "#/definitions/vec3" },
        "grid_cell": {
          "type": "object",
          "properties": { "col": { "type": "integer" }, "row": { "type": "integer" } }
        },
        "material": { "type": "string" },
        "collection": { "type": "string" },
        "properties": { "type": "object" }
      }
    },
    "light": {
      "type": "object",
      "required": ["type", "position", "intensity"],
      "properties": {
        "type": { "type": "string", "enum": ["sun", "point", "area", "spot"] },
        "position": { "$ref": "#/definitions/vec3" },
        "rotation_euler": { "$ref": "#/definitions/vec3" },
        "intensity": { "type": "number", "minimum": 0.0, "maximum": 10000.0 },
        "color_rgb": {
          "type": "array",
          "items": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
          "minItems": 3,
          "maxItems": 3,
          "default": [1.0, 1.0, 1.0]
        }
      }
    },
    "camera": {
      "type": "object",
      "required": ["position", "rotation_euler"],
      "properties": {
        "position": { "$ref": "#/definitions/vec3" },
        "rotation_euler": { "$ref": "#/definitions/vec3" },
        "fov_deg": { "type": "number", "minimum": 20.0, "maximum": 120.0, "default": 60.0 }
      }
    },
    "material": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": { "type": "string" },
        "pbr": {
          "type": "object",
          "properties": {
            "base_color": {
              "type": "array",
              "items": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
              "minItems": 3,
              "maxItems": 3
            },
            "metallic": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
            "roughness": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
            "normal_tex": { "type": "string" }
          }
        }
      }
    },
    "collection": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": { "type": "string" },
        "purpose": { "type": "string", "enum": ["geometry", "props", "lighting", "physics"] }
      }
    }
  }
}
```

Example Spec
```json
{
  "version": "1.0.0",
  "domain": "procedural_dungeon",
  "units": "meters",
  "seed": 12345,
  "metadata": { "quality_mode": "balanced", "hardware_profile": "gpu_8gb" },
  "grid": { "cell_size_m": 2.0, "dimensions": { "cols": 20, "rows": 15 } },
  "objects": [
    { "id": "room_a", "type": "room", "grid_cell": { "col": 3, "row": 4 }, "properties": { "width_cells": 6, "height_cells": 5 }, "material": "stone_wall", "collection": "geometry" },
    { "id": "corridor_1", "type": "corridor_segment", "grid_cell": { "col": 9, "row": 6 }, "properties": { "length_cells": 8, "direction": "east" }, "material": "stone_floor", "collection": "geometry" },
    { "id": "door_a", "type": "door", "grid_cell": { "col": 9, "row": 6 }, "properties": { "style": "wooden" }, "material": "wood_oak", "collection": "geometry" },
    { "id": "table_1", "type": "prop_instance", "position": [6.0, 10.0, 0.0], "rotation_euler": [0.0, 0.0, 0.5], "scale": [1.0, 1.0, 1.0], "properties": { "prop_asset": "tavern_table" }, "material": "wood_oak", "collection": "props" }
  ],
  "lighting": [
    { "type": "sun", "position": [5.0, 5.0, 10.0], "rotation_euler": [0.8, 0.0, 0.0], "intensity": 2.5, "color_rgb": [1.0, 0.98, 0.9] },
    { "type": "point", "position": [6.0, 10.0, 2.5], "intensity": 75.0, "color_rgb": [1.0, 0.85, 0.6] }
  ],
  "camera": { "position": [0.0, -15.0, 7.0], "rotation_euler": [1.2, 0.0, 0.0], "fov_deg": 65.0 },
  "materials": [
    { "name": "stone_wall", "pbr": { "base_color": [0.4, 0.4, 0.45], "roughness": 0.8, "metallic": 0.0 } },
    { "name": "stone_floor", "pbr": { "base_color": [0.35, 0.35, 0.4], "roughness": 0.7, "metallic": 0.0 } },
    { "name": "wood_oak", "pbr": { "base_color": [0.55, 0.38, 0.22], "roughness": 0.6, "metallic": 0.0 } }
  ],
  "collections": [
    { "name": "geometry", "purpose": "geometry" },
    { "name": "props", "purpose": "props" },
    { "name": "lighting", "purpose": "lighting" },
    { "name": "physics", "purpose": "physics" }
  ],
  "constraints": {
    "min_path_length_cells": 12,
    "require_traversable_start_to_goal": true,
    "max_polycount": 400000
  }
}
```

TIER 1: Critical (Blocks MVP)

Problem 1.1: LLM-to-Python geometry is unreliable
Scope
Replace Python code generation with a strictly validated JSON scene spec and a deterministic Blender executor. Define authoritative schema, enforce units and coordinate conventions, seed randomness, and publish validation rules. Build an executor that constructs scenes in an isolated collection, performs atomic commit or rollback, and guarantees reproducibility.

Implementation Steps
1. Publish v1.0.0 JSON Schema with domain-specific constraints for Procedural Dungeons.
2. Implement a validator that returns structured error reasons and paths for any invalid spec fields.
3. Implement a deterministic Blender executor: create isolated workspace collection, instantiate objects, apply transforms, assign materials, generate collision meshes, and commit atomically.
4. Implement a traversability validator using A* on the grid to ensure start-to-goal connectivity and enforce minimum path length constraints.
5. Implement seed handling across any local procedural operations to ensure re-runs reproduce geometry exactly.
6. Add unit tests for validator, executor, and traversability checks with a corpus of 50 specs.

Acceptance Criteria
1. A corpus of 50 diverse dungeon specs executes with 0 crashes and 95 percent correctness as scored by path connectivity, transform accuracy within 1 millimeter, and material assignments matching spec.
2. Executor produces identical geometry across three independent runs with the same spec and seed.
3. Invalid specs return actionable errors at the field level, and no partial scene pollution remains after rollback.

Dependencies
Schema design, Blender API access, grid and pathfinding utility.

Timeline
Two to three days.

Impact
Reliability improves from approximately 60 percent to approximately 80 percent.

Problem 1.2: No real Anthropic LLM integration
Scope
Implement production-grade Anthropic integration with streaming, strict JSON output, retries, and rate-limit awareness. Ship a test harness with 20 to 30 real prompts and document measured success rate.

Implementation Steps
1. Implement Anthropic client using the current SDK with streaming responses when available, otherwise non-streaming fallback.
2. Construct a system prompt that specifies domain, constraints, schema contract, JSON-only output, and disallows commentary outside JSON.
3. Provide two few-shot exemplars and the formal schema to the model; enable deterministic sampling parameters appropriate for JSON generation.
4. Implement structured retries with exponential backoff for rate limits and timeouts.
5. Implement a response sanitizer that trims non-JSON preambles, validates against schema, and either repairs via a constrained follow-up or returns validation errors to the user.
6. Build a manual evaluation harness that executes real prompts, records success/failure, and captures reasons for failure.

Acceptance Criteria
1. At least 20 real prompts generate valid specs with a minimum of 70 percent usable scenes in the chosen domain.
2. All responses are valid JSON without extraneous text; any invalid response yields a clear validation error with actionable guidance.
3. Rate limits and timeouts are visible to users with appropriate messaging and automatic retry behavior when safe.

Dependencies
API key management and preferences UI, schema availability.

Timeline
One day.

Impact
Enables end-to-end reality checks and informs iteration.

Problem 1.3: Mock mode hides real problems
Scope
Remove canned mock mode. Provide a low-quality mode powered by smaller LLMs with simplified schema but still real outputs. Always surface real failures to users with guidance.

Implementation Steps
1. Remove mock logic from generation paths and test code beyond basic infrastructure tests.
2. Introduce a low-quality mode that uses a smaller Anthropic model with lower-cost parameters while still conforming to the schema.
3. Tag outputs with quality metadata and allow users to upgrade prior specs with a high-quality re-run.

Acceptance Criteria
1. No canned geometry is ever presented within the generation UI after MVP; every scene derives from a real LLM or local param edits.
2. Users can select low-quality or high-quality modes and understand the tradeoffs.

Dependencies
LLM integration, schema compatibility across quality modes.

Timeline
Immediate.

Impact
Forces exposure to real output quality early and drives iteration.

TIER 2: High Priority (Needed for MVP)

Problem 2.1: No iteration workflow
Scope
Introduce a full loop: generate, preview, tweak, regenerate, compare, and revert. Expose parameters as editable controls mapped to spec fields. Provide a variations generator and history.

Implementation Steps
1. Store every spec as a JSON text block inside the Blender file and in a sidecar file for portability.
2. Build a parameters panel that surfaces complexity, lighting style, clutter, material styles, and domain-specific constraints; bind controls directly to spec fields and allow local regeneration with no LLM call.
3. Implement a Generate Variations function that produces five specs from the same prompt and seed perturbations or param sweeps; display thumbnails for quick selection.
4. Implement a generation history with labels, timestamps, diffs, and one-click revert; persist with the Blender file.
5. Implement a compare view that shows side-by-side screenshots and key stats such as polycount, path length, and export size.

Acceptance Criteria
1. Users can produce five variations from a single prompt, select one, tweak parameters locally, and regenerate without contacting the LLM.
2. History stores at least ten generations per project with diffs and revert.
3. Parameter edits are idempotent and reflect exact spec changes after regeneration.

Dependencies
LLM integration, spec schema, Blender UI.

Timeline
Three to four days after specs are working.

Impact
Usability improves substantially and unlocks productivity.

Problem 2.2: Scope is too broad
Scope
Constrain MVP to Procedural Dungeons. Encode domain-specific rules, ensure connectivity, and optimize evaluation and iteration.

Implementation Steps
1. Decide and lock MVP domain as procedural_dungeon with grid-based generation and a standard cell size default of two meters.
2. Add domain constraints to schema for corridor directions, room dimensions, allowable door placements, and required traversability.
3. Implement automated traversal validation using A* or Dijkstra from a defined start to a defined goal cell; fail scenes that are not traversable.
4. Provide a domain prompt template with few-shot examples emphasizing connectivity, scale, materials, and lighting norms; avoid outdoor or complex organic features.
5. Create a 30-prompt test set covering small rooms, multi-room layouts, branching corridors, loops, doors, and stairs.

Acceptance Criteria
1. Measured success rate improves from approximately 20 percent to approximately 70 percent within the dungeon domain based on traversability and user-rated visual plausibility.
2. All scenes adhere to scale conventions; no floating objects and minimal interpenetration.
3. Domain failure reasons are specific and lead to targeted fixes, such as corridor collision or missing door connectivity.

Dependencies
Schema, validator, LLM prompt design.

Timeline
One hour decision, then schema and validator changes.

Impact
Fundamental improvement to reliability and user trust.

Problem 2.3: Export and integration are incomplete
Scope
Deliver export presets for glTF, FBX, and USD with organized collections, PBR materials, collision meshes, and engine-friendly naming. Provide per-engine guidance and sample projects.

Implementation Steps
1. Implement export presets with consistent axis and scale mapping for glTF (GLB), FBX, and USD.
2. Auto-generate physics collision meshes and place them in a dedicated physics collection; support box and convex hull approximations.
3. Organize scene into geometry, props, lighting, and physics collections, and ensure unique object names.
4. Map Blender Principled BSDF to engine PBR standards where possible and embed or reference textures appropriately.
5. Produce sample Unity, Unreal, and Godot projects demonstrating import steps and verify correctness.

Acceptance Criteria
1. Exported assets load in Unity, Unreal, and Godot with correct scale, materials, and collision; verification includes walkable navmesh generation and lighting sanity checks.
2. Export scripts are one-click from the UI and produce deterministic outputs.
3. Documentation summarizes supported features, known limitations, and required manual steps when applicable.

Dependencies
Blender export APIs, material mapping, sample engine projects.

Timeline
Two to three days after specs and iteration workflow.

Impact
Enables real downstream usage and saves time.

TIER 3: Medium Priority (Nice for MVP, Required for Scale)

Problem 3.1: Parameters are not exposed
Scope
Parse spec fields into a parameter panel with sliders and selectors. Allow local regeneration without additional LLM calls and save presets.

Implementation Steps
1. Implement a parameter mapping layer from schema fields to UI controls.
2. Provide preset management for styles such as cozy, dark, bright, and minimal with serialized parameter sets.
3. Regenerate scenes locally when parameters change; keep seeds stable unless explicitly changed.
4. Save and load presets per project.

Acceptance Criteria
1. Users can adjust complexity, lighting style, clutter, and materials and see changes in seconds without hitting the LLM.
2. Presets are sharable and reproducible across machines with identical results.

Dependencies
Schema, executor, UI.

Timeline
Two days.

Impact
Improves UX and reduces API usage.

Problem 3.2: Concurrency is naive
Scope
Introduce a bounded queue, cancelation, and request state visibility. Avoid resource contention and race conditions.

Implementation Steps
1. Implement a generation queue with a maximum of two concurrent requests and FIFO ordering.
2. Track per-request states including queued, running, complete, and failed; expose status in the UI including position and ETA.
3. Implement cancelation that safely stops LLM calls and executor work, followed by rollback of any partial collections.
4. Add resource locking for Blender data blocks during execution.

Acceptance Criteria
1. Spamming Generate creates queued requests without crashing Blender or the executor.
2. Cancelation leaves no partial artifacts and the UI reflects accurate states.
3. CPU and GPU usage stay within reasonable bounds measured under load.

Dependencies
Executor, UI, LLM integration.

Timeline
One day.

Impact
Stability at scale.

Problem 3.3: Error messages are unhelpful
Scope
Provide user-friendly errors with clear remediation steps and log full technical details for debugging.

Implementation Steps
1. Map technical errors to user messages including invalid API key leading to checking Anthropic key in Preferences, rate limited leading to waiting before retry, timeout leading to simplifying the prompt, and invalid spec leading to rewording or using presets.
2. Include actions and links to docs for each error. Offer to downgrade to low-quality mode when hitting high model limits.
3. Log full technical errors, request IDs, and validation traces locally and optionally to a cloud endpoint if enabled.

Acceptance Criteria
1. Every failure includes a user-facing explanation and a suggested next step.
2. Logs contain sufficient detail to triage issues without reproducing them immediately.

Dependencies
Telemetry, UI messaging, integration.

Timeline
One day.

Impact
Reduces confusion and support burden.

Problem 3.4: No telemetry or logging
Scope
Instrument generation, validation, and export flows. Collect anonymized statistics with opt-in controls and a simple dashboard or CSV export.

Implementation Steps
1. Define an event schema that includes timestamp, prompt, domain, seed, duration, success or failure, error code, spec size, polycount, export format, and engine import result.
2. Persist events in the Blender file and optionally stream to a cloud endpoint with authentication and privacy opt-in.
3. Provide a dashboard view or CSV export; analyze success rates by domain and prompt type.

Acceptance Criteria
1. Telemetry reveals success rates, bottlenecks, and common failure reasons.
2. Users can export logs for support and debugging.

Dependencies
Storage, UI, optional cloud.

Timeline
One day.

Impact
Enables data-driven iteration.

TIER 4: Lower Priority (Phase 2+)

Problem 4.1: Hardware detection is stubbed
Scope
Detect GPU VRAM and CPU characteristics and feed a hardware profile into generation and execution to adjust quality.

Implementation Steps
1. Query GPU VRAM using available APIs and detect CPU core count.
2. Pass hardware profile to prompts and adjust max polycount and object density in the spec.
3. Expose Quality Mode in Preferences and surface effective profile in the UI.

Acceptance Criteria
1. Low-end hardware defaults to lighter geometry and textures; high-end produces richer scenes without stutter.
2. Users can override automatic detection.

Timeline
Phase 2.

Impact
Improves performance and compatibility.

Problem 4.2: Scene cleanup on failure is incomplete
Scope
Ensure fully atomic scene generation via isolated collections and single-commit semantics.

Implementation Steps
1. Always generate into a temporary collection with predictable naming.
2. On success, move or rename the collection; on failure, delete the temporary collection and any orphan data blocks.
3. Add unit tests for partial failure cases.

Acceptance Criteria
1. No residual materials, textures, or orphan meshes remain after failures.
2. Success paths produce clean, organized collections.

Timeline
Phase 2.

Impact
Cleaner failure recovery.

Problem 4.3: No texture generation
Scope
Elevate visual quality via procedural materials and curated CC0 texture sets, with optional tri-planar projection and automatic UV.

Implementation Steps
1. Ship a small library of CC0 PBR materials for stone, wood, and metal; map to schema materials by name.
2. Implement tri-planar mapping or Smart UV Project on props and terrain surfaces where appropriate.
3. Phase 2 exploration of external texture generation services and MaterialX conversion.

Acceptance Criteria
1. Scenes render with believable materials out of the box and are usable for gameplay prototypes.
2. Exported materials map correctly in target engines.

Timeline
Phase 2.

Impact
Improves perceived quality and utility.

Security, Preferences, and Compliance
1. Store API keys in Blender Preferences with secure storage where possible and never embed keys in specs or exports.
2. Provide opt-in telemetry with clear disclosures and a privacy policy summary.
3. Support offline local regeneration for parameter edits and schema validation.

Versioning and Migration
1. Add version to every spec and implement migration functions for minor schema changes.
2. Reject major version mismatches with clear guidance.

Testing Strategy
1. Unit tests for schema validation, executor operations, traversability, export functions, and parameter mapping.
2. Integration tests that run end-to-end from prompt to export across a 30-prompt corpus.
3. Performance tests for concurrency, memory usage, and export sizes on low, mid, and high hardware profiles.

Release Plan
1. Internal alpha with dungeon-only domain and all Tier 1 and Tier 2 items complete.
2. Public beta after passing acceptance criteria and export validation in Unity, Unreal, and Godot.
3. Phase 2 rollout with Tier 4 items and texture upgrades.

Success Metrics
1. At least 70 percent usable scenes within the dungeon domain by internal evaluation and user feedback.
2. Average generation time under five seconds for low-quality mode and under ten seconds for high-quality mode on mid-tier hardware.
3. Export success in three engines with minimal manual adjustments.

Prompt Template for Anthropic
Use a system prompt that states the domain, scale, rules, and schema. Demand JSON-only output matching the schema and disallow comments and explanations. Provide two few-shot examples with valid specs and ensure the model references the schema constraints. Require seeded randomness and enforce grid connectivity in the spec.

Deterministic Executor Notes
Prefer simple primitive instancing for walls, floors, and doors to ensure predictable topology. Snap transforms to grid cell boundaries. Clamp scales and rotations to safe ranges. Name data blocks deterministically based on spec IDs.

UI Overview
The UI presents a prompt field, Generate, Generate Variations, Save Spec, Parameter Panel, History, Queue Status, Export Presets, and Error Guidance. The Parameter Panel reflects current spec and allows local edits and regeneration. History provides thumbnails, labels, and diffs.

This roadmap defines the contract, architecture, and execution plan to reach a reliable MVP for Procedural Dungeons and sets the foundation for expanding into additional domains after validation.