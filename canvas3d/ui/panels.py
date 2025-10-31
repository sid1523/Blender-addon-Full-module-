# Canvas3D UI panels for 3D Viewport Sidebar

import bpy


# Variants list item and UIList for browsing generated variants
class CANVAS3D_VariantItem(bpy.types.PropertyGroup):
    summary: bpy.props.StringProperty(
        name="Summary",
        description="Human-readable summary of the variant"
    )
    index: bpy.props.IntProperty(
        name="Index",
        description="Variant index within the current request",
        default=0,
        min=0
    )

class CANVAS3D_UL_Variants(bpy.types.UIList):
    bl_idname = "CANVAS3D_UL_variants"

    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data: object, item: object, icon: int, active_data: object, active_propname: str, index: int) -> None:
        # item: CANVAS3D_VariantItem
        text = getattr(item, "summary", None) or f"Variant {index}"
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=text, icon='OUTLINER_OB_GROUP_INSTANCE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=str(index))

# History list item and UIList (for comparison/revert)
class CANVAS3D_HistoryItem(bpy.types.PropertyGroup):  # noqa: N801
    summary: bpy.props.StringProperty(
        name="Summary",
        description="Generation history entry summary"
    )
    index: bpy.props.IntProperty(
        name="Index",
        description="History entry index",
        default=0,
        min=0
    )

class CANVAS3D_UL_History(bpy.types.UIList):  # noqa: N801
    bl_idname = "CANVAS3D_UL_history"

    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data: object, item: object, icon: int, active_data: object, active_propname: str, index: int) -> None:
        text = getattr(item, "summary", None) or f"Entry {index}"
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=text, icon='FILE_TICK')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=str(index))

# Main Chat Panel
class CANVAS3D_PT_ChatPanel(bpy.types.Panel):  # noqa: N801
    bl_label = "Canvas3D Generator"
    bl_idname = "CANVAS3D_PT_chat_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Canvas3D'  # Sidebar tab name

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

        # Prompt input field
        box = layout.box()
        box.label(text="Prompt:")
        box.prop(context.scene, "canvas3d_prompt", text="")

        # Variant Controls
        ctrl = layout.box()
        ctrl.label(text="Variant Controls:")
        ctrl.prop(context.scene, "canvas3d_domain", text="Domain")
        ctrl.prop(context.scene, "canvas3d_size_scale", text="Size/Scale")
        ctrl.prop(context.scene, "canvas3d_complexity_density", text="Complexity/Density")
        ctrl.prop(context.scene, "canvas3d_layout_style", text="Layout Style")
        ctrl.prop(context.scene, "canvas3d_mood_lighting", text="Mood/Lighting")
        ctrl.prop(context.scene, "canvas3d_materials_palette", text="Materials Palette")
        ctrl.prop(context.scene, "canvas3d_camera_style", text="Camera Style")

        # Actions
        row = layout.row()
        row.operator("canvas3d.generate_scene", text="Generate Scene")
        row.operator("canvas3d.generate_variants", text="Generate Variants")

        # Variant selection
        sel = layout.box()
        sel.label(text="Variants Selection:")
        sel.prop(context.scene, "canvas3d_selected_request", text="Request ID")
        # Variants browser list with summaries
        sel.template_list(
            "CANVAS3D_UL_variants",
            "",
            context.scene, "canvas3d_variants",
            context.scene, "canvas3d_variants_index",
            rows=5
        )
        # Controls for selection/index
        row_list = sel.row()
        row_list.prop(context.scene, "canvas3d_selected_variant_index", text="Variant Index")
        row_list.operator("canvas3d.refresh_variants_list", text="Refresh List")
        row_list.operator("canvas3d.select_variant", text="Select Variant")
        row_list.operator("canvas3d.clear_variants", text="Clear Variants")

        # Enhancements actions
        row2 = sel.row()
        row2.operator("canvas3d.apply_enhancements", text="Apply Enhancements")
        row2.operator("canvas3d.more_ideas", text="More Ideas")

        # Local Iteration (No LLM)
        it = layout.box()
        it.label(text="Local Iteration (No LLM):")
        col = it.column(align=True)
        col.prop(context.scene, "canvas3d_edit_fov_deg", text="Camera FOV (deg)")
        col.prop(context.scene, "canvas3d_edit_light_intensity_scale", text="Light Intensity Scale")
        col.prop(context.scene, "canvas3d_edit_material_roughness", text="Global Roughness (0-1, -1=ignore)")
        col.prop(context.scene, "canvas3d_edit_material_metallic", text="Global Metallic (0-1, -1=ignore)")
        col.prop(context.scene, "canvas3d_edit_density", text="Density Heuristic")
        row_it = it.row(align=True)
        row_it.operator("canvas3d.load_overrides", text="Load Overrides from Selection")
        row_it.operator("canvas3d.regenerate_local", text="Regenerate Locally")

        # History (Compare/Revert)
        hist = layout.box()
        hist.label(text="History:")
        hist.template_list(
            "CANVAS3D_UL_history",
            "",
            context.scene, "canvas3d_history",
            context.scene, "canvas3d_history_index",
            rows=5
        )
        row_h = hist.row(align=True)
        row_h.operator("canvas3d.history_refresh", text="Refresh History")
        row_h.operator("canvas3d.history_revert", text="Revert Selected")

        # Export
        exp = layout.box()
        exp.label(text="Export:")
        exp.prop(context.scene, "canvas3d_export_path", text="File")
        exp.prop(context.scene, "canvas3d_export_format", text="Format")
        exp.prop(context.scene, "canvas3d_export_collision", text="Generate Collisions")
        exp.operator("canvas3d.export_last_scene", text="Export Last Scene")

        # Status text (read-only)
        layout.separator()
        layout.label(text="Status:")
        layout.prop(context.scene, "canvas3d_status", text="", emboss=False)

        # Last enhancements (read-only text)
        enh = layout.box()
        enh.label(text="Last Enhancements:")
        enh.prop(context.scene, "canvas3d_last_enhancements", text="")

        # Info: Spec pipeline
        info_box = layout.box()
        info_box.label(text="Spec-based generation (Schema v1.0.0)")
        info_box.label(text="Deterministic executor with atomic commit/rollback")
        info_box.label(text="Mock/Demo mode uses canned responses (no API calls)")

