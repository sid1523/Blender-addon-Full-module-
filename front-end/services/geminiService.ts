
import { GoogleGenAI, Type } from "@google/genai";
import type { TerrainFeature, ScatterObject, Biome, FoliageProperties, SeasonalVariations, LightingConfig, CameraConfig, WeatherConfig, BakingConfig, PostProcessingConfig, VegetationConfig } from "../App";

// ⚠️ CRITICAL SECURITY ISSUE: API key is exposed in client-side code!
// RECOMMENDATION: Move API calls to a backend proxy server (Node.js/Express) to hide credentials.
// For production use, implement:
// 1. Backend API endpoint (e.g., POST /api/generate-scene) that stores the Gemini API key securely
// 2. Update this service to call your backend instead of Gemini directly
// 3. Add authentication/rate limiting to prevent abuse
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY as string });

export async function enhancePrompt(originalPrompt: string): Promise<string> {
    const model = 'gemini-2.5-flash';
    const systemInstruction = `You are a creative prompt engineer specializing in 3D scene generation. 
    
    Expand the user's prompt by:
    1. Adding sensory details (lighting quality, time of day, weather)
    2. Specifying material properties (worn wood, polished metal, wet stone)
    3. Defining spatial relationships (foreground/background, clustering patterns)
    4. Including atmospheric effects (fog, god rays, particle effects)
    5. Suggesting color palettes and mood
    
    Structure your response as a single, eloquent paragraph with clear, visual language that can be parsed by another AI model.
    Do NOT use markdown, lists, or conversational fillers.`;

    try {
        const response = await ai.models.generateContent({
            model: model,
            contents: `Expand this prompt for a 3D scene, focusing on sensory details, lighting, atmosphere, and specific environmental elements: "${originalPrompt}"`,
            config: {
                systemInstruction: systemInstruction,
            },
        });
        return response.text.trim();
    } catch (error) {
        console.error("Error calling Gemini API for prompt enhancement:", error);
        if (error instanceof Error) {
            if (error.message.includes('API key not valid')) {
                throw new Error(`Invalid API Key. Please check your configuration.`);
            }
            throw new Error(`Failed to enhance prompt. Gemini API Error: ${error.message}`);
        }
        throw new Error("An unexpected error occurred while enhancing the prompt. Please check the console for details.");
    }
}

export async function generateColorPalette(prompt: string): Promise<string[]> {
    const model = 'gemini-2.5-flash';
    const systemInstruction = `You are a color theory expert. Analyze the user's prompt and generate a harmonious 5-color palette that captures the mood and theme. Respond ONLY with a JSON object containing a single key "palette" which is an array of 5 hex color strings.`;
    
    const schema = {
        type: Type.OBJECT,
        properties: {
            palette: {
                type: Type.ARRAY,
                description: "An array of 5 hex color strings.",
                items: { type: Type.STRING, pattern: "^#[0-9a-fA-F]{6}$" }
            }
        },
        required: ["palette"]
    };

    try {
        const response = await ai.models.generateContent({
            model: model,
            contents: `Generate a color palette for this prompt: "${prompt}"`,
            config: {
                systemInstruction,
                responseMimeType: "application/json",
                responseSchema: schema,
            },
        });
        const result = JSON.parse(response.text);
        return result.palette;
    } catch(error) {
        console.error("Error generating color palette:", error);
        if (error instanceof Error) {
            if (error.message.includes('API key not valid')) {
                throw new Error(`Invalid API Key. Please check your configuration.`);
            }
            throw new Error(`Failed to generate color palette. Gemini API Error: ${error.message}`);
        }
        throw new Error("An unexpected error occurred while generating the color palette. Please check the console for details.");
    }
}

// Canvas3D v1.0.0 Schema - Matches Python backend spec_validation.py
const canvas3dMaterialSchema = {
    type: Type.OBJECT,
    properties: {
        name: {
            type: Type.STRING,
            description: "Unique ASCII-safe material name (a-zA-Z0-9_-), e.g., 'stone_wall', 'torch_flame'."
        },
        pbr: {
            type: Type.OBJECT,
            description: "PBR material properties for Cycles/EEVEE rendering.",
            properties: {
                base_color: {
                    type: Type.ARRAY,
                    description: "Base color as RGB [r, g, b] with values 0.0-1.0.",
                    items: { type: Type.NUMBER, minimum: 0.0, maximum: 1.0 }
                },
                metallic: { type: Type.NUMBER, minimum: 0.0, maximum: 1.0, description: "Metallic factor 0.0-1.0." },
                roughness: { type: Type.NUMBER, minimum: 0.0, maximum: 1.0, description: "Roughness factor 0.0-1.0." },
                normal_tex: { type: Type.STRING, description: "Optional normal map texture path or identifier." }
            }
        }
    },
    required: ["name"]
};

