import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QCheckBox, QSlider
from miniatured_world.activity.provider import DemoActivityProvider
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.app.qt_widgets import build_main_window


def test_actual_controls_apply_and_survive_restart(tmp_path):
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(42, provider=DemoActivityProvider(), data_root=tmp_path)
    window = build_main_window(runtime); window.timer.stop()
    try:
        for name in ("keyboard", "mouse", "click", "scroll"):
            checkbox = window.findChild(QCheckBox, "activity_" + name)
            assert checkbox is not None
            checkbox.setChecked(False)
        window.advance(); window.advance()
        assert runtime.snapshot().activity_intensity == 0
        for name in ("keyboard", "mouse", "click", "scroll"):
            window.findChild(QCheckBox, "activity_" + name).setChecked(True)
        window.advance(); window.advance()
        assert runtime.snapshot().activity_intensity > 0
        window.findChild(QSlider, "activity_reflection").setValue(0)
        window.advance()
        assert runtime.snapshot().activity_intensity == 0
        runtime.stop()
        restarted = AppRuntime.start(42, provider=DemoActivityProvider(), data_root=tmp_path)
        assert restarted.service.settings.activity.reflection_strength == 0
        assert restarted.tick().activity_intensity == 0
    finally:
        runtime.stop(); window.close()
