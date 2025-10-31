# Utility helpers for Blender context, preferences, and secure key management for Canvas3D
#
# Responsibilities:
# - Safe access to Blender AddonPreferences when bpy is available
# - Fallback to environment variables and optional local config files when not
# - In-memory caching of keys with thread-safety and rotation support
# - No logging of secrets; only masked values in debug output
# - Cross-platform config path resolution (Windows/macOS/Linux)
# - UI helpers for status/prompt interactions kept lightweight and safe
#
# Environment variables supported:
#   OPENAI_API_KEY, CANVAS3D_OPENAI_KEY
#   CANVAS3D_MOCK_MODE (truthy: "1", "true", "yes", "on")
#
# Optional config file (JSON) search order:
#   1) %APPDATA%/Canvas3D/config.json (Windows)
#   2) ~/.config/canvas3d/config.json (Linux/XDG default)
#   3) ~/Library/Application Support/Canvas3D/config.json (macOS)
#   4) ~/.canvas3d/config.json (legacy fallback)

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Optional, Tuple, Dict, Any, List

try:
    import bpy  # type: ignore
except Exception:
    bpy = None  # Allows import outside Blender for tooling/tests and CI

logger = logging.getLogger(__name__)

# The add-on module name as installed by Blender. Must match the top-level package.
ADDON_ID = "canvas3d"

# In-memory cache (thread-safe) for API keys and mock mode, with TTL
_API_CACHE_LOCK = threading.Lock()
_API_CACHE: Dict[str, Any] = {
    "openai": "",
    "mock": False,
    "ts": 0.0,
}
_CACHE_TTL_SEC = 5.0  # small TTL to allow runtime rotation without heavy reads


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in {"1", "true", "yes", "on"}


def _mask(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    return ("*" * max(0, len(value) - visible)) + value[-visible:]


def _config_paths() -> List[str]:
    paths: List[str] = []
    # Windows
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(os.path.join(appdata, "Canvas3D", "config.json"))
    # Linux (XDG)
    home = os.path.expanduser("~")
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config"))
    paths.append(os.path.join(xdg_config_home, "canvas3d", "config.json"))
    # macOS
    paths.append(os.path.join(home, "Library", "Application Support", "Canvas3D", "config.json"))
    # Legacy fallback
    paths.append(os.path.join(home, ".canvas3d", "config.json"))
    return paths


def _load_config_file() -> Dict[str, Any]:
    for path in _config_paths():
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as ex:
            logger.warning(f"Failed reading config file {path}: {ex}")
    return {}


def get_addon_prefs():
    """
    Return the Canvas3D AddonPreferences instance or None if unavailable.
    Accesses Blender's preferences store for the add-on identified by ADDON_ID.
    """
    if bpy is None:
        logger.debug("bpy not available; get_addon_prefs returning None")
        return None

    try:
        prefs = getattr(bpy.context, "preferences", None)
        if not prefs:
            return None
        addon = prefs.addons.get(ADDON_ID)
        if not addon:
            return None
        return getattr(addon, "preferences", None)
    except Exception as ex:
        logger.warning(f"Failed to get add-on preferences: {ex}")
        return None


def _get_env_keys() -> Tuple[str, str, Optional[bool]]:
    a = (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("CANVAS3D_ANTHROPIC_KEY")
        or ""
    )
    o = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("CANVAS3D_OPENAI_KEY")
        or ""
    )
    m_env = os.environ.get("CANVAS3D_MOCK_MODE")
    m: Optional[bool] = _truthy(m_env) if m_env is not None else None
    return a, o, m


def _get_config_keys() -> Tuple[str, str, Optional[bool]]:
    cfg = _load_config_file()
    a = str(cfg.get("anthropic_api_key", "") or "")
    o = str(cfg.get("openai_api_key", "") or "")
    m_raw = cfg.get("mock_mode", None)
    m: Optional[bool] = bool(m_raw) if isinstance(m_raw, bool) else (_truthy(m_raw) if m_raw is not None else None)
    return a, o, m


def _should_reload_cache(now: float) -> bool:
    with _API_CACHE_LOCK:
        ts = float(_API_CACHE.get("ts", 0.0))
    return (now - ts) > _CACHE_TTL_SEC


def reload_api_keys() -> Tuple[str, str, bool]:
    """
    Force reload API keys into cache (ignoring TTL).
    Returns (anthropic_key, openai_key, mock_mode).
    """
    with _API_CACHE_LOCK:
        _API_CACHE["ts"] = 0.0
    return get_api_keys(force_reload=True)


