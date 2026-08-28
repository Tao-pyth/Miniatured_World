from __future__ import annotations

import ctypes
import json
import math
import os
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.snapshot import WorldSnapshot


Clock = Callable[[], float]
Sleeper = Callable[[float], None]


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint),
        ("PageFaultCount", ctypes.c_uint),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_PROCESS_MEMORY_API_CONFIGURED = False


def run_stability_check(
    runtime: AppRuntime,
    *,
    log_path: Path,
    duration_seconds: float,
    tick_interval_ms: int = 1000,
    realtime: bool = False,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> WorldSnapshot:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive.")
    if tick_interval_ms <= 0:
        raise ValueError("tick_interval_ms must be positive.")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, math.ceil(duration_seconds * 1000 / tick_interval_ms))
    started_at = clock()
    snapshot = runtime.snapshot()

    with log_path.open("w", encoding="utf-8") as log:
        _write_log(
            log,
            {
                "event": "start",
                "duration_seconds": duration_seconds,
                "tick_interval_ms": tick_interval_ms,
                "realtime": realtime,
                "provider": _provider_status(snapshot),
                "process": _process_metrics(),
            },
            started_at=started_at,
            clock=clock,
        )
        try:
            for frame_index in range(1, frame_count + 1):
                snapshot = runtime.tick(elapsed_ms=tick_interval_ms)
                _write_log(
                    log,
                    {
                        "event": "tick",
                        "frame": frame_index,
                        "summary": runtime.service.summary_text(),
                        "snapshot": _snapshot_payload(snapshot),
                        "process": _process_metrics(),
                    },
                    started_at=started_at,
                    clock=clock,
                )
                if realtime:
                    target = started_at + frame_index * (tick_interval_ms / 1000)
                    sleeper(max(0.0, target - clock()))

            _write_log(
                log,
                {
                    "event": "completed",
                    "frames": frame_count,
                    "summary": runtime.service.summary_text(),
                    "snapshot": _snapshot_payload(snapshot),
                    "process": _process_metrics(),
                },
                started_at=started_at,
                clock=clock,
            )
        except BaseException as error:
            _write_log(
                log,
                {
                    "event": "error",
                    "error_type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(limit=20),
                    "process": _process_metrics(),
                },
                started_at=started_at,
                clock=clock,
            )
            raise
    return snapshot


def _write_log(log, payload: dict[str, Any], *, started_at: float, clock: Clock) -> None:
    entry = {
        "utc_time": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(max(0.0, clock() - started_at), 3),
        **payload,
    }
    log.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    log.flush()


def _snapshot_payload(snapshot: WorldSnapshot) -> dict[str, Any]:
    return {
        "activity_collection_enabled": snapshot.activity_collection_enabled,
        "activity_intensity": snapshot.activity_intensity,
        "activity_level": snapshot.activity_level,
        "creature_count": snapshot.creature_count,
        "discoveries": len(snapshot.discoveries),
        "events": len(snapshot.events),
        "grid_materials": snapshot.grid_materials,
        "humidity": snapshot.humidity,
        "materials": snapshot.materials,
        "muted": snapshot.muted,
        "paused": snapshot.paused,
        "plant_count": snapshot.plant_count,
        "provider": _provider_status(snapshot),
        "running": snapshot.running,
        "seed": snapshot.seed,
        "temperature": snapshot.temperature,
        "tendency": snapshot.tendency,
        "traits": list(snapshot.traits),
        "wind": snapshot.wind,
        "world_time": snapshot.world_time,
        "world_visible": snapshot.world_visible,
    }


def _provider_status(snapshot: WorldSnapshot) -> dict[str, Any]:
    status = snapshot.provider_status
    return {
        "active": status.active,
        "available": status.available,
        "detail": status.detail,
        "display_name": status.display_name,
        "name": status.name,
    }


def _process_metrics() -> dict[str, Any]:
    return {
        "cpu_time_seconds": round(time.process_time(), 3),
        "pid": os.getpid(),
        "rss_bytes": _rss_bytes(),
    }


def _rss_bytes() -> int | None:
    if os.name != "nt":
        return None

    counters = _PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    _configure_process_memory_api(kernel32, psapi)
    ok = psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(),
        ctypes.byref(counters),
        counters.cb,
    )
    if not ok:
        return None
    return int(counters.WorkingSetSize)


def _configure_process_memory_api(kernel32, psapi) -> None:
    global _PROCESS_MEMORY_API_CONFIGURED
    if _PROCESS_MEMORY_API_CONFIGURED:
        return

    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
        ctypes.c_uint,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    _PROCESS_MEMORY_API_CONFIGURED = True