const canvas3dObjectSchema = {
    type: Type.OBJECT,
    properties: {
        id: {
            type: Type.STRING,
            description: "Unique ASCII-safe object ID (a-zA-Z0-9_-), e.g., 'room_1', 'corridor_2', 'door_3'."
        },
        type: {
            type: Type.STRING,
            enum: ['cube', 'plane', 'cylinder', 'corridor_segment', 'room', 'door', 'stair', 'prop_instance'],
            description: "Object type: room (dungeon room), corridor_segment (hallway), door (opening), prop_instance (chest/torch/etc)."
        },
        position: {
            type: Type.ARRAY,
            description: "World position [x, y, z] in meters.",
            items: { type: Type.NUMBER }
        },
        rotation_euler: {
            type: Type.ARRAY,
            description: "Rotation as Euler angles [rx, ry, rz] in radians.",
            items: { type: Type.NUMBER }
        },
        scale: {
            type: Type.ARRAY,
            description: "Scale factors [sx, sy, sz].",
            items: { type: Type.NUMBER }
        },
        grid_cell: {
            type: Type.OBJECT,
            description: "Grid cell coordinates for procedural_dungeon domain.",
            properties: {
                col: { type: Type.INTEGER, description: "Column index in grid." },
                row: { type: Type.INTEGER, description: "Row index in grid." }
            }
        },
        material: {
            type: Type.STRING,
            description: "Reference to material name from top-level 'materials' array."
        },
        collection: {
            type: Type.STRING,
            description: "Optional collection name this object belongs to."
        },
        properties: {
            type: Type.OBJECT,
            description: "Type-specific properties (e.g., width_cells, height_cells for rooms; direction, length_cells for corridors).",
            properties: {
                width_cells: { type: Type.INTEGER, description: "Room width in grid cells (procedural_dungeon)." },
                height_cells: { type: Type.INTEGER, description: "Room height in grid cells (procedural_dungeon)." },
                length_cells: { type: Type.INTEGER, description: "Corridor length in grid cells." },
                direction: {
                    type: Type.STRING,
                    enum: ['north', 'south', 'east', 'west'],
                    description: "Corridor direction."
                },
                blocked: { type: Type.BOOLEAN, description: "Whether this cell blocks traversal (for A* pathfinding)." }
            }
        }
    },
    required: ["id", "type"]
};

const canvas3dLightSchema = {
    type: Type.OBJECT,
    properties: {
        type: {
            type: Type.STRING,
            enum: ['sun', 'point', 'area', 'spot'],
            description: "Blender light type."
        },
        position: {
            type: Type.ARRAY,
            description: "Light position [x, y, z] in meters.",
            items: { type: Type.NUMBER }
        },
        rotation_euler: {
            type: Type.ARRAY,
            description: "Light rotation [rx, ry, rz] in radians.",
            items: { type: Type.NUMBER }
        },
        intensity: {
            type: Type.NUMBER,
            minimum: 0.0,
            maximum: 10000.0,
            description: "Light intensity (0-10000)."
        },
        color_rgb: {
            type: Type.ARRAY,
            description: "Light color as RGB [r, g, b] with values 0.0-1.0. Default [1.0, 1.0, 1.0] (white).",
            items: { type: Type.NUMBER, minimum: 0.0, maximum: 1.0 }
        }
    },
    required: ["type", "position", "intensity"]
};

const canvas3dCameraSchema = {
    type: Type.OBJECT,
    properties: {
        position: {
            type: Type.ARRAY,
            description: "Camera position [x, y, z] in meters.",
            items: { type: Type.NUMBER }
        },
        rotation_euler: {
            type: Type.ARRAY,
            description: "Camera rotation [rx, ry, rz] in radians.",
            items: { type: Type.NUMBER }
        },
        fov_deg: {
            type: Type.NUMBER,
            minimum: 20.0,
            maximum: 120.0,
            description: "Field of view in degrees (20-120). Default 60."
        }
    },
    required: ["position", "rotation_euler"]
};

const canvas3dCollectionSchema = {
    type: Type.OBJECT,
    properties: {
        name: {
            type: Type.STRING,
            description: "ASCII-safe collection name."
        },
        purpose: {
            type: Type.STRING,
            enum: ['geometry', 'props', 'lighting', 'physics'],
            description: "Collection purpose/category."
        }
    },
    required: ["name"]
};

