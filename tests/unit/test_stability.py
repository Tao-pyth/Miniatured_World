import json

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.stability import run_stability_check


def test_stability_log_contains_privacy_safe_runtime_entries(tmp_path) -> None:
    log_path = tmp_path / "stability.jsonl"
    runtime = AppRuntime.start(seed=42, provider=DemoActivityProvider())

    run_stability_check(
        runtime,
        log_path=log_path,
        duration_seconds=2,
        tick_interval_ms=1000,
        realtime=False,
    )

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert [entry["event"] for entry in entries] == ["start", "tick", "tick", "completed"]
    assert entries[-1]["summary"].startswith("Miniatured World")
    assert entries[-1]["snapshot"]["provider"]["name"] == "demo"
    assert entries[-1]["process"]["pid"] > 0

    serialized = json.dumps(entries, ensure_ascii=False)
    forbidden = {
        "super_secret_password",
        "key_sequence",
        "mouse_x",
        "mouse_y",
        "window_title",
        "clipboard",
        "screen_capture",
    }
    assert all(term not in serialized for term in forbidden)
