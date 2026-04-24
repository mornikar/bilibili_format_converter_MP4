# 🎬 BiliM4S2MP4

B站 m4s 视频格式转换工具 — 拖拽即可将 B 站下载的 m4s 分离流合并为 MP4 等常见视频格式。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-informational)

## ✨ 功能特性

| 功能 | 说明 |
|:-----|:-----|
| 🖱 拖拽转换 | 直接拖文件夹到窗口，自动识别 m4s 视频+音频流 |
| 📂 点击选择 | 也可点击浏览按钮选择文件夹 |
| 🎬 多格式输出 | 支持 MP4 / MKV / WebM / TS / FLV |
| 📁 自定义输出 | 自由选择输出目录 |
| 🏷 自动命名 | 读取 `videoInfo.json` 用视频标题命名输出文件 |
| ✂️ 自动去头 | 自动去除 B 站 DASH 头（前 9 字节），合并音视频流 |
| 🔧 内嵌 ffmpeg | 打包版 EXE 内嵌 ffmpeg，双击即用，无需额外安装 |
| 📋 实时日志 | 转换进度和结果实时显示在日志面板 |
| 🧵 多线程 | 转换在后台线程运行，UI 不卡顿 |
| 🎨 暗色主题 | 护眼暗色 UI，紫色调主题 |

## 📸 截图

```
┌──────────────────────────────────────────────┐
│  🎬 BiliM4S2MP4  v1.0          ✓ ffmpeg     │
├──────────────────────────────────────────────┤
│                                              │
│         🖱 拖拽文件夹到此处                    │
│         或点击选择文件夹                       │
│                                              │
├──────────────────────────────────────────────┤
│  待转换列表:                                  │
│  ┌────────────────────────────────────────┐  │
│  │  全网最高动漫场景素材                    │  │
│  │  4K 60帧 二次元的静谧与唯美              │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  输出格式: [MP4 ▾]  输出到: [E:\output ▾]    │
│                                              │
│  [🚀 开始转换]  [清空列表]  [移除选中]        │
│                                              │
│  日志:                                       │
│  ┌────────────────────────────────────────┐  │
│  │  ffmpeg 已找到                         │  │
│  │  添加: 全网最高动漫场景素材              │  │
│  │  [OK] 全网最高动漫场景素材.mp4 (42.3MB) │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## 🚀 快速开始

### 方式一：直接使用 EXE（推荐）

1. 前往 [Releases](../../releases) 下载最新版 `BiliM4S2MP4.exe`
2. 双击运行即可，无需安装 Python 或 ffmpeg

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/mornikar/bilibili_format_converter_MP4.git
cd bilibili_format_converter_MP4

# 安装依赖
pip install tkinterdnd2

# 确保 ffmpeg 可用（以下任选一种）
# - 已安装 ffmpeg 并加入 PATH
# - 将 ffmpeg.exe 放到本项目目录下

# 运行
python BiliM4S2MP4.py
```

### 方式三：自行打包 EXE

```bash
pip install tkinterdnd2 pyinstaller

# 打包（内嵌 ffmpeg，需先将 ffmpeg.exe 放到项目目录）
pyinstaller --noconfirm --onefile --windowed \
  --icon icon.ico \
  --add-data "ffmpeg.exe;." \
  --add-data "<tkinterdnd2安装路径>;tkinterdnd2" \
  --name BiliM4S2MP4 \
  BiliM4S2MP4.py
```

## 📖 使用方法

1. **打开工具** — 双击 `BiliM4S2MP4.exe`
2. **添加视频** — 将 B 站下载的视频文件夹拖入窗口，或点击选择
3. **选择格式** — 在"输出格式"下拉框选择目标格式（默认 MP4）
4. **选择输出目录** — 点击"浏览..."选择保存位置
5. **开始转换** — 点击"🚀 开始转换"，等待完成

### 支持的目录结构

工具会自动识别以下 B 站下载目录结构：

```
BilibiliData/
├── 370785126/                    ← 单个视频目录
│   ├── 370785126_nb2-1-30080.m4s  ← 视频流
│   ├── 370785126_nb2-1-30280.m4s  ← 音频流
│   ├── videoInfo.json             ← 视频信息
│   └── ...
├── 198089870/
│   ├── 198089870-1-30080.m4s
│   ├── 198089870-1-30280.m4s
│   └── ...
```

你可以：
- 拖入**单个视频目录**（如 `370785126`）
- 拖入**包含多个视频的父目录**（如 `BilibiliData`），工具会自动扫描子目录

## 🔧 技术原理

B 站客户端下载的视频采用 DASH 格式，将视频流和音频流分离存储为 `.m4s` 文件，且每个 m4s 文件前有 9 字节的 DASH Header。本工具的处理流程：

1. **扫描目录** — 识别视频流（`*30080*.m4s`）和音频流（`*30280*.m4s`）
2. **去除 DASH 头** — 去掉 m4s 文件前 9 字节，恢复标准 ftyp 容器
3. **合并流** — 使用 ffmpeg 将视频流和音频流无损合并为 MP4 等格式

```
原始 m4s:  [9B DASH头] [ftyp...] [moov...] [mdat...]
                    ↓ 去头
标准 m4s:  [ftyp...] [moov...] [mdat...]
                    ↓ ffmpeg 合并
输出 MP4:  [视频流 + 音频流] → MP4/MKV/WebM/TS/FLV
```

## 📋 依赖

| 依赖 | 用途 | 必需 |
|:-----|:-----|:-----|
| Python 3.10+ | 运行环境 | 源码运行时需要 |
| tkinterdnd2 | 拖拽支持 | 源码运行时需要 |
| ffmpeg | 音视频合并 | 必需（EXE 版内嵌） |
| PyInstaller | 打包 EXE | 仅打包时需要 |

## ⚠️ 注意事项

- 本工具仅适用于 B 站客户端下载的 m4s 格式视频
- 转换过程为**无损合并**，不重新编码，速度快且不损失画质
- 输出文件名来自 `videoInfo.json` 中的视频标题，非法字符会自动过滤
- 如文件名冲突，会自动添加序号后缀（如 `标题_1.mp4`）
- 批量转换时按顺序执行，不支持并发（避免 IO 争抢）

## 📄 开源协议

MIT License — 可自由使用、修改和分发。

## 🙏 致谢

- [ffmpeg](https://ffmpeg.org/) — 强大的音视频处理工具
- [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) — Tkinter 拖拽支持
