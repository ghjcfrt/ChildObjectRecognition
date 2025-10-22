# ChildObjectRecognition（COR）—— 儿童识物（基于 YOLOv11）

> 说明：儿童识物版本已移除交通灯相关模块与原“高级设置”界面，仅保留简洁易用的儿童识物 GUI 与检测 CLI。

ChildObjectRecognition（简称 COR）是一个基于 Ultralytics YOLOv11 的实时目标检测小应用，提供图形界面与命令行两种使用方式，可将检测结果保存为图片与可选的 YOLO txt 标签。

## 简介

本项目支持：
- 实时检测摄像头/视频，保存可视化结果和可选 YOLO txt 标签到 `results/`
- Windows 下摄像头友好名称显示（DirectShow，可选依赖）


## 环境要求

- 操作系统：Windows 10/11 推荐（CLI 在 Linux/macOS 也可运行；MPS 需 macOS 支持）
- Python：3.11+
- GPU：可选；若使用 CUDA，请与 `torch==2.5.1+cu121` 和驱动版本匹配


## 安装

项目使用 `pyproject.toml` 与 [uv](https://docs.astral.sh/uv/) 管理依赖，推荐如下安装：

```powershell
# 安装 uv（若未安装）
python -m pip install -U uv

# 同步依赖（已配置 pytorch-cu121 源）
uv sync

# 验证
uv run python -V
```

说明：
- 若无需 CUDA，可改装 CPU 版 torch/torchvision（移除自定义索引，安装 CPU 轮子）。
- 只用 CLI 时，可跳过 GUI 依赖，但使用 `uv sync` 会按 `pyproject.toml` 全量安装。


## Windows 摄像头友好名称（DirectShow / pygrabber）

为在 Windows 下显示更友好的摄像头名称（而不是仅有的 `Camera n` 索引），项目提供 DirectShow 路径：

- DirectShow（pygrabber）：由 `cor_io/camera_utils.py` 枚举输入设备名称，依赖少、速度快。

说明：儿童识物版本已移除基于 WMI（pywin32）的摄像头信息查询路径。

安装与验证（PowerShell）：

```powershell
# 安装/同步依赖
uv sync

# 自检：打印 DirectShow 设备名（pygrabber）
uv run python -c "from cor_io import get_directshow_device_names as g; print(g())"
```

注意事项：
- 顺序与索引：DirectShow 的枚举顺序与 OpenCV 的摄像头索引通常一致，但不保证 100% 对齐；发生不一致时，以能成功打开的索引为准。
- 虚拟摄像头：可能出现重复/虚拟设备（如会议软件虚拟摄像头）；可在系统设备管理器中禁用无关设备以简化列表。



## 快速开始

项目提供一个统一入口 `main.py`，以及可直接运行的模块入口。

1) 启动 GUI（PySide6）

```powershell
# 方式 A：统一入口
uv run python .\main.py

# 方式 B：直接运行模块
uv run python -m app.kids_gui
```

2) 命令行实时检测（YOLO）

```powershell
# 方式 A：统一入口
uv run python .\main.py detect --model models\yolo\yolo11n.pt --source 0 --conf 0.5 --save-txt

# 方式 B：直接运行模块
uv run python -m detection.cli --model models\yolo\yolo11n.pt --source 0 --conf 0.5 --save-txt
```

常用参数：
- `--model` 模型权重（默认 `models/yolo/yolo11n.pt`）
- `--device` 设备：`auto`/`cuda`/`cuda:N`/`cpu`/`mps`
- `--source` 视频源：摄像头索引（如 0）或视频文件路径
- `--save-dir` 输出目录（默认 `results`）
- `--save-txt` 保存 YOLO txt 标签
- `--conf` 置信度阈值（0~1）
- `--img-size` 推理尺寸：`640` 或 `640,640`；留空表示以原始帧尺寸为目标
- `--window-name`/`--timestamp-fmt`/`--exit-key`/`--no-fps` 等

窗口聚焦时按 `q`（或 `--exit-key` 指定）退出。

（交通灯模式已移除）


## 环境变量覆盖（前缀 COR_，兼容旧前缀 YV_）

除命令行外，也可用环境变量覆盖默认值（命令行优先）：

优先读取新前缀 COR_，若未设置将回退读取旧前缀 YV_。对应关系：

- `COR_MODEL_PATH` → `--model`
- `COR_DEVICE` → `--device`
- `COR_SOURCE` → `--source`
- `COR_SAVE_DIR` → `--save-dir`
- `COR_SAVE_TXT` → `--save-txt`
- `COR_SELECT_CAMERA` → `--select-camera`
- `COR_MAX_CAM_INDEX` → `--max-cam`
- `COR_CONF` → `--conf`
- `COR_IMG_SIZE` → `--img-size`
- `COR_WINDOW_NAME` → `--window-name`
- `COR_TIMESTAMP_FMT` → `--timestamp-fmt`
- `COR_EXIT_KEY` → `--exit-key`
- `COR_SHOW_FPS` → `--no-fps`（布尔，命令行为“关闭”）
- `COR_QUIET_CV` → `--quiet-cv`
- `COR_CAM_FAIL_LIMIT` → `--cam-fail-limit`

