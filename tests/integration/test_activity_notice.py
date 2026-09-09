"""実活動取得の開始境界と、旧設定を引き継ぐ説明UIの検査。"""

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.activity_startup import prepare_activity_startup
from miniatured_world.app.qt_activity_notice import ActivityChoiceDialog, attach_activity_notice
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.persistence import JsonStore, Settings


@pytest.mark.parametrize("enabled", [True, False])
def test_legacy_notice_preserves_all_preferences_and_discovery(tmp_path, enabled):
    app = QApplication.instance() or QApplication([])
    settings = Settings()
    settings = replace(settings, activity=replace(settings.activity, enabled=enabled),
                       sound=replace(settings.sound, master_volume=0.25),
                       display=replace(settings.display, fps_limit=12))
    old = asdict(settings)
    del old["activity_notice"]
    (tmp_path / "settings.json").write_text(json.dumps(old), encoding="utf-8")
    discovery = b'{"schema_version":1,"discoveries":["existing-test-discovery"]}'
    (tmp_path / "discovery.json").write_bytes(discovery)
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    created = []

    def factory():
        created.append(True)
        return DemoActivityProvider()

    assert runtime.service.settings.activity_notice == "legacy"
    assert prepare_activity_startup(runtime, "auto", factory, lambda: pytest.fail("旧設定で再選択"))
    window = build_main_window(runtime)
    attach_activity_notice(window, runtime)
    window.show()
    try:
        app.processEvents()
        assert app.activeModalWidget() is None
        assert window.activity_notice_banner.isVisible()
        assert created == []  # 初期画面のstatus参照でも生成しない。
        window.findChild(QPushButton, "activity_notice_close").click()
        assert not window.activity_notice_banner.isVisible()
        saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert saved.pop("activity_notice") == "shown"
        assert saved == old
        assert (tmp_path / "discovery.json").read_bytes() == discovery
        assert runtime.state.activity_collection_enabled is enabled
        runtime.tick()
        assert len(created) == int(enabled)
    finally:
        window.close()
    restarted = AppRuntime.start(seed=42, data_root=tmp_path)
    assert prepare_activity_startup(restarted, "auto", factory, lambda: pytest.fail("説明済みの再選択"))
    assert restarted.service.settings.activity_notice == "shown"
    assert restarted.state.activity_collection_enabled is enabled


@pytest.mark.parametrize("choice", ["enable", "disable", "exit"])
def test_new_user_choice_guards_provider_and_storage(tmp_path, choice):
    root = tmp_path / "new-data"
    runtime = AppRuntime.start(seed=42, data_root=root)
    created = []

    def factory():
        created.append(True)
        return DemoActivityProvider()

    def choose():
        assert created == []
        assert not root.exists()
        return choice

    allowed = prepare_activity_startup(runtime, "auto", factory, choose)
    assert created == []
    if choice == "exit":
        assert not allowed
        assert not root.exists()
        assert not runtime.state.running
        return
    assert allowed
    assert JsonStore(root).load_settings().activity_notice == "shown"
    assert JsonStore(root).load_settings().activity.enabled is (choice == "enable")
    before = runtime.service.now_ms
    runtime.tick()
    assert runtime.service.now_ms > before
    assert len(created) == int(choice == "enable")
    if choice == "disable":
        runtime.set_activity_collection(True)
        runtime.tick()
        assert len(created) == 1
        runtime.tick()
        assert len(created) == 1


@pytest.mark.parametrize("mode", ["demo", "none"])
def test_synthetic_run_does_not_mark_real_activity_notice_shown(tmp_path, mode):
    runtime = AppRuntime.start(seed=42, data_root=tmp_path)
    assert prepare_activity_startup(runtime, mode, DemoActivityProvider, lambda: pytest.fail("合成起動で選択"))
    runtime.tick()
    assert JsonStore(tmp_path).load_settings().activity_notice == "unseen"
    restarted = AppRuntime.start(seed=42, data_root=tmp_path)
    selected = []
    assert not prepare_activity_startup(restarted, "auto", DemoActivityProvider, lambda: selected.append(True) or "exit")
    assert selected == [True]


@pytest.mark.parametrize("action", ["enable", "disable", "exit", "escape", "close"])
def test_dialog_buttons_escape_and_close(action):
    app = QApplication.instance() or QApplication([])
    dialog = ActivityChoiceDialog()
    dialog.show()
    app.processEvents()
    if action == "escape":
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
    elif action == "close":
        dialog.close()
    else:
        dialog.findChild(QPushButton, f"activity_{action}").click()
    assert dialog.choice == (action if action in ("enable", "disable") else "exit")
    assert not dialog.isVisible()


@pytest.mark.parametrize("choice", ["enable", "disable", "exit"])
@pytest.mark.parametrize("ephemeral", [True, False])
def test_actual_main_to_qt_choice_before_any_provider(tmp_path, choice, ephemeral):
    # 子プロセスの本物のモーダルダイアログを操作。実OS入力取得元はスパイへ置換する。
    script = r'''
import json, os
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton
from miniatured_world import __main__ as entry
from miniatured_world.app import qt_app
from miniatured_world.activity import DemoActivityProvider
app = QApplication([])
created = []
def factory(mode):
    created.append(mode)
    return DemoActivityProvider()
qt_app.create_activity_provider = factory
entry.create_activity_provider = lambda mode: (_ for _ in ()).throw(AssertionError("GUI入口で取得元を生成"))
choice = os.environ["TEST_CHOICE"]
root = Path(os.environ["MINIATURED_WORLD_DATA_DIR"])
def select():
    dialog = app.activeModalWidget()
    assert dialog is not None
    assert not created
    assert not root.exists()
    dialog.findChild(QPushButton, "activity_" + choice).click()
QTimer.singleShot(50, select)
QTimer.singleShot(10000, app.quit)
args = ["--activity-provider", "auto", "--duration-seconds", "0.1", "--tick-interval-ms", "20"]
if os.environ["TEST_EPHEMERAL"] == "1":
    args.append("--ephemeral")
assert entry.main(args) == 0
assert created == (["auto"] if choice == "enable" else [])
print("verified")
'''
    root = tmp_path / "data"
    result = subprocess.run([sys.executable, "-c", script], env={
        **os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
        "QT_QPA_PLATFORM": "offscreen", "MINIATURED_WORLD_DATA_DIR": str(root),
        "TEST_CHOICE": choice, "TEST_EPHEMERAL": str(int(ephemeral)),
    }, capture_output=True, encoding="utf-8", timeout=25)
    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout
    if ephemeral or choice == "exit":
        assert not root.exists()
    else:
        saved = JsonStore(root).load_settings()
        assert saved.activity_notice == "shown"
        assert saved.activity.enabled is (choice == "enable")
