import { constructPrompt } from './prompt-constructor';
import { GenerationParams } from './types';
import {
    LightingConfig,
    CameraConfig,
    WeatherConfig,
    BakingConfig,
    PostProcessingConfig,
    VegetationConfig
} from '../App';

describe('constructPrompt', () => {
    it('should construct a prompt with all the required parts', () => {
        const params: GenerationParams = {
            prompt: 'A mystical forest',
            image: null,
            terrainFeatures: [],
            scatterObjects: [],
            lightingConfig: {
                preset: 'Default',
                ambientIntensity: 0.2,
                ambientColor: '#FFFFFF',
                lightType: 'directional',
            },
            postProcessingConfig: {
                bloom: { enabled: false, intensity: 0.05, threshold: 0.8, knee: 0.7 },
                depthOfField: { enabled: false, focusDistance: 10.0, fStop: 2.8, blades: 6 },
                colorGrading: { preset: 'None', exposure: 1.0, contrast: 0.0, saturation: 1.0 },
            },
            cameraConfig: {
                preset: 'Default',
                lens: 50,
                clipStart: 0.1,
                clipEnd: 1000,
            },
            weatherConfig: {
                type: 'none',
                intensity: 0.5,
                windStrength: 0.2,
                windDirection: [1, 0, 0]
            },
            bakingConfig: {
                enabled: false,
                resolution: 2048,
                maps: ['diffuse', 'normal', 'roughness'],
                sampleCount: 64,
            },
            vegetationConfig: {
                biomes: [],
                activeSeason: 'none',
                seasonalVariations: {
                    spring: { foliageColor: '#6A994E', leafDensity: 0.9 },
                    summer: { foliageColor: '#386641', leafDensity: 1.0 },
                    autumn: { foliageColor: '#BC4749', leafDensity: 0.6 },
                    winter: { foliageColor: '#A3A3A3', leafDensity: 0.1 },
                },
                foliageProperties: {
                    baseDensity: 0.8,
                    health: 1.0,
                    colorVariation: 0.2,
                },
            },
        };

        const prompt = constructPrompt(params);

        expect(prompt).toContain('User prompt: "A mystical forest"');
        expect(prompt).toContain('LIGHTING: Use preset \'Default\' as a guide. Set exact values: Ambient Intensity: 0.2, Ambient Color: "#FFFFFF", Main Light Type: "directional".');
        expect(prompt).toContain('CAMERA: Use preset \'Default\' to guide position. Set exact settings: Lens: 50mm, Clip Start: 0.1m, Clip End: 1000m.');
        expect(prompt).toContain('POST-PROCESSING: Use these exact \'postProcessing\' settings: {"bloom":{"enabled":false,"intensity":0.05,"threshold":0.8,"knee":0.7},"depthOfField":{"enabled":false,"focusDistance":10,"fStop":2.8,"blades":6},"colorGrading":{"preset":"None","exposure":1,"contrast":0,"saturation":1}}');
        expect(prompt).toContain('QUALITY GUIDELINES: Generate meshes with clean topology. Set schemaVersion to \'1.3\'.');
    });
});
