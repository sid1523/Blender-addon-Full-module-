
import React, { useState } from 'react';
import type { TerrainFeature, ScatterObject, LodVariant, Biome, FoliageProperties, DominantSpecies, SeasonalVariations, SeasonalVariation, LightingConfig, CameraConfig, WeatherConfig, BakingConfig, PostProcessingConfig, VegetationConfig } from '../App';
import { scenePresets } from '../App';
import Tooltip from './Tooltip';
import { generateColorPalette } from '../services/geminiService';

// --- Reusable Slider with Numeric Input Component ---
const SliderInput = ({ label, tooltip, value, onChange, min, max, step }: { label: string, tooltip: string, value: number, onChange: (val: number) => void, min: number, max: number, step: number }) => {
    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        onChange(parseFloat(e.target.value));
    };
    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) {
            onChange(Math.max(min, Math.min(max, val)));
        }
    };

    return (
        <div>
            <label className="block text-gray-400 mb-1 text-sm flex items-center">{label}<Tooltip text={tooltip} /></label>
            <div className="flex items-center gap-3">
                <input type="range" min={min} max={max} step={step} value={value} onChange={handleSliderChange} className="w-full" />
                <input type="number" min={min} max={max} step={step} value={value} onChange={handleInputChange} className="w-20 bg-gray-700 border border-gray-600 rounded-md p-1 text-center text-gray-300 focus:ring-1 focus:ring-cyan-500" />
            </div>
        </div>
    );
};

// --- Main Props Interface ---
interface ProjectInputProps {
  scenePreset: string;
  onScenePresetChange: (preset: string) => void;
  prompt: string;
  onPromptChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onImageChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onClearImage: () => void;
  imagePreview: string | null;
  onGenerate: () => void;
  onEnhance: () => void;
  isLoading: boolean;
  isEnhancing: boolean;
  terrainFeatures: TerrainFeature[];
  onAddFeature: (feature: TerrainFeature) => void;
  onRemoveFeature: (index: number) => void;
  scatterObjects: ScatterObject[];
  onAddScatterObject: (object: ScatterObject) => void;
  onRemoveScatterObject: (index: number) => void;
  onUpdateScatterObject: (index: number, object: ScatterObject) => void;
  lightingConfig: LightingConfig;
  onLightingConfigChange: (key: keyof LightingConfig, value: any) => void;
  postProcessingConfig: PostProcessingConfig;
  onPostProcessingConfigChange: (group: keyof PostProcessingConfig, key: string, value: any) => void;
  cameraConfig: CameraConfig;
  onCameraConfigChange: (key: keyof CameraConfig, value: any) => void;
  weatherConfig: WeatherConfig;
  onWeatherConfigChange: (key: string, value: any) => void;
  bakingConfig: BakingConfig;
  onBakingConfigChange: (key: keyof BakingConfig, value: any) => void;
  vegetationConfig: VegetationConfig;
  onVegetationConfigChange: (group: string, key: string, value: any, subKey?: string) => void;
  onAddBiome: (biome: Biome) => void;
  onRemoveBiome: (index: number) => void;
  onUpdateBiome: (index: number, biome: Biome) => void;
}

const lightingPresets = [
    'Default', 'Bright Daylight', 'Golden Hour', 'Deep Night', 'Overcast Gloom',
    'Dramatic Sunset', 'Mystical Fog', 'Sci-Fi Neon', 'Ethereal Dawn', 'Harsh Desert Sun'
];
const postProcessingPresets = [
    'None', 'Cinematic Warm', 'Cool Tone', 'Vibrant Pop',
    'Gritty Film Noir', 'Dreamy Haze', 'Vintage Sepia', 'Horror Gloom'
];
const allBakingMaps = ['diffuse', 'normal', 'roughness', 'metallic', 'ambient_occlusion', 'emission'];

