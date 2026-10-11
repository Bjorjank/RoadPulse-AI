import hashlib
import json
import time
import warnings

import cv2
import numpy as np
import onnxruntime as ort
import supervision as sv

from roadpulse.config import MODEL

CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def preprocess(frame, size):
    h, w = frame.shape[:2]
    if h == 0 or w == 0:
        raise ValueError("Empty image")
    scale = min(size[0] / h, size[1] / w)
    canvas = np.full((*size, 3), 114, dtype=np.uint8)
    resized = cv2.resize(frame, (int(w * scale), int(h * scale)))
    canvas[: resized.shape[0], : resized.shape[1]] = resized
    return np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32), scale


def decode(raw, size):
    values = raw[0].copy()
    grids, strides = [], []
    for stride in (8, 16, 32):
        y, x = np.mgrid[: size[0] // stride, : size[1] // stride]
        grids.append(np.stack((x, y), axis=-1).reshape(-1, 2))
        strides.append(np.full((x.size, 1), stride))
    grid, stride = np.concatenate(grids), np.concatenate(strides)
    if values.shape != (len(grid), 85):
        raise ValueError(f"Unexpected YOLOX tensor {values.shape}; expected {(len(grid), 85)}")
    values[:, :2] = (values[:, :2] + grid) * stride
    values[:, 2:4] = np.exp(np.clip(values[:, 2:4], -20, 20)) * stride
    return values


def postprocess(raw, size, ratio, frame_shape, threshold=0.1):
    values = decode(raw, size)
    scores = values[:, 4, None] * values[:, 5:]
    # Retain the best COCO category, then filter to vehicles.
    categories = scores.argmax(axis=1)
    confidence = scores[np.arange(len(scores)), categories]
    boxes = np.column_stack((values[:, :2] - values[:, 2:4] / 2, values[:, :2] + values[:, 2:4] / 2)) / ratio
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, frame_shape[1])
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, frame_shape[0])
    # Class-agnostic NMS matches the official demo's default and avoids
    # separate car/truck tracks for overlapping predictions of one vehicle.
    indices = np.where(
        (confidence >= threshold)
        & np.isfinite(boxes).all(axis=1)
        & (boxes[:, 2] > boxes[:, 0])
        & (boxes[:, 3] > boxes[:, 1])
    )[0]
    if len(indices):
        xywh = boxes[indices].copy()
        xywh[:, 2:] -= xywh[:, :2]
        selected = cv2.dnn.NMSBoxes(xywh.tolist(), confidence[indices].tolist(), threshold, 0.45)
        idx = indices[np.asarray(selected, dtype=int).reshape(-1)]
        idx = idx[np.isin(categories[idx], list(CLASSES))]
    else:
        idx = np.array([], dtype=int)
    return sv.Detections(
        xyxy=boxes[idx].astype(np.float32),
        confidence=confidence[idx].astype(np.float32),
        class_id=categories[idx],
    )


class Detector:
    def __init__(self, path=MODEL):
        start = time.perf_counter()
        path = type(MODEL)(path)
        if not path.exists():
            raise FileNotFoundError("Model missing. Run: python scripts/prepare_model.py")
        manifest = json.loads(path.with_suffix(".json").read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
            raise ValueError("Model checksum mismatch; prepare model again")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.failures = []
        available = ort.get_available_providers()
        for provider in (
            "CUDAExecutionProvider",
            "CoreMLExecutionProvider",
            "DmlExecutionProvider",
            "CPUExecutionProvider",
        ):
            if provider not in available:
                continue
            try:
                if provider == "DmlExecutionProvider":
                    options.enable_mem_pattern = False
                    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                session = ort.InferenceSession(
                    str(path),
                    sess_options=options,
                    providers=[provider, "CPUExecutionProvider"]
                    if provider != "CPUExecutionProvider"
                    else [provider],
                )
                shape = session.get_inputs()[0].shape
                self.size = (int(shape[2]), int(shape[3]))
                session.run(None, {session.get_inputs()[0].name: np.zeros((1, 3, *self.size), np.float32)})
                self.session = session
                self.provider = session.get_providers()[0]
                break
            except Exception as exc:
                self.failures.append(f"{provider}: {exc}")
                warnings.warn(self.failures[-1], RuntimeWarning)
        else:
            raise RuntimeError("No working inference provider: " + str(self.failures))
        self.initialization_seconds = time.perf_counter() - start

    def infer(self, frame):
        tensor, ratio = preprocess(frame, self.size)
        start = time.perf_counter()
        raw = self.session.run(None, {self.session.get_inputs()[0].name: tensor})[0]
        latency = time.perf_counter() - start
        return postprocess(raw, self.size, ratio, frame.shape), latency
