import os

# 抑制 macOS 上 Tkinter 的版本警告
os.environ["TK_SILENCE_DEPRECATION"] = "1"

import sys
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import subprocess
import time
import threading
from datetime import datetime
import re


class YTRecorderApp:
    # 顏色設定（深色主題）
    COLOR_SUCCESS = "#2ecc71"
    COLOR_ERROR = "#e74c3c"
    COLOR_WARNING = "#f39c12"
    COLOR_INFO = "#3498db"
    COLOR_PRIMARY = "#27ae60"
    COLOR_DANGER = "#c0392b"

    BG_COLOR = "#2b2b2b"
    FRAME_BG = "#2b2b2b"
    TEXT_COLOR = "#ffffff"
    ENTRY_BG = "#404040"
    ENTRY_FG = "#ffffff"
    CURSOR_COLOR = "#ffffff"
    BORDER_COLOR = "#555555"

    # User-Agent / Referer 及 403 workaround
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
    REFERER = "https://www.youtube.com/"
    EXTRACTOR_ARGS = (
        "youtube:player_client=default,web_safari;player_js_version=actual"
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YouTube 直播錄製 (macOS)")
        self.root.geometry("920x850")
        self.root.minsize(800, 700)
        self.root.configure(bg=self.BG_COLOR)

        # 主容器
        self.main_container = tk.Frame(self.root, bg=self.BG_COLOR)
        self.main_container.pack(fill="both", expand=True)

        # 狀態 / 執行緒
        self.is_monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self.stop_event = threading.Event()

        # UI 綁定的變數
        self.cookie_status_var = tk.StringVar(value="等待檢查...")
        self.cookie_test_url_var = tk.StringVar(
            value="https://www.youtube.com/live/KCDNSTKeiCc?si=ucf9QUiOX3mhLC35s"
        )

        self.check_interval_var = tk.StringVar(value="300")

        default_dir = os.path.join(
            os.path.expanduser("~"), "Downloads", "yt_recorder_downloads"
        )
        self.download_dir = tk.StringVar(value=default_dir)

        self.channel_url = tk.StringVar(
            value="https://www.youtube.com/@Umitw46/live"
        )
        self.test_video_url = tk.StringVar(value="")

        # 建立 UI
        self.create_widgets()

        # 快捷鍵
        self.root.bind("<Control-s>", lambda e: self.toggle_monitoring())
        self.root.bind("<Control-S>", lambda e: self.toggle_monitoring())
        self.root.bind("<Control-l>", lambda e: self.clear_logs())
        self.root.bind("<Control-L>", lambda e: self.clear_logs())

        # 啟動後自動做一次 Cookie 檢查（靜默）
        self.root.after(1000, lambda: self.check_cookies_thread(silent=True))

    # ------------------------------------------------------------------
    # 共用工具：yt-dlp 路徑與參數
    # ------------------------------------------------------------------

    def _get_ytdlp_executable(self) -> str | None:
        """
        取得可用的 yt-dlp 執行檔路徑。

        優先順序：
        1. 打包後 .app 內的 yt-dlp
        2. 與此 .py 同目錄的 yt-dlp
        3. 系統 PATH 內的 yt-dlp
        """
        candidates: list[str] = []

        # 1) 打包後 (.app / PyInstaller frozen)
        try:
            if getattr(sys, "frozen", False):
                exe_dir = os.path.dirname(sys.executable)
                # PyInstaller --add-binary "yt-dlp_macos:yt-dlp"
                candidates.append(os.path.join(exe_dir, "yt-dlp"))

                # 備用：.app/Contents/Resources/yt-dlp
                app_exec = Path(sys.executable).resolve()
                resources_path = app_exec.parents[1] / "Resources" / "yt-dlp"
                candidates.append(str(resources_path))
        except Exception:
            pass

        # 2) 開發模式：同目錄 yt-dlp
        try:
            script_dir = Path(__file__).resolve().parent
            candidates.append(str(script_dir / "yt-dlp"))
        except Exception:
            pass

        # 3) 系統 PATH
        path_exe = shutil.which("yt-dlp")
        if path_exe:
            candidates.append(path_exe)

        for p in candidates:
            if p and os.path.exists(p) and os.access(p, os.X_OK):
                return p

        return None

    def _base_ytdlp_args(self) -> list[str]:
        """所有 yt-dlp 呼叫共用的 Anti-403 參數。"""
        return [
            "--ignore-config",
            "--no-cache-dir",
            "--cookies-from-browser",
            "chrome",
            "--user-agent",
            self.USER_AGENT,
            "--referer",
            self.REFERER,
            "--extractor-args",
            self.EXTRACTOR_ARGS,
            "--remote-components",
            "ejs:github",
        ]

    def _build_ytdlp_command(
        self, extra_args: list[str], url: str | None = None
    ) -> list[str]:
        """組合完整 yt-dlp 命令列。找不到執行檔時丟 FileNotFoundError。"""
        exe = self._get_ytdlp_executable()
        if not exe:
            raise FileNotFoundError("yt-dlp executable not found")
        cmd = [exe]
        cmd.extend(extra_args)
        if url:
            cmd.append(url)
        return cmd

    # ------------------------------------------------------------------
    # GUI 建立
    # ------------------------------------------------------------------

    def create_widgets(self) -> None:
        label_style = {
            "bg": self.BG_COLOR,
            "fg": self.TEXT_COLOR,
            "font": ("", 10),
        }
        frame_style = {"bg": self.BG_COLOR}

        # 1. 核心設定與工具
        config_frame = tk.LabelFrame(
            self.main_container,
            text="核心設定與工具",
            padx=15,
            pady=15,
            font=("", 10, "bold"),
            bg=self.BG_COLOR,
            fg=self.TEXT_COLOR,
            bd=1,
            relief="solid",
        )
        config_frame.pack(fill="x", padx=10, pady=8)

        # 更新 yt-dlp 按鈕
        tools_frame = tk.Frame(config_frame, **frame_style)
        tools_frame.pack(fill="x", pady=(0, 10))

        tk.Button(
            tools_frame,
            text="更新 yt-dlp 核心",
            command=self.update_ytdlp,
            bg=self.COLOR_INFO,
            fg="black",
            padx=10,
            font=("", 9),
        ).pack(side="right")

        tk.Label(
            tools_frame,
            text="若遇 HTTP 403，請先嘗試更新 yt-dlp。",
            bg=self.BG_COLOR,
            fg="#aaaaaa",
            font=("", 9),
        ).pack(side="right", padx=10)

        # Cookie 測試
        cookie_input_frame = tk.Frame(config_frame, **frame_style)
        cookie_input_frame.pack(fill="x", pady=(0, 8))

        tk.Label(
            cookie_input_frame,
            text="Cookie 測試網址:",
            **label_style,
        ).pack(side="left")

        tk.Entry(
            cookie_input_frame,
            textvariable=self.cookie_test_url_var,
            width=45,
            bg=self.ENTRY_BG,
            fg=self.ENTRY_FG,
            insertbackground=self.CURSOR_COLOR,
            highlightbackground=self.BORDER_COLOR,
            relief="flat",
        ).pack(side="left", padx=8)

        tk.Button(
            cookie_input_frame,
            text="執行 Cookie 測試",
            command=lambda: self.check_cookies_thread(silent=False),
            bg=self.COLOR_INFO,
            fg="black",
            padx=12,
            cursor="hand2",
        ).pack(side="left", padx=5)

        self.status_indicator = tk.Label(
            config_frame,
            textvariable=self.cookie_status_var,
            bg=self.BG_COLOR,
            fg=self.COLOR_WARNING,
            font=("", 11, "bold"),
        )
        self.status_indicator.pack(anchor="w", padx=5, pady=(0, 12))

        # 分隔線
        tk.Frame(
            config_frame, height=2, bd=0, bg=self.BORDER_COLOR
        ).pack(fill="x", pady=8)

        # 直播網址
        url_frame = tk.Frame(config_frame, **frame_style)
        url_frame.pack(fill="x", pady=(5, 0))

        tk.Label(url_frame, text="直播網址:", **label_style).pack(side="left")

        tk.Entry(
            url_frame,
            textvariable=self.channel_url,
            width=50,
            bg=self.ENTRY_BG,
            fg=self.ENTRY_FG,
            insertbackground=self.CURSOR_COLOR,
            highlightbackground=self.BORDER_COLOR,
            relief="flat",
        ).pack(side="left", padx=8, fill="x", expand=True)

        tk.Label(
            config_frame,
            text="範例：https://www.youtube.com/@頻道名稱/live",
            bg=self.BG_COLOR,
            fg="#aaaaaa",
            font=("", 9),
        ).pack(anchor="w", padx=10, pady=(2, 8))

        # 檢測頻率
        interval_frame = tk.Frame(config_frame, **frame_style)
        interval_frame.pack(fill="x", pady=5)

        tk.Label(interval_frame, text="檢測頻率:", **label_style).pack(side="left")

        tk.Spinbox(
            interval_frame,
            from_=30,
            to=3600,
            textvariable=self.check_interval_var,
            width=10,
            validate="key",
            validatecommand=(self.root.register(self._validate_number), "%P"),
            bg=self.ENTRY_BG,
            fg=self.ENTRY_FG,
            insertbackground=self.CURSOR_COLOR,
            highlightbackground=self.BORDER_COLOR,
            relief="flat",
        ).pack(side="left", padx=8)

        tk.Label(interval_frame, text="秒", **label_style).pack(side="left", padx=2)

        tk.Label(
            interval_frame,
            text="(建議 60 秒以上，避免被 YouTube 限制)",
            bg=self.BG_COLOR,
            fg="#aaaaaa",
            font=("", 9),
        ).pack(side="left", padx=8)

        # 2. 影片測試下載
        test_frame = tk.LabelFrame(
            self.main_container,
            text="影片測試下載 (非直播)",
            padx=15,
            pady=12,
            font=("", 10, "bold"),
            fg=self.COLOR_INFO,
            bg=self.BG_COLOR,
            bd=1,
            relief="solid",
        )
        test_frame.pack(fill="x", padx=10, pady=8)

        test_input_frame = tk.Frame(test_frame, **frame_style)
        test_input_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            test_input_frame,
            text="影片網址:",
            **label_style,
        ).pack(side="left")

        tk.Entry(
            test_input_frame,
            textvariable=self.test_video_url,
            width=50,
            bg=self.ENTRY_BG,
            fg=self.ENTRY_FG,
            insertbackground=self.CURSOR_COLOR,
            highlightbackground=self.BORDER_COLOR,
            relief="flat",
        ).pack(side="left", padx=8, fill="x", expand=True)

        tk.Button(
            test_input_frame,
            text="立即下載",
            command=self.download_test_video,
            bg=self.COLOR_SUCCESS,
            fg="black",
            padx=15,
            cursor="hand2",
            font=("", 10, "bold"),
        ).pack(side="left", padx=5)

        tk.Label(
            test_frame,
            text="用於測試一般影片下載功能，檔案會儲存在下方設定的資料夾。",
            bg=self.BG_COLOR,
            fg="#aaaaaa",
            font=("", 9),
        ).pack(anchor="w", padx=5)

        # 3. 存檔位置
        path_frame = tk.LabelFrame(
            self.main_container,
            text="存檔位置",
            padx=15,
            pady=12,
            font=("", 10, "bold"),
            bg=self.BG_COLOR,
            fg=self.TEXT_COLOR,
            bd=1,
            relief="solid",
        )
        path_frame.pack(fill="x", padx=10, pady=8)

        tk.Entry(
            path_frame,
            textvariable=self.download_dir,
            width=60,
            state="readonly",
            bg=self.ENTRY_BG,
            fg=self.ENTRY_FG,
            readonlybackground="#333333",
            highlightbackground=self.BORDER_COLOR,
            relief="flat",
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        tk.Button(
            path_frame,
            text="選擇資料夾",
            command=self.select_directory,
            bg=self.COLOR_INFO,
            fg="black",
            padx=15,
            cursor="hand2",
        ).pack(side="right")

        # 4. 控制區
        control_frame = tk.Frame(self.main_container, pady=12, bg=self.BG_COLOR)
        control_frame.pack(fill="x", padx=10)

        self.btn_start = tk.Button(
            control_frame,
            text="開始自動監控 (Ctrl+S)",
            command=self.toggle_monitoring,
            bg=self.COLOR_PRIMARY,
            fg="black",
            font=("", 13, "bold"),
            height=2,
            cursor="hand2",
            relief="raised",
            bd=2,
        )
        self.btn_start.pack(fill="x")

        # 5. 日誌區
        status_frame = tk.LabelFrame(
            self.main_container,
            text="運作狀態與日誌",
            padx=12,
            pady=12,
            font=("", 10, "bold"),
            bg=self.BG_COLOR,
            fg=self.TEXT_COLOR,
            bd=1,
            relief="solid",
        )
        status_frame.pack(fill="both", expand=True, padx=10, pady=8)

        log_control_frame = tk.Frame(status_frame, **frame_style)
        log_control_frame.pack(fill="x", pady=(0, 5))

        tk.Button(
            log_control_frame,
            text="清除日誌 (Ctrl+L)",
            command=self.clear_logs,
            bg="#95a5a6",
            fg="black",
            padx=10,
            cursor="hand2",
        ).pack(side="right")

        self.log_text = scrolledtext.ScrolledText(
            status_frame,
            height=15,
            state="disabled",
            font=("Courier", 10),
            wrap="word",
            bg="#1e1e1e",
            fg="#00ff00",
            highlightbackground=self.BORDER_COLOR,
            relief="flat",
        )
        self.log_text.pack(fill="both", expand=True)

        # 底部狀態列
        self.status_label = tk.Label(
            self.main_container,
            text="就緒 | Ctrl+S: 開始/停止 | Ctrl+L: 清除日誌",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=("", 9),
            bg="#1e1e1e",
            fg="white",
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # 一般工具
    # ------------------------------------------------------------------

    def _validate_number(self, value: str) -> bool:
        return value == "" or value.isdigit()

    def _validate_url(self, url: str) -> bool:
        pattern = re.compile(r"^https?://(www\.)?youtube\.com/.+$")
        return bool(pattern.match(url))

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"

        def _update() -> None:
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, full_msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")

        self.root.after(0, _update)
        self.root.after(
            0,
            lambda: self.status_label.config(
                text=message[:100] + "..." if len(message) > 100 else message
            ),
        )

    def clear_logs(self) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        self.log("日誌已清除")

    # ------------------------------------------------------------------
    # yt-dlp 更新、路徑選擇
    # ------------------------------------------------------------------

    def update_ytdlp(self) -> None:
        """嘗試更新內建或系統的 yt-dlp。"""

        def _update_thread() -> None:
            self.log("正在更新 yt-dlp，請稍候...")
            try:
                exe = self._get_ytdlp_executable()
                if exe and os.path.basename(exe).startswith("yt-dlp"):
                    # 優先更新內建二進位檔（支援 -U）
                    result = subprocess.run(
                        [exe, "-U"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    self.log(result.stdout.strip())
                    if result.stderr.strip():
                        self.log(result.stderr.strip())
                    self.log("更新程序已結束。")
                else:
                    # 備用：使用 pip 更新系統套件
                    cmd = ["pip3", "install", "--upgrade", "yt-dlp"]
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    self.log(result.stdout.strip())
                    if result.stderr.strip():
                        self.log(result.stderr.strip())
                    self.log("已嘗試透過 pip 更新 yt-dlp。")
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "更新完成", "更新程序已執行，請查看日誌確認結果。"
                    ),
                )
            except Exception as e:
                self.log(f"更新失敗: {e}")

        threading.Thread(target=_update_thread, daemon=True).start()

    def select_directory(self) -> None:
        path = filedialog.askdirectory(initialdir=self.download_dir.get())
        if path:
            self.download_dir.set(path)
            self.log(f"已更改下載路徑: {path}")

    # ------------------------------------------------------------------
    # 測試影片下載
    # ------------------------------------------------------------------

    def download_test_video(self) -> None:
        url = self.test_video_url.get().strip()
        if not url:
            messagebox.showwarning("警告", "請輸入影片網址")
            return
        if not self._validate_url(url):
            messagebox.showerror("錯誤", "請輸入有效的 YouTube 網址")
            return
        self.log("開始下載測試影片...")
        threading.Thread(
            target=self._download_video_impl,
            args=(url,),
            daemon=True,
        ).start()

    def _download_video_impl(self, url: str) -> None:
        output_dir = self.download_dir.get()
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self.log(f"無法建立資料夾: {e}")
            return

        output_path = os.path.join(output_dir, "%(title)s-%(id)s.%(ext)s")

        try:
            command = self._build_ytdlp_command(
                self._base_ytdlp_args()
                + [
                    "-f",
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    output_path,
                    "--newline",
                    "--progress",
                ],
                url,
            )
        except FileNotFoundError:
            self.log("找不到 yt-dlp 可執行檔，請確認內建 yt-dlp 是否已正確打包。")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "錯誤",
                    "找不到內建 yt-dlp。\n\n"
                    "請重新下載安裝包，或確認打包時有加入 yt-dlp_macos。",
                ),
            )
            return

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                bufsize=1,
            )

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                if "WARNING" in line and "Remote components" in line:
                    continue
                if "Destination:" in line or "Merging" in line:
                    self.log(line)
                elif "[download]" in line and "%" in line:
                    self.log(line)

            process.wait()
            if process.returncode == 0:
                self.log("測試影片下載完成。")
                self.root.after(
                    0,
                    lambda: messagebox.showinfo("成功", "影片下載完成。"),
                )
            else:
                self.log(f"下載失敗，返回碼: {process.returncode}")
                self.root.after(
                    0,
                    lambda: messagebox.showerror("錯誤", "影片下載失敗，請檢查日誌。"),
                )
        except Exception as e:
            self.log(f"下載錯誤: {e}")
            self.root.after(
                0,
                lambda: messagebox.showerror("錯誤", f"下載錯誤: {e}"),
            )

    # ------------------------------------------------------------------
    # Cookie 檢查
    # ------------------------------------------------------------------

    def check_cookies_thread(self, silent: bool = False) -> None:
        threading.Thread(
            target=self._check_cookies_impl,
            args=(silent,),
            daemon=True,
        ).start()

    def _check_cookies_impl(self, silent: bool = False) -> None:
        test_url = self.cookie_test_url_var.get().strip()
        if not test_url:
            test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

        if not self._validate_url(test_url):
            self.log("無效的 YouTube 網址")
            self._update_cookie_ui(False, "網址格式錯誤", self.COLOR_ERROR)
            return

        if not silent:
            self.log("正在檢查 Cookie 權限...")
        self._update_cookie_ui(False, "檢查中...", self.COLOR_WARNING)

        try:
            command = self._build_ytdlp_command(
                self._base_ytdlp_args() + ["--print", "title"],
                test_url,
            )
        except FileNotFoundError:
            self._update_cookie_ui(False, "找不到 yt-dlp", self.COLOR_ERROR)
            if not silent:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "錯誤",
                        "找不到內建 yt-dlp。\n\n"
                        "請重新安裝或確認打包時已包含 yt-dlp。",
                    ),
                )
            return

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
                shell=False,
            )
            if result.returncode == 0:
                title = result.stdout.strip()
                msg = f"驗證成功 (標題: {title[:25]}...)"
                self._update_cookie_ui(True, msg, self.COLOR_SUCCESS)
                if not silent:
                    self.log(f"Cookie 有效，成功讀取影片: {title}")
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "驗證成功",
                            f"Cookie 運作正常。\n\n影片標題：{title}",
                        ),
                    )
            else:
                stderr = result.stderr
                self._update_cookie_ui(False, "存取失敗", self.COLOR_ERROR)
                if "WARNING" not in stderr or "Remote components" not in stderr:
                    self.log(f"Cookie 檢查失敗: {stderr[:100]}")
                if not silent:
                    self._show_cookie_error(stderr)
        except subprocess.TimeoutExpired:
            self._update_cookie_ui(False, "檢查超時", self.COLOR_ERROR)
            self.log("Cookie 檢查超時 (60 秒)")
        except Exception as e:
            self._update_cookie_ui(False, "錯誤", self.COLOR_ERROR)
            self.log(f"未知錯誤: {e}")

    def _show_cookie_error(self, stderr: str) -> None:
        msg = "無法讀取影片資訊。\n\n"
        lower = stderr.lower()
        if "sign in to confirm" in stderr or "age" in lower:
            msg += "原因：需要登入（Cookie 無效或未抓取）。"
        elif "private video" in stderr:
            msg += "原因：私人影片，需要特定權限。"
        elif "members-only" in lower or "members only" in lower:
            msg += "原因：會員限定內容，但目前 Cookie 沒有權限。"
        elif "403" in stderr:
            msg += "原因：403 禁止訪問，可能是 IP 被限制或 yt-dlp 版本過舊。"
        else:
            msg += f"錯誤詳情：{stderr[:200]}"

        msg += (
            "\n\n建議：\n"
            "1. 使用上方按鈕更新 yt-dlp\n"
            "2. 在 Chrome 登入 YouTube 並確認可正常播放此影片\n"
            "3. 完全關閉 Chrome 後重新測試"
        )
        self.root.after(0, lambda: messagebox.showerror("驗證失敗", msg))

    def _update_cookie_ui(self, success: bool, text: str, color: str) -> None:
        def _update() -> None:
            self.cookie_status_var.set(text)
            self.status_indicator.config(fg=color)

        self.root.after(0, _update)

    # ------------------------------------------------------------------
    # 直播監控與錄製
    # ------------------------------------------------------------------

    def toggle_monitoring(self) -> None:
        if not self.is_monitoring:
            # 驗證頻率
            try:
                interval = int(self.check_interval_var.get())
            except ValueError:
                messagebox.showerror("錯誤", "檢測頻率必須是有效數字")
                return

            if interval < 10:
                messagebox.showerror("錯誤", "檢測間隔不能小於 10 秒")
                return
            elif interval < 30:
                if not messagebox.askyesno(
                    "警告",
                    "檢測間隔小於 30 秒可能導致 IP 被 YouTube 限制，確定繼續？",
                ):
                    return

            # 驗證網址
            url = self.channel_url.get().strip()
            if not self._validate_url(url):
                messagebox.showerror("錯誤", "請輸入有效的 YouTube 網址")
                return

            # 開始監控
            self.is_monitoring = True
            self.stop_event.clear()
            self.btn_start.config(
                text="停止監控 (Ctrl+S)",
                bg=self.COLOR_DANGER,
            )
            self.log(f"開始監控 (間隔: {interval} 秒)")
            self.monitor_thread = threading.Thread(
                target=self.monitor_loop,
                daemon=True,
            )
            self.monitor_thread.start()
        else:
            # 停止監控
            self.is_monitoring = False
            self.stop_event.set()
            self.btn_start.config(
                text="開始自動監控 (Ctrl+S)",
                bg=self.COLOR_PRIMARY,
            )
            self.log("正在停止監控...")

    def is_live(self, url: str) -> bool:
        """檢查指定網址是否正在直播。"""
        try:
            command = self._build_ytdlp_command(
                self._base_ytdlp_args() + ["--get-title"],
                url,
            )
        except FileNotFoundError:
            self.log("找不到 yt-dlp，可執行檔遺失，無法檢測直播狀態。")
            return False

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                shell=False,
            )
            if result.returncode == 0:
                title = result.stdout.strip()
                self.log(f"偵測到直播：{title}")
                return True
            else:
                stderr = result.stderr.strip()
                if "will begin in" in stderr:
                    self.log("直播尚未開始。")
                return False
        except subprocess.TimeoutExpired:
            self.log("檢測直播狀態超時。")
            return False
        except Exception as e:
            self.log(f"檢測直播狀態錯誤: {e}")
            return False

    def record_live_stream(self, url: str) -> None:
        """錄製直播。"""
        output_dir = self.download_dir.get()
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self.log(f"無法建立資料夾: {e}")
            return

        output_path = os.path.join(output_dir, "%(title)s-%(id)s.%(ext)s")

        try:
            command = self._build_ytdlp_command(
                self._base_ytdlp_args()
                + [
                    "--live-from-start",
                    "--wait-for-video",
                    "5-60",
                    "-f",
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "--merge-output-format",
                    "mp4",
                    "--hls-use-mpegts",
                    "--concurrent-fragments",
                    "5",
                    "--no-part",
                    "--newline",
                    "--progress",
                    "-o",
                    output_path,
                ],
                url,
            )
        except FileNotFoundError:
            self.log("找不到 yt-dlp，可執行檔遺失，無法開始錄製直播。")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "錯誤",
                    "找不到內建 yt-dlp。\n\n"
                    "請重新安裝或確認打包時已包含 yt-dlp。",
                ),
            )
            return

        self.log("啟動直播錄製...")
        process: subprocess.Popen | None = None

        try:
            start_time = time.time()
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                bufsize=1,
            )

            last_log_time = 0.0
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                if "WARNING" in line and "Remote components" in line:
                    continue

                now = time.time()
                if now - last_log_time >= 10 and "[download]" in line:
                    self.log(line)
                    last_log_time = now

                if "Destination:" in line or "Merging" in line or "ERROR" in line:
                    self.log(line)

                if (
                    "HTTP Error 403" in line
                    and "Retrying" not in line
                ):
                    self.log("偵測到 HTTP 403，請嘗試更新 yt-dlp 或更換 IP。")

                if self.stop_event.is_set():
                    process.terminate()
                    self.log("使用者要求停止錄製。")
                    break

                elapsed = int(time.time() - start_time)
                h, rem = divmod(elapsed, 3600)
                m, s = divmod(rem, 60)

                def update_status() -> None:
                    self.status_label.config(
                        text=f"錄製中... {h:02d}:{m:02d}:{s:02d}"
                    )

                self.root.after(0, update_status)

            process.wait()
            if process.returncode == 0:
                self.log("錄製完成。")
            elif not self.stop_event.is_set():
                self.log(f"錄製結束，返回碼: {process.returncode}")
        except Exception as e:
            self.log(f"錄製錯誤: {e}")
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()

    def monitor_loop(self) -> None:
        """主監控迴圈。"""
        url = self.channel_url.get().strip()
        while not self.stop_event.is_set():
            try:
                try:
                    check_interval = int(self.check_interval_var.get())
                except ValueError:
                    check_interval = 120

                self.log("檢測直播狀態中...")
                if self.is_live(url):
                    self.log("確認到直播信號，準備開始錄製...")
                    time.sleep(3)
                    self.record_live_stream(url)
                    self.log("錄製結束，冷卻 60 秒...")
                    for _ in range(60):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)
                else:
                    for i in range(check_interval):
                        if self.stop_event.is_set():
                            break
                        if i % 10 == 0:
                            remaining = check_interval - i

                            def update_waiting() -> None:
                                self.status_label.config(
                                    text=f"等待下次檢測... 剩餘 {remaining} 秒"
                                )

                            self.root.after(0, update_waiting)
                        time.sleep(1)
            except Exception as e:
                self.log(f"監控迴圈錯誤: {e}")
                time.sleep(30)

        self.log("監控已停止。")
        self.root.after(0, lambda: self.status_label.config(text="就緒"))


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = YTRecorderApp(root)
        root.mainloop()
    except tk.TclError as e:
        if "no display name" in str(e) or "no $DISPLAY" in str(e):
            print("\n==============================")
            print("錯誤：無法啟動圖形介面 (No Display Found)")
            print("==============================")
            print("此程式為視窗應用程式，請在有桌面的 macOS 環境執行。")
            print("==============================\n")
        else:
            raise
