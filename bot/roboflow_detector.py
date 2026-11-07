"""Roboflow Workflow Integration Module for Real-time Player Detection & Tracking.

Connects to the Roboflow Serverless Workflows API using workflow:
'MW2 Player Detection Test' (DouSITeTirWq8RBro5aW).

Extracts and maps:
- `trained_marked_players`: Target candidates matching the specified marker color.
- `trained_tracked_players`: ByteTrack tracked entities with temporal IDs.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

import config
from bot.vision import Detection

__all__ = ["RoboflowDetector", "RoboflowDetection"]


@dataclass(frozen=True, slots=True)
class RoboflowDetection(Detection):
    """Detection enriched with Roboflow classification and tracking metadata."""

    confidence: float = 1.0
    class_name: str = "player"
    tracker_id: int | None = None
    is_tracked: bool = False


class RoboflowDetector:
    """High-performance Roboflow Serverless Workflow detector with background streaming."""

    DEFAULT_WORKFLOW_ID = "DouSITeTirWq8RBro5aW"
    DEFAULT_WORKSPACE = "khalids-workspace-ouiss"

    def __init__(
        self,
        api_key: str | None = None,
        workspace: str = DEFAULT_WORKSPACE,
        workflow_id: str = DEFAULT_WORKFLOW_ID,
        marker_color: str = "#EB4341",
    ) -> None:
        self.api_key = api_key or os.environ.get("ROBOFLOW_API_KEY", "0pcN46PMA6awFdLklUAQ")
        self.workspace = workspace
        self.workflow_id = workflow_id
        self.marker_color = marker_color

        self.endpoint_url = (
            f"https://detect.roboflow.com/infer/workflows/{self.workspace}/{self.workflow_id}"
        )

        # Threading state for non-blocking 60 FPS pipelining
        self._lock = threading.Lock()
        self._latest_detections: list[RoboflowDetection] = []
        self._latest_tracked: list[RoboflowDetection] = []
        self._latest_latency_ms: float = 0.0
        self._is_busy = False
        self._active = True

    def run_inference(self, frame_bgr: np.ndarray) -> list[RoboflowDetection]:
        """Synchronously execute the Roboflow workflow on a single BGR frame."""
        h, w = frame_bgr.shape[:2]
        if w <= 0 or h <= 0:
            return []

        # Downscale slightly if frame is large to optimize upload payload and inference latency
        max_dim = 640
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            proc_w, proc_h = int(w * scale), int(h * scale)
            resized = cv2.resize(frame_bgr, (proc_w, proc_h), interpolation=cv2.INTER_AREA)
            scale_x = w / float(proc_w)
            scale_y = h / float(proc_h)
        else:
            resized = frame_bgr
            scale_x = 1.0
            scale_y = 1.0

        success, encoded = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not success:
            return []

        b64_str = base64.b64encode(encoded.tobytes()).decode("utf-8")

        payload = {
            "api_key": self.api_key,
            "inputs": {
                "image": {"type": "base64", "value": b64_str},
                "marker_color": self.marker_color,
            },
        }

        req = urllib.request.Request(
            self.endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []

        outputs = data.get("outputs", [{}])[0]
        marked_preds = outputs.get("trained_marked_players", {}).get("predictions", [])
        tracked_preds = outputs.get("trained_tracked_players", {}).get("predictions", [])

        # Parse tracked player IDs
        tracked_map: dict[str, int] = {}
        for tp in tracked_preds:
            tid = tp.get("tracker_id")
            if tid is not None:
                bx = tp.get("x", 0.0) * scale_x
                by = tp.get("y", 0.0) * scale_y
                tracked_map[f"{int(bx)}_{int(by)}"] = tid

        results: list[RoboflowDetection] = []
        for p in marked_preds:
            cx = float(p.get("x", 0.0)) * scale_x
            cy = float(p.get("y", 0.0)) * scale_y
            bw = float(p.get("width", 0.0)) * scale_x
            bh = float(p.get("height", 0.0)) * scale_y
            conf = float(p.get("confidence", 0.0))
            cls_name = str(p.get("class", "player"))
            radius = max(bw, bh) / 2.0
            area = bw * bh

            left = int(cx - bw / 2.0)
            top = int(cy - bh / 2.0)
            bbox = (left, top, int(bw), int(bh))

            tid = tracked_map.get(f"{int(cx)}_{int(cy)}")

            det = RoboflowDetection(
                x=cx,
                y=cy,
                radius=radius,
                area=area,
                bbox=bbox,
                confidence=conf,
                class_name=cls_name,
                tracker_id=tid,
                is_tracked=(tid is not None),
            )
            results.append(det)

        with self._lock:
            self._latest_detections = results
            self._latest_latency_ms = elapsed_ms

        return results

    def submit_frame_async(self, frame_bgr: np.ndarray) -> None:
        """Submit frame for non-blocking background inference to maintain smooth 60 FPS."""
        with self._lock:
            if self._is_busy or not self._active:
                return
            self._is_busy = True

        def _worker_task() -> None:
            try:
                self.run_inference(frame_bgr)
            finally:
                with self._lock:
                    self._is_busy = False

        threading.Thread(target=_worker_task, daemon=True, name="RoboflowAsyncThread").start()

    def get_latest_detections(self) -> list[RoboflowDetection]:
        """Return the most recently completed Roboflow detections."""
        with self._lock:
            return list(self._latest_detections)

    def get_latency_ms(self) -> float:
        """Return round-trip latency of the latest workflow execution."""
        with self._lock:
            return self._latest_latency_ms

    def select_best_target(
        self,
        center_x: float,
        center_y: float,
        fov_radius: float = 250.0,
        max_area: float = 8000.0,
    ) -> RoboflowDetection | None:
        """Select best candidate target closest to center reticle inside FOV."""
        candidates = self.get_latest_detections()
        if not candidates:
            return None

        best: RoboflowDetection | None = None
        best_score = float("inf")

        for c in candidates:
            if c.area > max_area or c.area <= 0:
                continue

            dist = np.hypot(c.x - center_x, c.y - center_y)
            if fov_radius > 0 and dist > fov_radius:
                continue

            # Prioritize tracked players with high confidence closest to center
            tracker_bonus = 0.7 if c.is_tracked else 1.0
            conf_weight = max(0.2, c.confidence or 0.5)
            score = (dist / conf_weight) * tracker_bonus

            if score < best_score:
                best_score = score
                best = c

        return best
