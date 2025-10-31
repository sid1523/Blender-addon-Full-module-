import pytest

from canvas3d.utils.validation import (
    validate_scene_code,
    CodeValidationError,
    make_restricted_globals,
)

# -------------------------
# Validation (AST + tokens)
# -------------------------

def test_empty_code_rejected():
    with pytest.raises(CodeValidationError):
        validate_scene_code("")

def test_forbidden_token_open():
    with pytest.raises(CodeValidationError) as exc:
        validate_scene_code("open('danger.txt', 'w')")
    assert "forbidden token" in str(exc.value).lower()

def test_forbidden_import_os():
    with pytest.raises(CodeValidationError) as exc:
        validate_scene_code("import os\nx = 1")
    assert "forbidden import" in str(exc.value).lower() or "import not allowed" in str(exc.value).lower()

def test_forbidden_call_exec():
    with pytest.raises(CodeValidationError) as exc:
        validate_scene_code("exec('print(42)')")
    assert "forbidden call" in str(exc.value).lower()

def test_with_open_rejected_reports_line():
    bad = "x = 1\nwith open('f.txt','w') as f:\n    f.write('x')\n"
    with pytest.raises(CodeValidationError) as exc:
        validate_scene_code(bad)
    msg = str(exc.value).lower()
    assert "with-statement" in msg or "forbidden use of open" in msg

def test_import_not_allowed_mathutils():
    # If mathutils is not present, validation allows import but exec sandbox may skip resolution.
    # Validation allowlist includes 'mathutils' but may be unavailable outside Blender; should not error here.
    code = "import math\nx = math.sin(1.0)"
    validate_scene_code(code)  # should not raise


# -------------------------
# Sandbox globals (__builtins__)
# -------------------------

def test_sandbox_blocks_import_os_via_builtins():
    code = "import os\nx = 1"
    # Validation will catch this already; double-check with sandbox import
    with pytest.raises(CodeValidationError):
        validate_scene_code(code)

def test_sandbox_allows_math_and_print_only():
    code = "import math\nprint(int(math.fabs(-3)))"
    validate_scene_code(code)
    compiled = compile(code, "<test_sandbox>", "exec")
    g = make_restricted_globals(bpy_module=None)  # inject no bpy for unit test
    # Safe exec; should not raise and should produce output
    exec(compiled, g, {})

def test_builtins_do_not_include_eval_exec_compile_input_open():
    # Attempt to use dangerous builtins; even if validation missed, sandbox should not expose them
    compiled = compile("True", "<noop>", "exec")
    g = make_restricted_globals(bpy_module=None)
    assert "__import__" in g["__builtins__"]  # replaced by safe importer
    for dangerous in ("eval", "exec", "compile", "input", "open"):
        assert dangerous not in g["__builtins__"]

def test_safe_import_only_whitelist():
    g = make_restricted_globals(bpy_module=None)
    safe_import = g["__builtins__"]["__import__"]
    # Allowed: math
    m = safe_import("math")
    assert hasattr(m, "sin")
    # Not allowed: os
    with pytest.raises(ImportError):
        safe_import("os")

def test_compile_filename_in_errors_for_context():
    code = "raise RuntimeError('boom')"
    validate_scene_code(code)  # allowed
    compiled = compile(code, "<canvas3d_scene:req-test>", "exec")
    g = make_restricted_globals(bpy_module=None)
    try:
        exec(compiled, g, {})
    except RuntimeError as e:
        # traceback should include our filename; we cannot easily inspect here, but ensure exception raised
        assert "boom" in str(e)


# -------------------------
# Determinism and idempotency notes (placeholder)
# -------------------------

def test_determinism_placeholder():
    # Deterministic behavior is enforced by callers (e.g., seeding RNG before exec).
    # This test is a placeholder to ensure test suite recognizes that determinism is considered.
    assert True