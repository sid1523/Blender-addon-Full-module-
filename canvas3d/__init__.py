# Canvas3D: AI-Powered 3D Scene Generator for Blender
# https://github.com/your-username/canvas3d-blender-addon
#
# This add-on provides conversational AI-driven 3D scene generation,
# with visual editing (Paint Mode) planned for future phases.
#
# Author: Your Name
# License: MIT
# Compatible with Blender 4.0+

import logging

# Add-on metadata
bl_info = {
    "name": "Canvas3D",
    "author": "Your Name",
    "description": "AI-powered 3D scene generation for Blender",
    "blender": (4, 0, 0),
    "version": (0, 1, 0),
    "location": "3D Viewport Sidebar (N-panel) > Canvas3D tab",
    "warning": "Beta: API keys required for full functionality",
    "category": "Scene",
    "support": "COMMUNITY",
}

# Global logger for the add-on
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Handler to Blender console (if available) or stdout
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Suppress verbose logs from external libraries (e.g., requests)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

def register():
    """Register the add-on components."""
    logger.info("Registering Canvas3D add-on...")
    # Lazy import to avoid loading bpy/UI in non-Blender environments and tests
    from . import ui, core, generation, utils

    # Register UI components first (panels, operators)
    ui.register()

    # Register core modules
    core.register()

    # Register generation modules
    generation.register()

    # Register utilities
    utils.register()

    logger.info("Canvas3D add-on registered successfully.")

def unregister():
    """Unregister the add-on components."""
    logger.info("Unregistering Canvas3D add-on...")
    # Lazy import to avoid loading bpy/UI when running tests
    from . import ui, core, generation, utils

    # Unregister in reverse order
    utils.unregister()
    generation.unregister()
    core.unregister()
    ui.unregister()

    logger.info("Canvas3D add-on unregistered.")

# Blender calls this on add-on load
if __name__ == "__main__":
    register()