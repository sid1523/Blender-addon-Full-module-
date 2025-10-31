# Canvas3D LLM Interface: OpenAI ChatGPT integration with reliable retry,
# rate limiting, circuit breaking, backoff with jitter, and typed errors.
# Uses strict JSON parsing and schema validation.

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

import requests

from ..utils.blender_helpers import get_addon_prefs, get_api_keys
from ..utils.spec_validation import validate_scene_spec

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Typed exceptions for clearer user guidance
class ProviderError(Exception):
    """Generic provider error with user-facing guidance."""
    pass

class RateLimitError(ProviderError):
    """Rate limit exceeded."""
    pass

class ProviderTimeoutError(ProviderError):
    """Request timed out."""
    pass

class CircuitOpenError(ProviderError):
    """Circuit breaker is open; rejecting requests temporarily."""
    pass

def _mask(value: str) -> str:
    if not value:
        return ""
    return ("*" * max(0, len(value) - 4)) + value[-4:]

class TokenBucket:
    """Token-bucket rate limiter for O(1) checks and burst handling."""

    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._last = time.time()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.time()
        with self._lock:
            delta = now - self._last
            self._tokens = min(self.capacity, self._tokens + delta * self.rate)
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

# Global OpenAI rate limiter (60 requests/minute default)
_OPENAI_RATE_LIMITER = TokenBucket(rate=60/60.0, capacity=60)