// Canvas3D v1.0.0 Scene Spec Schema - EXACTLY matches Python backend validation
const baseSceneSpecSchema = {
    type: Type.OBJECT,
    properties: {
        version: {
            type: Type.STRING,
            description: "Schema version in format N.N.N (e.g., '1.0.0'). REQUIRED."
        },
        domain: {
            type: Type.STRING,
            enum: ['procedural_dungeon', 'film_interior'],
            description: "Scene domain. Use 'procedural_dungeon' for dungeon generation with grid-based layout."
        },
        units: {
            type: Type.STRING,
            enum: ['meters'],
            description: "Measurement units. Always 'meters'."
        },
        seed: {
            type: Type.INTEGER,
            minimum: 0,
            description: "Random seed for deterministic generation (>= 0). REQUIRED."
        },
        metadata: {
            type: Type.OBJECT,
            description: "Optional metadata for scene configuration.",
            properties: {
                quality_mode: {
                    type: Type.STRING,
                    enum: ['lite', 'balanced', 'high'],
                    description: "Quality mode for rendering/geometry complexity."
                },
                hardware_profile: { type: Type.STRING, description: "Optional hardware profile hint." },
                notes: { type: Type.STRING, description: "Optional notes about this scene." }
            }
        },
        grid: {
            type: Type.OBJECT,
            description: "Grid configuration for procedural_dungeon domain. REQUIRED for procedural_dungeon.",
            properties: {
                cell_size_m: {
                    type: Type.NUMBER,
                    minimum: 0.25,
                    maximum: 5.0,
                    description: "Size of each grid cell in meters (0.25-5.0)."
                },
                dimensions: {
                    type: Type.OBJECT,
                    description: "Grid dimensions.",
                    properties: {
                        cols: { type: Type.INTEGER, minimum: 5, maximum: 200, description: "Number of columns (5-200)." },
                        rows: { type: Type.INTEGER, minimum: 5, maximum: 200, description: "Number of rows (5-200)." }
                    },
                    required: ["cols", "rows"]
                }
            },
            required: ["cell_size_m", "dimensions"]
        },
        objects: {
            type: Type.ARRAY,
            description: "Array of scene objects (rooms, corridors, doors, props). REQUIRED.",
            items: canvas3dObjectSchema
        },
        lighting: {
            type: Type.ARRAY,
            description: "Array of lights in the scene. At least 1 light required. REQUIRED.",
            items: canvas3dLightSchema
        },
        camera: {
            ...canvas3dCameraSchema,
            description: "Camera configuration. REQUIRED."
        },
        materials: {
            type: Type.ARRAY,
            description: "Optional array of PBR materials.",
            items: canvas3dMaterialSchema
        },
        collections: {
            type: Type.ARRAY,
            description: "Optional array of Blender collections for organizing objects.",
            items: canvas3dCollectionSchema
        },
        constraints: {
            type: Type.OBJECT,
            description: "Optional scene constraints for validation.",
            properties: {
                min_path_length_cells: {
                    type: Type.INTEGER,
                    minimum: 5,
                    description: "Minimum path length in grid cells for dungeon traversability (>= 5)."
                },
                require_traversable_start_to_goal: {
                    type: Type.BOOLEAN,
                    description: "Whether to enforce A* pathfinding from start (0,0) to goal (cols-1,rows-1)."
                },
                max_polycount: {
                    type: Type.INTEGER,
                    minimum: 1000,
                    description: "Maximum polygon count for performance budgeting (>= 1000)."
                }
            }
        }
    },
    required: ["version", "domain", "seed", "objects", "lighting", "camera"]
};

