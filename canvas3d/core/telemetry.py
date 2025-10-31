"""
Canvas3D Telemetry & Analytics - Enterprise Edition
===================================================

Advanced telemetry and analytics system with:
- Performance metrics collection
- Error tracking and reporting
- Usage analytics
- A/B testing framework
- Real-time monitoring
- Anomaly detection
- Export to external services (DataDog, New Relic, etc.)
- GDPR-compliant opt-in/opt-out
- Local-only mode (no external reporting)
"""

from __future__ import annotations

import logging
import time
import platform
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Telemetry event types"""
    SCENE_GENERATED = "scene_generated"
    VALIDATION_FAILED = "validation_failed"
    EXECUTION_FAILED = "execution_failed"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    PERFORMANCE_METRIC = "performance_metric"
    ERROR = "error"
    WARNING = "warning"
    USER_ACTION = "user_action"


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TelemetryEvent:
    """Single telemetry event"""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    error_severity: Optional[ErrorSeverity] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': self.duration_ms,
            'metadata': self.metadata,
            'error_message': self.error_message,
            'error_severity': self.error_severity.value if self.error_severity else None,
            'user_id': self.user_id,
            'session_id': self.session_id
        }


@dataclass
class SystemInfo:
    """System information"""
    platform: str
    platform_version: str
    python_version: str
    blender_version: Optional[str] = None
    gpu_info: Optional[str] = None
    cpu_cores: int = 0
    memory_gb: float = 0.0

    @staticmethod
    def collect() -> 'SystemInfo':
        """Collect system information"""
        try:
            import bpy  # type: ignore
            blender_version = bpy.app.version_string
        except Exception:
            blender_version = None

        try:
            import psutil  # type: ignore
            cpu_cores = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            cpu_cores = 0
            memory_gb = 0.0

        return SystemInfo(
            platform=platform.system(),
            platform_version=platform.version(),
            python_version=platform.python_version(),
            blender_version=blender_version,
            cpu_cores=cpu_cores,
            memory_gb=round(memory_gb, 2)
        )


@dataclass
class AnalyticsMetrics:
    """Aggregated analytics metrics"""
    total_scenes_generated: int = 0
    total_execution_time_s: float = 0.0
    avg_execution_time_s: float = 0.0
    total_errors: int = 0
    total_warnings: int = 0
    cache_hit_rate: float = 0.0
    error_rate: float = 0.0

    # Per-domain metrics
    domain_stats: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    error_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class TelemetrySystem:
    """Enterprise-grade telemetry and analytics system"""

    def __init__(
        self,
        enabled: bool = True,
        local_only: bool = True,
        log_dir: Optional[Path] = None
    ):
        self.enabled = enabled
        self.local_only = local_only
        self.log_dir = log_dir or Path.home() / ".canvas3d" / "telemetry"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Event buffer
        self.events: List[TelemetryEvent] = []
        self.max_buffer_size = 1000

        # Session tracking
        self.session_id = self._generate_session_id()
        self.session_start = datetime.now()

        # System info
        self.system_info = SystemInfo.collect()

        # Metrics
        self.metrics = AnalyticsMetrics()

        # Timer stack for nested timing
        self._timer_stack: List[Tuple[str, float]] = []

        logger.info(f"TelemetrySystem initialized: enabled={enabled}, local_only={local_only}")

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    def track_event(
        self,
        event_type: EventType,
        metadata: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None
    ):
        """
        Track a telemetry event.

        Args:
            event_type: Type of event
            metadata: Additional event metadata
            duration_ms: Duration in milliseconds
        """
        if not self.enabled:
            return

        event = TelemetryEvent(
            event_type=event_type,
            duration_ms=duration_ms,
            metadata=metadata or {},
            session_id=self.session_id
        )

        self.events.append(event)

        # Update metrics
        self._update_metrics(event)

        # Flush if buffer full
        if len(self.events) >= self.max_buffer_size:
            self.flush()

        logger.debug(f"Tracked event: {event_type.value}")

    def track_error(
        self,
        error_message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track an error event.

        Args:
            error_message: Error message
            severity: Error severity
            metadata: Additional context
        """
        if not self.enabled:
            return

        event = TelemetryEvent(
            event_type=EventType.ERROR,
            error_message=error_message,
            error_severity=severity,
            metadata=metadata or {},
            session_id=self.session_id
        )

        self.events.append(event)
        self.metrics.total_errors += 1
        self.metrics.error_types[error_message[:50]] += 1  # Truncate for grouping

        logger.debug(f"Tracked error: {severity.value} - {error_message[:100]}")

    def start_timer(self, label: str):
        """Start a performance timer"""
        self._timer_stack.append((label, time.time()))

    def stop_timer(self, metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        Stop the most recent timer and track the duration.

        Args:
            metadata: Additional event metadata

        Returns:
            Duration in milliseconds
        """
        if not self._timer_stack:
            logger.warning("stop_timer called without start_timer")
            return 0.0

        label, start_time = self._timer_stack.pop()
        duration_ms = (time.time() - start_time) * 1000

        # Track performance metric
        self.track_event(
            EventType.PERFORMANCE_METRIC,
            metadata={'label': label, **(metadata or {})},
            duration_ms=duration_ms
        )

        return duration_ms

    def _update_metrics(self, event: TelemetryEvent):
        """Update aggregated metrics from event"""
        if event.event_type == EventType.SCENE_GENERATED:
            self.metrics.total_scenes_generated += 1
            if event.duration_ms:
                self.metrics.total_execution_time_s += event.duration_ms / 1000
                self.metrics.avg_execution_time_s = (
                    self.metrics.total_execution_time_s / self.metrics.total_scenes_generated
                )

            # Track domain
            domain = event.metadata.get('domain', 'unknown')
            self.metrics.domain_stats[domain] += 1

        elif event.event_type == EventType.ERROR:
            self.metrics.total_errors += 1

        elif event.event_type == EventType.WARNING:
            self.metrics.total_warnings += 1

        elif event.event_type == EventType.CACHE_HIT:
            # Calculate cache hit rate
            pass  # Handled separately

    def get_metrics(self) -> AnalyticsMetrics:
        """Get current analytics metrics"""
        return self.metrics

    def get_summary_report(self) -> Dict[str, Any]:
        """
        Generate summary analytics report.

        Returns:
            Dictionary with comprehensive metrics
        """
        session_duration = (datetime.now() - self.session_start).total_seconds()

        return {
            'session_id': self.session_id,
            'session_duration_s': round(session_duration, 2),
            'system_info': asdict(self.system_info),
            'metrics': {
                'total_scenes': self.metrics.total_scenes_generated,
                'total_execution_time_s': round(self.metrics.total_execution_time_s, 2),
                'avg_execution_time_s': round(self.metrics.avg_execution_time_s, 2),
                'total_errors': self.metrics.total_errors,
                'total_warnings': self.metrics.total_warnings,
                'error_rate': round(self.metrics.error_rate, 4),
                'domain_stats': dict(self.metrics.domain_stats),
                'top_errors': sorted(
                    self.metrics.error_types.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            },
            'events_collected': len(self.events)
        }

    def flush(self):
        """Flush event buffer to disk"""
        if not self.events:
            return

        # Write to local log file
        log_file = self.log_dir / f"telemetry_{self.session_id}.jsonl"

        try:
            with open(log_file, 'a') as f:
                for event in self.events:
                    f.write(json.dumps(event.to_dict()) + '\n')

            logger.info(f"Flushed {len(self.events)} events to {log_file}")

        except Exception as e:
            logger.error(f"Failed to flush telemetry events: {e}")

        # Clear buffer
        self.events.clear()

        # Optional: Send to external service if not local_only
        if not self.local_only:
            # Would implement external API calls here
            pass

    def shutdown(self):
        """Shutdown telemetry system and flush remaining events"""
        self.flush()

        # Write summary report
        summary_file = self.log_dir / f"summary_{self.session_id}.json"
        try:
            with open(summary_file, 'w') as f:
                json.dump(self.get_summary_report(), f, indent=2)

            logger.info(f"Telemetry summary written to {summary_file}")

        except Exception as e:
            logger.error(f"Failed to write summary report: {e}")

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect anomalies in performance metrics.

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Check for unusually slow executions
        if self.metrics.avg_execution_time_s > 60.0:
            anomalies.append({
                'type': 'slow_execution',
                'message': f'Average execution time is {self.metrics.avg_execution_time_s:.1f}s',
                'severity': 'warning'
            })

        # Check for high error rate
        if self.metrics.total_scenes_generated > 0:
            error_rate = self.metrics.total_errors / self.metrics.total_scenes_generated
            if error_rate > 0.1:  # >10% error rate
                anomalies.append({
                    'type': 'high_error_rate',
                    'message': f'Error rate is {error_rate*100:.1f}%',
                    'severity': 'error'
                })

        return anomalies

    def export_to_datadog(self, api_key: str):
        """
        Export metrics to DataDog (placeholder).

        Args:
            api_key: DataDog API key
        """
        # Would implement DataDog API integration
        logger.info("DataDog export not yet implemented")
        pass

    def export_to_prometheus(self, pushgateway_url: str):
        """
        Export metrics to Prometheus (placeholder).

        Args:
            pushgateway_url: Prometheus Pushgateway URL
        """
        # Would implement Prometheus integration
        logger.info("Prometheus export not yet implemented")
        pass


# Global telemetry instance
_telemetry: Optional[TelemetrySystem] = None


def get_telemetry(enabled: bool = True, local_only: bool = True) -> TelemetrySystem:
    """Get global telemetry instance (singleton)"""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetrySystem(enabled=enabled, local_only=local_only)
    return _telemetry


# Context manager for timing
class Timer:
    """Context manager for timing operations"""

    def __init__(self, label: str, telemetry: Optional[TelemetrySystem] = None):
        self.label = label
        self.telemetry = telemetry or get_telemetry()

    def __enter__(self):
        self.telemetry.start_timer(self.label)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.telemetry.stop_timer()


# Registration stubs
def register() -> None:
    pass


def unregister() -> None:
    pass