# Registration
def register() -> None:
    # Scene properties for UI state
    bpy.types.Scene.canvas3d_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="Natural language prompt for scene generation (multi-domain)",
        default="Create a dramatic interior set with strong chiaroscuro lighting and a hero prop in the foreground.",
    )
    bpy.types.Scene.canvas3d_status = bpy.props.StringProperty(
        name="Status",
        description="Generation status messages",
        default="Ready. Spec-based pipeline active. Enter a prompt and click Generate Scene.",
    )

    # Variant control knobs (v1)
    bpy.types.Scene.canvas3d_size_scale = bpy.props.EnumProperty(
        name="Size/Scale",
        description="Overall scene footprint scale",
        items=[
            ("small", "Small", "Compact footprint"),
            ("medium", "Medium", "Balanced footprint"),
            ("large", "Large", "Expanded footprint"),
        ],
        default="medium",
    )
    bpy.types.Scene.canvas3d_complexity_density = bpy.props.EnumProperty(
        name="Complexity/Density",
        description="Structural complexity and prop density",
        items=[
            ("sparse", "Sparse", "Few branches and props"),
            ("balanced", "Balanced", "Moderate branches and props"),
            ("dense", "Dense", "Many branches and props"),
        ],
        default="balanced",
    )
    bpy.types.Scene.canvas3d_layout_style = bpy.props.EnumProperty(
        name="Layout Style",
        description="High-level layout style",
        items=[
            ("linear", "Linear", "Mostly linear progression"),
            ("branching", "Branching", "Branching paths"),
            ("maze", "Maze", "Labyrinthine layout"),
        ],
        default="branching",
    )
    bpy.types.Scene.canvas3d_mood_lighting = bpy.props.EnumProperty(
        name="Mood/Lighting",
        description="Overall mood and lighting tone",
        items=[
            ("neutral", "Neutral", "Neutral tone"),
            ("warm", "Warm", "Warm lighting"),
            ("cool", "Cool", "Cool lighting"),
            ("dramatic", "Dramatic", "High-contrast dramatic"),
        ],
        default="neutral",
    )
    bpy.types.Scene.canvas3d_materials_palette = bpy.props.EnumProperty(
        name="Materials Palette",
        description="Material palette preference",
        items=[
            ("stone_wood", "Stone + Wood", "Stone walls with wooden accents"),
            ("marble_gold", "Marble + Gold", "Luxurious marble and gold"),
            ("lava_obsidian", "Lava + Obsidian", "Volcanic theme"),
            ("mossy_cobble", "Mossy Cobble", "Aged mossy stone"),
        ],
        default="stone_wood",
    )
    bpy.types.Scene.canvas3d_camera_style = bpy.props.EnumProperty(
        name="Camera Style",
        description="Camera language/style",
        items=[
            ("cinematic_static", "Cinematic Static", "Classic static framing"),
            ("handheld", "Handheld", "Handheld feel"),
            ("dolly", "Dolly", "Dolly/tracking moves"),
            ("topdown", "Top-down", "Top-down exploration"),
        ],
        default="cinematic_static",
    )

    # Domain selection (multi-domain support)
    bpy.types.Scene.canvas3d_domain = bpy.props.EnumProperty(
        name="Domain",
        description="Generation domain",
        items=[
            ("procedural_dungeon", "Procedural Dungeon", "Grid-based dungeon layout with rooms and corridors"),
            ("film_interior", "Film Interior", "Cinematic interior scene without grid requirements"),
        ],
        default="procedural_dungeon",
    )
 
    # Variants selection state
    bpy.types.Scene.canvas3d_selected_request = bpy.props.StringProperty(
        name="Selected Request",
        description="Current variants request id",
        default="",
    )
    bpy.types.Scene.canvas3d_selected_variant_index = bpy.props.IntProperty(
        name="Variant Index",
        description="Index of variant to execute",
        default=0,
        min=0,
        max=19,
    )

    # Enhancements display
    bpy.types.Scene.canvas3d_last_enhancements = bpy.props.StringProperty(
        name="Last Enhancements",
        description="Most recent heuristic or provider enhancement suggestions (read-only)",
        default="",
    )

    # Variants browser data model
    bpy.utils.register_class(CANVAS3D_VariantItem)
    bpy.utils.register_class(CANVAS3D_UL_Variants)

    # Collection holding current request variants with summaries
    bpy.types.Scene.canvas3d_variants = bpy.props.CollectionProperty(
        type=CANVAS3D_VariantItem,
        name="Variants",
        description="Generated variants for the current request"
    )
    bpy.types.Scene.canvas3d_variants_index = bpy.props.IntProperty(
        name="Variants Index",
        description="Active variant index in the list",
        default=0,
        min=0,
        max=999
    )

    # Local iteration overrides (No LLM)
    bpy.types.Scene.canvas3d_edit_fov_deg = bpy.props.FloatProperty(
        name="FOV (deg)",
        description="Override camera FOV in degrees (20-120); leave as 60 for typical",
        default=60.0,
        min=20.0,
        max=120.0,
        soft_min=20.0,
        soft_max=120.0,
    )
    bpy.types.Scene.canvas3d_edit_light_intensity_scale = bpy.props.FloatProperty(
        name="Light Intensity Scale",
        description="Multiply all light intensities by this scale (1.0 = no change)",
        default=1.0,
        min=0.01,
        max=10.0,
        soft_min=0.1,
        soft_max=4.0,
    )
    bpy.types.Scene.canvas3d_edit_material_roughness = bpy.props.FloatProperty(
        name="Global Roughness",
        description="Override all material roughness to this value (0-1). Use -1 to ignore.",
        default=-1.0,
        min=-1.0,
        max=1.0,
        soft_min=-1.0,
        soft_max=1.0,
    )
    bpy.types.Scene.canvas3d_edit_material_metallic = bpy.props.FloatProperty(
        name="Global Metallic",
        description="Override all material metallic to this value (0-1). Use -1 to ignore.",
        default=-1.0,
        min=-1.0,
        max=1.0,
        soft_min=-1.0,
        soft_max=1.0,
    )
    bpy.types.Scene.canvas3d_edit_density = bpy.props.EnumProperty(
        name="Density",
        description="Heuristic density change for dungeon domain (increase/decrease props, corridor lengths)",
        items=[
            ("unchanged", "Unchanged", "Leave density as-is"),
            ("increase", "Increase", "Increase density slightly"),
            ("decrease", "Decrease", "Decrease density slightly"),
        ],
        default="unchanged",
    )

    # History browser data model
    bpy.utils.register_class(CANVAS3D_HistoryItem)
    bpy.utils.register_class(CANVAS3D_UL_History)

    bpy.types.Scene.canvas3d_history = bpy.props.CollectionProperty(
        type=CANVAS3D_HistoryItem,
        name="History",
        description="Recent generation history entries"
    )
    bpy.types.Scene.canvas3d_history_index = bpy.props.IntProperty(
        name="History Index",
        description="Active history index in the list",
        default=0,
        min=0,
        max=999
    )

    # Export options
    bpy.types.Scene.canvas3d_export_path = bpy.props.StringProperty(
        name="Export File",
        description="Target file path for export (GLB/FBX/USD)",
        default="",
        subtype='FILE_PATH',
    )
    bpy.types.Scene.canvas3d_export_format = bpy.props.EnumProperty(
        name="Export Format",
        description="Choose export format",
        items=[
            ("gltf", "glTF (GLB)", "Export as glTF binary (.glb)"),
            ("fbx", "FBX", "Export as Autodesk FBX (.fbx)"),
            ("usd", "USD", "Export as Universal Scene Description (.usd/.usdc/.usda)"),
        ],
        default="gltf",
    )
    bpy.types.Scene.canvas3d_export_collision = bpy.props.BoolProperty(
        name="Generate Collisions",
        description="Generate simple collision meshes before export",
        default=False,
    )

    bpy.utils.register_class(CANVAS3D_PT_ChatPanel)

