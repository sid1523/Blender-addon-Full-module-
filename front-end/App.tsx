
import React, { useState, useCallback } from 'react';
import Header from './components/Header';
import { ProjectInput } from './components/ProjectInput';
import AnalysisDisplay from './components/AnalysisDisplay';
import Loader from './components/Loader';
import ErrorMessage from './components/ErrorMessage';
import { generateBlenderData, enhancePrompt } from './services/geminiService';
import LandingPage from './components/LandingPage';
import PromptingGuideModal from './components/PromptingGuideModal';

// Helper to convert file to base64
const fileToBase64 = (file: File): Promise<{ base64: string; mimeType: string }> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(',')[1];
      resolve({ base64, mimeType: file.type });
    };
    reader.onerror = (error) => reject(error);
  });
};

export interface TerrainFeature {
  type: string;
  material: string;
  roughness?: number;
  metallic?: number;
  specular?: number;
}

export interface LodVariant {
  level: 'high' | 'medium' | 'low';
  vertexCount: number;
}

export interface ScatterObject {
  type: string;
  density: number;
  scale_variation: number;
  min_distance: number;
  min_distance_from_feature: number;
  roughness?: number;
  metallic?: number;
  specular?: number;
  // Physics Properties
  collisionType?: 'mesh' | 'convex_hull' | 'box' | 'sphere' | 'none';
  mass?: number;
  friction?: number;
  restitution?: number;
  isDynamic?: boolean;
  // LOD Properties
  lodVariants?: LodVariant[];
}

export interface DominantSpecies {
  name: string;
  density: number;
}

export interface Biome {
  name: string;
  dominantSpecies: DominantSpecies[];
  coverage: number;
  moistureRange: [number, number];
  elevationRange: [number, number];
}

export interface FoliageProperties {
  baseDensity: number;
  health: number;
  colorVariation: number;
}

export interface SeasonalVariation {
  foliageColor: string;
  leafDensity: number;
}

export interface SeasonalVariations {
  spring: SeasonalVariation;
  summer: SeasonalVariation;
  autumn: SeasonalVariation;
  winter: SeasonalVariation;
}

// Config object interfaces for better state management
export interface PostProcessingConfig {
  bloom: { enabled: boolean; intensity: number; threshold: number; knee: number; };
  depthOfField: { enabled: boolean; focusDistance: number; fStop: number; blades: number; };
  colorGrading: { preset: string; exposure: number; contrast: number; saturation: number; };
}
export interface CameraConfig { preset: string; lens: number; clipStart: number; clipEnd: number; }
export interface WeatherConfig { type: string; intensity: number; windStrength: number; windDirection: [number, number, number]; }
export interface BakingConfig { enabled: boolean; resolution: number; maps: string[]; sampleCount: number; }
export interface LightingConfig { preset: string; ambientIntensity: number; ambientColor: string; lightType: string; }
export interface VegetationConfig {
  biomes: Biome[];
  activeSeason: string;
  seasonalVariations: SeasonalVariations;
  foliageProperties: FoliageProperties;
}


interface ScenePreset {
  prompt: string;
  lightingPreset: string;
  terrainFeatures: TerrainFeature[];
  scatterObjects: ScatterObject[];
}

