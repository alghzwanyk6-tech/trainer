"""Local DirectML-Accelerated Neural Network Vision Detector.

Accelerates YOLO (YOLOv8 / YOLO11) models using Microsoft ONNX Runtime with the
DirectML Execution Provider (DirectX 12 D3D12 compute). Works vendor-agnostic
across AMD Radeon, NVIDIA GeForce, and Intel Iris/Arc graphics cards, with
automatic graceful fallback to multi-threaded CPU execution.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any, Final, Sequence

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None  # type: ignore[assignment]

import config
from bot.assistant import SmartDetection
from bot.vision import Detection, Detector

__all__ = ["LocalAIDetector", "RESOLUTION_PROFILES"]

RESOLUTION_PROFILES: Final[dict[str, tuple[int, int]]] = {
    "HIGH_SPEED": (320, 320),
    "STANDARD": (640, 640),
    "HIGH_FIDELITY": (1280, 1280),
}


class LocalAIDetector(Detector):
    """Deep learning target detector accelerated by DirectML (DirectX 12).

    Parses YOLO output tensors, applies Non-Maximum Suppression (NMS), and
    implements head-bias vertical offset interpolation for instant target lock.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        conf_threshold: float = 0.45,
        iou_threshold: float = 0.45,
        head_bias_percent: float = 0.70,
        input_size: tuple[int, int] = (640, 640),
        device: str = "auto",
    ) -> None:
        self.conf_threshold = float(conf_threshold)
        self.iou_threshold = float(iou_threshold)
        self.head_bias_percent = float(head_bias_percent)
        self.input_size = input_size
        self.device = device
        self.session: Any | None = None
        self.active_provider: str = "None"
        self.input_name: str = "images"
        self.output_names: list[str] = []
        self.last_elapsed_ms: float = 0.0
        self._loaded_path: str = ""

        if model_path:
            self.load_model(model_path)

    def set_resolution_profile(self, profile: str) -> None:
        """Switch dynamic input resolution profile ('STANDARD', 'HIGH_SPEED', 'HIGH_FIDELITY')."""
        key = profile.strip().upper().replace("-", "_")
        if key in RESOLUTION_PROFILES:
            self.input_size = RESOLUTION_PROFILES[key]

    @property
    def is_directml_active(self) -> bool:
        """True if the inference session is running on DirectX 12 DirectML."""
        return "DmlExecutionProvider" in self.active_provider

    def load_model(self, model_path: str | Path) -> bool:
        """Load an ONNX model file and initialize the DirectML inference session."""
        if ort is None:
            return False

        path_obj = Path(model_path).resolve()
        if not path_obj.exists() or not path_obj.is_file():
            return False

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.enable_mem_pattern = True

        available = ort.get_available_providers()
        providers: list[Any] = []
        if self.device != "cpu" and "DmlExecutionProvider" in available:
            providers.append(("DmlExecutionProvider", {"device_id": 0}))
        providers.append("CPUExecutionProvider")

        try:
            self.session = ort.InferenceSession(
                str(path_obj),
                sess_options=sess_options,
                providers=providers,
            )
            current_providers = self.session.get_providers()
            self.active_provider = current_providers[0] if current_providers else "CPUExecutionProvider"

            inputs = self.session.get_inputs()
            if inputs:
                self.input_name = inputs[0].name
                # Extract input dimensions if fixed
                shape = inputs[0].shape
                if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                    self.input_size = (shape[3], shape[2])  # (W, H)

            self.output_names = [o.name for o in self.session.get_outputs()]
            self._loaded_path = str(path_obj)
            return True
        except Exception:
            self.session = None
            self.active_provider = "None"
            self._loaded_path = ""
            return False

    def configure(self, cfg: config.Config) -> None:
        """Apply live configuration settings."""
        self.conf_threshold = float(getattr(cfg, "local_ai_confidence", 0.45))
        self.head_bias_percent = float(getattr(cfg, "head_bias_percent", 0.70))
        model_path = getattr(cfg, "local_ai_model_path", "")
        if not model_path:
            default_p = Path("models/yolov8n.onnx")
            if default_p.is_file():
                model_path = str(default_p)
        if model_path and (self.session is None or self._loaded_path != str(model_path)):
            self.load_model(model_path)

    def preprocess(
        self,
        frame_bgr: np.ndarray,
    ) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Preprocess an input BGR frame into a normalized planar CHW tensor.

        Returns:
            (tensor, scale_factor, (pad_x, pad_y))
        """
        h, w = frame_bgr.shape[:2]
        target_w, target_h = self.input_size

        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2

        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        # BGR -> RGB, Normalize [0.0, 1.0], Planar HWC -> CHW, Add batch dimension
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        tensor = rgb.astype(np.float32) * (1.0 / 255.0)
        tensor = np.ascontiguousarray(np.transpose(tensor, (2, 0, 1))[np.newaxis, ...])
        return tensor, scale, (pad_x, pad_y)

    def postprocess(
        self,
        outputs: list[np.ndarray],
        orig_shape: tuple[int, int],
        scale: float,
        pad: tuple[int, int],
    ) -> list[SmartDetection]:
        """Decode YOLO bounding box predictions and apply NMS."""
        if not outputs or len(outputs) == 0:
            return []

        out = outputs[0]
        # YOLOv8/11 format: shape [1, 4 + classes, anchors] -> transpose to [anchors, 4 + classes]
        if out.ndim == 3 and out.shape[1] < out.shape[2]:
            out = np.transpose(out[0], (1, 0))
        elif out.ndim == 3:
            out = out[0]

        num_anchors, total_channels = out.shape
        num_classes = total_channels - 4
        if num_classes <= 0:
            return []

        boxes_xywh = out[:, :4]
        class_scores = out[:, 4:]

        max_scores = np.max(class_scores, axis=1)
        class_ids = np.argmax(class_scores, axis=1)

        # For COCO models (num_classes >= 80), class 0 is person
        if num_classes >= 80:
            mask = (max_scores >= self.conf_threshold) & (class_ids == 0)
        else:
            mask = max_scores >= self.conf_threshold

        if not np.any(mask):
            return []

        filt_boxes = boxes_xywh[mask]
        filt_scores = max_scores[mask]
        filt_classes = class_ids[mask]

        pad_x, pad_y = pad
        orig_h, orig_w = orig_shape

        boxes_for_nms: list[list[int]] = []
        confidences_for_nms: list[float] = []
        parsed_candidates: list[dict[str, Any]] = []

        for i in range(len(filt_scores)):
            cx, cy, w, h = filt_boxes[i]
            # Un-pad and scale back to original frame coordinates
            x1 = (cx - w / 2.0 - pad_x) / scale
            y1 = (cy - h / 2.0 - pad_y) / scale
            x2 = (cx + w / 2.0 - pad_x) / scale
            y2 = (cy + h / 2.0 - pad_y) / scale

            # Clamp to frame
            x1 = max(0.0, min(float(orig_w), x1))
            y1 = max(0.0, min(float(orig_h), y1))
            x2 = max(0.0, min(float(orig_w), x2))
            y2 = max(0.0, min(float(orig_h), y2))
            bw = x2 - x1
            bh = y2 - y1

            if bw <= 4.0 or bh <= 4.0:
                continue

            score = float(filt_scores[i])
            cls_id = int(filt_classes[i])

            boxes_for_nms.append([int(x1), int(y1), int(bw), int(bh)])
            confidences_for_nms.append(score)
            parsed_candidates.append({
                "bbox": (int(x1), int(y1), int(bw), int(bh)),
                "conf": score,
                "cls_id": cls_id,
                "w": bw,
                "h": bh,
                "cx": x1 + bw / 2.0,
                "cy": y1 + bh / 2.0,
            })

        if not boxes_for_nms:
            return []

        indices = cv2.dnn.NMSBoxes(
            boxes_for_nms,
            confidences_for_nms,
            self.conf_threshold,
            self.iou_threshold,
        )

        detections: list[SmartDetection] = []
        if len(indices) == 0:
            return []

        flat_indices = indices.flatten() if hasattr(indices, "flatten") else [i[0] for i in indices]
        for idx in flat_indices:
            cand = parsed_candidates[idx]
            cls_id = cand["cls_id"]
            is_head = (cls_id == 1)

            # Apply head-bias offset for body detections (class 0)
            target_x = cand["cx"]
            if is_head:
                target_y = cand["cy"]
            else:
                # Vertical interpolation towards head: Body_cy - (Body_h * 0.35 * head_bias)
                target_y = cand["cy"] - (cand["h"] * 0.35 * self.head_bias_percent)

            radius = max(4.0, min(cand["w"], cand["h"]) / 2.0)
            area = float(cand["w"] * cand["h"])

            det = SmartDetection(
                x=float(target_x),
                y=float(target_y),
                radius=float(radius),
                area=float(area),
                bbox=cand["bbox"],
                confidence=float(cand["conf"]),
                circularity=0.85 if is_head else 0.50,
                occluded=False,
                motion_ema=5.0,
                is_static_prop=False,
            )
            detections.append(det)

        return detections

    def detect(self, frame_bgr: np.ndarray) -> SmartDetection | None:
        """Execute DirectML neural inference and return the optimal target candidate."""
        if self.session is None or frame_bgr is None:
            return None

        started = time.perf_counter()
        h, w = frame_bgr.shape[:2]
        center_x, center_y = w / 2.0, h / 2.0

        tensor, scale, pad = self.preprocess(frame_bgr)
        try:
            outputs = self.session.run(self.output_names, {self.input_name: tensor})
            candidates = self.postprocess(outputs, (h, w), scale, pad)
        except Exception:
            self.last_elapsed_ms = (time.perf_counter() - started) * 1000.0
            return None

        self.last_elapsed_ms = (time.perf_counter() - started) * 1000.0
        if not candidates:
            return None

        # Prioritize candidate closest to center crosshairs with highest confidence
        best_cand: SmartDetection | None = None
        best_score = -1.0

        for cand in candidates:
            dist = math.hypot(cand.x - center_x, cand.y - center_y)
            proximity = 1.0 / (1.0 + (dist / 30.0) ** 2.0)
            score = proximity * 0.75 + cand.confidence * 0.25
            if score > best_score:
                best_score = score
                best_cand = cand

        return best_cand
