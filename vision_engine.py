import os
import time
import threading

import numpy as np

from logger import my_log  # 日志
import config

# ============================================================
# 【启动优化】mediapipe 延迟加载
# 原来 import mediapipe 写在模块顶层：打包环境下要卡 3~15 秒，
# 且创建 HandLandmarker 还要再等 1~2 秒，主线程窗口会直接假死。
# 现在改成"第一次真正用到时才加载"，窗口可以先把启动画面画出来。
# ============================================================
_mp = None        # mediapipe 模块本体
_mp_py = None     # mediapipe.tasks.python
_mp_vis = None    # mediapipe.tasks.python.vision
_RunMode = None   # RunningMode 枚举
_mp_ready = False
_mp_lock = threading.Lock()

hand_det = None   # HandLandmarker 检测器（同样是懒创建）
_det_lock = threading.Lock()

# 找模型文件：优先 exe 所在目录下的 models/，找不到再试服务器路径
_TASK_DIRS = [
    os.path.join(config.get_base_dir(), config.SETTINGS["paths"]["models_dir"],
                 config.SETTINGS["paths"]["model_name"]),  # 找配置
    '/mnt/user-data/uploads/hand_landmarker.task',          # 假如是服务器的路径
]
_real_task_path = next((p for p in _TASK_DIRS if os.path.exists(p)), None)

# 从配置里读最大手数（默认4个）
max_shou = config.SETTINGS["ai"].get("max_hands", 4)

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


def _load_mediapipe():
    """真正开始 import mediapipe（只在第一次调用时执行，之后直接返回）"""
    global _mp, _mp_py, _mp_vis, _RunMode, _mp_ready
    if _mp_ready:
        return
    with _mp_lock:
        if _mp_ready:
            return
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        _mp = mp
        _mp_py = mp_python
        _mp_vis = mp_vision
        _RunMode = mp_vision.RunningMode
        _mp_ready = True
        my_log.info("mediapipe 引擎加载完成")


def _create_detector(det_conf, pres_conf, track_conf, num_hands):
    """按给定参数创建一个 HandLandmarker"""
    _load_mediapipe()
    opts = _mp_vis.HandLandmarkerOptions(
        base_options=_mp_py.BaseOptions(model_asset_path=_real_task_path),  # 模型文件
        running_mode=_RunMode.VIDEO,  # 运行模式
        num_hands=num_hands,          # 最大识别手数
        # 如果光线太暗或者背景太乱 检测容易断连 后续把这个阈值再调低点 或者加个自适应！！！
        min_hand_detection_confidence=det_conf,
        min_hand_presence_confidence=pres_conf,
        min_tracking_confidence=track_conf,
    )
    return _mp_vis.HandLandmarker.create_from_options(opts)


def ensure_init(progress=None):
    """公开的预热接口：导入 mediapipe -> 创建检测器 -> 跑一帧空图预热。
    启动时由 main1.py 的后台加载线程调用，配合 progress(step) 回调刷新启动画面进度。
    step 含义：2=引擎加载完成 3=检测器创建完成 4=预热完成
    """
    global hand_det
    if _real_task_path is None:
        # 之前路径写死老是找不到文件 改自动搜索
        raise FileNotFoundError("找不到模型文件 models文件夹里有没有hand_landmarker.task")

    if hand_det is not None:
        return
    with _det_lock:
        if hand_det is not None:
            return
        _load_mediapipe()
        if progress:
            progress(2)

        my_log.info(f"加载模型: {_real_task_path}")
        # 按当前环境模式对应的阈值创建（切换模式时检测器可能还没建）
        cfg = BOOST_CONFIG if VISION_MODE == "BOOST" else NORMAL_CONFIG
        hand_det = _create_detector(cfg["det"], cfg["pres"], cfg["track"], max_shou)
        if progress:
            progress(3)

        # 预热：第一次推理会把底层初始化全部做完，之后就是纯推理
        dummy = np.zeros((240, 320, 3), dtype=np.uint8)
        detect_hands(dummy)
        if progress:
            progress(4)
        my_log.info("手势识别引擎预热完成")


def rebuild_detector(det_conf, pres_conf, track_conf):
    """按新阈值重建检测器（切换环境模式时用）"""
    global hand_det
    with _det_lock:
        try:
            if hand_det is not None:
                hand_det.close()
        except Exception:
            pass
        hand_det = _create_detector(det_conf, pres_conf, track_conf, max_shou)


def toggle_environment_mode():
    global VISION_MODE

    if VISION_MODE == "NORMAL":
        VISION_MODE = "BOOST"
        # 检测器还没创建的话就不用重建，等首次 detect 时会按 BOOST 配置创建
        if hand_det is not None:
            rebuild_detector(BOOST_CONFIG["det"], BOOST_CONFIG["pres"], BOOST_CONFIG["track"])
        my_log.info("环境增强模式开启")
    else:
        VISION_MODE = "NORMAL"
        if hand_det is not None:
            rebuild_detector(NORMAL_CONFIG["det"], NORMAL_CONFIG["pres"], NORMAL_CONFIG["track"])
        my_log.info("环境增强模式关闭")


def get_mode():
    return VISION_MODE


def get_now_ms() -> int:
    # mp要求的时间戳必须是严格递增的 不然直接崩溃
    return int((time.perf_counter_ns() - start_ns) // 1_000_000)


def detect_hands(rgb_frame: np.ndarray):
    # 检测器还没建就先建（懒加载兜底，兼容任何调用顺序）
    if hand_det is None:
        ensure_init()

    mp_img = _mp.Image(image_format=_mp.ImageFormat.SRGB, data=rgb_frame)
    ts_ms = get_now_ms()

    res = hand_det.detect_for_video(mp_img, ts_ms)

    all_lms = []    # 手的坐标
    hand_types = []  # 左手/右手

    if hasattr(res, 'hand_landmarks') and res.hand_landmarks:  # 检查有没有模型 是否检查到手
        for lm in res.hand_landmarks:
            all_lms.append(lm)

    if hasattr(res, 'handedness') and res.handedness:
        for h_type in res.handedness:
            # 记录一下是左手还是右手
            hand_types.append(h_type[0].category_name)

    return all_lms, hand_types


def close_det():  # 释放检测器资源
    global hand_det
    with _det_lock:
        if hand_det is not None:
            hand_det.close()
            hand_det = None