export const scenePresets: Record<string, Partial<ScenePreset>> = {
  'Custom': {},
  'Mystical Forest': {
    prompt: 'An ancient, mystical forest with glowing mushrooms and ethereal fog at dusk. Ancient, moss-covered trees with twisted roots dominate the landscape.',
    lightingPreset: 'Mystical Fog',
    terrainFeatures: [{ type: 'winding_path', material: 'mossy stone path', roughness: 0.8, metallic: 0.0, specular: 0.3 }],
    scatterObjects: [
      { type: 'glowing_mushroom', density: 0.6, scale_variation: 0.7, min_distance: 1.5, min_distance_from_feature: 0.5, roughness: 0.4, metallic: 0.0, specular: 0.5, collisionType: 'mesh', mass: 0.1, friction: 0.7, restitution: 0.2, isDynamic: false, lodVariants: [] },
      { type: 'ancient_twisted_tree', density: 0.2, scale_variation: 0.4, min_distance: 8.0, min_distance_from_feature: 3.0, roughness: 0.9, metallic: 0.0, specular: 0.2, collisionType: 'mesh', mass: 500, friction: 0.8, restitution: 0.1, isDynamic: false, lodVariants: [] },
    ]
  },
  'Desert Oasis': {
    prompt: 'A small, vibrant desert oasis surrounding a shimmering pool of clear water. The sun is high in the sky, casting sharp shadows on the golden sand dunes.',
    lightingPreset: 'Harsh Desert Sun',
    terrainFeatures: [{ type: 'water_pool', material: 'clear_water', roughness: 0.05, metallic: 0.0, specular: 0.8 }],
    scatterObjects: [
      { type: 'palm_tree', density: 0.3, scale_variation: 0.5, min_distance: 4.0, min_distance_from_feature: 1.0, roughness: 0.7, metallic: 0.0, specular: 0.3, collisionType: 'convex_hull', mass: 150, friction: 0.6, restitution: 0.4, isDynamic: true, lodVariants: [] }
    ]
  },
};

