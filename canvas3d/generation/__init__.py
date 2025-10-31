# Canvas3D Generation module

# Note: No top-level bpy import to allow offline tests and package import without Blender.

def register() -> None:
    """Register generation components (placeholder for now)."""
    # Scene builder does not require class registration; it is a service class.
    # Future: register geometry node assets, custom node groups, etc.
    pass

def unregister() -> None:
    """Unregister generation components."""
    pass