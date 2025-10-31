# Canvas3D Hardware Detector: Detect GPU/RAM for quality scaling

import logging

logger = logging.getLogger(__name__)

QUALITY_PROFILES = {
    "LITE": {
        "viewport_samples": 32,
        "max_particles": 1000,
        "texture_resolution": 1024,
        "geometry_detail": "low"
    },
    "BALANCED": {
        "viewport_samples": 128,
        "max_particles": 5000,
        "texture_resolution": 2048,
        "geometry_detail": "medium"
    },
    "HIGH": {
        "viewport_samples": 512,
        "max_particles": 20000,
        "texture_resolution": 4096,
        "geometry_detail": "high"
    }
}

def get_gpu_vram_gb():
    """Best-effort stub to estimate GPU VRAM (GB)."""
    # Environment override for testing/CI
    try:
        import os
        val = os.environ.get("GPU_VRAM_GB")
        if val:
            return float(val)
    except Exception:
        pass

    # Try Blender Cycles preferences to infer GPU usage (no direct VRAM API)
    try:
        import bpy
        pref = getattr(bpy.context, "preferences", None)
        if pref and hasattr(pref, "addons") and "cycles" in pref.addons:
            cycles_addon = pref.addons["cycles"]
            cycles_prefs = getattr(cycles_addon, "preferences", None)
            device_type = getattr(cycles_prefs, "compute_device_type", "") if cycles_prefs else ""
            if device_type and device_type.lower() != "none":
                # If GPU compute is enabled, assume at least 6GB VRAM
                return 6.0
    except Exception:
        pass

    # Unknown/CPU-only
    return None

def detect_hardware_profile():
    """Detect hardware capabilities and return quality profile."""
    try:
        import psutil
        system_ram_gb = psutil.virtual_memory().total / (1024**3)
        cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
    except ImportError:
        logger.warning("psutil not available, assuming balanced hardware")
        system_ram_gb = 16  # Assume 16GB
        cpu_cores = 4  # Assume 4 cores

    # Estimate GPU VRAM if possible, else fall back
    gpu_vram_est = get_gpu_vram_gb()
    gpu_vram_gb = gpu_vram_est if gpu_vram_est is not None else 4.0

    # Determine profile
    if gpu_vram_gb < 4 or system_ram_gb < 8:
        profile = "LITE"
    elif gpu_vram_gb < 8 or system_ram_gb < 16:
        profile = "BALANCED"
    else:
        profile = "HIGH"

    logger.info(f"Hardware: RAM={system_ram_gb:.1f}GB, VRAM={gpu_vram_gb:.1f}GB, cores={cpu_cores}")
    logger.info(f"Selected quality profile: {profile}")
    return profile

# Registration (no-op)
def register():
    pass

def unregister():
    pass