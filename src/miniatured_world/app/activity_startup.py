from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Literal

from miniatured_world.activity import ActivityProvider, ActivityProviderStatus
from miniatured_world.app.runtime import AppRuntime

ActivityChoice = Literal["enable", "disable", "exit"]


class DeferredActivityProvider:
    """表示のためのstatus参照では実活動の取得元を作らない。"""

    def __init__(self, factory: Callable[[], ActivityProvider]) -> None:
        self._factory = factory
        self._provider: ActivityProvider | None = None

    def status(self) -> ActivityProviderStatus:
        if self._provider is None:
            return ActivityProviderStatus(
                name="pending", display_name="待機", available=False, active=False,
                detail="活動取得元はまだ起動していません。",
            )
        return self._provider.status()

    def poll(self, now_ms: int):
        if self._provider is None:
            self._provider = self._factory()
        return self._provider.poll(now_ms)


def prepare_activity_startup(
    runtime: AppRuntime,
    mode: str,
    factory: Callable[[], ActivityProvider],
    choose: Callable[[], ActivityChoice],
) -> bool:
    """Falseなら保存・タイマー起動をせず終了する。旧設定は選択し直さない。"""
    if mode in ("demo", "none"):
        runtime.provider = factory()
        return True
    settings = runtime.service.settings
    if settings.activity_notice == "unseen":
        choice = choose()
        if choice == "exit":
            runtime.stop()
            return False
        enabled = choice == "enable"
        runtime.service.update_settings(replace(
            settings, activity=replace(settings.activity, enabled=enabled),
            activity_notice="shown",
        ))
        runtime.state.activity_collection_enabled = enabled
    runtime.provider = DeferredActivityProvider(factory)
    return True


def acknowledge_activity_notice(runtime: AppRuntime) -> None:
    runtime.service.update_settings(replace(runtime.service.settings, activity_notice="shown"))
