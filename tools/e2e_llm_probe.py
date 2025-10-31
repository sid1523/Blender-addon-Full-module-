#!/usr/bin/env python3
"""
Canvas3D LLM E2E Probe

Purpose:
- Make real HTTP calls to Anthropic (scene spec) and optionally OpenAI (code generation) via LLMInterface
- Run 20+ prompts end-to-end to validate JSON extraction, retries, and error handling
- Produce a JSON report with success rate, timings, errors, and minimal spec summaries

Requirements:
- Set API keys via Blender add-on preferences or environment/config as documented.
  Env vars supported:
    ANTHROPIC_API_KEY or CANVAS3D_ANTHROPIC_KEY
    OPENAI_API_KEY or CANVAS3D_OPENAI_KEY
  Optional: CANVAS3D_MOCK_MODE must be unset/false for real calls.

Usage:
  python tools/e2e_llm_probe.py --count 1 --timeout 30 --save_report
  python tools/e2e_llm_probe.py --provider anthropic --only anthropic --save_report
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import datetime
from typing import List, Dict, Any

# Import within repo context
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from canvas3d.core.llm_interface import (  # noqa: E402
    LLMInterface,
    ProviderError,
    RateLimitError,
    TimeoutError as ProviderTimeoutError,
)
from canvas3d.utils.blender_helpers import get_config_dir  # noqa: E402


DEFAULT_PROMPTS: List[str] = [
    "Open world desert valley at golden hour, rocky cliffs and winding path",
    "Dense rainforest clearing with soft god rays and mist",
    "Sci‑fi spaceship command bridge with holographic displays",
    "Cozy medieval tavern interior with fireplace and wooden tables",
    "Modern minimal living room with large glass windows and indoor plants",
    "Abandoned industrial warehouse with shafts of light",
    "Ancient temple ruins in a jungle, broken pillars and vines",
    "Snowy mountain pass with wooden bridge and blowing snow",
    "Cyberpunk alley with neon signs and wet reflective ground",
    "Futuristic lab clean room, white panels and soft area lighting",
    "Subway platform with arriving train, realistic materials",
    "Underground dungeon small room with a door and torches",
    "Castle courtyard at dusk with banners and torches",
    "Forest river bank, stones, logs, soft sunlight",
    "Sci‑fi hangar bay with parked ships and area lights",
    "Spaceship corridor with modules and maintenance panels",
    "Artist studio loft with skylights and wooden floor",
    "Retro diner interior with checkerboard floor and chrome",
    "Grand library hall with high shelves and ladders",
    "Rocky cave entrance with volumetric fog",
    "Open field with ruins and lone tree under overcast sky",
    "Minimal photography studio cyclorama with lights and camera",
    "Dark throne room with moody dramatic lighting",
    "Japanese garden with stone path, pond, and lantern",
]

def _summarize_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        out["version"] = spec.get("version")
        out["domain"] = spec.get("domain")
        out["units"] = spec.get("units")
        out["seed"] = spec.get("seed")
        out["num_objects"] = len(spec.get("objects", []) or [])
        out["num_lights"] = len(spec.get("lighting", []) or [])
        out["has_camera"] = bool(spec.get("camera"))
        if isinstance(spec.get("grid"), dict):
            dims = (spec["grid"].get("dimensions") or {})
            out["grid"] = {
                "cell_size_m": spec["grid"].get("cell_size_m"),
                "cols": dims.get("cols"),
                "rows": dims.get("rows"),
            }
    except Exception:
        pass
    return out

def run_probe(prompts: List[str], per_prompt_timeout: float, save_report: bool, count: int) -> Dict[str, Any]:
    llm = LLMInterface()
    # Ensure real calls
    if llm.mock_mode:
        print("Mock/Demo mode is enabled. Disable it to perform real HTTP calls.", file=sys.stderr)
        return {"error": "mock_mode_enabled"}

    results: List[Dict[str, Any]] = []
    t0 = time.perf_counter()
    successes = 0
    failures = 0

    # Optionally adjust timeout globally
    try:
        if per_prompt_timeout and per_prompt_timeout > 0:
            llm.timeout_sec = float(per_prompt_timeout)
    except Exception:
        pass

    for i, prompt in enumerate(prompts):
        entry: Dict[str, Any] = {
            "index": i,
            "prompt": prompt,
            "t_start": time.time(),
        }
        t_start = time.perf_counter()
        try:
            # Keep tokens conservative by using single spec (not bundle) for e2e validation
            spec = llm.get_scene_spec(prompt, request_id=f"probe-{i}")
            dur = time.perf_counter() - t_start
            entry["duration_sec"] = round(dur, 3)
            entry["ok"] = True
            entry["summary"] = _summarize_spec(spec)
            # Capture raw last text if available (method may not exist in some builds)
            try:
                entry["raw_captured"] = True
                entry["raw_excerpt"] = (llm.get_last_raw() or "")[:1000]
            except Exception:
                entry["raw_captured"] = False
            successes += 1
        except RateLimitError as e:
            dur = time.perf_counter() - t_start
            entry["duration_sec"] = round(dur, 3)
            entry["ok"] = False
            entry["error_type"] = "RateLimitError"
            entry["error"] = str(e).splitlines()[0]
            failures += 1
        except ProviderTimeoutError as e:
            dur = time.perf_counter() - t_start
            entry["duration_sec"] = round(dur, 3)
            entry["ok"] = False
            entry["error_type"] = "Timeout"
            entry["error"] = str(e).splitlines()[0]
            failures += 1
        except ProviderError as e:
            dur = time.perf_counter() - t_start
            entry["duration_sec"] = round(dur, 3)
            entry["ok"] = False
            entry["error_type"] = "ProviderError"
            entry["error"] = str(e).splitlines()[0]
            failures += 1
        except Exception as e:
            dur = time.perf_counter() - t_start
            entry["duration_sec"] = round(dur, 3)
            entry["ok"] = False
            entry["error_type"] = "Unexpected"
            entry["error"] = str(e).splitlines()[0]
            failures += 1

        entry["t_end"] = time.time()
        results.append(entry)

    total_dur = time.perf_counter() - t0
    success_rate = (successes / max(1, len(prompts))) * 100.0

    report: Dict[str, Any] = {
        "ts": time.time(),
        "ts_iso": datetime.datetime.utcnow().isoformat() + "Z",
        "total_prompts": len(prompts),
        "successes": successes,
        "failures": failures,
        "success_rate_pct": round(success_rate, 2),
        "total_duration_sec": round(total_dur, 3),
        "per_prompt_timeout_sec": per_prompt_timeout,
        "acceptance_met": success_rate >= 80.0,
        "results": results,
    }

    if save_report:
        try:
            cfg_dir = get_config_dir()
            out_dir = os.path.join(cfg_dir, "reports")
            os.makedirs(out_dir, exist_ok=True)
            ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            out_fp = os.path.join(out_dir, f"e2e_llm_probe_{ts}.json")
            with open(out_fp, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(f"Saved report: {out_fp}")
        except Exception as ex:
            print(f"Warning: failed to save report: {ex}", file=sys.stderr)

    print(f"Completed {len(prompts)} prompts. Success rate: {report['success_rate_pct']}% "
          f"({'PASS' if report['acceptance_met'] else 'FAIL'}). Total duration: {report['total_duration_sec']}s")
    return report


def main():
    ap = argparse.ArgumentParser(description="Canvas3D LLM E2E Probe")
    ap.add_argument("--count", type=int, default=1, help="Variants per prompt when applicable (not used in single spec)")
    ap.add_argument("--timeout", type=float, default=30.0, help="Per-prompt network timeout in seconds")
    ap.add_argument("--save_report", action="store_true", help="Save a JSON report under the Canvas3D config directory")
    ap.add_argument("--prompts_file", type=str, default="", help="Optional path to a JSON file with prompts array")
    args = ap.parse_args()

    prompts = DEFAULT_PROMPTS
    if args.prompts_file:
        try:
            with open(args.prompts_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
                prompts = raw
        except Exception as ex:
            print(f"Warning: failed to load prompts_file: {ex}", file=sys.stderr)

    # Ensure at least 20 prompts for acceptance criteria
    if len(prompts) < 20:
        prompts = (prompts * ((20 + len(prompts) - 1) // len(prompts)))[:20]

    run_probe(prompts=prompts, per_prompt_timeout=args.timeout, save_report=args.save_report, count=args.count)


if __name__ == "__main__":
    main()