import os
import time
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from logger import my_log#日志
import config

_mp_py = mp_python
_mp_vis = mp_vision
_RunMode = mp_vision.RunningMode

_TASK_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), config.SETTINGS["paths"]["models_dir"], config.SETTINGS["paths"]["model_name"]),#找配置
    '/mnt/user-data/uploads/hand_landmarker.task',#假如是服务器的路径
]
_real_task_path = next((p for p in _TASK_DIRS if os.path.exists(p)), None)#检查是否有文件
if _real_task_path is None:
    #之前路径写死老是找不到文件 改自动搜索
    raise FileNotFoundError("找不到模型文件 models文件夹里有没有hand_landmarker.task")

my_log.info(f"加载模型: {_real_task_path}")

def init_shoushi_det(max_hands: int) -> _mp_vis.HandLandmarker:#标注最后返回检测器
    opts = _mp_vis.HandLandmarkerOptions(
        base_options=_mp_py.BaseOptions(model_asset_path=_real_task_path),#模型文件
        running_mode=_RunMode.VIDEO,#运行模式
        num_hands=max_hands,#最大识别手数
        #如果光线太暗或者背景太乱 检测容易断连 后续把这个阈值再调低点  或者加个自适应！！！
        min_hand_detection_confidence=0.25, #越低越容易检测到
        min_hand_presence_confidence=0.25,
        min_tracking_confidence=0.35,
    )
    return _mp_vis.HandLandmarker.create_from_options(opts)



def rebuild_detector(det_conf, pres_conf, track_conf):
    global hand_det

    try:
        hand_det.close()
    except:
        pass

    opts = _mp_vis.HandLandmarkerOptions(
        base_options=_mp_py.BaseOptions(
            model_asset_path=_real_task_path
        ),
        running_mode=_RunMode.VIDEO,
        num_hands=max_shou,

        min_hand_detection_confidence=det_conf,
        min_hand_presence_confidence=pres_conf,
        min_tracking_confidence=track_conf,
    )

    hand_det = _mp_vis.HandLandmarker.create_from_options(opts)


#配置文件里读取最大手部数量 默认4个
max_shou = config.SETTINGS["ai"].get("max_hands", 4)#默认值是4
hand_det: _mp_vis.HandLandmarker = init_shoushi_det(max_shou) #变量类型注解 hand_det=init_....
start_ns: int = time.perf_counter_ns()

# =====================
# 环境自适应配置
# =====================

VISION_MODE = "NORMAL"

NORMAL_CONFIG = {
    "det": 0.25,
    "pres": 0.25,
    "track": 0.35
}

BOOST_CONFIG = {
    "det": 0.15,
    "pres": 0.15,
    "track": 0.20
}

def toggle_environment_mode():
    global VISION_MODE

    if VISION_MODE == "NORMAL":

        rebuild_detector(
            BOOST_CONFIG["det"],
            BOOST_CONFIG["pres"],
            BOOST_CONFIG["track"]
        )

        VISION_MODE = "BOOST"

        my_log.info("环境增强模式开启")

    else:

        rebuild_detector(
            NORMAL_CONFIG["det"],
            NORMAL_CONFIG["pres"],
            NORMAL_CONFIG["track"]
        )

        VISION_MODE = "NORMAL"

        my_log.info("环境增强模式关闭")


def get_mode():
    return VISION_MODE

def get_now_ms() -> int:
    #mp要求的时间戳必须是严格递增的 不然直接崩溃
    return int((time.perf_counter_ns() - start_ns) // 1_000_000)

def detect_hands(rgb_frame: np.ndarray):
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    ts_ms = get_now_ms()
    
    #print(f"当前送入模型的时间戳: {ts_ms}")
    
    res = hand_det.detect_for_video(mp_img, ts_ms)
    
    all_lms = []#手的坐标
    hand_types = []#左手/右手
    
    if hasattr(res, 'hand_landmarks') and res.hand_landmarks:#检查有没有模型 是否检查到手
        for lm in res.hand_landmarks:
            all_lms.append(lm)
            
    if hasattr(res, 'handedness') and res.handedness:
        for h_type in res.handedness:
            #记录一下是左手还是右手 
            hand_types.append(h_type[0].category_name)
            
    return all_lms, hand_types

def close_det():#双臂手部识别器 释放资源
    global hand_det
    hand_det.close()