class CircuitBreaker:
    """Basic circuit breaker with open/half-open/closed states."""

    def __init__(self, failure_threshold: int = 3, reset_timeout_sec: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_sec = reset_timeout_sec
        self._failures = 0
        self._state = "closed"  # closed|open|half-open
        self._opened_at = 0.0
        self._lock = threading.Lock()

    def on_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "closed"

    def on_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.time()

    def can_request(self) -> bool:
        with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                if time.time() - self._opened_at >= self.reset_timeout_sec:
                    self._state = "half-open"
                    return True
                return False
            if self._state == "half-open":
                return True
            return True

    def on_http_error(self, status_code: int) -> None:
        """Increment failure count only for real HTTP errors (500+ or 429)."""
        if status_code >= 500 or status_code == 429:
            self.on_failure()

    def on_timeout(self) -> None:
        """Timeouts are considered transient and do not trip the circuit."""
        pass

class LLMInterface:
    """Handles API calls to OpenAI ChatGPT in a resilient manner."""

    def __init__(self) -> None:
        # Secrets and mock mode from centralized helpers
        self.openai_key = ""
        self.mock_mode = False
        self._load_preferences()

        # Provider config with sane defaults
        self.openai_model = "gpt-4"
        self.temperature = 0.2
        self.max_tokens = 4000
        self.timeout_sec = 60.0
        self.openai_endpoint = "https://api.openai.com/v1/chat/completions"

        # Reliability primitives
        self._openai_circuit = CircuitBreaker(failure_threshold=3, reset_timeout_sec=30.0)
        
        # Last raw response for debugging
        self._last_raw = ""
        
        # Apply optional provider configuration overrides from preferences
        self._load_preferences()

    def _load_preferences(self) -> None:
        """Load API keys and provider configuration from Blender AddonPreferences and environment."""
        try:
            _, openai, mock = get_api_keys()
            self.openai_key = openai
            self.mock_mode = mock
            logger.debug(
                "Prefs loaded: mock_mode=%s, openai=%s",
                self.mock_mode,
                "set" if bool(self.openai_key) else "empty",
            )
        except Exception as ex:
            logger.warning(f"Could not load API keys, using defaults: {ex}")

        # Optional provider config from AddonPreferences
        try:
            prefs = get_addon_prefs()
            if prefs is not None:
                try:
                    ep = str(getattr(prefs, "openai_endpoint", "") or "").strip()
                    if ep:
                        self.openai_endpoint = ep
                except Exception as ex:
                    logger.debug("openai_endpoint preference read failed: %s", ex)
                try:
                    mdl = str(getattr(prefs, "openai_model", "") or "").strip()
                    if mdl:
                        self.openai_model = mdl
                except Exception as ex:
                    logger.debug("openai_model preference read failed: %s", ex)
                try:
                    to = float(getattr(prefs, "request_timeout_sec", 0.0) or 0.0)
                    if to >= 1.0:
                        self.timeout_sec = to
                except Exception as ex:
                    logger.debug("request_timeout_sec preference read failed: %s", ex)
        except Exception as ex:
            logger.debug(f"Provider config not loaded from AddonPreferences: {ex}")

    def _retry_with_backoff_jitter(
        self,
        func: Callable[[], T],
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        request_id: str | None = None,
        on_success: Callable[[], None] | None = None,
        on_failure: Callable[[], None] | None = None,
    ) -> T:
        """Retry with exponential backoff and jitter."""
        req = request_id or "req-unknown"
        delay = base_delay
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                result = func()
                if on_success:
                    on_success()
                return result
            except Exception as e:
                last_exc = e
                if on_failure:
                    on_failure()
                if attempt == max_retries - 1:
                    break
                jitter = secrets.SystemRandom().uniform(0.0, 0.25 * delay)
                sleep_for = min(max_delay, delay + jitter)
                logger.warning(f"[{req}] Attempt {attempt+1} failed: {e}. Retrying in {sleep_for:.2f}s...")
                time.sleep(sleep_for)
                delay = min(max_delay, delay * 2.0)
        if last_exc is None:
            raise ProviderError(f"[{req}] Retry exhaustion without captured exception")
        raise last_exc

    def _http_post(self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> requests.Response:
        """Execute HTTP POST with timeout."""
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            self._last_raw = response.text
            return response
        except requests.Timeout as e:
            raise ProviderTimeoutError(f"Request timed out after {timeout}s") from e
        except requests.RequestException as e:
            raise ProviderError(f"Network error: {e}") from e

    def _strip_code_fences(self, text: str) -> str:
        """Remove triple backtick fences and optional 'json' language tag."""
        if not isinstance(text, str):
            return ""
        s = text.strip()
        if "```" in s:
            start = s.find("```")
            end = s.find("```", start + 3)
            if start != -1 and end != -1 and end > start:
                inner = s[start + 3:end]
                lines = inner.splitlines()
                if lines and lines[0].strip().lower().startswith("json"):
                    inner = "\n".join(lines[1:])
                return inner.strip()
        return s

    def _extract_json_balanced(self, text: str) -> str:
        """Extract a balanced top-level JSON object by scanning braces."""
        s = self._strip_code_fences(str(text))
        start = s.find("{")
        if start == -1:
            raise ValueError("Could not locate '{' in response")
        depth = 0
        end_index = -1
        i = start
        while i < len(s):
            ch = s[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_index = i
                    break
            i += 1
        if end_index == -1:
            end = s.rfind("}")
            if end == -1 or end <= start:
                raise ValueError("Could not locate balanced JSON object in response")
            return s[start:end + 1]
        return s[start:end_index + 1]

    def _sanitize_and_validate_scene_spec(self, payload: object, request_id: str | None = None) -> dict[str, Any]:
        """Parse and validate scene spec JSON."""
        req = request_id or "req-unknown"

        if isinstance(payload, dict):
            spec = payload
        else:
            raw = str(payload)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                stripped = self._strip_code_fences(raw)
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    try:
                        content = self._extract_json_balanced(stripped)
                        parsed = json.loads(content)
                    except Exception as ex:
                        snippet = raw[:200].replace("\n", " ")
                        raise ProviderError(
                            f"[{req}] OpenAI did not return valid JSON. Raw response (first 200 chars): {snippet}"
                        ) from ex
            spec = parsed

        ok, issues = validate_scene_spec(spec, expect_version="1.0.0")
        if not ok:
            summarized = "; ".join(f"{i.path}: {i.message}" for i in issues[:5])
            raise ProviderError(f"[{req}] Generated spec failed validation: {summarized}")
        return spec

    def get_scene_spec(  # noqa: C901
        self,
        prompt: str,
        request_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Get scene specification JSON from OpenAI ChatGPT."""
        req = request_id or "req-unknown"

        if not self.openai_key:
            raise ProviderError(f"[{req}] OpenAI API key not configured. Set it in preferences or via environment.")

        if not _OPENAI_RATE_LIMITER.allow():
            raise RateLimitError("OpenAI rate limit exceeded; please wait and retry.")
        if not self._openai_circuit.can_request():
            raise CircuitOpenError("OpenAI circuit open due to recent failures; retry later.")

        def do_call() -> str:  # noqa: C901
            system_prompt = (
                "You are an AI assistant that generates 3D scene specifications in JSON format. "
                "Return ONLY a single valid JSON object conforming to the Canvas3D scene spec schema. "
                "Do not include any explanatory text, markdown fences, or comments. "
                "The JSON must be valid and include: version (1.0.0), domain (procedural_dungeon or film_interior), "
                "seed (positive integer), grid (for procedural_dungeon), objects, lighting, camera, materials, "
                "collections, and constraints. All object IDs must be unique and ASCII-safe."
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            payload = {
                "model": self.openai_model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}",
            }
            
            try:
                resp = self._http_post(self.openai_endpoint, headers=headers, payload=payload, timeout=self.timeout_sec)
            except Exception as exc:
                raise ProviderError(f"[{req}] Network error when calling OpenAI: {exc}") from exc

            if resp.status_code >= 500:
                self._openai_circuit.on_http_error(resp.status_code)
                raise ProviderError(f"[{req}] OpenAI server error: {resp.status_code} {resp.text}")
            if resp.status_code == 429:
                self._openai_circuit.on_http_error(resp.status_code)
                raise RateLimitError(f"[{req}] OpenAI rate limited: {resp.text}")
            if resp.status_code != 200:
                raise ProviderError(f"[{req}] OpenAI API returned {resp.status_code}: {resp.text}")

            try:
                data = resp.json()
            except Exception as ex:
                raise ProviderError(f"[{req}] Failed to decode OpenAI JSON response: {ex}") from ex

            # Extract text from response
            text = None
            if isinstance(data, dict):
                if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                    c0 = data["choices"][0]
                    if isinstance(c0, dict):
                        if "message" in c0 and isinstance(c0["message"], dict) and "content" in c0["message"]:
                            text = c0["message"]["content"]
                        elif "text" in c0:
                            text = c0["text"]

            if text is None:
                text = resp.text

            return text

        try:
            spec_text = self._retry_with_backoff_jitter(
                func=do_call,
                max_retries=3,
                base_delay=0.5,
                max_delay=5.0,
                request_id=req,
                on_success=self._openai_circuit.on_success,
                on_failure=self._openai_circuit.on_failure,
            )
        except RateLimitError:
            raise
        except CircuitOpenError:
            raise
        except ProviderError as e:
            raise ProviderError(f"[{req}] OpenAI provider error: {e}") from e
        except Exception as e:
            raise ProviderError(f"[{req}] OpenAI call failed: {e}") from e

        spec = self._sanitize_and_validate_scene_spec(spec_text, request_id=req)
        return spec

    def get_scene_spec_variants(  # noqa: C901
        self,
        prompt: str,
        controls: dict[str, Any] | None = None,
        request_id: str | None = None,
        count: int = 20,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        """Request a bundle of scene spec variants."""
        req = request_id or "req-unknown"
        controls = controls or {}

        if not self.openai_key:
            raise ProviderError(f"[{req}] OpenAI API key not configured.")

        if not _OPENAI_RATE_LIMITER.allow():
            raise RateLimitError("OpenAI rate limit exceeded.")
        if not self._openai_circuit.can_request():
            raise CircuitOpenError("OpenAI circuit open.")

        def _call_provider(n: int) -> str:  # noqa: C901
            system_prompt = (
                f"You are an AI assistant. Return ONLY a JSON object with key 'variants' containing "
                f"an array of exactly {n} different Canvas3D scene specifications. "
                "Each variant must be a complete, valid scene spec conforming to schema v1.0.0. "
                "Do not include explanatory text or markdown."
            )
            
            built_prompt = self._build_variants_prompt(prompt=prompt, controls=controls, count=n)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": built_prompt}
            ]
            
            payload = {
                "model": self.openai_model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}",
            }

            try:
                resp = self._http_post(self.openai_endpoint, headers=headers, payload=payload, timeout=self.timeout_sec)
            except Exception as exc:
                raise ProviderError(f"[{req}] Network error: {exc}") from exc

            if getattr(resp, "status_code", 0) == 413:
                raise ProviderError(f"[{req}] Payload too large (413) for {n} variants")

            if resp.status_code >= 500:
                raise ProviderError(f"[{req}] Server error: {resp.status_code}")
            if resp.status_code == 429:
                raise RateLimitError(f"[{req}] Rate limited")
            if resp.status_code != 200:
                raise ProviderError(f"[{req}] API returned {resp.status_code}")

            try:
                data = resp.json()
            except Exception:
                data = None

            text = None
            if isinstance(data, dict):
                if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                    c0 = data["choices"][0]
                    if isinstance(c0, dict):
                        if "message" in c0 and isinstance(c0["message"], dict):
                            text = c0["message"].get("content")
                        elif "text" in c0:
                            text = c0["text"]
            if text is None:
                text = resp.text
            return text

        def _attempt_with_fallback() -> list[dict[str, Any]]:
            try:
                raw = self._retry_with_backoff_jitter(
                    func=lambda: _call_provider(count),
                    max_retries=3,
                    base_delay=0.5,
                    max_delay=5.0,
                    request_id=req,
                    on_success=self._openai_circuit.on_success,
                    on_failure=self._openai_circuit.on_failure,
                )
                bundle = self._parse_variants_bundle(raw, request_id=req)
                return bundle
            except ProviderError as e:
                low = str(e).lower()
                if "413" in low or "too large" in low or "payload too large" in low:
                    left = max(1, count // 2)
                    right = max(1, count - left)

                    left_raw = self._retry_with_backoff_jitter(
                        func=lambda: _call_provider(left),
                        max_retries=3,
                        base_delay=0.5,
                        max_delay=5.0,
                        request_id=req,
                        on_success=self._openai_circuit.on_success,
                        on_failure=self._openai_circuit.on_failure,
                    )
                    right_raw = self._retry_with_backoff_jitter(
                        func=lambda: _call_provider(right),
                        max_retries=3,
                        base_delay=0.5,
                        max_delay=5.0,
                        request_id=req,
                        on_success=self._openai_circuit.on_success,
                        on_failure=self._openai_circuit.on_failure,
                    )

                    bundle_left = self._parse_variants_bundle(left_raw, request_id=req)
                    bundle_right = self._parse_variants_bundle(right_raw, request_id=req)

                    seen = set()
                    merged: list[dict[str, Any]] = []
                    for spec in bundle_left + bundle_right:
                        try:
                            key = json.dumps(spec, sort_keys=True)
                        except Exception:
                            key = str(spec)
                        if key not in seen:
                            seen.add(key)
                            merged.append(spec)
                    return merged
                raise

        variants = _attempt_with_fallback()

        validated: list[dict[str, Any]] = []
        dropped = 0
        for idx, spec in enumerate(variants):
            ok, issues = validate_scene_spec(spec, expect_version="1.0.0")
            if ok:
                validated.append(spec)
            else:
                dropped += 1
                if idx < 3:
                    summarized = "; ".join(f"{i.path}: {i.message}" for i in issues[:5])
                    logger.warning(f"[{req}] Dropping invalid variant[{idx}]: {summarized}")

        if not validated:
            raise ProviderError(f"[{req}] No valid variants generated.")

        return validated

    def _build_variants_prompt(self, prompt: str, controls: dict[str, Any], count: int) -> str:
        """Builds instruction string for variants bundle."""
        size = controls.get("size_scale", "medium")
        density = controls.get("complexity_density", "balanced")
        layout = controls.get("layout_style", "branching")
        mood = controls.get("mood_lighting", "neutral")
        palette = controls.get("materials_palette", "stone_wood")
        cam_style = controls.get("camera_style", "cinematic_static")
        domain = controls.get("domain", "procedural_dungeon")

        base_req = "Each variant must include version '1.0.0', units 'meters', a positive integer seed, >=1 light, and a camera."
        if str(domain) == "procedural_dungeon":
            base_req += " Include 'grid' with cell_size_m and integer dimensions (cols, rows)."

        details = [
            f"Return exactly {count} variants under key 'variants'.",
            f"Domain must be '{domain}'.",
            base_req,
            "Enforce ASCII-safe IDs and reasonable bounds.",
            f"Match controls: size='{size}', complexity='{density}', layout='{layout}', mood='{mood}', palette='{palette}', camera='{cam_style}'.",
        ]
        instr = "\n".join(details)
        return (
            f"User prompt:\n{prompt}\n\n"
            f"Controls:\n{json.dumps(controls, indent=2)}\n\n"
            f"Output contract:\n{instr}\n\n"
            "Return only JSON."
        )

    def _parse_variants_bundle(self, payload: object, request_id: str | None = None) -> list[dict[str, Any]]:
        """Parse variants bundle from provider response."""
        req = request_id or "req-unknown"
        try:
            if isinstance(payload, dict):
                data = payload
            else:
                raw = self._extract_json_balanced(str(payload))
                data = json.loads(raw)
        except Exception as ex:
            raise ProviderError(f"[{req}] Variants response was not valid JSON: {ex}") from ex

        if not isinstance(data, dict) or "variants" not in data or not isinstance(data["variants"], list):
            raise ProviderError(f"[{req}] Expected object with 'variants' array")

        out: list[dict[str, Any]] = []
        for it in data["variants"]:
            if isinstance(it, dict):
                out.append(it)
        return out

    def get_enhancement_ideas(  # noqa: C901
        self,
        prompt: str,
        selected_spec: dict[str, Any],
        controls: dict[str, Any] | None = None,
        request_id: str | None = None,
        count: int = 12,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> list[str]:
        """Request enhancement ideas for a selected spec."""
        req = request_id or "req-unknown"
        controls = controls or {}

        if not self.openai_key:
            raise ProviderError(f"[{req}] OpenAI API key not configured.")
        if not _OPENAI_RATE_LIMITER.allow():
            raise RateLimitError("Rate limit exceeded.")
        if not self._openai_circuit.can_request():
            raise CircuitOpenError("Circuit open.")

        def do_call() -> str:  # noqa: C901
            system_prompt = (
                f"You are an AI assistant. Return ONLY a JSON object with key 'ideas' containing "
                f"an array of exactly {count} short, distinct improvement ideas for the provided Canvas3D scene spec. "
                "Each idea must be a concise, actionable natural language string. "
                "Do not include any explanatory text, markdown, or comments; output raw JSON only."
            )
            
            user_content = (
                f"Controls:\n{json.dumps(controls, indent=2)}\n\n"
                f"User prompt:\n{prompt}\n\n"
                f"Selected spec:\n{json.dumps(selected_spec, indent=2)}"
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
            
            payload = {
                "model": self.openai_model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}",
            }

            try:
                resp = self._http_post(self.openai_endpoint, headers=headers, payload=payload, timeout=self.timeout_sec)
            except Exception as exc:
                raise ProviderError(f"[{req}] Network error: {exc}") from exc

            if resp.status_code >= 500:
                raise ProviderError(f"[{req}] Server error: {resp.status_code}")
            if resp.status_code == 429:
                raise RateLimitError(f"[{req}] Rate limited")
            if resp.status_code != 200:
                raise ProviderError(f"[{req}] API returned {resp.status_code}")

            try:
                data = resp.json()
            except Exception:
                data = None

            text = None
            if isinstance(data, dict):
                if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                    c0 = data["choices"][0]
                    if isinstance(c0, dict):
                        if "message" in c0 and isinstance(c0["message"], dict):
                            text = c0["message"].get("content")
                        elif "text" in c0:
                            text = c0["text"]
            if text is None:
                text = resp.text
            return text

        try:
            raw = self._retry_with_backoff_jitter(
                func=do_call,
                max_retries=3,
                base_delay=0.5,
                max_delay=5.0,
                request_id=req,
                on_success=self._openai_circuit.on_success,
                on_failure=self._openai_circuit.on_failure,
            )
        except RateLimitError:
            raise
        except CircuitOpenError:
            raise
        except ProviderError as e:
            raise ProviderError(f"[{req}] Provider error: {e}") from e
        except Exception as e:
            raise ProviderError(f"[{req}] Call failed: {e}") from e

        ideas = self._parse_ideas_bundle(raw, request_id=req)
        if not isinstance(ideas, list) or not all(isinstance(x, str) and x.strip() for x in ideas):
            raise ProviderError(f"[{req}] No valid ideas")

        out: list[str] = []
        seen = set()
        for s in ideas:
            k = s.strip()
            if k and k.lower() not in seen:
                seen.add(k.lower())
                out.append(k)
            if len(out) >= count:
                break
        if not out:
            raise ProviderError(f"[{req}] No usable ideas")
        return out

    def _parse_ideas_bundle(self, payload: object, request_id: str | None = None) -> list[str]:
        """Parse ideas bundle from provider response."""
        req = request_id or "req-unknown"
        data: Any = None
        try:
            if isinstance(payload, (dict, list)):
                data = payload
            else:
                data = json.loads(str(payload))
        except Exception:
            try:
                raw = self._extract_json_balanced(str(payload))
                data = json.loads(raw)
            except Exception as ex:
                raise ProviderError(f"[{req}] Ideas response invalid: {ex}") from ex

        ideas: list[str] = []
        if isinstance(data, dict) and isinstance(data.get("ideas"), list):
            for it in data["ideas"]:
                if isinstance(it, str):
                    ideas.append(it)
        elif isinstance(data, list):
            for it in data:
                if isinstance(it, str):
                    ideas.append(it)

        return ideas

    def get_last_raw(self) -> str:
        """Return last raw response for debugging."""
        return self._last_raw


def register() -> None:
    pass

def unregister() -> None:
    pass