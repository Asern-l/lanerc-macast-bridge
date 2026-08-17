"""Single-file Windows launcher and installer for Lanerc Cast."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Lanerc Cast"
APP_VERSION = "2.0.1"
CONTROL_URL = "http://127.0.0.1:4380/"
PLUGIN_FILES = (
    "lanerc_proxy.py",
    "lanerc_potplayer.py",
    "lanerc_tv.py",
    "lanerc_pro.py",
    "lanerc_pro.html",
)
ASSET_FILES = ("app.css", "app.js", "brand.svg")
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def config_root():
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("无法确定 Windows 用户配置目录。")
    return Path(local) / "xfangfang" / "Macast"


def log_message(message):
    try:
        root = config_root()
        root.mkdir(parents=True, exist_ok=True)
        with (root / "lanerc_launcher.log").open("a", encoding="utf-8") as handle:
            handle.write("{} {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except OSError:
        pass


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def installation_current():
    source = resource_root()
    target = config_root() / "renderer"
    try:
        for name in PLUGIN_FILES:
            if file_hash(source / name) != file_hash(target / name):
                return False
        for name in ASSET_FILES:
            if file_hash(source / "lanerc_assets" / name) != file_hash(
                target / "lanerc_assets" / name
            ):
                return False
        settings = json.loads((config_root() / "macast_setting.json").read_text())
        return settings.get("Macast_Renderer") == APP_NAME
    except (OSError, ValueError, TypeError):
        return False


def macast_processes():
    command = [
        "tasklist",
        "/FI",
        "IMAGENAME eq Macast-Windows-v0.7.exe",
        "/FO",
        "CSV",
        "/NH",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    return "Macast-Windows-v0.7.exe" in result.stdout


def stop_macast():
    subprocess.run(
        ["taskkill", "/IM", "Macast-Windows-v0.7.exe", "/T", "/F"],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    deadline = time.time() + 8
    while macast_processes() and time.time() < deadline:
        time.sleep(0.25)
    if macast_processes():
        raise RuntimeError("无法关闭 Macast，请从托盘退出后重试。")
    time.sleep(1.5)


def find_potplayer():
    candidates = [
        Path(r"D:\PotPlayer\PotPlayerMini64.exe"),
        Path(r"D:\PotPlayer\PotPlayerMini.exe"),
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "DAUM"
        / "PotPlayer"
        / "PotPlayerMini64.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "PotPlayer"
        / "PotPlayerMini64.exe",
    ]
    return next((str(path) for path in candidates if path.is_file()), "")


def find_ffmpeg():
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(r"D:\Macast\tools\ffmpeg\bin\ffmpeg.exe"),
        Path(r"D:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
    ]
    from_path = shutil.which("ffmpeg")
    if from_path:
        candidates.insert(0, Path(from_path))
    return next((str(path) for path in candidates if path.is_file()), "")


def install_plugin():
    source = resource_root()
    root = config_root()
    renderer = root / "renderer"
    assets = renderer / "lanerc_assets"
    backup = root / "backup"
    renderer.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=True)

    settings_path = root / "macast_setting.json"
    if settings_path.is_file():
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(settings_path, backup / "macast_setting-{}.json".format(timestamp))
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}
    else:
        settings = {}

    for name in PLUGIN_FILES:
        shutil.copy2(source / name, renderer / name)
    for name in ASSET_FILES:
        shutil.copy2(source / "lanerc_assets" / name, assets / name)

    potplayer = find_potplayer()
    ffmpeg = find_ffmpeg()
    settings["Macast_Renderer"] = APP_NAME
    settings.setdefault("LanercOutputMode", "local")
    settings.setdefault("LanercLocalPlayer", "potplayer" if potplayer else "mpv")
    settings.setdefault("LanercTVAudio", "tv")
    settings.setdefault("LanercAudioDelay", 2.0)
    settings.setdefault("LanercAutoSync", False)
    settings.setdefault("LanercControlPort", 4380)
    settings.setdefault("LanercTVIP", "")
    settings.setdefault("LanercTVLocation", "")
    settings.setdefault("LanercFFmpegPath", ffmpeg)
    settings.setdefault("LanercRelayPort", 0)
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=True, indent=4, sort_keys=True),
        encoding="utf-8",
    )
    log_message("Installed Lanerc Cast {}".format(APP_VERSION))


def find_macast_executable():
    candidates = []
    home = os.environ.get("MACAST_HOME")
    if home:
        candidates.append(Path(home) / "app" / "Macast-Windows-v0.7.exe")
    candidates.extend(
        [
            Path(r"D:\Macast\app\Macast-Windows-v0.7.exe"),
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "Macast"
            / "Macast-Windows-v0.7.exe",
        ]
    )
    found = next((path for path in candidates if path.is_file()), None)
    return found


def start_macast(executable):
    if macast_processes():
        return
    environment = os.environ.copy()
    macast_home = executable.parent.parent
    runtime = macast_home / "runtime"
    if runtime.parent == macast_home:
        runtime.mkdir(parents=True, exist_ok=True)
        environment["TEMP"] = str(runtime)
        environment["TMP"] = str(runtime)
    subprocess.Popen(
        [str(executable)],
        cwd=str(executable.parent),
        env=environment,
        close_fds=True,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    )


def wait_for_control_center(timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(CONTROL_URL + "api/status", timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if payload.get("ok") and payload.get("data", {}).get("app", {}).get(
                    "version"
                ) == APP_VERSION:
                    return True
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    return False


class LauncherWindow:
    def __init__(self, no_open=False):
        self.no_open = no_open
        self.root = tk.Tk()
        self.root.title("{} {}".format(APP_NAME, APP_VERSION))
        self.root.geometry("500x270")
        self.root.resizable(False, False)
        self.root.configure(bg="#f2f5f7")
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        try:
            self.root.iconbitmap(str(resource_root() / "lanerc_assets" / "app.ico"))
        except tk.TclError:
            pass
        self._center()

        header = tk.Frame(self.root, bg="#123147", height=92)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=APP_NAME,
            fg="white",
            bg="#123147",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=28, pady=(20, 0))
        tk.Label(
            header,
            text="Macast 播放兼容与电视转码  ·  {}".format(APP_VERSION),
            fg="#bfcdd5",
            bg="#123147",
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=28, pady=(1, 0))

        body = tk.Frame(self.root, bg="#f2f5f7")
        body.pack(fill="both", expand=True, padx=28, pady=24)
        self.status = tk.Label(
            body,
            text="正在准备…",
            fg="#17232d",
            bg="#f2f5f7",
            anchor="w",
            font=("Microsoft YaHei UI", 10),
        )
        self.status.pack(fill="x", pady=(0, 16))
        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.pack(fill="x")
        self.progress.start(12)
        self.detail = tk.Label(
            body,
            text="控制中心仅在本机运行",
            fg="#687985",
            bg="#f2f5f7",
            anchor="w",
            font=("Microsoft YaHei UI", 8),
        )
        self.detail.pack(fill="x", pady=(12, 0))
        self.exit_code = 1
        self.root.after(150, lambda: threading.Thread(target=self.run, daemon=True).start())

    def _center(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 500) // 2
        y = (self.root.winfo_screenheight() - 270) // 2
        self.root.geometry("500x270+{}+{}".format(x, y))

    def set_status(self, text, detail=None):
        self.root.after(0, lambda: self.status.config(text=text))
        if detail is not None:
            self.root.after(0, lambda: self.detail.config(text=detail))

    def ask_close_macast(self):
        result = {"value": False}
        event = threading.Event()

        def ask():
            result["value"] = messagebox.askyesno(
                "需要更新",
                "检测到 Macast 正在运行。\n\n是否停止当前播放、关闭 Macast 并继续更新？",
                parent=self.root,
            )
            event.set()

        self.root.after(0, ask)
        event.wait()
        return result["value"]

    def ask_macast_file(self):
        result = {"value": ""}
        event = threading.Event()

        def ask():
            result["value"] = filedialog.askopenfilename(
                parent=self.root,
                title="选择 Macast 主程序",
                filetypes=(
                    ("Macast", "Macast-Windows-v0.7.exe"),
                    ("Windows 程序", "*.exe"),
                ),
            )
            event.set()

        self.root.after(0, ask)
        event.wait()
        return Path(result["value"]) if result["value"] else None

    def finish(self, success, message):
        self.exit_code = 0 if success else 1

        def update():
            self.progress.stop()
            self.status.config(text=message)
            if success:
                self.detail.config(text="控制中心已就绪")
                self.root.after(900, self.root.destroy)
            else:
                self.detail.config(text="详情已写入 lanerc_launcher.log")
                messagebox.showerror(APP_NAME, message, parent=self.root)
                self.root.destroy()

        self.root.after(0, update)

    def run(self):
        try:
            needs_install = not installation_current()
            if needs_install and macast_processes():
                if not self.ask_close_macast():
                    self.root.after(0, self.root.destroy)
                    return
                self.set_status("正在关闭 Macast…")
                stop_macast()
            if needs_install:
                self.set_status("正在安装 Lanerc Cast…", "现有设置将被保留")
                install_plugin()
            executable = find_macast_executable() or self.ask_macast_file()
            if executable is None:
                self.finish(False, "未找到 Macast 主程序。")
                return
            self.set_status("正在启动 Macast…", str(executable))
            start_macast(executable)
            self.set_status("正在连接控制中心…", CONTROL_URL)
            if not wait_for_control_center():
                raise RuntimeError("控制中心启动超时，请检查 Macast 日志。")
            if not self.no_open:
                webbrowser.open(CONTROL_URL)
            self.finish(True, "Lanerc Cast 已启动")
        except Exception as exc:
            log_message("Launcher error: {!r}".format(exc))
            self.finish(False, str(exc))

    def mainloop(self):
        self.root.mainloop()
        return self.exit_code


def main():
    no_open = "--no-open" in sys.argv
    return LauncherWindow(no_open=no_open).mainloop()


if __name__ == "__main__":
    raise SystemExit(main())
