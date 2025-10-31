# Canvas3D UI module

# Lazy import inside register to avoid importing bpy-dependent modules during offline tests

def register():
    """Register UI components."""
    from . import panels, operators, preferences
    panels.register()
    operators.register()
    preferences.register()

def unregister():
    """Unregister UI components."""
    from . import panels, operators, preferences
    preferences.unregister()
    operators.unregister()
    panels.unregister()