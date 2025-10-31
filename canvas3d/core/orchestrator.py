# Canvas3D Orchestrator: Main controller for scene generation

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from typing import Any

from ..generation.spec_executor import SpecExecutionError, SpecExecutor
from ..utils.blender_helpers import append_history, get_prompt
from ..utils.traversability import is_spec_traversable
from .llm_interface import LLMInterface

try:
    import bpy  # for timers and main-thread execution
except Exception:
    bpy = None

logger = logging.getLogger(__name__)

class Canvas3DOrchestrator:
    """Orchestrates scene generation from prompt to execution with non-blocking, Blender-safe workflow."""

    def __init__(self) -> None:
        # Initialize components
        self.llm = LLMInterface()
        # New spec-based deterministic executor (preferred path)
        self.spec_executor = SpecExecutor()
        # Explicitly disable legacy code path to avoid attribute errors
        self.use_legacy_code_path = False

        # Always use spec-based executor for MVP. Legacy code path removed.
        # Internal state for async operations
        self._lock = threading.Lock()
        # Use typing aliases for compatibility across Python versions
        self._status_map: dict[str, str] = {}
        # Variants and controls memory per request_id (for selection/execution flow)
        self._variants_map: dict[str, list[dict]] = {}
        self._controls_map: dict[str, dict] = {}
        # Variants retention policy
        self._variants_timestamps: dict[str, float] = {}
        self._variants_ttl_sec: float = 600.0  # 10 minutes TTL
        self._variants_max_entries: int = 10   # cap variants bundles retained

        # Main-thread task queue: background threads enqueue callables to run on Blender main thread
        # Keep the Queue unparameterized for older Python compatibility
        self._main_thread_queue = queue.Queue()

        # Register a repeating timer to process main-thread queue when bpy is available
        if bpy and hasattr(bpy, "app") and hasattr(bpy.app, "timers"):
            def _process_queue() -> float:
                try:
                    # Process up to N tasks per tick to avoid long blocking
                    for _ in range(8):
                        try:
                            fn = self._main_thread_queue.get_nowait()
                        except Exception:
                            break
                        try:
                            fn()
                        except Exception as ex:
                            logger.error(f"Error in queued main-thread task: {ex}")
                    # Continue timer
                except Exception as ex:
                    logger.debug(f"Main-thread queue processing failed: {ex}")
                return 0.05  # run again in 50ms

            try:
                bpy.app.timers.register(_process_queue, first_interval=0.1)
            except Exception as ex:
                # If registering fails, that's fine; fallback will still use timers inline
                logger.debug(f"Failed to register queue timer: {ex}")

    def _set_status_main_thread(self, context: object, text: str) -> None:
        """Set status text on Blender main thread using bpy.app.timers if available."""
        def _apply() -> None:
            try:
                if context and hasattr(context, "scene") and hasattr(context.scene, "canvas3d_status"):
                    context.scene.canvas3d_status = text
            except Exception as ex:
                logger.debug(f"Failed to set status: {ex}")
            return None  # one-shot timer
        if bpy and hasattr(bpy, "app") and hasattr(bpy.app, "timers"):
            bpy.app.timers.register(_apply, first_interval=0.0)
        else:
            # Fallback when bpy is unavailable (tests/CI)
            logger.info(f"[status] {text}")

    def _friendly_error(self, err: Exception) -> str:
        """
        Convert low-level exceptions into user-facing, filmmaker-friendly messages.
        Keeps details concise and actionable.
        """
        try:
            s = str(err) if err is not None else ""
        except Exception:
            s = ""

        if not s:
            return "Unknown error"

        # Spec validation issues (path-scoped) -> simplified guidance
        if ("Scene spec validation failed" in s) or ("Generated spec failed validation" in s):
            tip = ("Spec invalid. Ensure: grid present with integer dimensions, object IDs ASCII and unique, "
                   "grid_cell col/row are integers, at least one light, and camera vectors are [x,y,z].")
            first = s.splitlines()[0]
            return f"{tip} Details: {first}"

        # Provider not implemented
        if "not yet implemented" in s.lower():
            return "Provider not implemented in this build. Enable Mock/Demo Mode in Preferences."

        # Rate limit / timeout classes of issues
        low = s.lower()
        if "rate limit" in low:
            return "Rate limited by provider. Wait a few seconds and try again."
        if "timeout" in low:
            return "The provider request timed out. Try again."

        # Default: first line only
        return s.splitlines()[0]

    def _traversability_gate(self, spec: dict, request_id: str, context: object, label: str = "spec") -> bool:
        """
        Gate execution for dungeon specs using traversability validation.
        - Only applies to domain == 'procedural_dungeon' (other domains pass through).
        - Logs telemetry (cols, rows, start, goal, blocked_count, path_len).
        - Appends a history entry for analytics.
        - Sets a user-facing status on failure with actionable guidance.
        Returns True if execution should proceed, False if blocked.
        """
        try:
            domain = str(spec.get("domain", "")).lower()
            if domain != "procedural_dungeon":
                return True

            ok, path_len, info = is_spec_traversable(spec)
            logger.info(f"[{request_id}] Traversability ({label}): ok={ok} path_len={path_len} info={info}")
            try:
                append_history({
                    "type": "traversability_check",
                    "request_id": request_id,
                    "label": label,
                    "ok": bool(ok),
                    "path_len": path_len,
                    "info": info,
                })
            except Exception as ex:
                logger.debug(f"append_history failed: {ex}")

            if not ok:
                msg = (
                    "Dungeon is not traversable end-to-end. Try generating again or tweak controls "
                    "(e.g., increase size, add more corridors/doors)."
                )
                self._set_status_main_thread(context, f"Error: {msg}")
                logger.warning(f"[{request_id}] Traversability gate failed for {label}: info={info}")
                return False

            return True
        except Exception as ex:
            # Fail open on unexpected validator errors; log for diagnostics
            logger.error(f"[{request_id}] Traversability gate error: {ex}")
            return True
    def start_generate_scene(self, prompt: str, context: object) -> str:
        """
        Start non-blocking scene generation. Returns a request_id used for log correlation.
        The LLM calls run in a background thread; the final scene execution is scheduled on Blender's main thread.
        """
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        self._set_status_main_thread(context, "Requesting scene spec from Anthropic...")
        with self._lock:
            self._status_map[request_id] = "starting"

        t = threading.Thread(
            target=self._worker_generate_scene,
            args=(prompt, context, request_id),
            name=f"Canvas3DGen-{request_id}",
            daemon=True,
        )
        t.start()
        return request_id

    # -------- Variants flow (generate 15–20 options, persist selection, execute) --------
    def start_generate_variants(self, prompt: str, controls: dict | None, context: object) -> str:
        """
        Start non-blocking generation of a high-quality bundle of scene spec variants.
        Stores variants and controls in memory keyed by request_id. UI can later call
        select_and_execute_variant(request_id, index, context) to run the chosen one.
        """
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        self._set_status_main_thread(context, "Requesting variants bundle from Anthropic...")
        with self._lock:
            self._status_map[request_id] = "variants_starting"
            self._controls_map[request_id] = dict(controls or {})
            # Opportunistic purge to enforce TTL/cap
            self._purge_variants()
        t = threading.Thread(
            target=self._worker_generate_variants,
            args=(prompt, controls or {}, context, request_id),
            name=f"Canvas3DVariants-{request_id}",
            daemon=True,
        )
        t.start()
        return request_id

    def start_load_spec(self, spec: dict[str, Any], context: object) -> str:
        """
        Start non-blocking loading of a JSON scene spec (from front-end) and build in Blender.
        Returns a request_id for status tracking.
        """
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        self._set_status_main_thread(context, "Loading scene spec...")
        with self._lock:
            self._status_map[request_id] = "loading"

        t = threading.Thread(
            target=self._worker_load_spec,
            args=(spec, context, request_id),
            name=f"Canvas3DLoad-{request_id}",
            daemon=True,
        )
        t.start()
        return request_id

    def _worker_generate_variants(self, prompt: str, controls: dict, context: object, request_id: str) -> None:
        """Background thread: request variant bundle and store it for selection."""
        start_ts = time.perf_counter()
        try:
            variants = self.llm.get_scene_spec_variants(
                prompt=prompt,
                controls=controls,
                request_id=request_id,
                count=20,
            )
            with self._lock:
                self._variants_map[request_id] = variants
                self._status_map[request_id] = f"variants_ready:{len(variants)}"
                self._variants_timestamps[request_id] = time.time()
                # Enforce TTL/cap after updating
                self._purge_variants()
            self._set_status_main_thread(context, f"Variants ready: {len(variants)} options. Select one to execute.")
            # Persist a history entry
            try:
                append_history({
                    "type": "variants_ready",
                    "request_id": request_id,
                    "count": len(variants),
                    "prompt": prompt,
                    "controls": controls,
                })
            except Exception as ex:
                logger.debug(f"append_history failed: {ex}")
        except Exception as e:
            friendly = self._friendly_error(e)
            self._set_status_main_thread(context, f"Error (variants): {friendly}")
            logger.error(f"[{request_id}] Variants generation failed: {e}")
        finally:
            dur = time.perf_counter() - start_ts
            logger.info(f"[{request_id}] Variants orchestration finished in {dur:.2f}s")

    def get_variant_spec(self, request_id: str, index: int) -> dict | None:
        """
        Return a single variant spec for a given request_id and index, or None if unavailable/out of range.
        """
        with self._lock:
            arr = self._variants_map.get(request_id) or []
            if not isinstance(arr, list):
                return None
            if index < 0 or index >= len(arr):
                return None
            try:
                # Return a shallow copy to avoid accidental mutation across callers
                spec = dict(arr[index])
            except Exception:
                spec = arr[index]
            return spec

    def get_variants_snapshot(self, request_id: str) -> list[dict]:
        """Return a shallow copy of variants for a given request_id (for UI listing)."""
        with self._lock:
            # Purge expired/overflow entries before returning snapshot
            self._purge_variants()
            arr = self._variants_map.get(request_id, [])
            return list(arr) if isinstance(arr, list) else []

    def _purge_variants(self) -> None:
        """Purge variants bundles by TTL and cap oldest to max entries."""
        try:
            now = time.time()
            # TTL-based purge
            expired = [rid for rid, ts in list(self._variants_timestamps.items()) if (now - float(ts)) > float(self._variants_ttl_sec)]
            for rid in expired:
                self._variants_map.pop(rid, None)
                self._controls_map.pop(rid, None)
                self._variants_timestamps.pop(rid, None)
            # Cap by max entries (evict oldest first)
            if len(self._variants_map) > int(self._variants_max_entries):
                ordered = sorted(self._variants_timestamps.items(), key=lambda kv: float(kv[1]))
                for rid, _ts in ordered:
                    if len(self._variants_map) <= int(self._variants_max_entries):
                        break
                    self._variants_map.pop(rid, None)
                    self._controls_map.pop(rid, None)
                    self._variants_timestamps.pop(rid, None)
        except Exception as ex:
            # Non-fatal
            logger.debug(f"Variants purge failed: {ex}")

    def clear_variants(self, request_id: str | None = None) -> int:
        """
        Clear stored variants:
        - When request_id provided, clears only that bundle and returns 1 if it existed else 0
        - When omitted, clears all bundles and returns count of cleared bundles
        """
        with self._lock:
            if isinstance(request_id, str) and request_id:
                existed = 1 if request_id in self._variants_map else 0
                self._variants_map.pop(request_id, None)
                self._controls_map.pop(request_id, None)
                self._variants_timestamps.pop(request_id, None)
                return existed
            count = len(self._variants_map)
            self._variants_map.clear()
            self._controls_map.clear()
            self._variants_timestamps.clear()
            return count

    def select_and_execute_variant(self, request_id: str, index: int, context: object) -> bool:  # noqa: C901
        """
        Persist selection and execute deterministically via SpecExecutor.
        Mirrors selected index into scene properties when available.
        """
        with self._lock:
            variants = self._variants_map.get(request_id) or []
            controls = self._controls_map.get(request_id) or {}
        if not variants:
            self._set_status_main_thread(context, "No variants available for this request.")
            return False
        if index < 0 or index >= len(variants):
            self._set_status_main_thread(context, f"Invalid variant index {index}.")
            return False

        spec = variants[index]
        # Traversability gate for dungeon domain; abort execution if unplayable
        if not self._traversability_gate(spec, request_id, context, label="variant"):
            return False
        # Mirror selection into scene custom properties if available
        try:
            if context and hasattr(context, "scene") and context.scene is not None:
                try:
                    context.scene["canvas3d_selected_request"] = request_id
                    context.scene["canvas3d_selected_variant_index"] = int(index)
                except Exception as ex:
                    logger.debug(f"Persist selected variant into scene failed: {ex}")
        except Exception as ex:
            logger.debug(f"Persist selected variant outer failed: {ex}")

        # Persist selection to history
        try:
            the_prompt = ""
            try:
                the_prompt = get_prompt(context) or ""
            except Exception as ex:
                logger.debug(f"get_prompt failed: {ex}")
            append_history({
                "type": "variant_selected",
                "request_id": request_id,
                "index": index,
                "prompt": the_prompt,
                "controls": controls,
                "spec_summary": {
                    "version": spec.get("version"),
                    "domain": spec.get("domain"),
                },
                "spec": spec,
            })
        except Exception as ex:
            logger.debug(f"[{request_id}] append_history failed: {ex}")

        # Execute on Blender's main thread if available
        self._set_status_main_thread(context, "Executing selected variant deterministically...")
        def _exec_on_main() -> None:
            try:
                commit_name = self.spec_executor.execute_scene_spec(
                    spec,
                    request_id=request_id,
                    expect_version="1.0.0",
                    dry_run_when_no_bpy=True,
                    cleanup_on_failure=True,
                )
                # Mirror last committed collection name into scene property (best-effort)
                try:
                    if context and hasattr(context, "scene") and context.scene is not None:
                        context.scene["canvas3d_last_collection"] = str(commit_name)
                except Exception as ex:
                    logger.debug(f"Mirror last collection name failed: {ex}")
                self._set_status_main_thread(context, f"Scene generated successfully (collection: {commit_name})")
                logger.info(f"[{request_id}] Selected variant executed successfully. commit={commit_name}")
            except SpecExecutionError as e:
                logger.error(f"[{request_id}] Spec execution error: {e}")
                friendly = self._friendly_error(e)
                self._set_status_main_thread(context, f"Error: {friendly}")
            except Exception as e:
                logger.error(f"[{request_id}] Unexpected execution error: {e}")
                friendly = self._friendly_error(e)
                self._set_status_main_thread(context, f"Error: {friendly}")
            return None

        if bpy and hasattr(bpy, "app") and hasattr(bpy.app, "timers"):
            bpy.app.timers.register(_exec_on_main, first_interval=0.0)
        else:
            try:
                commit_name = self.spec_executor.execute_scene_spec(
                    spec,
                    request_id=request_id,
                    expect_version="1.0.0",
                    dry_run_when_no_bpy=True,
                    cleanup_on_failure=False,
                )
                logger.info(f"[{request_id}] Dry-run complete (selected variant). bpy unavailable. commit={commit_name}")
            except Exception as e:
                logger.error(f"[{request_id}] Dry-run error (selected variant): {e}")
        return True

    def execute_spec(self, spec: dict, context: object, label: str = "local_regen") -> bool:
        """
        Execute a provided spec deterministically without calling the provider again.
        Appends a history entry with the full spec and mirrors the last committed collection
        name into the scene (when bpy is available).
        """
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        # Persist to history up-front for traceability
        try:
            append_history({
                "type": label,
                "request_id": request_id,
                "spec_summary": {
                    "version": spec.get("version"),
                    "domain": spec.get("domain"),
                },
                "spec": spec,
            })
        except Exception as ex:
            logger.debug(f"append_history failed: {ex}")

        # Traversability gate for dungeon domain; abort early if unplayable
        if not self._traversability_gate(spec, request_id, context, label="local"):
            return False
        self._set_status_main_thread(context, "Executing spec (local) deterministically...")

        def _exec_on_main() -> None:
            try:
                commit_name = self.spec_executor.execute_scene_spec(
                    spec,
                    request_id=request_id,
                    expect_version="1.0.0",
                    dry_run_when_no_bpy=True,
                    cleanup_on_failure=True,
                )
                # Mirror last committed collection into scene property
                try:
                    if context and hasattr(context, "scene") and context.scene is not None:
                        context.scene["canvas3d_last_collection"] = str(commit_name)
                except Exception as ex:
                    logger.debug(f"Mirror last collection name failed: {ex}")
                self._set_status_main_thread(context, f"Local regeneration complete (collection: {commit_name})")
                logger.info(f"[{request_id}] Local spec executed successfully. commit={commit_name}")
            except SpecExecutionError as e:
                logger.error(f"[{request_id}] Spec execution error: {e}")
                friendly = self._friendly_error(e)
                self._set_status_main_thread(context, f"Error: {friendly}")
            except Exception as e:
                logger.error(f"[{request_id}] Unexpected execution error: {e}")
                friendly = self._friendly_error(e)
                self._set_status_main_thread(context, f"Error: {friendly}")
            return None

        if bpy and hasattr(bpy, "app") and hasattr(bpy.app, "timers"):
            bpy.app.timers.register(_exec_on_main, first_interval=0.0)
        else:
            try:
                commit_name = self.spec_executor.execute_scene_spec(
                    spec,
                    request_id=request_id,
                    expect_version="1.0.0",
                    dry_run_when_no_bpy=True,
                    cleanup_on_failure=False,
                )
                logger.info(f"[{request_id}] Dry-run complete (local regen). bpy unavailable. commit={commit_name}")
            except Exception as e:
                logger.error(f"[{request_id}] Dry-run error (local regen): {e}")
        return True

    def _worker_generate_scene(self, prompt: str, context: object, request_id: str) -> None:
        """Background thread: LLM orchestration (Claude) and scheduling spec-based execution."""
        start_ts = time.perf_counter()
        try:
            # Step 1: Get scene spec from Anthropic (or fallback)
            scene_spec = self.llm.get_scene_spec(prompt, request_id=request_id)
            logger.debug(f"[{request_id}] Scene spec obtained")
            self._set_status_main_thread(context, "Validating scene spec...")
            # Traversability gate for dungeon domain; abort early if unplayable
            if not self._traversability_gate(scene_spec, request_id, context, label="single"):
                return

            if self.use_legacy_code_path:
                # Legacy path: generate Blender code and execute via SceneBuilder
                # Legacy code path removed; fall through to spec execution
                logger.info(f"[{request_id}] Legacy code path requested but removed in MVP; proceeding with spec execution.")
            else:
                # Spec-based deterministic path: execute via SpecExecutor
                self._set_status_main_thread(context, "Executing scene spec deterministically...")
                def _exec_on_main_spec() -> None:
                    try:
                        commit_name = self.spec_executor.execute_scene_spec(
                            scene_spec,
                            request_id=request_id,
                            expect_version="1.0.0",
                            dry_run_when_no_bpy=True,
                            cleanup_on_failure=True,
                        )
                        self._set_status_main_thread(context, f"Scene generated successfully (collection: {commit_name})")
                        logger.info(f"[{request_id}] Spec executed successfully. Committed collection: {commit_name}")
                    except SpecExecutionError as e:
                        logger.error(f"[{request_id}] Spec execution error: {e}")
                        friendly = self._friendly_error(e)
                        self._set_status_main_thread(context, f"Error: {friendly}")
                    except Exception as e:
                        logger.error(f"[{request_id}] Unexpected execution error: {e}")
                        friendly = self._friendly_error(e)
                        self._set_status_main_thread(context, f"Error: {friendly}")
                    return None  # one-shot

                if bpy and hasattr(bpy, "app") and hasattr(bpy.app, "timers"):
                    bpy.app.timers.register(_exec_on_main_spec, first_interval=0.0)
                else:
                    # No bpy: validate + dry-run succeeds via SpecExecutor
                    try:
                        commit_name = self.spec_executor.execute_scene_spec(
                            scene_spec,
                            request_id=request_id,
                            expect_version="1.0.0",
                            dry_run_when_no_bpy=True,
                            cleanup_on_failure=False,
                        )
                        logger.info(f"[{request_id}] Dry-run complete (spec). bpy unavailable. commit={commit_name}")
                    except Exception as e:
                        logger.error(f"[{request_id}] Dry-run error (spec): {e}")

        except Exception as e:
            logger.error(f"[{request_id}] Scene generation failed during LLM orchestration: {e}")
            friendly = self._friendly_error(e)
            self._set_status_main_thread(context, f"Error: {friendly}")
        finally:
            dur = time.perf_counter() - start_ts
            logger.info(f"[{request_id}] Orchestration finished in {dur:.2f}s")

    def generate_scene(self, prompt: str, context: object) -> bool:
        """
        Synchronous generation for compatibility (prefer start_generate_scene() for non-blocking).
        Uses spec-based deterministic executor unless legacy feature flag is enabled.
        """
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        try:
            self._set_status_main_thread(context, "Requesting scene spec from Anthropic...")
            scene_spec = self.llm.get_scene_spec(prompt, request_id=request_id)
            self._set_status_main_thread(context, "Validating scene spec...")
            if not self._traversability_gate(scene_spec, request_id, context, label="single_sync"):
                return False
            self._set_status_main_thread(context, "Executing scene spec deterministically...")
            commit_name = self.spec_executor.execute_scene_spec(
                scene_spec,
                request_id=request_id,
                expect_version="1.0.0",
                dry_run_when_no_bpy=True,
                cleanup_on_failure=True,
            )
            self._set_status_main_thread(context, f"Scene generated successfully (collection: {commit_name})")
            return True
        except Exception as e:
            logger.error(f"[{request_id}] Scene generation failed: {e}")
            friendly = self._friendly_error(e)
            self._set_status_main_thread(context, f"Error: {friendly}")
            return False

# Registration (no-op for now)
def register() -> None:
    pass

def unregister() -> None:
    pass
# --- Orchestrator singleton for shared variant memory across operators ---

_SINGLETON: Canvas3DOrchestrator | None = None

def get_orchestrator() -> Canvas3DOrchestrator:
    """
    Module-level singleton to ensure variants/state are shared across UI operators
    within the Blender session.
    """
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = Canvas3DOrchestrator()
    return _SINGLETON