// Validation for Canvas3D v1.0.0 JSON (matches Python backend validation)
function validateGeneratedJSON(jsonData: any): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Required top-level fields
    if (!jsonData.version) {
        errors.push("Missing required field: 'version'");
    } else if (!/^[0-9]+\.[0-9]+\.[0-9]+$/.test(jsonData.version)) {
        errors.push("Field 'version' must match pattern N.N.N (e.g., '1.0.0')");
    }

    if (!jsonData.domain) {
        errors.push("Missing required field: 'domain'");
    } else if (!['procedural_dungeon', 'film_interior'].includes(jsonData.domain)) {
        errors.push("Field 'domain' must be 'procedural_dungeon' or 'film_interior'");
    }

    if (typeof jsonData.seed !== 'number' || jsonData.seed < 0) {
        errors.push("Field 'seed' must be a non-negative integer");
    }

    if (!Array.isArray(jsonData.objects)) {
        errors.push("Missing or invalid required field: 'objects' (must be array)");
    }

    if (!Array.isArray(jsonData.lighting) || jsonData.lighting.length < 1) {
        errors.push("Missing or invalid required field: 'lighting' (must be array with at least 1 light)");
    }

    if (!jsonData.camera || typeof jsonData.camera !== 'object') {
        errors.push("Missing or invalid required field: 'camera' (must be object)");
    }

    // Grid required for procedural_dungeon
    if (jsonData.domain === 'procedural_dungeon') {
        if (!jsonData.grid) {
            errors.push("Field 'grid' is required for domain 'procedural_dungeon'");
        } else {
            if (typeof jsonData.grid.cell_size_m !== 'number' ||
                jsonData.grid.cell_size_m < 0.25 || jsonData.grid.cell_size_m > 5.0) {
                errors.push("Field 'grid.cell_size_m' must be a number between 0.25 and 5.0");
            }
            if (!jsonData.grid.dimensions ||
                typeof jsonData.grid.dimensions.cols !== 'number' ||
                typeof jsonData.grid.dimensions.rows !== 'number' ||
                jsonData.grid.dimensions.cols < 5 || jsonData.grid.dimensions.cols > 200 ||
                jsonData.grid.dimensions.rows < 5 || jsonData.grid.dimensions.rows > 200) {
                errors.push("Field 'grid.dimensions' must have 'cols' and 'rows' integers between 5 and 200");
            }
        }
    }

    // Validate objects
    const asciiSafePattern = /^[a-zA-Z0-9_\-]+$/;
    const objectIds = new Set<string>();

    if (Array.isArray(jsonData.objects)) {
        jsonData.objects.forEach((obj: any, i: number) => {
            if (!obj.id || !asciiSafePattern.test(obj.id)) {
                errors.push(`Object #${i+1}: 'id' must be ASCII-safe (a-zA-Z0-9_-)`);
            } else if (objectIds.has(obj.id)) {
                errors.push(`Object #${i+1}: duplicate id '${obj.id}'`);
            } else {
                objectIds.add(obj.id);
            }

            const validTypes = ['cube', 'plane', 'cylinder', 'corridor_segment', 'room', 'door', 'stair', 'prop_instance'];
            if (!obj.type || !validTypes.includes(obj.type)) {
                errors.push(`Object #${i+1}: 'type' must be one of ${validTypes.join(', ')}`);
            }

            // Check corridor direction
            if (obj.type === 'corridor_segment' && obj.properties?.direction) {
                const validDirections = ['north', 'south', 'east', 'west'];
                if (!validDirections.includes(obj.properties.direction)) {
                    errors.push(`Object #${i+1}: corridor_segment 'direction' must be one of ${validDirections.join(', ')}`);
                }
            }
        });
    }

    // Validate materials
    if (jsonData.materials && Array.isArray(jsonData.materials)) {
        const materialNames = new Set<string>();
        jsonData.materials.forEach((mat: any, i: number) => {
            if (!mat.name || !asciiSafePattern.test(mat.name)) {
                errors.push(`Material #${i+1}: 'name' must be ASCII-safe (a-zA-Z0-9_-)`);
            } else if (materialNames.has(mat.name)) {
                errors.push(`Material #${i+1}: duplicate name '${mat.name}'`);
            } else {
                materialNames.add(mat.name);
            }
        });
    }

    // Validate lights
    if (Array.isArray(jsonData.lighting)) {
        jsonData.lighting.forEach((light: any, i: number) => {
            const validTypes = ['sun', 'point', 'area', 'spot'];
            if (!light.type || !validTypes.includes(light.type)) {
                errors.push(`Light #${i+1}: 'type' must be one of ${validTypes.join(', ')}`);
            }
            if (!Array.isArray(light.position) || light.position.length !== 3) {
                errors.push(`Light #${i+1}: 'position' must be [x, y, z] array`);
            }
            if (typeof light.intensity !== 'number' || light.intensity < 0 || light.intensity > 10000) {
                errors.push(`Light #${i+1}: 'intensity' must be number between 0 and 10000`);
            }
        });
    }

    // Validate camera
    if (jsonData.camera) {
        if (!Array.isArray(jsonData.camera.position) || jsonData.camera.position.length !== 3) {
            errors.push("Camera 'position' must be [x, y, z] array");
        }
        if (!Array.isArray(jsonData.camera.rotation_euler) || jsonData.camera.rotation_euler.length !== 3) {
            errors.push("Camera 'rotation_euler' must be [rx, ry, rz] array");
        }
    }

    return { valid: errors.length === 0, errors };
}

