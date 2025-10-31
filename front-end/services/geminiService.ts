
import { GoogleGenAI, Type } from "@google/genai";
import type { TerrainFeature, ScatterObject, Biome, FoliageProperties, SeasonalVariations, LightingConfig, CameraConfig, WeatherConfig, BakingConfig, PostProcessingConfig, VegetationConfig } from "../App";

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
            throw new Error(`Gemini API Error: ${error.message}`);
        }
        throw new Error("An unexpected error occurred while enhancing the prompt.");
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
        throw new Error("Failed to generate a color palette from the prompt.");
    }
}

const nodeTreeSchema = {
    type: Type.OBJECT,
    description: "A simplified representation of a procedural shader node graph.",
    properties: {
        nodes: {
            type: Type.ARRAY,
            items: {
                type: Type.OBJECT,
                properties: {
                    id: { type: Type.STRING, description: "Unique identifier for this node, e.g., 'noise_tex_1'." },
                    type: { type: Type.STRING, description: "The type of Blender shader node, e.g., 'ShaderNodeTexNoise', 'ShaderNodeMath'." },
                    params: { type: Type.OBJECT, description: "A map of parameter names to values, e.g., {'scale': 5, 'detail': 16}." }
                }
            }
        },
        links: {
            type: Type.ARRAY,
            items: {
                type: Type.OBJECT,
                properties: {
                    from_node: { type: Type.STRING, description: "The 'id' of the source node." },
                    from_socket: { type: Type.STRING, description: "The name of the output socket, e.g., 'Fac', 'Color'." },
                    to_node: { type: Type.STRING, description: "The 'id' of the destination node." },
                    to_socket: { type: Type.STRING, description: "The name of the input socket, e.g., 'Base Color', 'Scale'." }
                }
            }
        }
    }
};

const pbrMaterialSchema = {
    type: Type.OBJECT,
    properties: {
        name: { type: Type.STRING, description: "Unique name for this material, e.g., 'grassy_ground_mat'." },
        baseColor: { type: Type.STRING, pattern: "^#[0-9a-fA-F]{6}$", description: "Hex code for the material's albedo/diffuse color." },
        roughness: { type: Type.NUMBER, description: "Material roughness. Range 0.0 (smooth) to 1.0 (rough)." },
        metallic: { type: Type.NUMBER, description: "Material metallicness. Range 0.0 (dielectric) to 1.0 (full metallic)." },
        specular: { type: Type.NUMBER, description: "Material specular highlight intensity. Range 0.0 to 1.0." },
        normalMap: { type: Type.STRING, description: "Description of a procedural node setup for normal/bump mapping, e.g., 'noise_texture_strength_0.5_scale_50'." },
        emissive: { type: Type.NUMBER, description: "Emission strength. A value greater than 0 makes the material glow. Range: 0 to infinity." },
        transmission: { type: Type.NUMBER, description: "Transparency factor. 1.0 is fully transparent (like glass). Range 0.0 to 1.0." },
        ior: { type: Type.NUMBER, description: "Index of Refraction for transmissive materials (e.g., 1.45 for glass, 1.33 for water)." },
        nodeTree: nodeTreeSchema,
        displacement: {
            type: Type.OBJECT,
            properties: {
                strength: { type: Type.NUMBER },
                midLevel: { type: Type.NUMBER, default: 0.5, description: "The value that will be mapped to no displacement." }
            }
        }
    },
    required: ["name", "baseColor", "roughness", "metallic"]
};

const physicsSchema = {
    type: Type.OBJECT,
    properties: {
        collisionType: { 
            type: Type.STRING, 
            enum: ['mesh', 'convex_hull', 'box', 'sphere', 'none'] 
        },
        mass: { type: Type.NUMBER, description: "Mass of the object in kilograms." },
        friction: { type: Type.NUMBER },
        restitution: { type: Type.NUMBER, description: "Bounciness of the object." },
        isDynamic: { type: Type.BOOLEAN, description: "Whether the object should react to physics forces." }
    }
};

