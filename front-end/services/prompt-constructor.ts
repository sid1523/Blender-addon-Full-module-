import type { GenerationParams } from './types';

export function constructPrompt(params: GenerationParams): string {
    const {
        prompt,
        lightingConfig,
        cameraConfig,
        weatherConfig,
        bakingConfig,
        terrainFeatures,
        scatterObjects,
        vegetationConfig,
        postProcessingConfig
    } = params;

    const promptParts = [];
    promptParts.push(`User prompt: "${prompt}"`);

    promptParts.push(`LIGHTING: Use preset '${lightingConfig.preset}' as a guide. Set exact values: Ambient Intensity: ${lightingConfig.ambientIntensity}, Ambient Color: "${lightingConfig.ambientColor}", Main Light Type: "${lightingConfig.lightType}".`);
    promptParts.push(`CAMERA: Use preset '${cameraConfig.preset}' to guide position. Set exact settings: Lens: ${cameraConfig.lens}mm, Clip Start: ${cameraConfig.clipStart}m, Clip End: ${cameraConfig.clipEnd}m.`);
    if (weatherConfig.type !== 'none') {
        promptParts.push(`WEATHER: You MUST populate 'weatherSystem' with: Type: '${weatherConfig.type}', Intensity: ${weatherConfig.intensity}, Wind Strength: ${weatherConfig.windStrength}, Wind Direction: [${weatherConfig.windDirection.join(', ')}].`);
    }
    if (bakingConfig.enabled) {
        promptParts.push(`TEXTURE BAKING: You MUST populate 'textureBaking': Enabled: true, Resolution: ${bakingConfig.resolution}, Maps: [${bakingConfig.maps.map(m => `'${m}'`).join(', ')}], Sample Count: ${bakingConfig.sampleCount}.`);
    }

    if (terrainFeatures.length > 0) {
        promptParts.push(`TERRAIN FEATURES: Create materials and features for: ${terrainFeatures.map(f => `'${f.type}' with material '${f.material}'`).join(', ')}.`);
    }
    if (scatterObjects.length > 0) {
        promptParts.push(`SCATTER OBJECTS: Create materials and objects for: ${scatterObjects.map(o => `'${o.type}' with density ${o.density.toFixed(2)}`).join(', ')}.`);
    }

    const { biomes, activeSeason, seasonalVariations, foliageProperties } = vegetationConfig;
    if (biomes.length > 0 || activeSeason !== 'none') {
        let vegInstructions = `VEGETATION SYSTEM: Populate 'vegetationSystem'.\n`;
        if (activeSeason !== 'none') {
            const seasonSettings = seasonalVariations[activeSeason as keyof typeof seasonalVariations];
            vegInstructions += `- Active season is '${activeSeason}'. Use settings: Foliage Color: '${seasonSettings.foliageColor}', Leaf Density: ${seasonSettings.leafDensity.toFixed(2)}.\n`;
        }
        vegInstructions += `- General foliage properties: baseDensity: ${foliageProperties.baseDensity.toFixed(2)}, health: ${foliageProperties.health.toFixed(2)}, colorVariation: ${foliageProperties.colorVariation.toFixed(2)}.\n`;
        if (biomes.length > 0) {
            vegInstructions += `- Define biomes: ${biomes.map(b => `'${b.name}'`).join(', ')}.\n`;
        }
        promptParts.push(vegInstructions);
    }

    promptParts.push(`POST-PROCESSING: Use these exact 'postProcessing' settings: ${JSON.stringify(postProcessingConfig)}`);
    promptParts.push(`QUALITY GUIDELINES: Generate meshes with clean topology. Set schemaVersion to '1.3'.`);

    return promptParts.join('\n\n');
}
