# Canvas3D Preferences panel for API keys and settings

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty


# Add-on preferences class
class Canvas3DPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__.replace("canvas3d.ui.", "canvas3d")  # Points to main add-on package

    # API Keys (stored persistently)

    openai_api_key: StringProperty(
        name="OpenAI API Key",
        description="API key for OpenAI Chat Completions (ChatGPT models)",
        default="",
        subtype='PASSWORD',  # Hidden input
    )

    # Demo mode toggle
    mock_mode: BoolProperty(
        name="Mock/Demo Mode",
        description="Enable demo mode with canned responses (no API calls)",
        default=False,
    )
    # Front-end UI server
    server_enable: BoolProperty(
        name="Enable Front-End Server",
        description="Serve embedded front-end UI via HTTP on localhost",
        default=False,
    )
    server_port: IntProperty(
        name="Front-End Server Port",
        description="Port for front-end HTTP server",
        default=8000,
        min=1024,
        max=65535,
    )

    # Provider endpoints and models
    openai_endpoint: StringProperty(
        name="OpenAI Endpoint",
        description="HTTP endpoint for OpenAI Chat Completions API",
        default="https://api.openai.com/v1/chat/completions",
    )
    openai_model: StringProperty(
        name="OpenAI Model",
        description="Model name for OpenAI Chat Completions",
        default="gpt-5",
    )

    # Rate limits (requests per minute)
    openai_rpm: IntProperty(
        name="OpenAI RPM",
        description="Max OpenAI requests per minute",
        default=60,
        min=1,
        max=600,
    )

    # Request timeout
    request_timeout_sec: FloatProperty(
        name="Request Timeout (sec)",
        description="HTTP timeout for provider calls",
        default=30.0,
        min=5.0,
        max=120.0,
        soft_min=5.0,
        soft_max=60.0,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

        # API Keys section
        box = layout.box()
        box.label(text="API Configuration:")
        box.prop(self, "openai_api_key")
        box.prop(self, "mock_mode")

        # Provider Settings
        layout.separator()
        pbox = layout.box()
        pbox.label(text="Provider Settings:")
        # OpenAI
        pbox.prop(self, "openai_endpoint")
        pbox.prop(self, "openai_model")
        pbox.prop(self, "openai_rpm")
        # Timeout
        pbox.prop(self, "request_timeout_sec")

        # Instructions
        layout.separator()
        layout.label(text="Note: API keys are required for full functionality.")
        layout.label(text="Enable Mock Mode to test UI without keys.")
        layout.label(text="Adjust endpoints, models, rate limits, and timeout if using compatible providers or proxies.")

        # Front-end server controls
        layout.separator()
        sbox = layout.box()
        sbox.label(text="Front-End UI Server:")
        sbox.prop(self, "server_enable")
        if self.server_enable:
            sbox.prop(self, "server_port")
            sbox.label(text=f"UI available at http://127.0.0.1:{self.server_port}")

# Registration
def register() -> None:
    bpy.utils.register_class(Canvas3DPreferences)

def unregister() -> None:
    bpy.utils.unregister_class(Canvas3DPreferences)