const createdObjectSchema = {
    type: Type.OBJECT,
    properties: {
        name: {
            type: Type.STRING,
            description: "A descriptive name for the generated object, e.g., 'Low-Poly Sword', 'Character Maquette'."
        },
        prompt: {
            type: Type.STRING,
            description: "The user prompt that was used to generate this specific object."
        },
        meshData: {
            type: Type.OBJECT,
            description: "The raw geometry data for the 3D model.",
            properties: {
                vertices: {
                    type: Type.ARRAY,
                    description: "An array of vertex coordinates. Each vertex is an array of 3 numbers [x, y, z].",
                    items: { type: Type.ARRAY, items: { type: Type.NUMBER } }
                },
                edges: {
                    type: Type.ARRAY,
                    description: "Optional. Array of edge indices [v1, v2]. Useful for complex meshes to ensure correct topology and subdivision.",
                    items: { type: Type.ARRAY, items: { type: Type.INTEGER } }
                },
                faces: {
                    type: Type.ARRAY,
                    description: "An array of faces, defining how vertices connect. Each face is an array of vertex indices [v1, v2, v3, ...]. Faces must reference valid vertex indices (0 to len(vertices)-1).",
                    items: { type: Type.ARRAY, items: { type: Type.INTEGER } }
                },
                uvs: {
                    type: Type.ARRAY,
                    description: "Optional. UV map coordinates as an array of [u, v] pairs, corresponding to each vertex. Essential for applying textures.",
                    items: { type: Type.ARRAY, items: { type: Type.NUMBER } }
                },
                normals: {
                    type: Type.ARRAY,
                    description: "Optional. Per-vertex normal vectors [nx, ny, nz] for custom shading and smoothing.",
                    items: { type: Type.ARRAY, items: { type: Type.NUMBER } }
                },
                topologyHints: {
                    type: Type.OBJECT,
                    description: "Optional hints for the backend renderer about the mesh's structure.",
                    properties: {
                        isManifold: { type: Type.BOOLEAN, description: "True if the mesh is watertight with no holes, which is ideal for 3D printing and simulations." },
                        windingOrder: { type: Type.STRING, enum: ['CW', 'CCW'], description: "The winding order of face vertices, which determines the direction of face normals. 'CCW' (Counter-Clockwise) is standard." },
                        subdivisionLevels: { type: Type.INTEGER, description: "Suggested levels of Catmull-Clark subdivision surface modifier to apply for a smoother result (0-3)." }
                    }
                },
                description: {
                    type: Type.STRING,
                    description: "A detailed text description of the generated mesh, summarizing its inferred style (e.g., 'low-poly', 'realistic', 'stylized'), complexity, and main features."
                }
            },
            required: ["vertices", "faces", "description"]
        },
        materialRef: {
            type: Type.STRING,
            description: "The name of the material from the top-level 'materials' array to assign to this object."
        },
        approximateScale: {
            type: Type.STRING,
            description: "The approximate perceived scale of the object relative to a human or typical scene elements, eg., 'small', 'medium', 'large', 'life-size', 'massive'.",
        },
        colorPalette: {
            type: Type.ARRAY,
            description: "An array of dominant hex color codes inferred from the image for this object, e.g., ['#FF5733', '#C70039']. This can be used to generate the baseColor for its material.",
            items: { type: Type.STRING, pattern: "^#[0-9a-fA-F]{6}$" }
        },
        materialType: {
            type: Type.STRING,
            description: "The primary inferred material type for the object, e.g., 'metallic', 'wood', 'stone', 'fabric', 'plastic', 'glass', 'organic'.",
        },
        animationRig: {
            type: Type.OBJECT,
            properties: {
                rigType: { type: Type.STRING, enum: ['humanoid', 'quadruped', 'none'] },
                boneNames: { type: Type.ARRAY, items: { type: Type.STRING }, description: "Suggested bone names for the armature." },
                ikChains: {
                    type: Type.ARRAY,
                    description: "Inverse Kinematics chain definitions.",
                    items: {
                        type: Type.OBJECT,
                        properties: {
                            name: { type: Type.STRING, description: "e.g., 'left_arm_ik'" },
                            bones: { type: Type.ARRAY, items: { type: Type.STRING }, description: "List of bone names in the chain from root to tip." }
                        }
                    }
                }
            }
        },
        physics: physicsSchema
    },
    required: ["name", "prompt", "meshData", "materialRef", "approximateScale", "colorPalette", "materialType"]
};

