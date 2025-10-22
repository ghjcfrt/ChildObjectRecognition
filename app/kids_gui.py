"""儿童识物教学 GUI

功能
- 图片识物：打开图片 -> 识别 -> 在图上标注并播报
- 摄像头识物：选择摄像头 -> 开始 -> 实时识别并高亮中心物体，可自动播报当前中心物体

设计
- 大按钮与简洁布局，适合儿童与家长使用
- 仅暴露必要选项（摄像头选择、自动播报开关）
"""
from __future__ import annotations

import contextlib
import pathlib
import sys
import time
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QStatusBar,
                               QVBoxLayout, QWidget)

from app.kids_core import ChildConfig, ChildDetector
from detection.api import enumerate_cameras
from detection.coco_intros_cn import get_intro_by_id
from voice.tts_queue import TTSManager
from cor_io.camera_utils import get_directshow_device_names


def _bgr_to_qpix(img_bgr: np.ndarray) -> QPixmap:
    """将 BGR 图像转换为 QPixmap"""
    if img_bgr is None:
        return QPixmap()
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    bytes_per_line = 3 * w
    qim = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qim)


class KidsWindow(QWidget):
    def __init__(self) -> None:
        """儿童识物主窗口"""
        super().__init__()
        self.setWindowTitle("儿童识物 - YOLO 教学")
        self.resize(980, 700)

        # 检测器：固定图片尺寸为 640 以确保实时性
        model_path = str(pathlib.Path(__file__).resolve().parents[1] / "models" / "yolo" / "yolo11n.pt")
        self._cfg = ChildConfig(model_path=model_path, conf=0.5, img_size=[640, 640], device="auto")
        try:
            self._det = ChildDetector(self._cfg)
        except Exception as e:
            QMessageBox.critical(self, "模型加载失败", f"请检查模型文件是否存在：\n{model_path}\n\n错误：{e}")
            raise

        # 摄像头
        self._cap: Optional[cv2.VideoCapture] = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._last_center_label: Optional[str] = None
        self._last_speak_t: float = 0.0
        # 最近一次检测结果缓存
        self._last_dets: list = []
        self._last_center_idx: Optional[int] = None

        # TTS
        from voice import tts as _tts_mod
        self._tts = TTSManager(tts_module=_tts_mod, dup_window=1.2)
        self._tts.start()

        # 播报介绍期间禁用“播报介绍”按钮的轮询守护
        self._intro_btn_guard = QTimer(self)
        self._intro_btn_guard.setInterval(120)
        self._intro_btn_guard.timeout.connect(self._poll_intro_busy)

        # UI
        self._build_ui()
        self._refresh_cameras()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        """构建界面元素"""
        root = QVBoxLayout(self)
        self._status = QStatusBar()
        self._status.setSizeGripEnabled(False)
        root.addWidget(self._status)

        # 预览区
        self._preview = QLabel("在这里显示识别结果")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("QLabel { background: #202020; color: #C0C0C0; font-size: 16px; }")
        self._preview.setMinimumHeight(420)
        root.addWidget(self._preview, 1)

        # 按钮区
        row = QHBoxLayout()
        self._btn_open = QPushButton("打开图片")
        self._btn_open.setMinimumHeight(40)
        self._btn_open.clicked.connect(self._on_open_image)
        self._btn_recognize = QPushButton("识别并播报")
        self._btn_recognize.setMinimumHeight(40)
        self._btn_recognize.clicked.connect(self._on_recognize_image)

        cam_group = QGroupBox("摄像头识物")
        grid = QGridLayout(cam_group)
        self._cam_combo = QComboBox()
        self._btn_cam_refresh = QPushButton("刷新")
        self._btn_cam_refresh.clicked.connect(self._refresh_cameras)
        self._btn_cam_start = QPushButton("开始摄像头")
        self._btn_cam_start.clicked.connect(self._on_cam_start)
        self._btn_cam_stop = QPushButton("停止")
        self._btn_cam_stop.clicked.connect(self._on_cam_stop)
        self._auto_speak_chk = QCheckBox("自动播报中心物体")
        self._auto_speak_chk.setChecked(True)
        # 介绍播报控件
        self._auto_intro_chk = QCheckBox("自动播报介绍")
        self._auto_intro_chk.setChecked(False)
        self._btn_speak_intro = QPushButton("播报介绍")
        self._btn_speak_intro.clicked.connect(self._on_speak_intro)

        grid.addWidget(QLabel("摄像头:"), 0, 0)
        grid.addWidget(self._cam_combo, 0, 1)
        grid.addWidget(self._btn_cam_refresh, 0, 2)
        grid.addWidget(self._btn_cam_start, 1, 1)
        grid.addWidget(self._btn_cam_stop, 1, 2)
        grid.addWidget(self._auto_speak_chk, 2, 1, 1, 2)
        grid.addWidget(self._auto_intro_chk, 3, 1, 1, 2)
        grid.addWidget(self._btn_speak_intro, 4, 1, 1, 2)

        row.addWidget(self._btn_open, 1)
        row.addWidget(self._btn_recognize, 1)
        row.addWidget(cam_group, 2)
        root.addLayout(row)

    # ---------- 事件 ----------
    def _start_intro_guard(self) -> None:
        """在即将播报“介绍”时禁用按钮，直到播报结束再自动恢复"""
        if hasattr(self, "_btn_speak_intro") and self._btn_speak_intro is not None:
            self._btn_speak_intro.setEnabled(False)
        if not self._intro_btn_guard.isActive():
            self._intro_btn_guard.start()

    def _poll_intro_busy(self) -> None:
        """轮询检查 TTS 播报状态以恢复“播报介绍”按钮"""
        # 只要 TTS 仍在播报，就保持按钮禁用；结束后恢复并停止轮询
        busy = False
        try:
            busy = bool(self._tts and self._tts.is_busy())
        except Exception:
            busy = False
        if not busy:
            if hasattr(self, "_btn_speak_intro") and self._btn_speak_intro is not None:
                self._btn_speak_intro.setEnabled(True)
            self._intro_btn_guard.stop()
    def _refresh_cameras(self) -> None:
        """刷新摄像头列表"""
        # 若摄像头正在使用，避免刷新以免底层枚举触发驱动错误
        if self._cap is not None:
            return
        self._cam_combo.clear()
        try:
            cams = enumerate_cameras(8)
        except Exception:
            cams = []
        if not cams:
            self._cam_combo.addItem("无可用摄像头")
            self._cam_combo.setEnabled(False)
            return
        self._cam_combo.setEnabled(True)
        # 使用 DirectShow 设备名称（Windows）
        names: list[str] = []
        try:
            names = get_directshow_device_names()
        except Exception:
            names = []
        for i, cam_idx in enumerate(cams):
            label = f"Camera {cam_idx}"
            if i < len(names) and names[i].strip():
                label = f"{names[i].strip()} (# {cam_idx})"
            self._cam_combo.addItem(label, userData=cam_idx)

    def _on_open_image(self) -> None:
        """打开图片文件"""
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", filter="图像 (*.jpg *.png *.jpeg *.bmp);;所有文件 (*.*)")
        if not path:
            return
        self._last_image_path = path
        img = cv2.imread(path)
        if img is None:
            QMessageBox.warning(self, "读取失败", "无法读取该图片")
            return
        self._last_image_bgr = img
        self._preview.setPixmap(
            _bgr_to_qpix(img).scaled(
                self._preview.width(),
                self._preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._status.showMessage(f"已打开: {path}")

    def _on_recognize_image(self) -> None:
        """识别当前打开的图片并播报结果"""
        img = getattr(self, "_last_image_bgr", None)
        if img is None:
            QMessageBox.information(self, "提示", "请先打开一张图片")
            return
        dets, plotted = self._det.detect_frame(img)
        # 选择中心并高亮
        idx = self._det.pick_center_object(dets, plotted.shape)
        self._last_dets = dets
        self._last_center_idx = idx
        annotated = self._det.annotate_with_center(plotted, dets, idx)
        self._preview.setPixmap(
            _bgr_to_qpix(annotated).scaled(
                self._preview.width(),
                self._preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        # 播报：若有中心物体就播报该物体，否则播报前几类
        if idx is not None:
            label = dets[idx].label_cn
            self._tts.speak(f"这是{label}")
            if self._auto_intro_chk.isChecked():
                intro = get_intro_by_id(dets[idx].cls_id)
                if intro:
                    self._tts.speak(intro)
                    self._start_intro_guard()
        else:
            if dets:
                names = list(dict.fromkeys([d.label_cn for d in dets]))[:3]
                self._tts.speak("我找到了：" + "，".join(names))
            else:
                self._tts.speak("没有找到可以识别的物体")

    def _on_cam_start(self) -> None:
        """启动摄像头识物"""
        if self._cap is not None:
            return
        idx = self._cam_combo.currentData()
        if idx is None:
            QMessageBox.information(self, "提示", "没有可用摄像头")
            return
        # Windows 使用 DirectShow 优先
        if sys.platform.startswith("win"):
            cap = cv2.VideoCapture(int(idx), cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(int(idx))
        if not cap.isOpened():
            QMessageBox.critical(self, "错误", f"无法打开摄像头 {idx}")
            return
        self._cap = cap
        self._last_center_label = None
        self._last_speak_t = 0.0
        self._timer.start(33)
        self._status.showMessage("摄像头已启动，按‘停止’结束")
        # 摄像头开启时禁用刷新与设备选择
        with contextlib.suppress(Exception):
            self._btn_cam_refresh.setEnabled(False)
            self._cam_combo.setEnabled(False)

    def _on_cam_stop(self) -> None:
        """停止摄像头识物"""
        if self._cap is not None:
            try:
                self._timer.stop()
                self._cap.release()
            except Exception:
                pass
            self._cap = None
            self._status.showMessage("已停止摄像头")
            # 恢复刷新与设备选择
            with contextlib.suppress(Exception):
                self._btn_cam_refresh.setEnabled(True)
                self._cam_combo.setEnabled(True)

    def _on_speak_intro(self) -> None:
        """手动播报当前中心物体的简介"""
        dets = self._last_dets
        idx = self._last_center_idx if self._last_center_idx is not None else None
        if not dets:
            QMessageBox.information(self, "提示", "当前没有识别结果")
            return
        if idx is None or not (0 <= idx < len(dets)):
            # 若没有中心物体，就取第一个
            idx = 0
        intro = get_intro_by_id(dets[idx].cls_id)
        if intro:
            self._tts.speak(intro)
            self._start_intro_guard()
        else:
            QMessageBox.information(self, "提示", "该物体暂无简介")

    def _on_timer(self) -> None:
        """摄像头定时器回调：抓取一帧并处理显示与播报"""
        cap = self._cap
        if cap is None:
            return
        ok, frame = cap.read()
        if not ok or frame is None:
            return
        # 推理
        dets, plotted = self._det.detect_frame(frame)
        idx = self._det.pick_center_object(dets, plotted.shape)
        self._last_dets = dets
        self._last_center_idx = idx
        annotated = self._det.annotate_with_center(plotted, dets, idx)
        self._preview.setPixmap(
            _bgr_to_qpix(annotated).scaled(
                self._preview.width(),
                self._preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        # 自动播报（中心物体变化时 + 冷却 1.2s）
        if self._auto_speak_chk.isChecked() and idx is not None and 0 <= idx < len(dets):
            label = dets[idx].label_cn
            now = time.time()
            if label != self._last_center_label and (now - self._last_speak_t) > 1.2:
                self._tts.speak(f"这是{label}")
                if self._auto_intro_chk.isChecked():
                    intro = get_intro_by_id(dets[idx].cls_id)
                    if intro:
                        self._tts.speak(intro)
                        self._start_intro_guard()
                self._last_center_label = label
                self._last_speak_t = now

    def closeEvent(self, event) -> None:
        """窗口关闭事件处理：确保释放摄像头与停止 TTS"""
        try:
            self._on_cam_stop()
        finally:
            try:
                self._tts.stop()
            except Exception:
                pass
        return super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    win = KidsWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
