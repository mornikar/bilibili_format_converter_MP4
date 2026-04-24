"""
BiliM4S2MP4 - B站m4s视频转换工具
支持拖拽文件夹/文件，自动识别m4s并合并为MP4/MKV/WebM
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD

# ─── 常量 ────────────────────────────────────────────────────────────
APP_NAME = "BiliM4S2MP4"
APP_VERSION = "1.0"
DASH_HEADER_SIZE = 9  # B站 m4s 文件前9字节 DASH 头

SUPPORTED_FORMATS = {
    "MP4":  ".mp4",
    "MKV":  ".mkv",
    "WebM": ".webm",
    "TS":   ".ts",
    "FLV":  ".flv",
}

# 视频流和音频流的m4s后缀标识
VIDEO_IDS = ("30080", "30032", "30064", "30016")  # 不同清晰度的视频流ID
AUDIO_IDS = ("30280", "30232", "30216")            # 不同音质的音频流ID

# ffmpeg 查找路径（常见安装位置）
FFMPEG_SEARCH_PATHS = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
]

# ─── 颜色主题 ────────────────────────────────────────────────────────
COLORS = {
    "bg":       "#1e1e2e",
    "surface":  "#2a2a3d",
    "accent":   "#7c3aed",
    "accent2":  "#a78bfa",
    "text":     "#e2e8f0",
    "dim":      "#94a3b8",
    "success":  "#22c55e",
    "error":    "#ef4444",
    "warning":  "#f59e0b",
    "drop_bg":  "#1e1b4b",
    "drop_border": "#7c3aed",
}

# ─── 工具函数 ────────────────────────────────────────────────────────

def get_app_dir():
    """获取应用所在目录（兼容PyInstaller打包后路径）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def find_ffmpeg():
    """查找系统中的 ffmpeg"""
    # 0. 先查打包内嵌
    bundled = os.path.join(get_app_dir(), "ffmpeg.exe")
    if os.path.isfile(bundled):
        return bundled
    # 1. 查 EXE 同目录
    if getattr(sys, 'frozen', False):
        local = os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe")
        if os.path.isfile(local):
            return local
    # 2. 查 PATH
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        ffmpeg_path = os.path.join(path_dir, "ffmpeg.exe")
        if os.path.isfile(ffmpeg_path):
            return ffmpeg_path
    # 3. 查常见路径
    for p in FFMPEG_SEARCH_PATHS:
        if os.path.isfile(p):
            return p
    # 4. 查脚本同目录
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
    if os.path.isfile(local):
        return local
    return None


def strip_dash_header(input_path, output_path):
    """去掉 m4s 的 B站 DASH 头（前9字节）"""
    with open(input_path, 'rb') as f:
        data = f.read()
    with open(output_path, 'wb') as f:
        f.write(data[DASH_HEADER_SIZE:])


def get_video_title(dir_path):
    """从 videoInfo.json 读取视频标题"""
    info_path = os.path.join(dir_path, 'videoInfo.json')
    if os.path.exists(info_path):
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
            title = info.get('title', '')
            if title:
                return "".join(c for c in title if c not in r'\/:*?"<>|')
        except Exception:
            pass
    return os.path.basename(dir_path)


def find_m4s_pairs(dir_path):
    """在目录中查找视频/音频 m4s 对"""
    files = os.listdir(dir_path)
    video_file = None
    audio_file = None
    
    for f in files:
        if not f.endswith('.m4s'):
            continue
        for vid in VIDEO_IDS:
            if vid in f:
                video_file = os.path.join(dir_path, f)
                break
        for aid in AUDIO_IDS:
            if aid in f:
                audio_file = os.path.join(dir_path, f)
                break
    
    return video_file, audio_file


def scan_input_paths(paths):
    """扫描输入路径，返回可处理的目录列表
    支持直接拖入 m4s 文件所在目录，或包含多个子目录的父目录
    """
    result = []
    for p in paths:
        p = p.strip()
        # 处理 Windows 路径花括号
        if p.startswith('{') and p.endswith('}'):
            p = p[1:-1]
        if not os.path.exists(p):
            continue
        if os.path.isfile(p):
            # 拖入的是文件，取其所在目录
            p = os.path.dirname(p)
        
        # 检查目录本身是否包含 m4s
        v, a = find_m4s_pairs(p)
        if v and a:
            result.append(p)
        else:
            # 检查子目录
            try:
                for sub in os.listdir(p):
                    sub_path = os.path.join(p, sub)
                    if os.path.isdir(sub_path):
                        v, a = find_m4s_pairs(sub_path)
                        if v and a:
                            result.append(sub_path)
            except PermissionError:
                pass
    return result


