from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from miniatured_world.app.activity_startup import ActivityChoice, acknowledge_activity_notice
from miniatured_world.app.runtime import AppRuntime

ACTIVITY_EXPLANATION = (
    "キーボードやマウスの操作量・リズムなどの活動特徴を、ラボの変化に使います。\n"
    "入力した文字やキー列、マウスの座標・軌跡、アプリ名・ウィンドウ名、"
    "画面・クリップボードの内容は保存しません。活動情報を外部へ送信しません。\n"
    "活動取得は、後から「設定」またはトレイの「活動取得を停止／再開」で変更できます。"
)


class ActivityChoiceDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.choice: ActivityChoice = "exit"
        self.setWindowTitle("小さなラボラトリー — 活動取得について")
        self.setMinimumWidth(600)
        self.setStyleSheet(
            "QDialog {background:#f8f3e9;} QLabel {color:#302b25; font-size:14px;}"
            "QPushButton {padding:10px 16px; font-size:14px;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)
        title = QLabel("PCの活動をラボに反映しますか？")
        title.setStyleSheet("font-size:20px; font-weight:bold;")
        layout.addWidget(title)
        body = QLabel(ACTIVITY_EXPLANATION)
        body.setWordWrap(True)
        layout.addWidget(body)
        hint = QLabel("取得せずに使う場合も、ラボは動き続けます。選ぶまでは活動取得を開始しません。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QHBoxLayout()
        for text, choice in (("終了", "exit"), ("取得せずに使う", "disable"), ("取得する", "enable")):
            button = QPushButton(text)
            button.setObjectName(f"activity_{choice}")
            button.setAutoDefault(False)
            button.setDefault(choice == "disable")
            button.clicked.connect(lambda checked=False, value=choice: self._choose(value))
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _choose(self, choice: ActivityChoice) -> None:
        self.choice = choice
        self.accept()


def choose_activity() -> ActivityChoice:
    dialog = ActivityChoiceDialog()
    dialog.exec()
    return dialog.choice


def attach_activity_notice(window, runtime: AppRuntime) -> None:
    """既存ユーザーの操作を止めず、設定を保ったまま説明する。"""
    content = window.takeCentralWidget()
    container = QWidget(window)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    banner = QFrame(container)
    banner.setObjectName("activity_notice")
    banner.setStyleSheet("QFrame#activity_notice {background:#f2e6cb; border:1px solid #baa77e;}"
                        "QLabel {color:#302b25;}")
    notice_layout = QVBoxLayout(banner)
    title = QLabel("活動取得について — 現在のON/OFF設定を引き継いでいます")
    title.setStyleSheet("font-weight:bold;")
    title.setWordWrap(True)
    notice_layout.addWidget(title)
    body = QLabel(ACTIVITY_EXPLANATION)
    body.setWordWrap(True)
    notice_layout.addWidget(body)
    close = QPushButton("説明を閉じる")
    close.setObjectName("activity_notice_close")

    def acknowledge() -> None:
        acknowledge_activity_notice(runtime)
        banner.hide()

    close.clicked.connect(acknowledge)
    notice_layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
    layout.addWidget(banner)
    layout.addWidget(content, 1)
    window.setCentralWidget(container)
    window.activity_notice_banner = banner
    window.acknowledge_activity_notice = acknowledge