def unregister() -> None:
    bpy.utils.unregister_class(CANVAS3D_PT_ChatPanel)

    # Clean up scene properties
    del bpy.types.Scene.canvas3d_prompt
    del bpy.types.Scene.canvas3d_status

    # Controls
    del bpy.types.Scene.canvas3d_size_scale
    del bpy.types.Scene.canvas3d_complexity_density
    del bpy.types.Scene.canvas3d_layout_style
    del bpy.types.Scene.canvas3d_mood_lighting
    del bpy.types.Scene.canvas3d_materials_palette
    del bpy.types.Scene.canvas3d_camera_style
    del bpy.types.Scene.canvas3d_domain

    # Selection
    del bpy.types.Scene.canvas3d_selected_request
    del bpy.types.Scene.canvas3d_selected_variant_index

    # Variants list
    del bpy.types.Scene.canvas3d_variants_index
    del bpy.types.Scene.canvas3d_variants
    bpy.utils.unregister_class(CANVAS3D_UL_Variants)
    bpy.utils.unregister_class(CANVAS3D_VariantItem)

    # Enhancements
    del bpy.types.Scene.canvas3d_last_enhancements

    # Local iteration
    del bpy.types.Scene.canvas3d_edit_fov_deg
    del bpy.types.Scene.canvas3d_edit_light_intensity_scale
    del bpy.types.Scene.canvas3d_edit_material_roughness
    del bpy.types.Scene.canvas3d_edit_material_metallic
    del bpy.types.Scene.canvas3d_edit_density

    # History
    del bpy.types.Scene.canvas3d_history_index
    del bpy.types.Scene.canvas3d_history
    bpy.utils.unregister_class(CANVAS3D_UL_History)
    bpy.utils.unregister_class(CANVAS3D_HistoryItem)

    # Export
    del bpy.types.Scene.canvas3d_export_path
    del bpy.types.Scene.canvas3d_export_format
    del bpy.types.Scene.canvas3d_export_collision