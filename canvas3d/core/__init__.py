# Canvas3D Core module

import bpy
from . import orchestrator, llm_interface, hardware_detector

def register():
    """Register core components."""
    orchestrator.register()
    llm_interface.register()
    hardware_detector.register()

def unregister():
    """Unregister core components."""
    hardware_detector.unregister()
    llm_interface.unregister()
    orchestrator.unregister()