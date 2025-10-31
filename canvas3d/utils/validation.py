# Code validation utilities for Canvas3D
# Provides AST-based checks and helpers to restrict execution environment.

from __future__ import annotations

import ast
import logging
from typing import Iterable, Optional, Set

logger = logging.getLogger(__name__)
ALLOWED_IMPORTS: Set[str] = {"bpy", "math", "mathutils"}


class CodeValidationError(Exception):
    """Raised when generated code fails validation."""
    pass


# Conservative defaults for MVP. Can be expanded in Phase 3.
FORBIDDEN_IMPORTS: Set[str] = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "ctypes",
    "multiprocessing",
    "threading",
}
FORBIDDEN_CALLS: Set[str] = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "input",
}
# Quick token scan to short-circuit obviously unsafe code.
# Special-case: direct open(...) should be caught here to produce a clear "forbidden token" message,
# but "with open(...)" should be handled by AST to report precise with-statement context.
FORBIDDEN_TOKENS: Iterable[str] = (
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import shutil",
    "import pathlib",
    "import ctypes",
    "multiprocessing",
    "threading",
    "subprocess",
    "socket",
    "shutil",
    "open(",
    "__import__",
    "eval(",
    "exec(",
    "compile(",
    "input(",
)

# bpy.ops security policy:
# Allow only conservative operator namespaces used to build scenes.
# Explicitly forbid namespaces that can write to disk, render, or otherwise cause side effects.
ALLOWED_BPY_OPS_PREFIXES: Set[str] = {
    "object",
    "mesh",
    "camera",
    "light",
    "transform",
    "curve",
    "collection",
}

FORBIDDEN_BPY_OPS_PREFIXES: Set[str] = {
    "wm",
    "render",
    "image",
    "text",
    "script",
    "sound",
    "export_scene",
    "import_scene",
    "file",
    "screen",
    "window",
    "preferences",
}


def quick_token_scan(code: str) -> Optional[str]:
    """
    Cheap substring-based scan to catch blatant unsafe usage early.
    Returns the first offending token found, or None if clean.
    """
    lowered = code.lower()
    for token in FORBIDDEN_TOKENS:
        # Allow AST to handle "with open(...)" for better error context; only flag direct open(...)
        if token == "open(" and "with open(" in lowered:
            continue
        if token in lowered:
            return token
    return None


