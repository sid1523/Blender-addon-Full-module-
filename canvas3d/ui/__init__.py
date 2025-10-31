# Canvas3D UI module

# Lazy import inside register to avoid importing bpy-dependent modules during offline tests

def register():
    """Register UI components."""
    import bpy

    from . import frontend_server, operators, panels, preferences

    panels.register()
    operators.register()
    preferences.register()

    # Start front-end server if enabled in preferences
    try:
        prefs = bpy.context.preferences.addons[__package__.split(".")[0]].preferences
        if getattr(prefs, 'server_enable', False):
            frontend_server.FrontendServer.start(prefs.server_port)
    except Exception:
        pass

def unregister():
    """Unregister UI components."""
    from . import frontend_server, operators, panels, preferences

    # Stop front-end server
    try:
        frontend_server.FrontendServer.stop()
    except Exception:
        pass

    preferences.unregister()
    operators.unregister()
    panels.unregister()
