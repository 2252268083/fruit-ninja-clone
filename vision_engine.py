import os
import time
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from logger import my_log
import config

_mp_py = mp_python
_mp_vis = mp_vision
_RunMode = mp_vision.RunningMode

_TASK_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), config.SETTINGS["paths"]["models_dir"], config.SETTINGS["paths"]["model_name"]),
    '/mnt/user-data/uploads/hand_landmarker.task',
]
_real_task_path = next((p for p in _TASK_DIRS if os.path.exists(p)), None)
if _real_task_path is None:
    #之前路径写死老是找不到文件 现在改自动搜索了
    raise FileNotFoundError("找不到模型文件 看下models文件夹里有没有hand_landmarker.task")

my_log.info(f"加载模型: {_real_task_path}")

def init_shoushi_det(max_hands: int) -> _mp_vis.HandLandmarker:
    opts = _mp_vis.HandLandmarkerOptions(
        base_options=_mp_py.BaseOptions(model_asset_path=_real_task_path),
        running_mode=_RunMode.VIDEO,
        num_hands=max_hands,
        #现场如果光线太暗或者背景太乱 检测容易断连 回头试试把这个阈值再调低点或者加个自适应
        min_hand_detection_confidence=0.25, 
        min_hand_presence_confidence=0.25,
        min_tracking_confidence=0.35,
    )
    return _mp_vis.HandLandmarker.create_from_options(opts)

#配置文件里读取最大手部数量 默认4个够了
max_shou = config.SETTINGS["ai"].get("max_hands", 4)
hand_det: _mp_vis.HandLandmarker = init_shoushi_det(max_shou)
start_ns: int = time.perf_counter_ns()

def get_now_ms() -> int:
    #mp要求的时间戳必须是严格递增的 不然直接崩溃
    return int((time.perf_counter_ns() - start_ns) // 1_000_000)

def detect_hands(rgb_frame: np.ndarray):
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    ts_ms = get_now_ms()
    
    #print(f"当前送入模型的时间戳: {ts_ms}")
    
    res = hand_det.detect_for_video(mp_img, ts_ms)
    
    all_lms = []
    hand_types = []
    
    if hasattr(res, 'hand_landmarks') and res.hand_landmarks:
        for lm in res.hand_landmarks:
            all_lms.append(lm)
            
    if hasattr(res, 'handedness') and res.handedness:
        for h_type in res.handedness:
            #记录一下是左手还是右手 虽然现在还没怎么用到
            hand_types.append(h_type[0].category_name)
            
    return all_lms, hand_types

def close_det():
    global hand_det
    hand_det.close()