import { constructPrompt } from './prompt-constructor';
import type { GenerationParams } from './types';

export async function generateBlenderData(params: GenerationParams): Promise<string> {
    const model = 'gemini-2.5-flash';

    // System prompt for Canvas3D v1.0.0 schema (matches Python backend)
    const systemPrompt = `You are an expert procedural content generator for Canvas3D, a Blender add-on for generating dungeon and interior scenes.

CRITICAL REQUIREMENTS:
- Output ONLY valid JSON conforming to the Canvas3D v1.0.0 schema
- Set "version": "1.0.0" (REQUIRED)
- Set "domain": "procedural_dungeon" for dungeons or "film_interior" for interiors
- Provide a random "seed" (integer >= 0) for deterministic generation
- For procedural_dungeon domain, ALWAYS include "grid" with cell_size_m (0.25-5.0) and dimensions (cols/rows 5-200)
- All object IDs must be ASCII-safe (a-zA-Z0-9_-)
- Include at least 1 light in "lighting" array
- Camera must have "position" and "rotation_euler" arrays [x,y,z]

DUNGEON GENERATION GUIDE:
- Objects can be: "room", "corridor_segment", "door", "prop_instance", "cube", "plane", etc.
- Rooms need properties: { "width_cells": N, "height_cells": M }
- Corridors need properties: { "length_cells": N, "direction": "north|south|east|west" }
- Doors connect rooms/corridors, need grid_cell and properties.direction
- All objects should have "grid_cell": { "col": C, "row": R } for grid placement
- Materials array is optional but recommended for PBR materials
- Use "blocked": true in properties to mark cells that block pathfinding

EXAMPLE STRUCTURE:
{
  "version": "1.0.0",
  "domain": "procedural_dungeon",
  "seed": 42,
  "grid": {
    "cell_size_m": 3.0,
    "dimensions": { "cols": 10, "rows": 10 }
  },
  "objects": [
    { "id": "room_0", "type": "room", "grid_cell": { "col": 0, "row": 0 }, "properties": { "width_cells": 3, "height_cells": 3 }, "material": "stone_floor" },
    { "id": "corridor_0_1", "type": "corridor_segment", "grid_cell": { "col": 3, "row": 1 }, "properties": { "length_cells": 2, "direction": "east" } },
    { "id": "door_0", "type": "door", "grid_cell": { "col": 3, "row": 1 }, "properties": { "direction": "east" } }
  ],
  "lighting": [
    { "type": "point", "position": [5.0, 5.0, 3.0], "intensity": 100.0, "color_rgb": [1.0, 0.9, 0.7] }
  ],
  "camera": {
    "position": [15.0, 15.0, 20.0],
    "rotation_euler": [0.9, 0.0, 0.8],
    "fov_deg": 60.0
  },
  "materials": [
    { "name": "stone_floor", "pbr": { "base_color": [0.5, 0.5, 0.5], "roughness": 0.8, "metallic": 0.0 } }
  ]
}

Generate a creative, playable dungeon based on the user's prompt!`;

    try {
        const fullPrompt = constructPrompt(params);

        const response = await ai.models.generateContent({
            model: model,
            contents: fullPrompt,
            config: {
                systemInstruction: systemPrompt,
                responseMimeType: "application/json",
                responseSchema: baseSceneSpecSchema,
            },
        });

        const jsonString = response.text;
        try {
            const parsedJson = JSON.parse(jsonString);
            const validationResult = validateGeneratedJSON(parsedJson);
            if (!validationResult.valid) {
                throw new Error(`AI returned invalid JSON. Validation errors:\n${validationResult.errors.join('\n')}`);
            }
            return JSON.stringify(parsedJson, null, 2);
        } catch (jsonError) {
            console.error("Gemini returned invalid JSON or failed validation:", jsonString, jsonError);
            if (jsonError instanceof Error) {
                throw new Error(`The AI returned invalid JSON. Details: ${jsonError.message}`);
            }
            throw new Error("The AI returned invalid JSON. Please try regenerating.");
        }
    } catch (error) {
        console.error("Error calling Gemini API:", error);
        if (error instanceof Error) {
            if (error.message.includes('API key not valid')) {
                throw new Error(`Invalid API Key. Please check your configuration.`);
            }
            throw new Error(`Failed to generate scene specification. Gemini API Error: ${error.message}`);
        }
        throw new Error("An unexpected error occurred while communicating with the Gemini API. Please check the console for details.");
    }
}
