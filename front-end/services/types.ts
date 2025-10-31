import {
    TerrainFeature,
    ScatterObject,
    Biome,
    FoliageProperties,
    SeasonalVariations,
    LightingConfig,
    CameraConfig,
    WeatherConfig,
    BakingConfig,
    PostProcessingConfig,
    VegetationConfig
} from '../App';

export interface GenerationParams {
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
