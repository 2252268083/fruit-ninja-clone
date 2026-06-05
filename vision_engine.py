import os
import time
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from logger import logger
import config

# ============================================================
#  MediaPipe Hand Landmarker（新版 Tasks API，极端环境优化版）
# ============================================================
_mp_python  = mp_python
_mp_vision  = mp_vision
_RunningMode = mp_vision.RunningMode

_TASK_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), config.SETTINGS["paths"]["models_dir"], config.SETTINGS["paths"]["model_name"]),
    '/mnt/user-data/uploads/hand_landmarker.task',
]
_TASK_PATH = next((p for p in _TASK_CANDIDATES if os.path.exists(p)), None)
if _TASK_PATH is None:
    raise FileNotFoundError(
        "找不到 hand_landmarker.task！请将文件放到 models 目录下。"
    )
logger.info(f"使用 Hand Landmarker 模型: {_TASK_PATH}")

def _make_landmarker(num_hands: int) -> _mp_vision.HandLandmarker:
    opts = _mp_vision.HandLandmarkerOptions(
        base_options=_mp_python.BaseOptions(model_asset_path=_TASK_PATH),
        running_mode=_RunningMode.VIDEO,
        num_hands=num_hands,
        min_hand_detection_confidence=0.25,  # 降低阈值，适应暗光
        min_hand_presence_confidence=0.25,
        min_tracking_confidence=0.35,
    )
    return _mp_vision.HandLandmarker.create_from_options(opts)

# 使用配置文件中定义的最大手部数量
_max_hands = config.SETTINGS["ai"].get("max_hands", 4)
_landmarker: _mp_vision.HandLandmarker = _make_landmarker(_max_hands)
_landmarker_start_ns: int = time.perf_counter_ns()

def _now_ms() -> int:
    return int((time.perf_counter_ns() - _landmarker_start_ns) // 1_000_000)

# 【修复点】：确保参数名 rgb_frame 与内部使用的变量名一致
def detect_hands(rgb_frame: np.ndarray):
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    timestamp_ms = _now_ms()
    result = _landmarker.detect_for_video(mp_image, timestamp_ms)
    
    all_hands_landmarks = []
    hand_handedness = []
    
    if hasattr(result, 'hand_landmarks') and result.hand_landmarks:
        for landmarks in result.hand_landmarks:
            all_hands_landmarks.append(landmarks)
            
    if hasattr(result, 'handedness') and result.handedness:
        for handedness in result.handedness:
            hand_handedness.append(handedness[0].category_name)
            
    return all_hands_landmarks, hand_handedness

def close_landmarker():
    global _landmarker
    _landmarker.close()