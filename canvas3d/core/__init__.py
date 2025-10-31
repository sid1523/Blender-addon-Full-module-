# Canvas3D Core module

try:
    import bpy
except ImportError:
    bpy = None
from . import hardware_detector, llm_interface, orchestrator


def register() -> None:
    """Register core components."""
    orchestrator.register()
    llm_interface.register()
    hardware_detector.register()

def unregister() -> None:
    """Unregister core components."""
    hardware_detector.unregister()
    llm_interface.unregister()
    orchestrator.unregister()