const baseSceneSpecSchema = {
    type: Type.OBJECT,
    properties: {
        schemaVersion: { type: Type.STRING, description: "The version of the schema, e.g., '1.3'." },
        sceneDescription: { type: Type.STRING, description: "A brief, evocative description of the generated scene, suitable for a loading screen or title." },
        colorPalette: { type: Type.ARRAY, description: "A harmonious 5-color palette based on the prompt.", items: { type: Type.STRING, pattern: "^#[0-9a-fA-F]{6}$" } },
        qualityMetrics: {
            type: Type.OBJECT,
            properties: {
                estimatedPolyCount: { type: Type.INTEGER },
                textureResolution: { type: Type.INTEGER, description: "Recommended texture resolution, e.g., 2048 for 2K." },
                renderComplexity: { type: Type.STRING, enum: ['low', 'medium', 'high', 'ultra'] },
                estimatedRenderTime: { type: Type.NUMBER, description: "Estimated render time in seconds for a sample frame." }
            }
        },
        environment: {
            type: Type.OBJECT,
            properties: {
                skyType: { type: Type.STRING, description: "Type of sky. Examples: 'clear_day', 'sunset', 'starry_night', 'overcast'." },
                sunStrength: { type: Type.NUMBER, description: "The intensity of the main light source (sun). Range: 0.1 to 10." },
                ambientLightIntensity: { type: Type.NUMBER, description: "Intensity of the global ambient light, from 0.0 (dark) to 1.0 (full)." },
                ambientLightColor: { type: Type.STRING, description: "The hex color code for the ambient light, e.g., '#406080' for a bluish skylight." },
                mainLightType: { type: Type.STRING, description: "The type of the primary light source. Can be 'directional' (like a sun), 'point' (like a lamp), or 'spot'." }
            },
        },
        materials: { type: Type.ARRAY, description: "A library of reusable PBR materials for objects and terrain features in the scene.", items: pbrMaterialSchema },
        terrain: {
            type: Type.OBJECT,
            properties: {
                baseMaterialRef: { type: Type.STRING, description: "Reference to the name of the primary material for the terrain from the top-level 'materials' array." },
                elevationScale: { type: Type.NUMBER, description: "The overall height variation of the terrain. 0 is flat, higher numbers mean more mountainous." },
                heightmap: {
                    type: Type.OBJECT,
                    properties: {
                        resolution: { type: Type.INTEGER, description: "Grid resolution, e.g., 128 for a 128x128 heightmap." },
                        data: { type: Type.ARRAY, description: "Flattened array of height values (0.0-1.0). Length must be resolution*resolution.", items: { type: Type.NUMBER } },
                        noiseSettings: {
                            type: Type.OBJECT,
                            description: "Parameters for procedurally generating the heightmap if data is not provided.",
                            properties: { octaves: { type: Type.INTEGER }, persistence: { type: Type.NUMBER }, lacunarity: { type: Type.NUMBER }, seed: { type: Type.INTEGER } }
                        }
                    }
                },
                features: {
                    type: Type.ARRAY,
                    description: "Specific terrain features to add.",
                    items: { type: Type.OBJECT, properties: { type: { type: Type.STRING, description: "Type of feature, e.g., 'river', 'lake', 'winding_path'." }, materialRef: { type: Type.STRING, description: "Reference to the name of the material for this feature from the top-level 'materials' array." } }, required: ["type", "materialRef"] }
                }
            }
        },
        objects: {
            type: Type.ARRAY,
            description: "A list of standard objects to be scattered across the terrain.",
            items: {
                type: Type.OBJECT,
                properties: {
                    type: { type: Type.STRING, description: "The type of object, e.g., 'tree', 'rock', 'bush', 'flower_patch'." },
                    variant: { type: Type.STRING, description: "A specific variant of the object, e.g., 'pine_tree', 'oak_tree', 'large_boulder'." },
                    density: { type: Type.NUMBER, description: "How densely the objects are packed. Range 0.0 to 1.0." },
                    scale_variation: { type: Type.NUMBER, description: "The amount of random variation in the scale of each object. Range 0.0 to 1.0." },
                    min_distance: { type: Type.NUMBER, description: "The minimum distance between instances of this object, preventing clustering. In abstract Blender units. Omit if not specified." },
                    min_distance_from_feature: { type: Type.NUMBER, description: "The minimum distance this object type should be placed from any defined terrain feature (e.g., river, path). In abstract Blender units. Omit if not specified." },
                    materialRef: { type: Type.STRING, description: "Reference to the name of the material for this object from the top-level 'materials' array." },
                    useParticleSystem: { type: Type.BOOLEAN, description: "Set to true if density is high (>0.7) to suggest the backend use a particle system for efficiency." },
                    physics: physicsSchema,
                    lodVariants: { type: Type.ARRAY, description: "Level of Detail variants for this object, used for performance optimization.", items: { type: Type.OBJECT, properties: { level: { type: Type.STRING, enum: ['high', 'medium', 'low'] }, vertexCount: { type: Type.INTEGER }, materialRef: { type: Type.STRING, description: "Material for this LOD level, could be simpler than the main one." } } } },
                    animations: {
                        type: Type.ARRAY,
                        description: "Keyframe animations specific to this object variant, e.g., for wind sway on trees.",
                        items: {
                            type: Type.OBJECT,
                            properties: {
                                type: { type: Type.STRING, enum: ['rotation', 'position', 'scale'] },
                                keyframes: {
                                    type: Type.ARRAY,
                                    items: { type: Type.OBJECT, properties: { frame: { type: Type.INTEGER }, value: { type: Type.ARRAY, items: { type: Type.NUMBER } }, interpolation: { type: Type.STRING, enum: ['LINEAR', 'BEZIER', 'CONSTANT'] } } }
                                },
                                looping: { type: Type.BOOLEAN }
                            }
                        }
                    },
                },
                required: ["type", "variant", "density", "scale_variation", "materialRef"],
            }
        },
        vegetationSystem: {
            type: Type.OBJECT,
            properties: {
                biomes: {
                    type: Type.ARRAY,
                    items: {
                        type: Type.OBJECT,
                        properties: {
                            name: { type: Type.STRING },
                            coverage: { type: Type.NUMBER, description: "Percentage of terrain this biome covers." },
                            moistureRange: { type: Type.ARRAY, items: { type: Type.NUMBER }, description: "[min, max] moisture range." },
                            elevationRange: { type: Type.ARRAY, items: { type: Type.NUMBER }, description: "[min, max] elevation range." },
                            dominantSpecies: {
                                type: Type.ARRAY,
                                items: {
                                    type: Type.OBJECT,
                                    properties: {
                                        name: { type: Type.STRING, description: "Name of the object variant, which MUST correspond to a 'variant' in the top-level 'objects' array." },
                                        density: { type: Type.NUMBER, description: "Density of this species within the biome (0.0 to 1.0)." }
                                    },
                                    required: ['name', 'density']
                                },
                                description: "List of dominant species with their respective densities within this biome."
                            }
                        }
                    }
                },
                seasonalVariation: { type: Type.OBJECT, properties: { season: { type: Type.STRING, enum: ['spring', 'summer', 'autumn', 'winter'] }, foliageColor: { type: Type.STRING, pattern: "^#[0-9a-fA-F]{6}$" }, leafDensity: { type: Type.NUMBER, description: "Multiplier for leaf density, from 0.0 (bare) to 1.0 (full)." } } },
                foliageProperties: {
                     type: Type.OBJECT,
                     description: "General properties for foliage across the scene, can be overridden by biome or season.",
                     properties: {
                         baseDensity: { type: Type.NUMBER, description: "Overall foliage density multiplier (0.0 to 1.0)." },
                         health: { type: Type.NUMBER, description: "Overall health of vegetation, affecting color saturation and fullness (0.0 dead to 1.0 vibrant)." },
                         colorVariation: { type: Type.NUMBER, description: "Amount of random color variation between individual plants (0.0 uniform to 1.0 high variation)." }
                     }
                }
            }
        },
        sceneHierarchy: {
            type: Type.OBJECT,
            description: "Defines the scene's structure, including object collections, camera, and world settings.",
            properties: {
                collections: { type: Type.ARRAY, description: "Logical groupings of objects, similar to folders or layers.", items: { type: Type.OBJECT, properties: { name: { type: Type.STRING, description: "Name of the collection, e.g., 'Characters', 'EnvironmentProps'." }, objects: { type: Type.ARRAY, items: { type: Type.STRING }, description: "A list of object names (from 'objectsToCreate' or inferred scatter objects) belonging to this collection." } } } },
                camera: {
                    type: Type.OBJECT,
                    description: "Initial setup for the scene camera.",
                    properties: {
                        position: { type: Type.ARRAY, items: { type: Type.NUMBER }, description: "Camera position as [x, y, z]." },
                        rotation: { type: Type.ARRAY, items: { type: Type.NUMBER }, description: "Camera rotation as Euler angles [rx, ry, rz] in radians." },
                        lens: { type: Type.NUMBER, description: "Focal length in millimeters (e.g., 50 for standard, 24 for wide-angle)." },
                        clipStart: { type: Type.NUMBER, description: "Camera near clip distance." },
                        clipEnd: { type: Type.NUMBER, description: "Camera far clip distance." }
                    }
                },
                world: { type: Type.OBJECT, description: "World and background lighting settings.", properties: { backgroundColor: { type: Type.STRING, pattern: "^#[0-9a-fA-F]{6}$", description: "Background color if not using a procedural sky." }, strength: { type: Type.NUMBER, description: "Strength of the background light." }, proceduralSky: { type: Type.STRING, enum: ['nishita', 'none'], description: "Which procedural sky model to use. 'nishita' is physically-based." } } }
            }
        },
        weatherSystem: {
            type: Type.OBJECT,
            properties: {
                type: { type: Type.STRING, enum: ['none', 'rain', 'snow', 'fog', 'dust', 'leaves'] },
                intensity: { type: Type.NUMBER, description: "0.0 to 1.0" },
                windDirection: { type: Type.ARRAY, items: { type: Type.NUMBER }, description: "[x, y, z] vector" },
                windStrength: { type: Type.NUMBER },
                particleSettings: { type: Type.OBJECT, properties: { count: { type: Type.INTEGER }, size: { type: Type.NUMBER }, lifetime: { type: Type.NUMBER }, color: { type: Type.STRING, pattern: "^#[0-9a-fA-F]{6}$" } } }
            }
        },
        animations: {
            type: Type.OBJECT,
            properties: {
                objectAnimations: {
                    type: Type.ARRAY,
                    items: {
                        type: Type.OBJECT,
                        properties: {
                            objectName: { type: Type.STRING, description: "The name of the object to animate ('name' from created objects, 'variant' from scattered objects)." },
                            type: { type: Type.STRING, enum: ['rotation', 'position', 'scale'] },
                            keyframes: {
                                type: Type.ARRAY,
                                items: { type: Type.OBJECT, properties: { frame: { type: Type.INTEGER }, value: { type: Type.ARRAY, items: { type: Type.NUMBER }, description: "e.g., [x, y, z]" }, interpolation: { type: Type.STRING, enum: ['LINEAR', 'BEZIER', 'CONSTANT'] } } }
                            },
                            looping: { type: Type.BOOLEAN }
                        }
                    }
                },
                cameraAnimation: { type: Type.OBJECT, properties: { path: { type: Type.ARRAY, items: { type: Type.OBJECT, properties: { frame: { type: Type.INTEGER }, position: { type: Type.ARRAY, items: { type: Type.NUMBER } }, lookAt: { type: Type.ARRAY, items: { type: Type.NUMBER }, description: "A point [x,y,z] for the camera to track." } } } } } }
            }
        },
        textureBaking: {
            type: Type.OBJECT,
            properties: {
                enabled: { type: Type.BOOLEAN },
                resolution: { type: Type.INTEGER, enum: [512, 1024, 2048, 4096] },
                texturesToBake: { type: Type.ARRAY, items: { type: Type.STRING, enum: ['diffuse', 'normal', 'roughness', 'metallic', 'ambient_occlusion', 'emission'] } },
                sampleCount: { type: Type.INTEGER, description: "Bake quality, e.g., 128." }
            }
        },
        postProcessing: {
            type: Type.OBJECT,
            description: "Configuration for post-processing effects and render settings.",
            properties: {
                bloom: { type: Type.OBJECT, properties: { enabled: { type: Type.BOOLEAN }, intensity: { type: Type.NUMBER }, threshold: { type: Type.NUMBER }, knee: { type: Type.NUMBER } }, required: ["enabled", "intensity", "threshold", "knee"] },
                depthOfField: { type: Type.OBJECT, properties: { enabled: { type: Type.BOOLEAN }, focusDistance: { type: Type.NUMBER }, fStop: { type: Type.NUMBER }, blades: { type: Type.INTEGER } }, required: ["enabled", "focusDistance", "fStop", "blades"] },
                colorGrading: { type: Type.OBJECT, properties: { preset: { type: Type.STRING }, exposure: { type: Type.NUMBER }, contrast: { type: Type.NUMBER }, saturation: { type: Type.NUMBER } }, required: ["preset", "exposure", "contrast", "saturation"] },
                renderSettings: { type: Type.OBJECT, description: "Settings for the final render output.", properties: { engine: { type: Type.STRING, enum: ['CYCLES', 'EEVEE'], default: 'EEVEE' }, resolutionX: { type: Type.INTEGER, default: 1920 }, resolutionY: { type: Type.INTEGER, default: 1080 }, samples: { type: Type.INTEGER, description: "e.g., 128 for EEVEE, 1024 for Cycles." }, useDenoising: { type: Type.BOOLEAN } } }
            },
            required: ["bloom", "depthOfField", "colorGrading", "renderSettings"]
        }
    },
    required: ["schemaVersion", "sceneDescription", "environment", "materials", "terrain", "objects", "postProcessing", "sceneHierarchy"]
};