def convert_one(dir_path, output_dir, fmt, ffmpeg_path, log_callback):
    """转换单个目录"""
    title = get_video_title(dir_path)
    ext = SUPPORTED_FORMATS.get(fmt, ".mp4")
    output_file = os.path.join(output_dir, f"{title}{ext}")
    
    # 检查输出文件是否已存在
    if os.path.exists(output_file):
        base, ext2 = os.path.splitext(output_file)
        i = 1
        while os.path.exists(f"{base}_{i}{ext2}"):
            i += 1
        output_file = f"{base}_{i}{ext2}"
    
    video_m4s, audio_m4s = find_m4s_pairs(dir_path)
    if not video_m4s or not audio_m4s:
        log_callback(f"[ERROR] {title}: 未找到视频/音频m4s文件", "error")
        return False
    
    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_video = os.path.join(tmp_dir, 'video.m4s')
        tmp_audio = os.path.join(tmp_dir, 'audio.m4s')
        
        log_callback(f"去DASH头: {os.path.basename(video_m4s)}")
        strip_dash_header(video_m4s, tmp_video)
        log_callback(f"去DASH头: {os.path.basename(audio_m4s)}")
        strip_dash_header(audio_m4s, tmp_audio)
        
        log_callback(f"合并中: {title}{ext}")
        cmd = [
            ffmpeg_path, '-i', tmp_video, '-i', tmp_audio,
            '-c:v', 'copy', '-c:a', 'copy',
            '-movflags', '+faststart',
            '-y', output_file
        ]
        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            log_callback(f"[ERROR] ffmpeg: {result.stderr[-200:]}", "error")
            return False
        
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        log_callback(f"[OK] {title}{ext} ({size_mb:.1f} MB)", "success")
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ─── GUI ─────────────────────────────────────────────────────────────

class BiliConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("680x560")
        self.root.configure(bg=COLORS["bg"])
        self.root.resizable(True, True)
        self.root.minsize(560, 440)
        
        # 尝试设置DPI感知
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        
        self.ffmpeg_path = find_ffmpeg()
        self.task_queue = []      # 待处理的目录列表
        self.is_converting = False
        
        self._build_ui()
        self._check_ffmpeg()
    
    def _build_ui(self):
        # ── 标题栏 ──
        header = tk.Frame(self.root, bg=COLORS["surface"], height=50)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        
        tk.Label(
            header, text=f"🎬 {APP_NAME}",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg=COLORS["accent2"], bg=COLORS["surface"]
        ).pack(side="left", padx=16, pady=8)
        
        tk.Label(
            header, text=f"v{APP_VERSION}",
            font=("Microsoft YaHei UI", 9),
            fg=COLORS["dim"], bg=COLORS["surface"]
        ).pack(side="left", padx=0, pady=8)
        
        # ffmpeg 状态
        self.ffmpeg_label = tk.Label(
            header, text="",
            font=("Microsoft YaHei UI", 9),
            fg=COLORS["dim"], bg=COLORS["surface"]
        )
        self.ffmpeg_label.pack(side="right", padx=16, pady=8)
        
        # ── 拖拽区 ──
        self.drop_frame = tk.Frame(
            self.root, bg=COLORS["drop_bg"],
            highlightbackground=COLORS["drop_border"],
            highlightthickness=2, relief="flat"
        )
        self.drop_frame.pack(fill="x", padx=16, pady=(12, 0))
        
        self.drop_label = tk.Label(
            self.drop_frame,
            text="🖱 拖拽文件夹到此处\n或点击选择文件夹",
            font=("Microsoft YaHei UI", 13),
            fg=COLORS["accent2"], bg=COLORS["drop_bg"],
            cursor="hand2"
        )
        self.drop_label.pack(expand=True, fill="both", pady=30)
        
        # 拖拽绑定
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind('<<Drop>>', self._on_drop)
        
        # 点击选择
        self.drop_label.bind("<Button-1>", lambda e: self._browse_folders())
        
        # ── 文件列表 ──
        list_frame = tk.Frame(self.root, bg=COLORS["bg"])
        list_frame.pack(fill="x", padx=16, pady=(8, 0))
        
        tk.Label(
            list_frame, text="待转换列表:",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(anchor="w")
        
        list_container = tk.Frame(self.root, bg=COLORS["surface"], relief="flat")
        list_container.pack(fill="x", padx=16, pady=(4, 0))
        
        self.file_listbox = tk.Listbox(
            list_container, height=5,
            font=("Consolas", 10),
            fg=COLORS["text"], bg=COLORS["surface"],
            selectbackground=COLORS["accent"],
            selectforeground="white",
            borderwidth=0, highlightthickness=0,
            activestyle="none"
        )
        self.file_listbox.pack(fill="x", padx=4, pady=4)
        
        # ── 选项行 ──
        opt_frame = tk.Frame(self.root, bg=COLORS["bg"])
        opt_frame.pack(fill="x", padx=16, pady=(10, 0))
        
        # 输出格式
        tk.Label(
            opt_frame, text="输出格式:",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(side="left")
        
        self.fmt_var = tk.StringVar(value="MP4")
        fmt_combo = ttk.Combobox(
            opt_frame, textvariable=self.fmt_var,
            values=list(SUPPORTED_FORMATS.keys()),
            state="readonly", width=8
        )
        fmt_combo.pack(side="left", padx=(4, 16))
        
        # 输出目录
        tk.Label(
            opt_frame, text="输出到:",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(side="left")
        
        self.output_var = tk.StringVar()
        output_entry = tk.Entry(
            opt_frame, textvariable=self.output_var,
            font=("Consolas", 10),
            fg=COLORS["text"], bg=COLORS["surface"],
            insertbackground=COLORS["text"],
            relief="flat", width=28
        )
        output_entry.pack(side="left", padx=(4, 4), ipady=3)
        
        tk.Button(
            opt_frame, text="浏览...",
            font=("Microsoft YaHei UI", 9),
            fg=COLORS["text"], bg=COLORS["accent"],
            activebackground=COLORS["accent2"],
            activeforeground="white",
            relief="flat", cursor="hand2",
            command=self._browse_output
        ).pack(side="left", padx=2)
        
        # ── 按钮行 ──
        btn_frame = tk.Frame(self.root, bg=COLORS["bg"])
        btn_frame.pack(fill="x", padx=16, pady=(10, 0))
        
        self.convert_btn = tk.Button(
            btn_frame, text="🚀 开始转换",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg="white", bg=COLORS["accent"],
            activebackground=COLORS["accent2"],
            activeforeground="white",
            relief="flat", cursor="hand2",
            padx=24, pady=6,
            command=self._start_convert
        )
        self.convert_btn.pack(side="left")
        
        self.clear_btn = tk.Button(
            btn_frame, text="清空列表",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["dim"], bg=COLORS["surface"],
            activebackground=COLORS["accent"],
            activeforeground="white",
            relief="flat", cursor="hand2",
            padx=12, pady=4,
            command=self._clear_list
        )
        self.clear_btn.pack(side="left", padx=(8, 0))
        
        self.rm_btn = tk.Button(
            btn_frame, text="移除选中",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["dim"], bg=COLORS["surface"],
            activebackground=COLORS["accent"],
            activeforeground="white",
            relief="flat", cursor="hand2",
            padx=12, pady=4,
            command=self._remove_selected
        )
        self.rm_btn.pack(side="left", padx=(4, 0))
        
        # ── 日志区 ──
        tk.Label(
            self.root, text="日志:",
            font=("Microsoft YaHei UI", 10),
            fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(anchor="w", padx=16, pady=(10, 0))
        
        log_container = tk.Frame(self.root, bg=COLORS["surface"])
        log_container.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        
        self.log_text = tk.Text(
            log_container, font=("Consolas", 9),
            fg=COLORS["text"], bg=COLORS["surface"],
            insertbackground=COLORS["text"],
            relief="flat", wrap="word",
            state="disabled"
        )
        scrollbar = tk.Scrollbar(log_container, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        
        # 日志颜色tag
        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("error", foreground=COLORS["error"])
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])
        self.log_text.tag_configure("info", foreground=COLORS["accent2"])
    
    def _check_ffmpeg(self):
        if self.ffmpeg_path:
            self.ffmpeg_label.config(text=f"✓ ffmpeg", fg=COLORS["success"])
            self.log(f"ffmpeg 已找到: {self.ffmpeg_path}", "success")
        else:
            self.ffmpeg_label.config(text="✗ ffmpeg 未找到", fg=COLORS["error"])
            self.log("未找到 ffmpeg! 请安装后重启本工具。", "error")
            self.log("安装方式: winget install Gyan.FFmpeg", "warning")
    
    def _log(self, msg, tag=None):
        """线程安全的日志输出"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def log(self, msg, tag=None):
        """从主线程或子线程安全写日志"""
        self.root.after(0, self._log, msg, tag)
    
    def _on_drop(self, event):
        """拖拽回调"""
        raw = event.data
        # Windows 下多个文件用空格分隔，路径可能有花括号
        paths = []
        if raw.startswith('{'):
            # 多文件模式
            import re
            paths = re.findall(r'\{([^}]+)\}', raw)
            if not paths:
                paths = [raw]
        else:
            paths = raw.split()
        
        self._add_paths(paths)
    
    def _browse_folders(self):
        """点击浏览选择文件夹"""
        dirs = filedialog.askdirectory(title="选择B站视频文件夹")
        if dirs:
            self._add_paths([dirs])
    
    def _add_paths(self, paths):
        """添加路径到列表"""
        found = scan_input_paths(paths)
        new_count = 0
        for d in found:
            if d not in self.task_queue:
                self.task_queue.append(d)
                title = get_video_title(d)
                self.file_listbox.insert("end", f"  {title}")
                self.file_listbox.itemconfig("end", fg=COLORS["text"])
                new_count += 1
                self.log(f"添加: {title}", "info")
        
        if new_count == 0 and found:
            self.log("所选目录已在列表中", "warning")
        elif new_count == 0:
            self.log("未在所选路径中找到m4s文件", "warning")
        
        # 自动设置输出目录为第一个输入的父目录
        if not self.output_var.get() and self.task_queue:
            self.output_var.set(os.path.dirname(self.task_queue[0]))
    
    def _browse_output(self):
        """选择输出目录"""
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_var.set(d)
    
    def _clear_list(self):
        """清空列表"""
        self.task_queue.clear()
        self.file_listbox.delete(0, "end")
        self.log("列表已清空", "info")
    
    def _remove_selected(self):
        """移除选中项"""
        sel = self.file_listbox.curselection()
        if not sel:
            return
        for i in reversed(sel):
            self.task_queue.pop(i)
            self.file_listbox.delete(i)
        self.log("已移除选中项", "info")
    
    def _start_convert(self):
        """开始转换"""
        if self.is_converting:
            return
        if not self.task_queue:
            messagebox.showwarning("提示", "请先添加要转换的文件夹")
            return
        if not self.ffmpeg_path:
            messagebox.showerror("错误", "未找到 ffmpeg，无法转换")
            return
        
        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showwarning("提示", "请选择输出目录")
            return
        
        os.makedirs(output_dir, exist_ok=True)
        
        self.is_converting = True
        self.convert_btn.config(state="disabled", text="转换中...")
        fmt = self.fmt_var.get()
        dirs = list(self.task_queue)
        
        def worker():
            success = 0
            fail = 0
            for d in dirs:
                try:
                    if convert_one(d, output_dir, fmt, self.ffmpeg_path, self.log):
                        success += 1
                    else:
                        fail += 1
                except Exception as e:
                    self.log(f"[ERROR] {get_video_title(d)}: {e}", "error")
                    fail += 1
            
            self.log(f"\n{'='*40}", "info")
            self.log(f"转换完成! 成功 {success} / 失败 {fail}", 
                     "success" if fail == 0 else "warning")
            
            self.is_converting = False
            self.root.after(0, lambda: self.convert_btn.config(
                state="normal", text="🚀 开始转换"))
        
        threading.Thread(target=worker, daemon=True).start()


# ─── 入口 ────────────────────────────────────────────────────────────

def main():
    root = TkinterDnD.Tk()
    app = BiliConverterApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