def get_api_keys(force_reload: bool = False) -> Tuple[str, str, bool]:
    """
    Retrieve Anthropic/OpenAI API keys and mock mode with precedence:
      1) Blender AddonPreferences (if available)
      2) Environment variables
      3) Config file
    Returns a tuple (anthropic_key, openai_key, mock_mode).
    Values are cached in-memory with a short TTL, and can be force reloaded.
    """
    now = time.time()
    if not force_reload and not _should_reload_cache(now):
        with _API_CACHE_LOCK:
            return (
                str(_API_CACHE.get("anthropic", "")),
                str(_API_CACHE.get("openai", "")),
                bool(_API_CACHE.get("mock", False)),
            )

    # Preferences (highest precedence)
    anthropic = ""
    openai = ""
    mock: Optional[bool] = None

    prefs = get_addon_prefs()
    if prefs is not None:
        try:
            anthropic = str(getattr(prefs, "anthropic_api_key", "") or "")
            openai = str(getattr(prefs, "openai_api_key", "") or "")
            mock = bool(getattr(prefs, "mock_mode", False))
        except Exception as ex:
            logger.warning(f"Error accessing AddonPreferences: {ex}")

    # Environment fallback (only fill if missing from prefs)
    env_a, env_o, env_m = _get_env_keys()
    if not anthropic and env_a:
        anthropic = env_a
    if not openai and env_o:
        openai = env_o
    if mock is None and env_m is not None:
        mock = env_m

    # Config file fallback (only fill if still missing)
    if not anthropic or not openai or mock is None:
        cfg_a, cfg_o, cfg_m = _get_config_keys()
        if not anthropic and cfg_a:
            anthropic = cfg_a
        if not openai and cfg_o:
            openai = cfg_o
        if mock is None and cfg_m is not None:
            mock = cfg_m

    resolved_mock = bool(mock) if mock is not None else False

    # Only OpenAI is supported (disable Anthropic/Claude)
    anthropic = ""
    # Store to cache
    with _API_CACHE_LOCK:
        _API_CACHE["anthropic"] = anthropic
        _API_CACHE["openai"] = openai
        _API_CACHE["mock"] = resolved_mock
        _API_CACHE["ts"] = now

    # Debug logs (masked)
    logger.debug(
        "API keys loaded: openai=%s, mock=%s",
        _mask(openai),
        resolved_mock,
    )

    return anthropic, openai, resolved_mock


def set_status(context, text: str) -> None:
    """
    Safely set the Canvas3D status text on the scene, if the property exists.
    This avoids attribute errors if the UI panel has not registered properties yet.
    """
    if not context:
        return
    try:
        scene = getattr(context, "scene", None)
        if scene and hasattr(scene, "canvas3d_status"):
            scene.canvas3d_status = text
    except Exception as ex:
        logger.debug(f"Failed to set status: {ex}")


def get_prompt(context) -> str:
    """
    Retrieve the current Canvas3D prompt from the scene if available, else empty string.
    """
    if not context:
        return ""
    try:
        scene = getattr(context, "scene", None)
        if scene and hasattr(scene, "canvas3d_prompt"):
            return scene.canvas3d_prompt or ""
    except Exception as ex:
        logger.debug(f"Failed to get prompt: {ex}")
    return ""


def register():
    # No classes to register in utils
    pass


def unregister():
    # No classes to unregister in utils
    pass
# --- Persistence helpers: config dir and generation history ---

def get_config_dir() -> str:
    """
    Resolve and ensure the Canvas3D config directory exists, following the same
    platform-specific search order as _config_paths(), but returning a directory.
    """
    try:
        paths = _config_paths()
        dirs = [os.path.dirname(p) for p in paths]
        for d in dirs:
            try:
                if not os.path.isdir(d):
                    os.makedirs(d, exist_ok=True)
                return d
            except Exception:
                continue
    except Exception as ex:
        logger.debug(f"get_config_dir: could not resolve preferred paths: {ex}")

    # Fallback to legacy directory under home
    home = os.path.expanduser("~")
    fallback = os.path.join(home, ".canvas3d")
    try:
        os.makedirs(fallback, exist_ok=True)
    except Exception:
        pass
    return fallback


def get_history_path() -> str:
    """
    Return the absolute path to the Canvas3D generation history JSON file.
    Ensures the parent directory exists.
    """
    cfg = get_config_dir()
    return os.path.join(cfg, "history.json")


def append_history(entry: Dict[str, Any]) -> None:
    """
    Append a single history entry to the Canvas3D history JSON file.
    The file format is a JSON array of objects. Non-array or corrupt files are reset.
    Adds a 'ts' timestamp to the entry.
    """
    path = get_history_path()
    # Read existing array or reset
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        else:
            data = []
    except Exception:
        data = []

    e = dict(entry) if isinstance(entry, dict) else {"entry": str(entry)}
    try:
        e.setdefault("ts", time.time())
    except Exception:
        e["ts"] = time.time()

    data.append(e)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as ex:
        logger.warning(f"Failed to write history {path}: {ex}")
# --- History reading helpers ---


def read_history(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Read the Canvas3D generation history JSON array.
    Returns a list of entries (dict). If limit is provided, returns the most recent N entries.
    """
    path = get_history_path()
    data: List[Dict[str, Any]] = []
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                data = raw
    except Exception as ex:
        logger.warning(f"Failed to read history {path}: {ex}")
        data = []
    if isinstance(limit, int) and limit > 0 and len(data) > limit:
        return data[-limit:]
    return data

def summarize_history_entry(entry: Dict[str, Any]) -> str:
    """
    Produce a compact human-readable summary for a history entry.
    """
    try:
        typ = str(entry.get("type", "unknown"))
        req = str(entry.get("request_id", "") or "")
        idx = entry.get("index", None)
        cnt = entry.get("count", None)
        spec = entry.get("spec", {}) or {}
        dom = str(spec.get("domain", entry.get("controls", {}).get("domain", "")) or "")
        ts = entry.get("ts", None)
        parts: List[str] = []
        parts.append(typ)
        if dom:
            parts.append(f"domain={dom}")
        if isinstance(idx, int):
            parts.append(f"index={idx}")
        if isinstance(cnt, int):
            parts.append(f"count={cnt}")
        if req:
            parts.append(f"req={req}")
        if isinstance(ts, (int, float)):
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(ts)
                parts.append(dt.strftime("%Y-%m-%d %H:%M"))
            except Exception:
                parts.append(f"ts={ts}")
        return " | ".join(parts)
    except Exception:
        return "history-entry"