function validateGeneratedJSON(jsonData: any): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    const hexColorRegex = /^#[0-9a-fA-F]{6}$/;

    const checkColors = (obj: any, path: string) => {
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                const value = obj[key];
                const lowerKey = key.toLowerCase();
                if (typeof value === 'string' && (lowerKey.includes('color') || lowerKey === 'basecolor') && !value.startsWith('var(') ) {
                    if (!hexColorRegex.test(value)) {
                        errors.push(`Invalid hex color format at ${path}.${key}: '${value}'`);
                    }
                } else if (typeof value === 'object' && value !== null) {
                    checkColors(value, `${path}.${key}`);
                }
            }
        }
    };
    checkColors(jsonData, 'root');
    
    const materialNames = new Set(jsonData.materials?.map((m: any) => m.name) || []);
    const checkMaterialRef = (ref: string, context: string) => { if (ref && !materialNames.has(ref)) { errors.push(`${context} references undefined material: '${ref}'`); } };
    
    jsonData.terrain?.features?.forEach((f: any, i: number) => checkMaterialRef(f.materialRef, `Terrain feature #${i+1}`));
    jsonData.objects?.forEach((o: any, i: number) => checkMaterialRef(o.materialRef, `Scatter object #${i+1} ('${o.type}')`));
    jsonData.objectsToCreate?.forEach((o: any, i: number) => checkMaterialRef(o.materialRef, `Created object #${i+1} ('${o.name}')`));
    
    jsonData.objectsToCreate?.forEach((o: any, i: number) => {
        const vCount = o.meshData?.vertices?.length || 0;
        if (vCount === 0 && o.meshData?.faces?.length > 0) { errors.push(`Created object #${i+1} ('${o.name}') has faces but no vertices.`); }
        
        o.meshData?.faces?.forEach((face: number[], faceIdx: number) => face.forEach(idx => { if (idx < 0 || idx >= vCount) { errors.push(`Created object #${i+1} ('${o.name}'), face #${faceIdx+1} has invalid vertex index ${idx} (v count: ${vCount})`); } }));

        o.meshData?.uvs?.forEach((uv: number[], uvIdx: number) => {
            if (uv.length !== 2 || uv[0] < 0 || uv[0] > 1 || uv[1] < 0 || uv[1] > 1) {
                errors.push(`Created object #${i+1} ('${o.name}'), UV #${uvIdx+1} is invalid. Must be [u,v] between 0 and 1. Got: [${uv.join(', ')}]`);
            }
        });
    });

    const scatterVariants = new Set(jsonData.objects?.map((o: any) => o.variant) || []);
    jsonData.vegetationSystem?.biomes?.forEach((b: any, i: number) => {
        b.dominantSpecies?.forEach((s: any) => {
            if (!scatterVariants.has(s.name)) {
                errors.push(`Biome '${b.name}' references dominant species '${s.name}', but no scatter object with that variant exists.`);
            }
        });
    });
    
    return { valid: errors.length === 0, errors };
}

