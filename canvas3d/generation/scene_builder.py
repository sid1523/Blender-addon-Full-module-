# Canvas3D Scene Builder: Safe execution of generated Blender code

import logging
import time
import random
from typing import Optional

from ..utils.validation import validate_scene_code, make_restricted_globals, CodeValidationError
from ..utils.cleanup import snapshot_datablocks, cleanup_new_datablocks

try:
    import bpy
except Exception:
    bpy = None

logger = logging.getLogger(__name__)

class SceneExecutionError(Exception):
    """Raised when scene code fails validation or execution."""
    pass

class SceneBuilder:
    """Executes generated Blender code with basic safety checks."""

    def __init__(self) -> None:
        pass

    def execute_scene_code(
        self,
        code: str,
        request_id: Optional[str] = None,
        timeout_sec: Optional[float] = None,
        dry_run_when_no_bpy: bool = True,
        cleanup_on_failure: bool = True,
    ) -> None:
        """
        Validate and execute Blender Python code in a restricted environment.
        Raises SceneExecutionError on failure.

        Parameters:
        - request_id: Correlates logs across the pipeline (used for structured logging)
        - timeout_sec: Optional soft limit for execution time; logs warning if exceeded
        - dry_run_when_no_bpy: When True, perform validation/compilation only outside Blender
        - cleanup_on_failure: Attempt removal of newly created objects if execution fails
        """
        req_id = request_id or "req-unknown"
        start_ts = time.perf_counter()

        # Deterministic behavior where possible
        random.seed(0)

        if not isinstance(code, str) or not code.strip():
            raise SceneExecutionError("Empty code string")

        # Validate code safety using centralized validators (AST + allowlist)
        try:
            validate_scene_code(code)
        except CodeValidationError as e:
            raise SceneExecutionError(f"[{req_id}] Validation failed: {e}") from e

        # Degrade gracefully when bpy is unavailable (e.g., CI, headless unit tests)
        if bpy is None:
            if dry_run_when_no_bpy:
                try:
                    # Compile only, using request-scoped filename for clear tracebacks
                    compile(code, f"<canvas3d_scene:{req_id}>", "exec", dont_inherit=True, optimize=2)
                except Exception as e:
                    raise SceneExecutionError(f"[{req_id}] Compilation failed outside Blender: {e}") from e
                finally:
                    dur = time.perf_counter() - start_ts
                    logger.info(f"[{req_id}] Dry-run validation complete in {dur:.3f}s (bpy unavailable)")
                return
            else:
                raise SceneExecutionError(f"[{req_id}] bpy module not available. Run inside Blender.")

        # Compile with request-id annotated filename for clearer error context
        try:
            compiled = compile(code, f"<canvas3d_scene:{req_id}>", "exec", dont_inherit=True, optimize=2)
        except Exception as e:
            logger.error(f"[{req_id}] Code compilation failed: {e}")
            raise SceneExecutionError(f"[{req_id}] Compilation failed: {e}") from e

        # Snapshot existing datablocks for targeted cleanup on failure
        pre = snapshot_datablocks(bpy)

        # Restricted globals using centralized helper (no builtins, allowlisted symbols only)
        safe_globals = make_restricted_globals(bpy)
        safe_locals = {}

        try:
            exec(compiled, safe_globals, safe_locals)
        except Exception as e:
            # Extract line info from traceback referencing our compiled filename
            line_info = ""
            tb = e.__traceback__
            while tb:
                frame = tb.tb_frame
                fname = frame.f_code.co_filename
                if isinstance(fname, str) and fname.startswith("<canvas3d_scene"):
                    line_info = f" at {fname}, line {tb.tb_lineno}"
                tb = tb.tb_next

            logger.error(f"[{req_id}] Scene execution failed{line_info}: {e}")

            if cleanup_on_failure:
                try:
                    cleanup_new_datablocks(pre, None, bpy)
                    logger.info(f"[{req_id}] Cleanup complete.")
                except Exception as cleanup_err:
                    logger.warning(f"[{req_id}] Cleanup encountered an error: {cleanup_err}")

            raise SceneExecutionError(f"[{req_id}] Execution failed{line_info}: {e}") from e
        finally:
            dur = time.perf_counter() - start_ts
            if timeout_sec is not None and dur > timeout_sec:
                logger.warning(f"[{req_id}] Execution exceeded soft timeout {timeout_sec:.2f}s (actual {dur:.2f}s)")

        logger.info(f"[{req_id}] Scene executed successfully in {dur:.3f}s.")

# Registration (no-op)
def register():
    pass

def unregister():
    pass