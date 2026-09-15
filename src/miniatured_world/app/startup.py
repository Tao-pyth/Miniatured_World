"""明示操作だけで変更する、利用者・保存先ごとのWindows起動登録。"""

from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable
from miniatured_world.persistence.validation import json_object, reject_constant


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
OWNER_KEY = r"Software\MiniaturedWorld\Startup"


class StartupConflict(ValueError):
    """所有を確認できない値は変更しない。内容はエラー表示へ含めない。"""


class StartupUnavailable(ValueError):
    """利用者へそのまま表示できる固定メッセージだけを使う。"""


@dataclass(frozen=True, slots=True)
class StartupStatus:
    registered: bool | None
    can_change: bool
    message: str
    succeeded: bool = True


class WindowsRegistry:
    def read(self, key: str, name: str) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_QUERY_VALUE) as handle:
                value, kind = winreg.QueryValueEx(handle, name)
        except FileNotFoundError:
            return None
        if kind != winreg.REG_SZ or not isinstance(value, str):
            raise StartupConflict()
        return value

    def write(self, key: str, name: str, value: str) -> None:
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)

    def delete(self, key: str, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, name)
        except FileNotFoundError:
            pass


def startup_command(data_root: Path) -> str:
    """登録時だけ実行環境を確認。元のCLI引数やPYTHONPATHを引き継がない。"""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        arguments = [str(executable)]
    else:
        executable = Path(sys.executable).with_name("pythonw.exe").resolve()
        # -IはCWDとPYTHONPATHを除外する。登録後も同じ起動条件を使う。
        probe = subprocess.run(
            [sys.executable, "-I", "-c", "import sys, miniatured_world; from PySide6.QtWidgets import QApplication; sys.stdout.buffer.write(miniatured_world.__file__.encode('utf-8'))"],
            cwd=Path(sys.executable).parent,
            capture_output=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        import miniatured_world

        try:
            installed = Path(probe.stdout.decode("utf-8").strip()).resolve()
        except (ValueError, OSError, UnicodeError):
            raise StartupUnavailable("インストールされたアプリから設定してください。") from None
        if probe.returncode or installed != Path(miniatured_world.__file__).resolve():
            raise StartupUnavailable("インストールされたアプリから設定してください。")
        arguments = [str(executable), "-I", "-m", "miniatured_world"]
    if not executable.is_file():
        raise StartupUnavailable("起動に必要な実行ファイルが見つかりません。")
    arguments += ["--data-root", str(data_root)]
    command = subprocess.list2cmdline(arguments)
    if not _valid_command(command):
        raise StartupUnavailable("起動設定のパスが長すぎるか、使用できない文字を含んでいます。")
    return command


def _valid_command(command: object) -> bool:
    # Windowsの文字数はUTF-16コード単位。補助文字も過少計数しない。
    try:
        return bool(
            isinstance(command, str) and command and not any(c in command for c in "\0\r\n")
            and len(command.encode("utf-16-le")) // 2 <= 260
        )
    except UnicodeError:
        return False


class StartupManager:
    def __init__(
        self, data_root: Path | None, *, registry=None,
        command_builder: Callable[[Path], str] = startup_command,
    ) -> None:
        self.root = None if data_root is None else Path(data_root).resolve()
        self.registry = registry if registry is not None else (WindowsRegistry() if os.name == "nt" else None)
        self.command_builder = command_builder
        self.identity = "" if self.root is None else os.path.normcase(str(self.root))
        self.name = "MiniaturedWorld." + hashlib.sha256(self.identity.encode("utf-8")).hexdigest()[:24]

    def _pair(self) -> tuple[str | None, str | None, list[str]]:
        run = self.registry.read(RUN_KEY, self.name)
        marker = self.registry.read(OWNER_KEY, self.name)
        commands = []
        if marker is not None:
            try:
                if len(marker) > 8192:
                    raise StartupConflict()
                data = json.loads(marker, object_pairs_hook=json_object, parse_constant=reject_constant)
                if not isinstance(data, dict) or set(data) != {"schema_version", "root", "commands"}:
                    raise StartupConflict()
                if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["root"] != self.identity:
                    raise StartupConflict()
                commands = data["commands"]
                if not isinstance(commands, list) or not 1 <= len(commands) <= 2 or not all(_valid_command(c) for c in commands):
                    raise StartupConflict()
            except (ValueError, TypeError, RecursionError):
                raise StartupConflict() from None
        if run is not None and (not _valid_command(run) or run not in commands):
            raise StartupConflict()
        return run, marker, commands

    def inspect(self) -> StartupStatus:
        if self.root is None:
            return StartupStatus(False, False, "一時実行ではログイン時の起動を登録できません。")
        if self.registry is None:
            return StartupStatus(False, False, "ログイン時の起動登録はWindowsで利用できます。")
        try:
            run, _, _ = self._pair()
        except StartupConflict:
            return StartupStatus(None, False, "起動登録の所有情報を確認できないため保護しています。Windowsのスタートアップ設定を確認してください。", False)
        except OSError:
            return StartupStatus(None, False, "起動登録の状態を確認できませんでした。再確認してください。", False)
        if run is None:
            return StartupStatus(False, True, "ログイン時の起動は未登録です。")
        return StartupStatus(True, True, "ログイン時の起動を登録済みです。Windows側で無効にしている場合は起動しません。")

    def _marker(self, commands: list[str]) -> str:
        return json.dumps({"schema_version": 1, "root": self.identity, "commands": commands}, ensure_ascii=True)

    def _unchanged(self, key: str, expected: str | None) -> None:
        if self.registry.read(key, self.name) != expected:
            raise StartupConflict()

    def set_enabled(self, enabled: bool) -> StartupStatus:
        state = self.inspect()
        if not state.can_change:
            return replace(state, succeeded=False)
        try:
            run, marker, _ = self._pair()
            if enabled:
                command = self.command_builder(self.root)
                if not _valid_command(command):
                    raise StartupUnavailable("起動設定のパスが長すぎるか、使用できない文字を含んでいます。")
                # 2段階の所有記録。Run更新の途中で失敗しても旧/新の所有を失わない。
                pending = self._marker(list(dict.fromkeys(([run] if run else []) + [command])))
                self._unchanged(RUN_KEY, run)
                self._unchanged(OWNER_KEY, marker)
                self.registry.write(OWNER_KEY, self.name, pending)
                self._unchanged(RUN_KEY, run)
                self.registry.write(RUN_KEY, self.name, command)
                self._unchanged(OWNER_KEY, pending)
                self._unchanged(RUN_KEY, command)
                self.registry.write(OWNER_KEY, self.name, self._marker([command]))
            else:
                if run is not None:
                    self._unchanged(OWNER_KEY, marker)
                    self._unchanged(RUN_KEY, run)
                    self.registry.delete(RUN_KEY, self.name)
                # 解除の途中に別の登録が入った場合は所有記録を残す。
                self._unchanged(RUN_KEY, None)
                self._unchanged(OWNER_KEY, marker)
                if marker is not None:
                    self.registry.delete(OWNER_KEY, self.name)
            return self.inspect()
        except StartupConflict:
            message = "起動登録が外部で変更されたか、所有を確認できないため変更を中止しました。"
        except (OSError, subprocess.TimeoutExpired):
            message = "起動登録の変更を完了できませんでした。状態を再確認してからやり直してください。"
        except StartupUnavailable as error:
            message = str(error)
        except ValueError:
            message = "起動設定を確認できませんでした。設定をやり直してください。"
        return replace(self.inspect(), succeeded=False, message=message)