const ControlSection: React.FC<{ title: string; tooltip: string; children: React.ReactNode; defaultOpen?: boolean }> = ({ title, tooltip, children, defaultOpen = false }) => (
    <details className="bg-gray-900/50 rounded-lg border border-gray-700 open:shadow-lg open:shadow-cyan-500/10 open:border-gray-600/70 transition-all duration-300 group" open={defaultOpen}>
        <summary className="font-semibold text-lg p-4 cursor-pointer flex justify-between items-center text-gray-300 hover:text-white list-none">
            <div className="flex items-center">
                 {title}
                <Tooltip text={tooltip} />
            </div>
            <svg className="w-5 h-5 transform transition-transform duration-300 text-gray-500 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
            </svg>
        </summary>
        <div className="p-4 border-t border-gray-700/80">
            {children}
        </div>
        <style>{`
            details summary::-webkit-details-marker { display: none; }
        `}</style>
    </details>
);

export const ProjectInput: React.FC<ProjectInputProps> = (props) => {
  const { onGenerate, isLoading, isEnhancing, prompt } = props;
  
  const [colorPalette, setColorPalette] = useState<string[]>([]);
  const [isPaletteLoading, setIsPaletteLoading] = useState(false);
  const [paletteError, setPaletteError] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !isLoading) {
      onGenerate();
    }
  };
  
  const handleSuggestPalette = async () => {
      if (!prompt.trim()) {
          setPaletteError('Please enter a prompt to suggest a palette.');
          return;
      }
      setIsPaletteLoading(true);
      setPaletteError('');
      try {
          const palette = await generateColorPalette(prompt);
          setColorPalette(palette);
      } catch(e) {
          setPaletteError(e instanceof Error ? e.message : 'Failed to get palette.');
      } finally {
          setIsPaletteLoading(false);
      }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  }

  return (
    <div className="bg-gray-800 rounded-lg shadow-2xl flex flex-col h-full border border-gray-700/50">
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-xl font-bold text-cyan-400">Scene & Model Controls</h2>
      </div>
      <div className="p-6 flex-grow flex flex-col overflow-y-auto space-y-4">
        {/* --- Main Prompt Section --- */}
        <div className="space-y-4">
            <div>
                <label className="block text-gray-400 mb-2 font-semibold flex items-center">
                    Scene Preset
                    <Tooltip text="Select a preset to quickly load a starting configuration for your scene." />
                </label>
                <select value={props.scenePreset} onChange={e => props.onScenePresetChange(e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded-md p-2 text-gray-300 focus:ring-1 focus:ring-cyan-500 focus:shadow-[0_0_15px_rgba(56,189,248,0.3)]">
                    {Object.keys(scenePresets).map(p => <option key={p} value={p}>{p}</option>)}
                </select>
            </div>
            <div>
                <label className="block text-gray-400 mb-2 font-semibold flex items-center">
                    Prompt
                    <Tooltip text="Describe the overall scene, environment, or the 3D model you want to generate. Be as descriptive as you like. You can use the 'Enhance' button to let the AI enrich your idea." />
                </label>
                <div className="relative flex items-center">
                  <input
                    type="text" value={prompt} onChange={props.onPromptChange} onKeyDown={handleKeyDown}
                    placeholder="e.g., 'a barren desert' or 'a low-poly model of this character'"
                    className="w-full bg-gray-900 border border-gray-700 rounded-md p-4 pr-28 text-gray-300 text-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 transition-shadow duration-300"
                    disabled={isLoading || isEnhancing} aria-label="Scene prompt input"
                  />
                   <button 
                      onClick={props.onEnhance} disabled={isLoading || isEnhancing || !prompt.trim()}
                      className="absolute right-2.5 bg-gray-700 hover:bg-cyan-600 text-white font-semibold py-2 px-3 rounded-md text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                      aria-label="Enhance prompt"
                    >
                      {isEnhancing ? (
                        <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                      ) : (
                        <><svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.71c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>Enhance</>
                      )}
                    </button>
                </div>
            </div>
             <div className="flex items-center gap-4">
                <button 
                    onClick={handleSuggestPalette} disabled={isPaletteLoading || !prompt.trim()}
                    className="bg-gray-700 hover:bg-purple-600 text-white font-semibold py-2 px-4 rounded-md text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                    {isPaletteLoading ? <svg className="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> : <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor"><path d="M17.25 2.75a.75.75 0 00-1.06 0l-1.25 1.25a.75.75 0 000 1.06l.25.25a.75.75 0 001.06 0l1.25-1.25a.75.75 0 000-1.06l-.25-.25zM10 2.25a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2.25zM4.06 4.06a.75.75 0 010 1.06l-1.25 1.25a.75.75 0 11-1.06-1.06l1.25-1.25a.75.75 0 011.06 0zM2.25 10a.75.75 0 01.75-.75h1.5a.75.75 0 010 1.5h-1.5a.75.75 0 01-.75-.75zM4.06 15.94a.75.75 0 011.06 0l1.25 1.25a.75.75 0 11-1.06 1.06l-1.25-1.25a.75.75 0 010-1.06zM10 17.75a.75.75 0 01-.75-.75v-1.5a.75.75 0 011.5 0v1.5a.75.75 0 01-.75.75zM15.94 15.94a.75.75 0 010-1.06l1.25-1.25a.75.75 0 111.06 1.06l-1.25 1.25a.75.75 0 01-1.06 0zM17.75 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5a.75.75 0 01.75.75zM10 5a5 5 0 100 10 5 5 0 000-10z" /></svg>}
                    Suggest Palette
                </button>
                 {colorPalette.length > 0 && (
                    <div className="flex gap-2 items-center">
                        {colorPalette.map(color => (
                             <div key={color} className="relative group">
                                <button onClick={() => copyToClipboard(color)} style={{ backgroundColor: color }} className="w-8 h-8 rounded-full border-2 border-gray-600 cursor-pointer transition transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-cyan-500"></button>
                                <span className="absolute bottom-full left-1/2 z-10 -translate-x-1/2 mb-2 p-1 bg-gray-900 text-white text-xs rounded-md shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">{color}</span>
                            </div>
                        ))}
                    </div>
                )}
                {paletteError && <p className="text-sm text-red-400">{paletteError}</p>}
            </div>
            <div>
                <label className="block text-gray-400 mb-2 font-semibold flex items-center">Reference Image (Optional)<Tooltip text="Provide an image to guide the AI, especially for generating a 3D model of a specific object or character." /></label>
                <div className="mt-1 flex items-center justify-center px-6 pt-5 pb-6 border-2 border-gray-600 border-dashed rounded-md">
                    {props.imagePreview ? (
                        <div className="relative group">
                            <img src={props.imagePreview} alt="Preview" className="h-40 rounded-md" />
                            <button onClick={props.onClearImage} className="absolute top-1 right-1 bg-red-600/80 hover:bg-red-500 text-white rounded-full p-1 leading-none opacity-0 group-hover:opacity-100 transition-opacity">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" /></svg>
                            </button>
                        </div>
                    ) : (
                        <div className="space-y-1 text-center">
                            <svg className="mx-auto h-12 w-12 text-gray-500" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true"><path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                            <div className="flex text-sm text-gray-400">
                                <label htmlFor="file-upload" className="relative cursor-pointer bg-gray-700 rounded-md font-medium text-cyan-400 hover:text-cyan-300 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-offset-gray-800 focus-within:ring-cyan-500 px-2 py-1">
                                    <span>Upload a file</span>
                                    <input id="file-upload" name="file-upload" type="file" className="sr-only" onChange={props.onImageChange} accept="image/*" />
                                </label>
                                <p className="pl-1">or drag and drop</p>
                            </div>
                            <p className="text-xs text-gray-500">PNG, JPG, GIF up to 10MB</p>
                        </div>
                    )}
                </div>
            </div>
        </div>

        <ControlSection title="Terrain Features" tooltip="Define specific features on your terrain, like rivers or paths. These will be added on top of the base terrain.">
            {/* Terrain Section content here */}
        </ControlSection>
        
        <ControlSection title="Scatter Objects" tooltip="Define objects to scatter across the terrain, like trees or rocks. Control their density, scale, and placement rules.">
            {/* Scatter Objects Section content here */}
        </ControlSection>

        <ControlSection title="Vegetation & Biomes" tooltip="Define ecological zones and seasonal properties for your world.">
            {/* Vegetation Section content here */}
        </ControlSection>

        <ControlSection title="Camera Setup" tooltip="Configure the initial camera position and settings.">
             <div className="space-y-4">
                <div>
                    <label className="block text-gray-400 mb-2 font-semibold">Camera Preset</label>
                    <select value={props.cameraConfig.preset} onChange={e => props.onCameraConfigChange('preset', e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded-md p-2 text-gray-300 focus:ring-1 focus:ring-cyan-500">
                        <option value="Default">Default</option><option value="BirdsEye">Bird's Eye View</option><option value="Cinematic">Cinematic (Low Angle)</option><option value="FirstPerson">First Person</option><option value="Isometric">Isometric</option>
                    </select>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <SliderInput label="Focal Length (mm)" tooltip="Camera focal length." value={props.cameraConfig.lens} onChange={v => props.onCameraConfigChange('lens', v)} min={15} max={200} step={1} />
                    <SliderInput label="Clip Start (m)" tooltip="Near clipping distance." value={props.cameraConfig.clipStart} onChange={v => props.onCameraConfigChange('clipStart', v)} min={0.01} max={10} step={0.01} />
                    <SliderInput label="Clip End (m)" tooltip="Far clipping distance." value={props.cameraConfig.clipEnd} onChange={v => props.onCameraConfigChange('clipEnd', v)} min={100} max={5000} step={50} />
                </div>
            </div>
        </ControlSection>
        
        <ControlSection title="Lighting" tooltip="Define the overall lighting and mood of the scene.">
           <div className="space-y-4">
                <div><label className="block text-gray-400 mb-2 font-semibold">Lighting Preset</label><select value={props.lightingConfig.preset} onChange={e => props.onLightingConfigChange('preset', e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded-md p-2 text-gray-300 focus:ring-1 focus:ring-cyan-500">{lightingPresets.map(p => <option key={p} value={p}>{p}</option>)}</select></div>
                <details className="mt-4"><summary className="cursor-pointer text-sm text-gray-400 hover:text-white font-medium">Advanced Lighting Controls</summary>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 text-sm mt-3 pt-3 border-t border-gray-600/50">
                        <SliderInput label="Ambient Intensity" tooltip="Global ambient light intensity." value={props.lightingConfig.ambientIntensity} onChange={v => props.onLightingConfigChange('ambientIntensity', v)} min={0} max={2} step={0.01} />
                        <div><label className="block text-gray-400 mb-1">Main Light Type</label><select value={props.lightingConfig.lightType} onChange={e => props.onLightingConfigChange('lightType', e.target.value)} className="w-full bg-gray-600 border border-gray-500 rounded-md p-2 text-gray-300 focus:ring-1 focus:ring-cyan-500"><option value="directional">Directional (Sun)</option><option value="point">Point (Lamp)</option><option value="spot">Spot Light</option></select></div>
                        <div className="md:col-span-2"><label className="block text-gray-400 mb-1">Ambient Color</label><input type="color" value={props.lightingConfig.ambientColor} onChange={e => props.onLightingConfigChange('ambientColor', e.target.value)} className="w-full h-10 bg-gray-600 border border-gray-500 rounded-md cursor-pointer" /></div>
                    </div>
                </details>
            </div>
        </ControlSection>

        <ControlSection title="Weather & Particle Effects" tooltip="Add atmospheric effects like rain, snow, or fog to your scene.">
            {/* Weather Section content here */}
        </ControlSection>

        <ControlSection title="Post-Processing & Effects" tooltip="Control visual effects like bloom, depth of field, and color grading.">
            {/* Post-Processing Section content here */}
        </ControlSection>
        
        <ControlSection title="Texture Baking" tooltip="For game assets, specify which texture maps to bake from the procedural materials.">
            {/* Texture Baking Section content here */}
        </ControlSection>
      </div>
      <div className="p-6 border-t border-gray-700">
        <button
          onClick={onGenerate} disabled={isLoading || isEnhancing || !prompt.trim()}
          className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold py-4 px-4 rounded-lg text-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105 shadow-lg hover:shadow-cyan-500/30"
          aria-label="Generate Blender recipe"
        >
          {isLoading ? 'Generating...' : 'Generate'}
        </button>
      </div>
    </div>
  );
};