interface GenerationParams {
    prompt: string;
    image: { base64: string; mimeType: string } | null;
    terrainFeatures: TerrainFeature[];
    scatterObjects: ScatterObject[];
    lightingConfig: LightingConfig;
    postProcessingConfig: PostProcessingConfig;
    cameraConfig: CameraConfig;
    weatherConfig: WeatherConfig;
    bakingConfig: BakingConfig;
    vegetationConfig: VegetationConfig;
}

export async function generateBlenderData(params: GenerationParams): Promise<string> {
    const { prompt, image, terrainFeatures, scatterObjects, lightingConfig, postProcessingConfig, cameraConfig, weatherConfig, bakingConfig, vegetationConfig } = params;
    
    const model = 'gemini-2.5-flash';
    
    let systemPrompt = `You are an expert-level procedural content director for a Blender add-on. Your job is to take a user's high-level description and convert it into a detailed, structured JSON "recipe" that a Blender script can use to generate the 3D content. The JSON output MUST strictly conform to the provided schema.

Key responsibilities:
- Schema Conformance: Output only schema-conformant JSON. Start with schemaVersion '1.3'. Do not add conversational text.
- Mesh Topology: Generated meshes must have valid, manifold topology (watertight, no self-intersections) with a consistent Counter-Clockwise (CCW) winding order. Face indices must always be valid and within the bounds of the vertex array.
- UV Unwrapping: If generating mesh data, you MUST provide valid UV coordinates for all vertices.
- Logical Consistency: You MUST ensure that any 'materialRef' or other reference points to an entity that you have defined within the same JSON output. For biomes, 'dominantSpecies.name' MUST match a 'variant' from the top-level 'objects' array.
- PBR Materials: Create and reuse materials in the 'materials' array. Use physically-based values. Also, generate a harmonious 5-color palette based on the prompt.
- Scene Structure: Organize objects into logical collections in 'sceneHierarchy'. Use 'name' from 'objectsToCreate' or 'variant' from 'objects' as identifiers. Provide a sensible default camera.
- Procedural Materials: For complex materials, you can define a 'nodeTree' to describe a procedural shader graph.
- Ecological Systems: For natural scenes, define biomes, seasonal variations, and general foliage properties in 'vegetationSystem'.`;
    
    const finalSchema = JSON.parse(JSON.stringify(baseSceneSpecSchema));

    if (image) {
        systemPrompt += `\n\nYour primary task is to analyze the reference image and prompt to generate a detailed 3D object in 'objectsToCreate'. Infer 'approximateScale', 'colorPalette', 'materialType'. Create a new PBR material for it in the 'materials' array and reference it by name in 'materialRef'. Then, generate the 'meshData' including a text description. If the prompt describes a broader scene, integrate the created object naturally.`;
        (finalSchema.properties as any).objectsToCreate = { type: Type.ARRAY, description: "3D objects generated from image references.", items: createdObjectSchema };
    } else {
         systemPrompt += `\n\nBe creative and fill in details based on the prompt. For a "forest", create materials for ground/trees, define tree scatter objects, and set up a forest environment. For a "desert", create sand materials and dune-like terrain.`;
    }

    try {
        const contentParts = [];
        if (image) {
            contentParts.push({inlineData: {data: image.base64, mimeType: image.mimeType}});
        }

        const promptParts = [];
        promptParts.push(`User prompt: "${prompt}"`);
        
        promptParts.push(`LIGHTING: Use preset '${lightingConfig.preset}' as a guide. Set exact values: Ambient Intensity: ${lightingConfig.ambientIntensity}, Ambient Color: "${lightingConfig.ambientColor}", Main Light Type: "${lightingConfig.lightType}".`);
        promptParts.push(`CAMERA: Use preset '${cameraConfig.preset}' to guide position. Set exact settings: Lens: ${cameraConfig.lens}mm, Clip Start: ${cameraConfig.clipStart}m, Clip End: ${cameraConfig.clipEnd}m.`);
        if (weatherConfig.type !== 'none') promptParts.push(`WEATHER: You MUST populate 'weatherSystem' with: Type: '${weatherConfig.type}', Intensity: ${weatherConfig.intensity}, Wind Strength: ${weatherConfig.windStrength}, Wind Direction: [${weatherConfig.windDirection.join(', ')}].`);
        if (bakingConfig.enabled) promptParts.push(`TEXTURE BAKING: You MUST populate 'textureBaking': Enabled: true, Resolution: ${bakingConfig.resolution}, Maps: [${bakingConfig.maps.map(m => `'${m}'`).join(', ')}], Sample Count: ${bakingConfig.sampleCount}.`);

        if (terrainFeatures.length > 0) promptParts.push(`TERRAIN FEATURES: Create materials and features for: ${terrainFeatures.map(f => `'${f.type}' with material '${f.material}'`).join(', ')}.`);
        if (scatterObjects.length > 0) promptParts.push(`SCATTER OBJECTS: Create materials and objects for: ${scatterObjects.map(o => `'${o.type}' with density ${o.density.toFixed(2)}`).join(', ')}.`);
        
        const { biomes, activeSeason, seasonalVariations, foliageProperties } = vegetationConfig;
        if (biomes.length > 0 || activeSeason !== 'none') {
             let vegInstructions = `VEGETATION SYSTEM: Populate 'vegetationSystem'.\n`;
             if (activeSeason !== 'none') {
                const seasonSettings = seasonalVariations[activeSeason as keyof SeasonalVariations];
                vegInstructions += `- Active season is '${activeSeason}'. Use settings: Foliage Color: '${seasonSettings.foliageColor}', Leaf Density: ${seasonSettings.leafDensity.toFixed(2)}.\n`;
            }
             vegInstructions += `- General foliage properties: baseDensity: ${foliageProperties.baseDensity.toFixed(2)}, health: ${foliageProperties.health.toFixed(2)}, colorVariation: ${foliageProperties.colorVariation.toFixed(2)}.\n`;
             if (biomes.length > 0) vegInstructions += `- Define biomes: ${biomes.map(b => `'${b.name}'`).join(', ')}.\n`;
             promptParts.push(vegInstructions);
        }

        promptParts.push(`POST-PROCESSING: Use these exact 'postProcessing' settings: ${JSON.stringify(postProcessingConfig)}`);
        promptParts.push(`QUALITY GUIDELINES: Generate meshes with clean topology. Set schemaVersion to '1.3'.`);

        const fullPrompt = promptParts.join('\n\n');
        contentParts.push({text: fullPrompt});

        const response = await ai.models.generateContent({
            model: model,
            contents: { parts: contentParts },
            config: {
                systemInstruction: systemPrompt,
                responseMimeType: "application/json",
                responseSchema: finalSchema,
            },
        });
        
        const jsonString = response.text;
        try {
            const parsedJson = JSON.parse(jsonString);
            const validationResult = validateGeneratedJSON(parsedJson);
            if (!validationResult.valid) {
                throw new Error(`AI returned logically invalid JSON. Details: ${validationResult.errors.join('; ')}`);
            }
            return JSON.stringify(parsedJson, null, 2);
        } catch (jsonError) {
            console.error("Gemini returned invalid JSON or failed validation:", jsonString, jsonError);
            if (jsonError instanceof Error) {
                 throw new Error(`The AI returned a response that was not valid or logical JSON. Please try regenerating. Details: ${jsonError.message}`);
            }
            throw new Error("The AI returned a response that was not valid or logical JSON. Please try regenerating.");
        }

    } catch (error) {
        console.error("Error calling Gemini API:", error);
        if (error instanceof Error) {
            throw new Error(`Gemini API Error: ${error.message}`);
        }
        throw new Error("An unexpected error occurred while communicating with the Gemini API.");
    }
}
