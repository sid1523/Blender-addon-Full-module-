import pytest

from canvas3d.utils.validation import (
    validate_scene_code,
    make_restricted_globals,
    CodeValidationError,
)


class _LeafCall:
    def __init__(self, name, on_call):
        self._name = name
        self._on_call = on_call

    def __call__(self, *args, **kwargs):
        if self._on_call:
            self._on_call(self._name, args, kwargs)
        return "ok"


class _Namespace:
    def __init__(self, mapping=None):
        self._mapping = mapping or {}

    def __getattr__(self, name: str):
        try:
            return self._mapping[name]
        except KeyError as ex:
            raise AttributeError(name) from ex

    def __setattr__(self, name: str, value):
        if name == "_mapping":
            super().__setattr__(name, value)
        else:
            self._mapping[name] = value


class _FakeBpy:
    """
    Minimal fake bpy with an ops tree to exercise runtime guard.
    Only the attributes used by tests are defined.
    """
    def __init__(self, on_call=None):
        self._calls = []
        self._on_call = on_call or (lambda name, args, kwargs: self._calls.append((name, args, kwargs)))

        # Build ops namespace: bpy.ops.object.camera_add and bpy.ops.wm.save_mainfile
        wm_ns = _Namespace({
            "save_mainfile": _LeafCall("wm.save_mainfile", self._on_call)
        })
        object_ns = _Namespace({
            "camera_add": _LeafCall("object.camera_add", self._on_call)
        })
        self.ops = _Namespace({
            "wm": wm_ns,
            "object": object_ns,
        })


# -----------------------------
# AST-based validation (static)
# -----------------------------

def test_ast_forbidden_bpy_ops_wm_save_mainfile():
    code = "bpy.ops.wm.save_mainfile(filepath='x')"
    with pytest.raises(CodeValidationError) as e:
        validate_scene_code(code)
    assert "Forbidden bpy.ops call" in str(e.value)


def test_ast_forbidden_bpy_ops_render():
    code = "bpy.ops.render.render(write_still=True)"
    with pytest.raises(CodeValidationError) as e:
        validate_scene_code(code)
    assert "Forbidden bpy.ops call" in str(e.value)


def test_ast_forbidden_bpy_ops_image_save_all():
    code = "bpy.ops.image.save_all()"
    with pytest.raises(CodeValidationError) as e:
        validate_scene_code(code)
    assert "Forbidden bpy.ops call" in str(e.value)


def test_ast_allowed_bpy_ops_object_camera_add():
    code = "bpy.ops.object.camera_add()"
    # Should not raise at validation time
    validate_scene_code(code)


# -------------------------------------------
# Runtime sandbox: OpsProxy guard and builtins
# -------------------------------------------

def test_runtime_ops_proxy_blocks_forbidden_wm_save_mainfile():
    # Setup fake bpy and sandbox globals
    called = {"hit": False}

    def on_call(name, args, kwargs):
        # If underlying function is ever called for forbidden op, mark and fail
        called["hit"] = True
        raise AssertionError("Underlying forbidden op was invoked")

    fake_bpy = _FakeBpy(on_call=on_call)
    safe_globals = make_restricted_globals(fake_bpy, allowed_imports={"bpy"}, extra_symbols=None)

    # Execute code referencing bpy injected into globals (no import)
    code = "bpy.ops.wm.save_mainfile(filepath='x')"
    with pytest.raises(RuntimeError) as e:
        exec(compile(code, "<test_forbidden_op>", "exec"), safe_globals, {})
    assert "Forbidden bpy.ops call blocked by Canvas3D sandbox" in str(e.value)
    # Ensure the underlying callable was never reached
    assert called["hit"] is False


def test_runtime_ops_proxy_allows_allowed_object_camera_add():
    calls = []

    def on_call(name, args, kwargs):
        calls.append((name, args, kwargs))

    fake_bpy = _FakeBpy(on_call=on_call)
    safe_globals = make_restricted_globals(fake_bpy, allowed_imports={"bpy"}, extra_symbols=None)

    code = "bpy.ops.object.camera_add()"
    # Should not raise; should call through to fake op
    exec(compile(code, "<test_allowed_op>", "exec"), safe_globals, {})
    assert any(n == "object.camera_add" for n, _, _ in calls)


def test_runtime_safe_builtins_available_without_bpy():
    # No bpy needed to exercise safe builtins
    safe_globals = make_restricted_globals(bpy_module=None, allowed_imports=set(), extra_symbols=None)
    local_ns = {}
    code = "x = int(3.7); y = round(3.2); z = sum([1,2,3]); a = bool(1); b = list((1,2)); c = dict([('k', 1)])"
    exec(compile(code, "<test_builtins>", "exec"), safe_globals, local_ns)
    assert local_ns["x"] == 3
    assert local_ns["y"] == 3
    assert local_ns["z"] == 6
    assert local_ns["a"] is True
    assert local_ns["b"] == [1, 2]
    assert local_ns["c"] == {"k": 1}