const App: React.FC = () => {
  const [view, setView] = useState<'landing' | 'generator'>('landing');
  const [isGuideOpen, setIsGuideOpen] = useState(false);
  
  const [scenePreset, setScenePreset] = useState<string>('Custom');
  const [prompt, setPrompt] = useState<string>('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [terrainFeatures, setTerrainFeatures] = useState<TerrainFeature[]>([]);
  const [scatterObjects, setScatterObjects] = useState<ScatterObject[]>([]);
  
  const [lightingConfig, setLightingConfig] = useState<LightingConfig>({
    preset: 'Default',
    ambientIntensity: 0.2,
    ambientColor: '#FFFFFF',
    lightType: 'directional',
  });

  const [postProcessingConfig, setPostProcessingConfig] = useState<PostProcessingConfig>({
    bloom: { enabled: false, intensity: 0.05, threshold: 0.8, knee: 0.7 },
    depthOfField: { enabled: false, focusDistance: 10.0, fStop: 2.8, blades: 6 },
    colorGrading: { preset: 'None', exposure: 1.0, contrast: 0.0, saturation: 1.0 },
  });
  
  const [cameraConfig, setCameraConfig] = useState<CameraConfig>({
    preset: 'Default', lens: 50, clipStart: 0.1, clipEnd: 1000,
  });

  const [weatherConfig, setWeatherConfig] = useState<WeatherConfig>({
    type: 'none', intensity: 0.5, windStrength: 0.2, windDirection: [1, 0, 0]
  });

  const [bakingConfig, setBakingConfig] = useState<BakingConfig>({
    enabled: false, resolution: 2048, maps: ['diffuse', 'normal', 'roughness'], sampleCount: 64,
  });
  
  const [vegetationConfig, setVegetationConfig] = useState<VegetationConfig>({
    biomes: [],
    activeSeason: 'none',
    seasonalVariations: {
      spring: { foliageColor: '#6A994E', leafDensity: 0.9 },
      summer: { foliageColor: '#386641', leafDensity: 1.0 },
      autumn: { foliageColor: '#BC4749', leafDensity: 0.6 },
      winter: { foliageColor: '#A3A3A3', leafDensity: 0.1 },
    },
    foliageProperties: {
      baseDensity: 0.8, health: 1.0, colorVariation: 0.2,
    },
  });

  const [sceneSpec, setSceneSpec] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isEnhancing, setIsEnhancing] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const handlePresetChange = useCallback((presetName: string) => {
    setScenePreset(presetName);
    if (presetName === 'Custom') return;

    const preset = scenePresets[presetName];
    if (!preset) return;

    setPrompt(preset.prompt || '');
    setLightingConfig(prev => ({...prev, preset: preset.lightingPreset || 'Default'}));
    setTerrainFeatures(preset.terrainFeatures || []);
    setScatterObjects(preset.scatterObjects || []);
  }, []);
  
  const handleAnyChange = useCallback(() => {
    setScenePreset('Custom');
  }, []);

  const handleImageChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  }, []);

  const clearImage = useCallback(() => {
    setImageFile(null);
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
      setImagePreview(null);
    }
  }, [imagePreview]);

  const handleAddFeature = useCallback((feature: TerrainFeature) => {
    if (feature.type.trim() && feature.material.trim()) {
      setTerrainFeatures(prev => [...prev, feature]);
      handleAnyChange();
    }
  }, [handleAnyChange]);

  const handleRemoveFeature = useCallback((indexToRemove: number) => {
    setTerrainFeatures(prev => prev.filter((_, index) => index !== indexToRemove));
    handleAnyChange();
  }, [handleAnyChange]);

  const handleAddScatterObject = useCallback((object: ScatterObject) => {
    if (object.type.trim()) {
      setScatterObjects(prev => [...prev, object]);
      handleAnyChange();
    }
  }, [handleAnyChange]);
  
  const handleUpdateScatterObject = useCallback((indexToUpdate: number, updatedObject: ScatterObject) => {
    setScatterObjects(prev => prev.map((obj, index) => 
        index === indexToUpdate ? updatedObject : obj
    ));
    handleAnyChange();
  }, [handleAnyChange]);

  const handleRemoveScatterObject = useCallback((indexToRemove: number) => {
    setScatterObjects(prev => prev.filter((_, index) => index !== indexToRemove));
    handleAnyChange();
  }, [handleAnyChange]);

  const handleEnhancePrompt = useCallback(async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt to enhance.');
      return;
    }
    setIsEnhancing(true);
    setError('');
    
    try {
      const enhanced = await enhancePrompt(prompt);
      setPrompt(enhanced);
      handleAnyChange();
    } catch (e) {
      console.error(e);
      const errorMessage = e instanceof Error ? e.message : 'An unknown error occurred.';
      setError(`Failed to enhance prompt. ${errorMessage}`);
    } finally {
      setIsEnhancing(false);
    }
  }, [prompt, handleAnyChange]);


  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) {
      setError('Please enter a description or prompt.');
      return;
    }
    setIsLoading(true);
    setError('');
    setSceneSpec('');

    try {
      let imagePayload: { base64: string; mimeType: string } | null = null;
      if (imageFile) {
        imagePayload = await fileToBase64(imageFile);
      }
      const result = await generateBlenderData({
          prompt,
          image: imagePayload,
          terrainFeatures,
          scatterObjects,
          lightingConfig,
          postProcessingConfig,
          cameraConfig,
          weatherConfig,
          bakingConfig,
          vegetationConfig,
      });
      setSceneSpec(result);
    } catch (e) {
      console.error(e);
      const errorMessage = e instanceof Error ? e.message : 'An unknown error occurred.';
      setError(`Failed to generate specification. ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  }, [
    prompt, imageFile, terrainFeatures, scatterObjects, lightingConfig, postProcessingConfig,
    cameraConfig, weatherConfig, bakingConfig, vegetationConfig
  ]);
  
  if (view === 'landing') {
    return <LandingPage onStart={() => setView('generator')} />;
  }

  return (
    <>
      <div className="min-h-screen bg-gray-900/50 text-gray-200 flex flex-col font-sans">
        <Header onOpenGuide={() => setIsGuideOpen(true)} />
        <main className="flex-grow container mx-auto px-4 py-8 flex flex-col lg:flex-row gap-8">
          <div className="lg:w-1/2 flex flex-col">
            <ProjectInput
              scenePreset={scenePreset}
              onScenePresetChange={handlePresetChange}
              prompt={prompt}
              onPromptChange={(e) => { setPrompt(e.target.value); handleAnyChange(); }}
              onImageChange={handleImageChange}
              onClearImage={clearImage}
              imagePreview={imagePreview}
              onGenerate={handleGenerate}
              onEnhance={handleEnhancePrompt}
              isLoading={isLoading}
              isEnhancing={isEnhancing}
              terrainFeatures={terrainFeatures}
              onAddFeature={handleAddFeature}
              onRemoveFeature={handleRemoveFeature}
              scatterObjects={scatterObjects}
              onAddScatterObject={handleAddScatterObject}
              onRemoveScatterObject={handleRemoveScatterObject}
              onUpdateScatterObject={handleUpdateScatterObject}
              lightingConfig={lightingConfig}
              onLightingConfigChange={(key, value) => { setLightingConfig(p => ({...p, [key]: value})); handleAnyChange(); }}
              postProcessingConfig={postProcessingConfig}
              onPostProcessingConfigChange={(group, key, value) => {
                setPostProcessingConfig(p => ({
                  ...p,
                  [group]: { ...p[group], [key]: value }
                }));
                handleAnyChange();
              }}
              cameraConfig={cameraConfig}
              onCameraConfigChange={(key, value) => { setCameraConfig(p => ({...p, [key]: value})); handleAnyChange(); }}
              weatherConfig={weatherConfig}
              onWeatherConfigChange={(key, value) => {
                 if (key === 'windDirectionX') {
                    setWeatherConfig(p => ({ ...p, windDirection: [value as number, p.windDirection[1], p.windDirection[2]] }));
                } else if (key === 'windDirectionY') {
                    setWeatherConfig(p => ({ ...p, windDirection: [p.windDirection[0], value as number, p.windDirection[2]] }));
                } else {
                    setWeatherConfig(p => ({...p, [key]: value}));
                }
                handleAnyChange();
              }}
              bakingConfig={bakingConfig}
              onBakingConfigChange={(key, value) => { setBakingConfig(p => ({...p, [key]: value})); handleAnyChange(); }}
              vegetationConfig={vegetationConfig}
              onVegetationConfigChange={(group, key, value, subKey) => {
                if (group === 'seasonalVariations') {
                   setVegetationConfig(p => ({...p, seasonalVariations: { ...p.seasonalVariations, [key]: { ...p.seasonalVariations[key as keyof SeasonalVariations], [subKey!]: value }}}));
                } else if (group === 'foliageProperties') {
                   setVegetationConfig(p => ({...p, foliageProperties: { ...p.foliageProperties, [key]: value }}));
                } else {
                   setVegetationConfig(p => ({...p, [key]: value }));
                }
                handleAnyChange();
              }}
              onAddBiome={(biome) => { setVegetationConfig(p => ({...p, biomes: [...p.biomes, biome]})); handleAnyChange(); }}
              onRemoveBiome={(index) => { setVegetationConfig(p => ({...p, biomes: p.biomes.filter((_, i) => i !== index)})); handleAnyChange(); }}
              onUpdateBiome={(index, biome) => { setVegetationConfig(p => ({...p, biomes: p.biomes.map((b, i) => i === index ? biome : b)})); handleAnyChange(); }}
            />
          </div>
          <div className="lg:w-1/2 flex flex-col">
            <div className="bg-gray-800 rounded-lg shadow-2xl flex-grow h-[75vh] lg:h-auto flex flex-col">
              <div className="p-4 border-b border-gray-700 flex justify-between items-center">
                <h2 className="text-xl font-bold text-cyan-400">Generated Recipe (JSON)</h2>
              </div>
              <div className="p-6 overflow-hidden flex-grow relative">
                {isLoading && <Loader />}
                {error && <ErrorMessage message={error} />}
                {sceneSpec && <AnalysisDisplay content={sceneSpec} />}
                {!isLoading && !error && !sceneSpec && (
                  <div className="text-center text-gray-500 flex items-center justify-center h-full">
                    <p>Your generated world recipe will appear here.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
      <PromptingGuideModal isOpen={isGuideOpen} onClose={() => setIsGuideOpen(false)} />
    </>
  );
};

export default App;