class _SafeCodeVisitor(ast.NodeVisitor):
    """
    AST visitor to detect disallowed imports and calls, including guarded bpy.ops usage.
    """

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def _add_error(self, msg: str, node: Optional[ast.AST] = None) -> None:
        loc = ""
        if node is not None and hasattr(node, "lineno"):
            loc = f" (line {getattr(node, 'lineno', '?')})"
        self.errors.append(f"{msg}{loc}")

    def _get_attr_chain(self, node: ast.AST) -> list[str]:
        """
        Return attribute/name chain e.g. bpy.ops.object.camera_add -> ["bpy","ops","object","camera_add"]
        """
        chain: list[str] = []
        cur = node
        while isinstance(cur, ast.Attribute):
            chain.insert(0, cur.attr or "")
            cur = cur.value
        if isinstance(cur, ast.Name):
            chain.insert(0, cur.id or "")
        return chain

    # Import validations
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod = (alias.name or "").split(".")[0]
            if mod in FORBIDDEN_IMPORTS:
                self._add_error(f"Forbidden import: {alias.name}", node)
            elif mod not in ALLOWED_IMPORTS:
                self._add_error(f"Import not allowed: {alias.name}", node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = (node.module or "").split(".")[0] if node.module else ""
        if mod in FORBIDDEN_IMPORTS:
            self._add_error(f"Forbidden import from: {node.module}", node)
        elif mod and mod not in ALLOWED_IMPORTS:
            self._add_error(f"Import from not allowed: {node.module}", node)
        self.generic_visit(node)

    # Call validations (names, attributes, bpy.ops, bpy.app.handlers)
    def visit_Call(self, node: ast.Call) -> None:
        # Direct function name e.g. open(), eval(), exec()
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in FORBIDDEN_CALLS:
                self._add_error(f"Forbidden call: {func_name}()", node)

        # Attribute calls e.g. os.system(), subprocess.Popen()
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            base = node.func.value
            base_name = base.id if isinstance(base, ast.Name) else ""
            if base_name in {"os", "subprocess"} and attr.lower() in {
                "system", "popen", "run", "call", "popen3", "popen2", "popen4", "check_call", "check_output"
            }:
                self._add_error(f"Forbidden call: {base_name}.{attr}()", node)

        # Guard bpy.ops.* namespace via allow/deny lists
        chain = self._get_attr_chain(node.func)
        if len(chain) >= 3 and chain[0] == "bpy" and chain[1] == "ops":
            prefix = chain[2]
            full = ".".join(chain)
            if prefix in FORBIDDEN_BPY_OPS_PREFIXES or prefix not in ALLOWED_BPY_OPS_PREFIXES:
                self._add_error(f"Forbidden bpy.ops call: {full}()", node)

        # Minimal protection against bpy.app.handlers usage (calls)
        if len(chain) >= 3 and chain[0] == "bpy" and chain[1] == "app" and chain[2] == "handlers":
            self._add_error("Use of bpy.app.handlers is not allowed", node)

        self.generic_visit(node)

    # Assignments: block modifying bpy.app.handlers
    def visit_Assign(self, node: ast.Assign) -> None:
        for tgt in node.targets:
            if isinstance(tgt, ast.Attribute):
                chain = self._get_attr_chain(tgt)
                if len(chain) >= 3 and chain[0] == "bpy" and chain[1] == "app" and chain[2] == "handlers":
                    self._add_error("Modifying bpy.app.handlers is not allowed", node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        tgt = node.target
        if isinstance(tgt, ast.Attribute):
            chain = self._get_attr_chain(tgt)
            if len(chain) >= 3 and chain[0] == "bpy" and chain[1] == "app" and chain[2] == "handlers":
                self._add_error("Modifying bpy.app.handlers is not allowed", node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        tgt = node.target
        if isinstance(tgt, ast.Attribute):
            chain = self._get_attr_chain(tgt)
            if len(chain) >= 3 and chain[0] == "bpy" and chain[1] == "app" and chain[2] == "handlers":
                self._add_error("Modifying bpy.app.handlers is not allowed", node)
        self.generic_visit(node)

    # Optional: Prevent with open(...) patterns even if aliased
    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            # with open(...) as f:
            if isinstance(item.context_expr, ast.Call):
                call = item.context_expr
                if isinstance(call.func, ast.Name) and call.func.id == "open":
                    self._add_error("Forbidden use of open() in with-statement", node)
        self.generic_visit(node)


def validate_scene_code(code: str) -> None:
    """
    Validate generated Blender code for safety.
    Raises CodeValidationError on any violation.
    """
    if not isinstance(code, str) or not code.strip():
        raise CodeValidationError("Code is empty")

    token = quick_token_scan(code)
    if token:
        # Produce clearer, test-friendly messages for common cases, while keeping a fast path.
        if token.startswith("import "):
            mod = token.split(" ", 1)[1].strip()
            raise CodeValidationError(f"Import not allowed: {mod}")
        if token.startswith("exec("):
            raise CodeValidationError("Forbidden call: exec()")
        if token.startswith("eval("):
            raise CodeValidationError("Forbidden call: eval()")
        if token.startswith("compile("):
            raise CodeValidationError("Forbidden call: compile()")
        if token.startswith("input("):
            raise CodeValidationError("Forbidden call: input()")
        if token == "__import__":
            raise CodeValidationError("Forbidden call: __import__()")
        raise CodeValidationError(f"Code contains forbidden token: {token}")

    try:
        tree = ast.parse(code, filename="<canvas3d_generated>", mode="exec")
    except SyntaxError as syn:
        raise CodeValidationError(f"Syntax error: {syn}") from syn
    except Exception as ex:
        raise CodeValidationError(f"Parsing failed: {ex}") from ex

    visitor = _SafeCodeVisitor()
    visitor.visit(tree)
    if visitor.errors:
        raise CodeValidationError("Unsafe code detected:\n- " + "\n- ".join(visitor.errors))


def make_restricted_globals(bpy_module, allowed_imports: Optional[Set[str]] = None, extra_symbols: Optional[dict] = None) -> dict:
    """
    Construct a constrained globals dict for exec():
    - Restricts builtins to a safe, minimal set
    - Provides a safe __import__ that allows only whitelisted modules
    - Exposes bpy and explicitly allowed modules/symbols
    """
    import importlib

    allowed = set(allowed_imports or ALLOWED_IMPORTS)

    # Pre-resolve allowed modules to ensure availability without exposing general import
    resolved = {}
    for name in allowed:
        if name == "bpy":
            # defer injection; we'll wrap with a proxy below
            continue
        try:
            resolved[name] = importlib.import_module(name)
        except Exception as ex:
            # Module may not exist in environment (e.g., mathutils outside Blender); skip silently
            logger.debug(f"Optional allowed module not available: {name} ({ex})")

    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        base = (name or "").split(".")[0]
        if base in allowed:
            return importlib.import_module(name)
        raise ImportError(f"Import of '{name}' is not allowed by Canvas3D sandbox")

    # Runtime guard: proxy for bpy.ops that enforces ALLOWED_BPY_OPS_PREFIXES/FORBIDDEN_BPY_OPS_PREFIXES
    class _OpsProxy:
        def __init__(self, real_ops, path=()):
            self._real_ops = real_ops
            self._path = tuple(path)

        def __getattr__(self, name: str):
            # accumulate attribute chain segments (e.g., object, camera_add)
            return _OpsProxy(self._real_ops, self._path + (name,))

        def __call__(self, *args, **kwargs):
            # Validate fully qualified op id before dispatch
            parts = list(self._path)
            op_id = "bpy.ops." + ".".join(parts) if parts else "bpy.ops"
            if not parts:
                raise RuntimeError(f"Invalid operator call: {op_id}")
            prefix = parts[0]
            if prefix in FORBIDDEN_BPY_OPS_PREFIXES or prefix not in ALLOWED_BPY_OPS_PREFIXES:
                raise RuntimeError(f"Forbidden bpy.ops call blocked by Canvas3D sandbox: {op_id}()")
            # Resolve callable on real bpy.ops and execute
            target = self._real_ops
            for seg in parts:
                target = getattr(target, seg)
            return target(*args, **kwargs)

    class _BpyProxy:
        """Expose bpy with guarded ops; pass-through for other attributes."""
        def __init__(self, real_bpy):
            self._real_bpy = real_bpy
            self.ops = _OpsProxy(real_bpy.ops) if hasattr(real_bpy, "ops") else None

        def __getattr__(self, name: str):
            # Prefer explicit ops proxy; otherwise delegate attribute to real bpy
            if name == "ops":
                return self.ops
            return getattr(self._real_bpy, name)

    # Safe builtins (harmless utilities only; no eval/exec/compile/open/input)
    safe_builtins = {
        "__import__": _safe_import,
        "range": range,
        "len": len,
        "min": min,
        "max": max,
        "abs": abs,
        "sum": sum,
        "enumerate": enumerate,
        "zip": zip,
        "sorted": sorted,
        "any": any,
        "all": all,
        # additional harmless builtins to reduce false negatives
        "int": int,
        "float": float,
        "bool": bool,
        "round": round,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        # Common exception classes to allow generated code to raise/handle errors safely
        "BaseException": BaseException,
        "Exception": Exception,
        "RuntimeError": RuntimeError,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "NameError": NameError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AssertionError": AssertionError,
    }

    sandbox_globals = {
        "__builtins__": safe_builtins,
        "print": print,
    }

    # Inject guarded bpy proxy if available
    if bpy_module is not None:
        sandbox_globals["bpy"] = _BpyProxy(bpy_module)

    # Inject other allowed, pre-resolved modules (math, mathutils, etc.)
    sandbox_globals.update(resolved)

    if extra_symbols:
        sandbox_globals.update(extra_symbols)

    return sandbox_globals


def register():
    # No classes to register
    pass


def unregister():
    # No classes to unregister
    pass