摄像头枚举阶段日志抑制：`COR_SUPPRESS_ENUM_ERRORS=1`（默认开启；同样兼容旧变量 `YV_SUPPRESS_ENUM_ERRORS`）。

示例（PowerShell）：

```powershell
$env:COR_MODEL_PATH = ".\models\yolo\yolo11n.pt"
$env:COR_SOURCE = "0"
$env:COR_CONF = "0.45"
uv run python -m detection.cli --save-txt
```


## 目录结构（节选）

```
app/                # GUI 与核心
  kids_gui.py       # 儿童识物 GUI（PySide6）
  kids_core.py      # 儿童识物核心逻辑

detection/          # YOLO 检测核心与 CLI 封装
  core.py           # YOLOConfig/YOLODetector，摄像头枚举、保存、TTS 播报
  api.py            # 门面导出（供 GUI/CLI 复用）
  cli.py            # 命令行入口（python -m detection.cli）

voice/              # TTS 工具
  tts.py, tts_queue.py, announce.py

cor_io/             # 设备与摄像头名称工具
  camera_utils.py   # DirectShow 设备名称（pygrabber）
  camera_name.py    # WMI 存根（已移除实现）
  device_utils.py

models/             # 放置模型（例如 models/yolo/yolo11n.pt）
results/            # 运行输出
docs/STRUCTURE.md   # 目录说明
main.py             # 统一入口（gui/detect 路由）
pyproject.toml      # 依赖与工具配置（uv、ruff 等）
```


## 技术实现与算法逻辑

### 整体架构与数据流

- 统一入口 `main.py` 将命令路由至：
  - GUI：`app.kids_gui`（PySide6）
  - YOLO 检测 CLI：`detection.cli` → `detection.core`
- 检测核心：`detection/core.py`
  - 构造 `YOLOConfig`（支持命令行 + 环境变量 COR_ 前缀，命令行优先；兼容旧前缀 YV_）
  - `YOLODetector` 加载 Ultralytics YOLO 模型，读取视频帧并推理
  - 绘制结果、叠加 FPS、保存每帧与可选 YOLO txt；统计类别并做语音播报
- GUI：`app/kids_gui.py`
  - 简洁布局，支持打开图片与摄像头识物；可选自动播报中心物体与简介
  - 支持摄像头友好名（`cor_io.camera_utils`）、TTS 队列去抖


### YOLO 检测流水线（detection/core.py）

1) 设备选择：
  - `auto` 优先 `cuda`，再 `mps`，否则 `cpu`（`torch.cuda.is_available()` / `torch.backends.mps.is_available()`）
2) 输入尺寸：
  - 若 `--img-size` 未设，则以“原始帧尺寸”作为目标推理尺寸 `imgsz=[h,w]`，减少拉伸与比例失真
  - 否则按传入的 `640` 或 `640,640` 执行
3) YOLO txt 导出：
  - 将每帧的检测框转换为归一化 `x_center y_center width height` 格式保存为 `frame_*.txt`
4) FPS 显示：
  - 指数滑动平均平滑 FPS：新 FPS 用 0.1 权重更新，抑制抖动
5) OpenCV 摄像头：
  - Windows 优先 `cv2.CAP_DSHOW` 打开整型索引摄像头；读取失败计数超过阈值提前退出
  - 支持抑制 OpenCV 低层枚举错误日志（仅在“摄像头枚举阶段”临时降低日志级别）


<!-- 交通灯相关章节已移除：儿童识物版本不包含该模块 -->


### GUI 线程与语音集成（app/kids_gui.py, voice/*）

- 主线程纯 UI；推理在 GUI 定时器中循环调用检测器，避免卡顿
- TTS：`voice.tts_queue.TTSManager` 管理播报队列，提供去重与去“包含词”能力，避免重复与打断
- 摄像头友好名：`cor_io.camera_utils` 使用 DirectShow 获取友好名称；无依赖则回退为 `Camera n`


### 边界与可靠性措施

- 帧读取失败：累计连续失败数，超过阈值提前结束，避免长时间空转
- OpenCV 日志抑制：仅在“枚举摄像头”阶段降低日志级别，避免刷屏，但不影响运行阶段日志
- 文本导出：YOLO txt 使用统一归一化格式，便于再训练或标注复核
- FPS 平滑：指数滑动平均抑制抖动，读数更稳定
- Windows 打开摄像头：整型索引默认使用 `CAP_DSHOW`，兼容性更好


## 常见问题（FAQ）

1) CUDA/torch 报错？
- 使用 `--device cpu`；或安装与你驱动匹配的 CUDA 版 `torch/torchvision`。

2) 打不开摄像头或黑屏？
- 确认索引正确，尝试 0/1/2；关闭占用摄像头的软件；在 Windows 设备管理器检查设备。

3) GUI 启动失败（Qt 异常）？
- 确认安装 `PySide6`；无显示环境改用 CLI。

4) Windows 下无友好名称？
- 安装 `pygrabber`（DirectShow），否则显示 `Camera n`。

5) 交通灯颜色不稳定？
- 调整 `--conf` 与 `--img-size`，或使用手动 ROI；注意场景光照与距离。


## 致谢

- Ultralytics YOLO

如有问题或建议，欢迎提交 Issue。

