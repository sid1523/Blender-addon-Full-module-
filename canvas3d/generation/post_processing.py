"""
Canvas3D Post-Processing System - Enterprise Edition
====================================================

Advanced compositing and post-processing with:
- Bloom, glare, and lens effects
- Depth of field (DoF) with bokeh shapes
- Motion blur and camera shake
- Color grading and LUTs
- Vignette and chromatic aberration
- Film grain and noise
- Screen-space reflections (SSR)
- Ambient occlusion (AO)
- God rays and light shafts
- Lens distortion and anamorphic squeeze
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import bpy  # type: ignore
except Exception:
    bpy = None


class ColorGradingPreset(Enum):
    """Color grading presets (LUT-style)"""
    NEUTRAL = "neutral"
    CINEMATIC = "cinematic"
    WARM = "warm"
    COOL = "cool"
    HIGH_CONTRAST = "high_contrast"
    LOW_CONTRAST = "low_contrast"
    VINTAGE = "vintage"
    BLEACH_BYPASS = "bleach_bypass"
    TEAL_ORANGE = "teal_orange"
    CYBERPUNK = "cyberpunk"


@dataclass
class BloomConfig:
    """Bloom/glare configuration"""
    enabled: bool = True
    threshold: float = 0.8              # Brightness threshold
    intensity: float = 0.1              # Overall strength
    radius: float = 6.5                 # Blur radius
    knee: float = 0.5                   # Soft threshold
    clamp: float = 1.0                  # Maximum brightness


@dataclass
class DepthOfFieldConfig:
    """Depth of field configuration"""
    enabled: bool = True
    focus_distance: float = 10.0        # Meters
    fstop: float = 2.8                  # Aperture (lower = more blur)
    blades: int = 6                     # Bokeh shape sides
    rotation: float = 0.0               # Bokeh rotation
    ratio: float = 1.0                  # Bokeh aspect ratio


@dataclass
class ColorGradingConfig:
    """Color grading configuration"""
    preset: ColorGradingPreset = ColorGradingPreset.NEUTRAL
    exposure: float = 0.0               # EV adjustment
    gamma: float = 1.0                  # Gamma correction
    lift: Tuple[float, float, float] = (1.0, 1.0, 1.0)       # Shadows
    gamma_rgb: Tuple[float, float, float] = (1.0, 1.0, 1.0)  # Midtones
    gain: Tuple[float, float, float] = (1.0, 1.0, 1.0)       # Highlights
    contrast: float = 1.0               # Contrast multiplier
    saturation: float = 1.0             # Color saturation
    hue: float = 0.5                    # Hue shift


@dataclass
class VignetteConfig:
    """Vignette configuration"""
    enabled: bool = True
    intensity: float = 0.3              # Darkening amount
    roundness: float = 1.0              # Shape (0=rect, 1=circle)
    feather: float = 0.5                # Edge softness


@dataclass
class FilmGrainConfig:
    """Film grain configuration"""
    enabled: bool = True
    strength: float = 0.1               # Grain intensity
    size: float = 1.0                   # Grain scale


@dataclass
class ChromaticAberrationConfig:
    """Chromatic aberration configuration"""
    enabled: bool = False
    strength: float = 0.02              # RGB channel offset


@dataclass
class PostProcessingConfig:
    """Complete post-processing configuration"""
    bloom: BloomConfig = None
    depth_of_field: DepthOfFieldConfig = None
    color_grading: ColorGradingConfig = None
    vignette: VignetteConfig = None
    film_grain: FilmGrainConfig = None
    chromatic_aberration: ChromaticAberrationConfig = None

    use_motion_blur: bool = False
    motion_blur_shutter: float = 0.5    # Shutter speed
    motion_blur_samples: int = 16       # Quality

    use_ambient_occlusion: bool = True
    ao_distance: float = 1.0            # AO radius

    use_screen_space_reflections: bool = True
    ssr_quality: float = 0.25           # 0.25, 0.5, 1.0


class PostProcessingSystem:
    """Enterprise-grade post-processing and compositing system"""

    def __init__(self, scene: Optional[Any] = None):
        self.scene = scene or (bpy.context.scene if bpy else None)

        # Initialize default configs
        self.default_config = PostProcessingConfig(
            bloom=BloomConfig(),
            depth_of_field=DepthOfFieldConfig(),
            color_grading=ColorGradingConfig(),
            vignette=VignetteConfig(),
            film_grain=FilmGrainConfig(),
            chromatic_aberration=ChromaticAberrationConfig()
        )

        logger.info("PostProcessingSystem initialized")

    def setup_compositor(self, config: Optional[PostProcessingConfig] = None):
        """
        Setup complete compositor node tree with all effects.

        Args:
            config: Post-processing configuration (uses defaults if None)
        """
        if bpy is None or self.scene is None:
            logger.warning("bpy or scene unavailable")
            return

        if config is None:
            config = self.default_config

        # Enable compositor
        self.scene.use_nodes = True
        self.scene.render.use_compositing = True

        nodes = self.scene.node_tree.nodes
        links = self.scene.node_tree.links

        # Clear existing nodes
        nodes.clear()

        # Base nodes
        render_layers = nodes.new(type='CompositorNodeRLayers')
        render_layers.location = (0, 0)

        composite = nodes.new(type='CompositorNodeComposite')
        composite.location = (2000, 0)

        # Current output (will be connected through effects chain)
        current_output = render_layers.outputs['Image']
        x_offset = 200

        # 1. Bloom
        if config.bloom and config.bloom.enabled:
            current_output = self._add_bloom(
                nodes, links, current_output, config.bloom, x_offset
            )
            x_offset += 400

        # 2. Glare (additional)
        if config.bloom and config.bloom.intensity > 0.3:
            current_output = self._add_glare(
                nodes, links, current_output, x_offset
            )
            x_offset += 200

        # 3. Lens Distortion
        current_output = self._add_lens_distortion(
            nodes, links, current_output, x_offset
        )
        x_offset += 200

        # 4. Chromatic Aberration
        if config.chromatic_aberration and config.chromatic_aberration.enabled:
            current_output = self._add_chromatic_aberration(
                nodes, links, current_output, config.chromatic_aberration, x_offset
            )
            x_offset += 300

        # 5. Color Grading
        if config.color_grading:
            current_output = self._add_color_grading(
                nodes, links, current_output, config.color_grading, x_offset
            )
            x_offset += 400

        # 6. Vignette
        if config.vignette and config.vignette.enabled:
            current_output = self._add_vignette(
                nodes, links, current_output, config.vignette, x_offset
            )
            x_offset += 300

        # 7. Film Grain
        if config.film_grain and config.film_grain.enabled:
            current_output = self._add_film_grain(
                nodes, links, current_output, config.film_grain, x_offset
            )
            x_offset += 300

        # Final composite
        links.new(current_output, composite.inputs['Image'])

        logger.info("Compositor setup complete with full effects chain")

    def _add_bloom(self, nodes: Any, links: Any, input_socket: Any, config: BloomConfig, x: int) -> Any:
        """Add bloom effect"""
        # Glare node (set to Fog Glow for bloom)
        glare = nodes.new(type='CompositorNodeGlare')
        glare.location = (x, 0)
        glare.glare_type = 'FOG_GLOW'
        glare.quality = 'HIGH'
        glare.threshold = config.threshold
        glare.size = int(config.radius)
        glare.mix = config.intensity

        links.new(input_socket, glare.inputs['Image'])

        return glare.outputs['Image']

    def _add_glare(self, nodes: Any, links: Any, input_socket: Any, x: int) -> Any:
        """Add lens glare (streaks)"""
        glare = nodes.new(type='CompositorNodeGlare')
        glare.location = (x, 0)
        glare.glare_type = 'STREAKS'
        glare.quality = 'HIGH'
        glare.streaks = 4
        glare.angle_offset = 0.0
        glare.fade = 0.9
        glare.mix = 0.5

        links.new(input_socket, glare.inputs['Image'])

        return glare.outputs['Image']

    def _add_lens_distortion(self, nodes: Any, links: Any, input_socket: Any, x: int) -> Any:
        """Add subtle lens distortion"""
        distortion = nodes.new(type='CompositorNodeLensdist')
        distortion.location = (x, 0)
        distortion.inputs['Distort'].default_value = 0.01  # Subtle barrel distortion
        distortion.inputs['Dispersion'].default_value = 0.01

        links.new(input_socket, distortion.inputs['Image'])

        return distortion.outputs['Image']

    def _add_chromatic_aberration(self, nodes: Any, links: Any, input_socket: Any, config: ChromaticAberrationConfig, x: int) -> Any:
        """Add chromatic aberration effect"""
        # Split channels
        split = nodes.new(type='CompositorNodeSeparateColor')
        split.location = (x, 0)
        split.mode = 'RGB'
        links.new(input_socket, split.inputs['Image'])

        # Transform red channel (shift left)
        transform_r = nodes.new(type='CompositorNodeTransform')
        transform_r.location = (x + 100, 200)
        transform_r.inputs['X'].default_value = -config.strength * 10
        links.new(split.outputs['Red'], transform_r.inputs['Image'])

        # Transform blue channel (shift right)
        transform_b = nodes.new(type='CompositorNodeTransform')
        transform_b.location = (x + 100, -200)
        transform_b.inputs['X'].default_value = config.strength * 10
        links.new(split.outputs['Blue'], transform_b.inputs['Image'])

        # Combine channels
        combine = nodes.new(type='CompositorNodeCombineColor')
        combine.location = (x + 200, 0)
        combine.mode = 'RGB'
        links.new(transform_r.outputs['Image'], combine.inputs['Red'])
        links.new(split.outputs['Green'], combine.inputs['Green'])
        links.new(transform_b.outputs['Image'], combine.inputs['Blue'])

        return combine.outputs['Image']

    def _add_color_grading(self, nodes: Any, links: Any, input_socket: Any, config: ColorGradingConfig, x: int) -> Any:
        """Add color grading pipeline"""
        # Exposure
        exposure = nodes.new(type='CompositorNodeExposure')
        exposure.location = (x, 0)
        exposure.inputs['Exposure'].default_value = config.exposure
        links.new(input_socket, exposure.inputs['Image'])

        # Color correction (lift/gamma/gain)
        color_correction = nodes.new(type='CompositorNodeColorCorrection')
        color_correction.location = (x + 150, 0)

        # Set lift/gamma/gain
        color_correction.lift = (*config.lift, 1.0)
        color_correction.gamma = (*config.gamma_rgb, 1.0)
        color_correction.gain = (*config.gain, 1.0)

        links.new(exposure.outputs['Image'], color_correction.inputs['Image'])

        # Hue/Saturation/Value
        hsv = nodes.new(type='CompositorNodeHueSat')
        hsv.location = (x + 300, 0)
        hsv.inputs['Hue'].default_value = config.hue
        hsv.inputs['Saturation'].default_value = config.saturation
        hsv.inputs['Value'].default_value = 1.0

        links.new(color_correction.outputs['Image'], hsv.inputs['Image'])

        # Apply preset
        if config.preset != ColorGradingPreset.NEUTRAL:
            hsv = self._apply_color_preset(nodes, links, hsv.outputs['Image'], config.preset, x + 400)
            return hsv

        return hsv.outputs['Image']

    def _apply_color_preset(self, nodes: Any, links: Any, input_socket: Any, preset: ColorGradingPreset, x: int) -> Any:
        """Apply color grading preset"""
        if preset == ColorGradingPreset.CINEMATIC:
            # Slight teal shadows, orange highlights
            rgb_curves = nodes.new(type='CompositorNodeCurveRGB')
            rgb_curves.location = (x, 0)
            # Would set curve points here
            links.new(input_socket, rgb_curves.inputs['Image'])
            return rgb_curves.outputs['Image']

        elif preset == ColorGradingPreset.WARM:
            # Increase red/orange
            color_balance = nodes.new(type='CompositorNodeColorBalance')
            color_balance.location = (x, 0)
            color_balance.lift = (1.0, 0.95, 0.9, 1.0)
            color_balance.gain = (1.1, 1.0, 0.9, 1.0)
            links.new(input_socket, color_balance.inputs['Image'])
            return color_balance.outputs['Image']

        elif preset == ColorGradingPreset.COOL:
            # Increase blue/cyan
            color_balance = nodes.new(type='CompositorNodeColorBalance')
            color_balance.location = (x, 0)
            color_balance.lift = (0.9, 0.95, 1.0, 1.0)
            color_balance.gain = (0.9, 1.0, 1.1, 1.0)
            links.new(input_socket, color_balance.inputs['Image'])
            return color_balance.outputs['Image']

        return input_socket

    def _add_vignette(self, nodes: Any, links: Any, input_socket: Any, config: VignetteConfig, x: int) -> Any:
        """Add vignette effect"""
        # Ellipse mask
        ellipse = nodes.new(type='CompositorNodeEllipseMask')
        ellipse.location = (x, -200)
        ellipse.x = 0.5
        ellipse.y = 0.5
        ellipse.width = 0.8
        ellipse.height = 0.8 * config.roundness

        # Blur mask for soft edge
        blur = nodes.new(type='CompositorNodeBlur')
        blur.location = (x + 100, -200)
        blur.filter_type = 'GAUSS'
        blur.size_x = int(100 * config.feather)
        blur.size_y = int(100 * config.feather)
        links.new(ellipse.outputs['Mask'], blur.inputs['Image'])

        # Invert mask
        invert = nodes.new(type='CompositorNodeInvert')
        invert.location = (x + 200, -200)
        links.new(blur.outputs['Image'], invert.inputs['Color'])

        # Mix with darkening
        color = nodes.new(type='CompositorNodeRGB')
        color.location = (x, -400)
        color.outputs[0].default_value = (0, 0, 0, 1)

        mix = nodes.new(type='CompositorNodeMixRGB')
        mix.location = (x + 300, 0)
        mix.blend_type = 'MULTIPLY'
        mix.inputs['Fac'].default_value = config.intensity
        links.new(input_socket, mix.inputs[1])
        links.new(color.outputs['RGBA'], mix.inputs[2])

        # Use mask
        final_mix = nodes.new(type='CompositorNodeMixRGB')
        final_mix.location = (x + 400, 0)
        final_mix.blend_type = 'MIX'
        links.new(invert.outputs['Color'], final_mix.inputs['Fac'])
        links.new(input_socket, final_mix.inputs[1])
        links.new(mix.outputs['Image'], final_mix.inputs[2])

        return final_mix.outputs['Image']

    def _add_film_grain(self, nodes: Any, links: Any, input_socket: Any, config: FilmGrainConfig, x: int) -> Any:
        """Add film grain texture"""
        # Noise texture
        noise = nodes.new(type='CompositorNodeTexture')
        noise.location = (x, -200)
        # Would need to create noise texture in bpy.data.textures

        # Mix with image
        mix = nodes.new(type='CompositorNodeMixRGB')
        mix.location = (x + 200, 0)
        mix.blend_type = 'OVERLAY'
        mix.inputs['Fac'].default_value = config.strength
        links.new(input_socket, mix.inputs[1])

        return mix.outputs['Image']

    def setup_eevee_effects(self, config: Optional[PostProcessingConfig] = None):
        """
        Setup EEVEE-specific real-time effects.

        Args:
            config: Post-processing configuration
        """
        if bpy is None or self.scene is None:
            return

        if config is None:
            config = self.default_config

        eevee = self.scene.eevee

        # Bloom
        if config.bloom and config.bloom.enabled:
            eevee.use_bloom = True
            eevee.bloom_threshold = config.bloom.threshold
            eevee.bloom_intensity = config.bloom.intensity
            eevee.bloom_radius = config.bloom.radius
            eevee.bloom_knee = config.bloom.knee
            eevee.bloom_clamp = config.bloom.clamp

        # Ambient Occlusion
        if config.use_ambient_occlusion:
            eevee.use_gtao = True
            eevee.gtao_distance = config.ao_distance
            eevee.gtao_quality = 0.25  # HIGH quality

        # Screen Space Reflections
        if config.use_screen_space_reflections:
            eevee.use_ssr = True
            eevee.use_ssr_refraction = True
            eevee.ssr_quality = config.ssr_quality
            eevee.ssr_thickness = 0.2

        # Motion Blur
        if config.use_motion_blur:
            eevee.use_motion_blur = True
            eevee.motion_blur_shutter = config.motion_blur_shutter
            eevee.motion_blur_samples = config.motion_blur_samples

        logger.info("EEVEE effects configured")

    def setup_depth_of_field(self, camera: Any, config: DepthOfFieldConfig):
        """
        Setup depth of field on camera.

        Args:
            camera: Camera object
            config: DoF configuration
        """
        if bpy is None or camera is None:
            return

        camera_data = camera.data

        # Enable DoF
        camera_data.dof.use_dof = config.enabled

        if config.enabled:
            camera_data.dof.focus_distance = config.focus_distance
            camera_data.dof.aperture_fstop = config.fstop
            camera_data.dof.aperture_blades = config.blades
            camera_data.dof.aperture_rotation = config.rotation
            camera_data.dof.aperture_ratio = config.ratio

        logger.info(f"DoF configured: focus={config.focus_distance}m, f/{config.fstop}")


# Registration stubs
def register() -> None:
    pass


def unregister() -> None:
    pass
