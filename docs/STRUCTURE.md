# 目录结构说明（儿童识物版）

目标：
- 提供稳定的 GUI 与 CLI 入口，简化使用与维护。

## 目录结构与入口说明

本项目采用模块化组织，核心分为 GUI、检测核心、语音与设备工具等部分（交通灯/ROI 模块已移除）。

顶层关键文件：
- `main.py`：统一入口，根据参数路由到 儿童识物 GUI/检测 CLI
- `pyproject.toml`：依赖与工具配置（uv 源、ruff 规则等）

核心目录结构：

```
app/
  kids_gui.py       # PySide6 GUI：打开图片/摄像头识物与播报
  kids_core.py      # 儿童识物核心逻辑与绘制

detection/
  core.py           # YOLOConfig/YOLODetector，摄像头枚举、推理与保存
  api.py            # 门面导出（供 GUI/CLI 统一调用）
  cli.py            # 命令行入口（python -m detection.cli）

voice/
  tts.py            # 本地 TTS（pyttsx3）
  tts_queue.py      # 播报队列与去重
  announce.py       # 数量播报工具

cor_io/
  camera_utils.py   # DirectShow 设备名称（pygrabber）
  device_utils.py   # 设备列表（CUDA/MPS/CPU）

models/             # 放置模型（例如 yolo11n.pt）
results/            # 运行输出（帧与 txt）
docs/STRUCTURE.md   # 本说明
```

可运行入口：
- GUI：`python .\main.py` 或 `python -m app.kids_gui`
- 检测 CLI：`python .\main.py detect ...` 或 `python -m detection.cli ...`

命令行与环境变量约定：
- 所有检测参数既可通过命令行提供，也可用 `COR_` 前缀环境变量覆盖默认值（命令行优先；兼容旧前缀 `YV_`）。

输出组织：
- `results/frame_{id}_{ts}.jpg|.txt`：每帧可视化与 YOLO 标签（可选）

备注：
- Windows 下如需摄像头友好名称，请安装 `pygrabber`（DirectShow）。
- CUDA 使用请确保本机驱动与 `torch==2.5.1+cu121` 兼容；无需 CUDA 可改装 CPU 版 torch。
