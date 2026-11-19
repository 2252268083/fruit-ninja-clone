import os
import warnings
import threading
import time

# 去掉警告看着烦
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['GLOG_minloglevel'] = '2'
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf.symbol_database')

import cv2
import numpy as np

from version import __version__  # 版本号统一在 version.py 里维护

from PIL import Image, ImageDraw
from fonts import get_ziti as _get_ziti   # 与 config 共用一份字体缓存

# ---------- 启动画面皮肤：渐变背景 + 步骤卡片 + 底部进度条（全中文，PIL 绘制） ----------
_SPLASH_W, _SPLASH_H = 1280, 720

def _splash_bg():
    # 深蓝紫 -> 近黑 的竖直渐变背景
    c_top = np.array([84, 26, 40], dtype=np.float64)   # BGR 深蓝紫
    c_bot = np.array([20, 10, 12], dtype=np.float64)   # BGR 近黑
    t = np.linspace(0.0, 1.0, _SPLASH_H)[:, None, None]
    bg = c_top[None, None, :] * (1 - t) + c_bot[None, None, :] * t
    return np.repeat(bg, _SPLASH_W, axis=1).astype(np.uint8)

def _render_loading(steps, step, err=None):
    """画启动画面：err=None 时画步骤卡片+进度条；有 err 时画错误信息"""
    pil = Image.fromarray(cv2.cvtColor(_splash_bg(), cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    d.rectangle([0, 0, _SPLASH_W, 6], fill=(255, 180, 60))  # 顶部金色饰条

    d.text((_SPLASH_W // 2, 130), "Swift-Fruit-Slice", font=_get_ziti(64),
           fill=(255, 214, 90), anchor="mm")
    d.text((_SPLASH_W // 2, 205), f"AI 体感切水果  v{__version__}", font=_get_ziti(26),
           fill=(160, 170, 190), anchor="mm")

    if err is not None:
        d.text((_SPLASH_W // 2, 300), "加载失败！", font=_get_ziti(44), fill=(255, 90, 90), anchor="mm")
        d.text((_SPLASH_W // 2, 380), str(err), font=_get_ziti(26), fill=(225, 230, 240), anchor="mm")
        d.text((_SPLASH_W // 2, 440), "详情见控制台窗口或 logs\\game.log，5 秒后自动退出",
               font=_get_ziti(24), fill=(150, 160, 180), anchor="mm")
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    d.text((_SPLASH_W // 2, 265), "正在加载……请稍候", font=_get_ziti(24),
           fill=(130, 140, 160), anchor="mm")

    # 步骤卡片：状态点（进行中的点会呼吸闪烁）+ 右侧状态文字
    x0, w = 420, 440
    for i, txt in enumerate(steps):
        y = 330 + i * 56
        done, cur = i < step, i == step
        d.rounded_rectangle([x0, y, x0 + w, y + 46], radius=14,
                            fill=(38, 42, 64) if (done or cur) else (24, 26, 40),
                            outline=(70, 76, 100), width=1)
        if done:
            dot_c, side_c, side_t = (90, 220, 120), (90, 220, 120), "完成"
        elif cur:
            on = int(time.time() * 2) % 2 == 0
            dot_c = (255, 200, 80) if on else (120, 100, 50)
            side_c, side_t = (255, 200, 80), "进行中"
        else:
            dot_c, side_c, side_t = (95, 100, 115), (110, 115, 130), "等待"
        d.ellipse([x0 + 20, y + 15, x0 + 36, y + 31], fill=dot_c)
        d.text((x0 + 56, y + 23), txt, font=_get_ziti(24),
               fill=(232, 236, 245) if (done or cur) else (115, 120, 135), anchor="lm")
        d.text((x0 + w - 24, y + 23), side_t, font=_get_ziti(20), fill=side_c, anchor="rm")

    # 底部总进度条
    pct = step / len(steps)
    bx0, bx1, by = 340, _SPLASH_W - 340, 660
    d.rounded_rectangle([bx0, by - 13, bx1, by + 13], radius=13, fill=(30, 33, 50))
    if pct > 0:
        d.rounded_rectangle([bx0, by - 13, bx0 + int((bx1 - bx0) * pct), by + 13],
                            radius=13, fill=(255, 180, 60))
    d.text((_SPLASH_W // 2, by - 40), f"总进度 {int(pct * 100)}%", font=_get_ziti(20),
           fill=(150, 160, 180), anchor="mm")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

def _render_message(title, lines, color=(255, 90, 90)):
    """同款皮肤的消息画面（摄像头打不开等提示用）"""
    pil = Image.fromarray(cv2.cvtColor(_splash_bg(), cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    d.rectangle([0, 0, _SPLASH_W, 6], fill=(255, 180, 60))
    d.text((_SPLASH_W // 2, 270), title, font=_get_ziti(48), fill=color, anchor="mm")
    for i, ln in enumerate(lines):
        d.text((_SPLASH_W // 2, 370 + i * 52), ln, font=_get_ziti(26),
               fill=(220, 225, 235) if i == 0 else (150, 160, 180), anchor="mm")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

def _show_splash(img):
    """启动/提示画面跟随窗口当前尺寸，窗口被拉伸后不再留黑边"""
    try:
        w, h = cv2.getWindowImageRect('Swift-Fruit-Slice')[2:4]
        if w > 0 and h > 0 and (w, h) != (img.shape[1], img.shape[0]):
            img = cv2.resize(img, (w, h))
    except Exception:
        pass
    cv2.imshow('Swift-Fruit-Slice', img)


def _window_closed():
    """用户点了游戏窗口右上角的 × 时返回 True（连续两次确认，避免窗口重建瞬间误判）"""
    def _visible():
        try:
            return cv2.getWindowProperty('Swift-Fruit-Slice', cv2.WND_PROP_VISIBLE)
        except cv2.error:
            return -1

    if _visible() >= 1:
        return False
    time.sleep(0.1)
    return _visible() < 1

def _open_camera(idx):
    # 打开摄像头：Windows 优先 DSHOW 后端，防止卡死5-10秒
    if os.name == 'nt':
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()   # 先释放失败的句柄，否则个别驱动会一直占着设备
            cap = cv2.VideoCapture(idx)
    else:
        cap = cv2.VideoCapture(idx)
    return cap


def _open_camera_auto(prefer_idx):
    """先用配置编号，打不开就扫描 0~3；返回 (cap, 实际编号)，全都失败时编号为 None"""
    cap = _open_camera(prefer_idx)
    if cap.isOpened():
        return cap, prefer_idx
    cap.release()
    for idx in range(4):
        if idx == prefer_idx:
            continue
        cap2 = _open_camera(idx)
        if cap2.isOpened():
            return cap2, idx
        cap2.release()
    return None, None


def _apply_camera_settings(cap):
    """统一设置摄像头参数（启动与断线重连共用）"""
    import config
    from logger import my_log
    cam_cfg = config.SETTINGS["camera"]
    want_w = cam_cfg.get("width", 1280)
    want_h = cam_cfg.get("height", 720)
    want_fps = cam_cfg.get("fps", 60)

    # 顺序：先格式(MJPG) → 再帧率 → 再分辨率，反了部分驱动会不生效
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FPS, want_fps)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, want_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, want_h)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # 只保留最新一帧，减少延迟

    real_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    real_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    real_fps = cap.get(cv2.CAP_PROP_FPS)
    my_log.info(f"摄像头参数已应用 分辨率 {real_w}x{real_h} 驱动标称 {real_fps:.0f}FPS")
    if want_fps >= 60 and real_fps < 45:
        my_log.warning(
            f"摄像头没跑到 {want_fps}FPS（驱动上报 {real_fps:.0f}FPS），"
            f"可把 settings.yaml 的 camera.width/height 调小，或确认该分辨率支持 MJPG 高帧率")


def _assign_hands(hands, last_hands, last_speed, max_shou, match_dist, pk):
    """把本帧检测到的手分配给刀光槽位。

    匹配阈值随上一帧手速自适应：30Hz 下快速横扫一帧能移动 300~400px，
    固定 256px 会被误判成"新手"导致刀光断开。
    返回 (assigned, unassigned, new_speed)：
      assigned   {本帧手序号: 槽位}
      unassigned [(本帧手序号, 可分配范围)]
      new_speed  更新后的各槽位手速
    """
    import config
    import math
    assigned = {}
    taken = set()
    unassigned = []
    new_speed = list(last_speed)

    for hi, h in enumerate(hands):
        if pk:
            half = max(1, max_shou // 2)
            choose_range = (range(0, half) if h['rx'] < config.WINDOW_WIDTH // 2
                            else range(half, max_shou))
        else:
            choose_range = range(max_shou)

        best_i, min_dist = -1, float('inf')
        for i in choose_range:
            if last_hands[i] is None or i in taken:
                continue
            dist = math.hypot(h['rx'] - last_hands[i][0], h['ry'] - last_hands[i][1])
            limit = min(int(config.WINDOW_WIDTH * 0.6),
                        match_dist + int(0.6 * last_speed[i]))
            if dist < limit and dist < min_dist:
                min_dist, best_i = dist, i

        if best_i != -1:
            assigned[hi] = best_i
            taken.add(best_i)
            new_speed[best_i] = min_dist
        else:
            unassigned.append((hi, choose_range))

    return assigned, unassigned, new_speed


# ======================== 采集线程 ========================
class CaptureThread(threading.Thread):
    """
    只负责读摄像头，始终保存"最新一帧"。
    以前读帧和推理在同一个循环里：推理 25~40ms/帧，摄像头却有 60fps，
    缓冲区会越堆越多，画面和手势就会越来越延迟（感觉像卡住了）。
    现在读帧独立成线程，每帧都取最新的，延迟恒定不累积。
    """
    def __init__(self, cap, display_width, display_height,
                 infer_width=None, mirror=True):
        super().__init__(daemon=True)
        import config
        self.cap = cap
        self.disp_w = display_width
        self.disp_h = display_height
        self.infer_w = infer_width or config.get_infer_width()
        self.mirror = mirror
        self.running = True
        self.fps = 0.0
        self.failed = False    # 摄像头断开/持续读不到画面时置 True，主线程据此提示退出

        self._lock = threading.Lock()
        self._display = None   # 显示用大图（给主线程画游戏）
        self._small = None     # 推理用小图（给视觉线程）
        self._seq = 0          # 帧序号，主线程据此判断有没有新画面

    def run(self):
        from logger import my_log
        count, t0 = 0, time.time()
        fail_since = None
        while self.running:
            try:
                ret, frame = self.cap.read()
            except Exception as e:
                ret, frame = False, None
                my_log.warning(f"读取摄像头画面异常：{e}")
            if not ret or frame is None:
                # 摄像头被拔掉/被其他程序占用：持续读不到就判定断开，避免永久停在最后一帧
                if fail_since is None:
                    fail_since = time.time()
                elif time.time() - fail_since > 3.0:
                    self.failed = True
                    self.running = False
                    my_log.error("摄像头连续 3 秒读不到画面，判定为设备断开")
                    break
                time.sleep(0.005)
                continue
            fail_since = None

            if self.mirror:
                frame = cv2.flip(frame, 1)

            display = frame
            if (frame.shape[1], frame.shape[0]) != (self.disp_w, self.disp_h):
                display = cv2.resize(frame, (self.disp_w, self.disp_h))
            # 推理图按原始宽高比缩放：1280x720 压成 320x240 会把手压扁，关键点精度下降
            infer_h = max(2, int(round(self.infer_w * frame.shape[0] / frame.shape[1])))
            small = cv2.resize(frame, (self.infer_w, infer_h))

            with self._lock:
                self._display = display
                self._small = small
                self._seq += 1

            count += 1
            if count % 30 == 0:   # 统计采集帧率
                now = time.time()
                self.fps = 30 / max(1e-6, now - t0)
                t0 = now

    def latest_display(self):
        """返回 (最新显示帧副本, 帧序号)；还没有帧时返回 (None, -1)"""
        with self._lock:
            if self._display is None:
                return None, -1
            return self._display.copy(), self._seq

    def latest_small(self):
        """返回 (最新推理帧副本, 帧序号)"""
        with self._lock:
            if self._small is None:
                return None, -1
            return self._small.copy(), self._seq

    def stop(self):
        self.running = False


# ======================== 视觉线程类 ========================
class VisionThread(threading.Thread):
    """
    独立线程：只做推理，永远取采集线程的"最新帧"，
    算得慢也只是识别帧率低，不会拖慢画面、不会积压延迟。
    """
    def __init__(self, capture, max_hands=4):
        super().__init__(daemon=True)
        self.capture = capture
        self.max_hands = max_hands
        self.running = True
        self.fps = 0.0
        self.failed = False    # 识别线程彻底不可用时置 True

        self._lock = threading.Lock()
        self._hands = []      # 归一化食指指尖坐标 [(x, y), ...]

    def run(self):
        from logger import my_log
        import vision_engine  # 延迟导入，避免阻塞主线程启动
        # 启动时 ensure_init() 已经预热过，这里不再重复预热

        last_seq = -1
        err_count = 0
        count, t0 = 0, time.time()
        while self.running:
            small, seq = self.capture.latest_small()
            # 没有新画面（或还没采到帧）就等一下，避免重复推理同一帧
            if small is None or seq == last_seq:
                time.sleep(0.002)
                continue
            last_seq = seq

            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            try:
                lm_list, _ = vision_engine.detect_hands(rgb)
            except Exception as e:
                # 单帧推理失败不算致命，连续失败才停止，避免线程静默死掉、游戏"看起来正常但切不动"
                err_count += 1
                if err_count <= 3:
                    my_log.warning(f"手势识别异常（第 {err_count} 次）：{e}")
                if err_count > 60:
                    self.failed = True
                    my_log.error("手势识别连续失败，已停止识别线程")
                    break
                time.sleep(0.05)
                continue
            err_count = 0

            # 只取食指指尖（索引8），归一化坐标 0~1
            hands = [(lm[8].x, lm[8].y) for lm in (lm_list or [])[:self.max_hands]]
            with self._lock:
                self._hands = hands

            count += 1
            if count % 20 == 0:   # 统计识别帧率
                now = time.time()
                self.fps = 20 / max(1e-6, now - t0)
                t0 = now

    def get_hands(self):
        with self._lock:
            return list(self._hands)

    def stop(self):
        self.running = False
# ============================================================


def main():
    # ---------------- 优化启动速度：立即显示窗口 + 后台并行加载 ----------------
    cv2.namedWindow('Swift-Fruit-Slice', cv2.WINDOW_NORMAL)

    # 后台加载线程的状态（子线程写、主线程读）
    state = {'step': 0, 'done': False, 'error': None, 'cap': None}
    step_texts = [
        '读取配置与素材...',              # 0: 配置+素材+音频
        '导入 AI 手势引擎...',            # 1: 导入 mediapipe
        '创建手势检测器...',              # 2: 创建检测器
        '预热模型...',                    # 3: 预热
        '打开摄像头...',                  # 4: 打开摄像头
    ]

    _show_splash(_render_loading(step_texts, 0))
    cv2.waitKey(1)

    def _set_step(s):
        state['step'] = s

    def load_worker():
        try:
            # 1. 配置+素材+pygame音频（config 模块级完成加载）
            import config
            import math_utils
            import vision_engine
            import game_core
            from ui_screens import xuanze_moshi_ui, xuanze_daoguang_ui, jiesuan_ui
            from logger import my_log
            my_log.info(f"游戏启动 v{__version__}")
            state['step'] = 1

            # 2~4. mediapipe 导入 / 创建检测器 / 预热（vision_engine 内部懒加载）
            vision_engine.ensure_init(progress=_set_step)

            # 5. 打开摄像头：先用配置编号，打不开就自动扫描 0~3，再不行也优雅退出不卡死
            my_cam = config.SETTINGS["camera"]["index"]
            cap, used_idx = _open_camera_auto(my_cam)
            if cap is not None and cap.isOpened():
                if used_idx != my_cam:
                    my_log.warning(f"配置的摄像头 index={my_cam} 打不开，已自动改用 index={used_idx}")
                my_log.info(f"摄像头已打开 index={used_idx}")
                _apply_camera_settings(cap)
            else:
                my_log.error(f"摄像头打不开：配置的 index={my_cam}，自动扫描 0~3 也没有可用设备")
            state['cap'] = cap
            state['step'] = 5

            if cap.isOpened():
                config.play_bgm()
            my_log.info("后台加载全部完成")
            state['done'] = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                from logger import my_log
                my_log.exception("启动加载失败")
            except Exception:
                pass
            state['error'] = e

    loader = threading.Thread(target=load_worker, daemon=True)
    loader.start()

    # 主线程只负责刷窗口画进度，全程不假死
    t_cam_start = None
    while not state['done'] and state['error'] is None:
        # 摄像头打开超过20秒还没返回 → 判定卡死，超时报错退出（后台线程是守护线程，不影响退出）
        if state['step'] >= 4:
            if t_cam_start is None:
                t_cam_start = time.time()
            elif time.time() - t_cam_start > 20:
                state['error'] = TimeoutError("摄像头打开超时（超过20秒），可能是编号无效或设备被占用")
                break
        _show_splash(_render_loading(step_texts, state['step']))
        cv2.waitKey(30)
        if _window_closed():   # 加载中点了右上角 ×，直接结束
            cv2.destroyAllWindows()
            return

    # 加载失败：中文提示错误原因，5秒后退出
    if state['error'] is not None:
        _show_splash(_render_loading(step_texts, state['step'], err=state['error']))
        for _ in range(50):   # 最多等 5 秒，按任意键或关闭窗口可提前退出
            if cv2.waitKey(100) != -1 or _window_closed():
                break
        cv2.destroyAllWindows()
        # 窗口版没有控制台，异常直接 raise 会静默消失；错误页已经展示过原因
        try:
            from logger import my_log
            my_log.error(f"启动加载失败：{state['error']}")
        except Exception:
            pass
        return

    # 后台线程已把慢库导入完毕，这里直接用（缓存命中，瞬间完成）
    import math
    from collections import deque
    import config
    import math_utils
    import vision_engine
    import game_core
    from logger import my_log
    from ui_screens import xuanze_moshi_ui, xuanze_daoguang_ui, jiesuan_ui

    cap = state['cap']
    if cap is None or not cap.isOpened():
        # 摄像头打不开：中文提示 + 等按键退出，绝不能进游戏循环"假死卡住"
        cam_idx = config.SETTINGS["camera"]["index"]
        my_log.error(f"摄像头不可用（配置 index={cam_idx}，已自动扫描 0~3），游戏退出")
        _show_splash(_render_message(
            "未检测到可用的摄像头！",
            [f"settings.yaml 里 camera.index 当前是 {cam_idx}",
             "请检查摄像头是否被占用 / 未接好",
             "处理完后按任意键退出，再重新打开游戏"],
        ))
        for _ in range(300):   # 最多等 30 秒，按任意键或关闭窗口可提前退出
            if cv2.waitKey(100) != -1 or _window_closed():
                break
        cv2.destroyAllWindows()
        return

    # 采集线程 / 视觉线程（游戏循环中创建，本局结束就停）
    capture_thread = None
    vision_thread = None

    while True:   # 游戏大循环（可以无限次重新开始）
        # --- 1. 选模式 ---
        moshi = xuanze_moshi_ui(cap)
        if moshi == 'quit':
            break

        # --- 2. 选刀光 ---
        my_dao = xuanze_daoguang_ui(cap)
        if my_dao == 'quit':
            break

        my_log.info(f"选了模式: {moshi}")
        my_log.info(f"选了刀光: {my_dao}")

        # --- 3. 开始玩 ---
        is_playing = True
        while is_playing:   # 单局循环（重玩会重新创建游戏）
            game = game_core.Game(selected_blade=my_dao, mode=moshi)

            max_shou = config.SETTINGS["ai"].get("max_hands", 4)
            dao_trails = [deque(maxlen=15) for _ in range(max_shou)]
            pinghua_qis = [math_utils.FingerSmoother(method='ewma', alpha=0.45, adaptive=True)
                           for _ in range(max_shou)]
            last_hands = [None] * max_shou
            last_speed = [0.0] * max_shou   # 各槽位上一帧手速，用于自适应匹配阈值

            # ============ 启动采集线程 + 视觉线程 ============
            ai_cfg = config.SETTINGS.get("ai", {})
            capture_thread = CaptureThread(
                cap,
                display_width=config.WINDOW_WIDTH,
                display_height=config.WINDOW_HEIGHT,
                infer_width=ai_cfg.get("infer_width", 320),    # 推理宽度（越小越快）
                mirror=config.SETTINGS["camera"].get("mirror", True),
            )
            capture_thread.start()
            vision_thread = VisionThread(capture_thread, max_hands=max_shou)
            vision_thread.start()
            # ====================================

            frame_counter = 0   # 仅用于日志节流
            step_acc = 0.0      # 固定步长累加器
            last_step_t = time.time()
            quit_to_menu = False
            game_err = None     # 设备类故障，退出后给用户中文提示
            t_play_start = time.time()

            while not game.game_over:
                # ---------- 设备故障检测：线程静默死掉时给出明确提示，而不是卡在最后一帧 ----------
                if capture_thread.failed:
                    game_err = "摄像头已断开（连续读不到画面）"
                    break
                if vision_thread.failed:
                    game_err = "手势识别已停止（AI 推理连续失败）"
                    break

                # ---------- 取最新画面 + 最新手势（两者独立，互不阻塞） ----------
                frame, _seq = capture_thread.latest_display()
                if frame is None:
                    # 摄像头打开了却一直没画面（虚拟摄像头/被占用），5 秒后判定异常
                    if time.time() - t_play_start > 5:
                        game_err = "摄像头没有画面输出（可能是设备被占用或驱动异常）"
                        break
                    time.sleep(0.002)
                    continue
                hands_norm = vision_thread.get_hands()

                # 将归一化坐标映射到屏幕坐标
                now_hands = []
                if hands_norm is not None:
                    for (x, y) in hands_norm:
                        rx = int(x * config.WINDOW_WIDTH)
                        ry = int(y * config.WINDOW_HEIGHT)
                        now_hands.append({'rx': rx, 'ry': ry})

                # ---------- 防串线算法：匹配阈值随手速自适应 ----------
                if not now_hands:   # 没检测到手
                    for i in range(max_shou):
                        pinghua_qis[i].reset()
                        last_hands[i] = None
                        last_speed[i] = 0.0
                else:
                    match_dist = max(120, int(config.WINDOW_WIDTH * 0.2))  # 基础匹配阈值随窗口宽度自适应
                    assigned, unassigned, last_speed = _assign_hands(
                        now_hands, last_hands, last_speed, max_shou, match_dist, moshi == 'pk')
                    used = set()

                    for hi, best_i in assigned.items():
                        h = now_hands[hi]
                        used.add(best_i)
                        sx, sy = pinghua_qis[best_i].smooth(h['rx'], h['ry'])
                        # 卡路里计算
                        if len(dao_trails[best_i]) > 0:
                            last_pt = dao_trails[best_i][-1]
                            dist = math.hypot(sx - last_pt[0], sy - last_pt[1])
                            game.add_distance(dist, best_i)
                        dao_trails[best_i].append((sx, sy))
                        last_hands[best_i] = (h['rx'], h['ry'])

                    # 未分配的手给空闲的刀光
                    for hi, choose_range in unassigned:
                        h = now_hands[hi]
                        for i in choose_range:
                            if i not in used:
                                used.add(i)
                                pinghua_qis[i].reset()  # 新手接管空闲刀光，避免刀光从上一只手的位置瞬移过来
                                sx, sy = pinghua_qis[i].smooth(h['rx'], h['ry'])
                                dao_trails[i].append((sx, sy))
                                last_hands[i] = (h['rx'], h['ry'])
                                last_speed[i] = 0.0
                                break

                    # 没出现的手清空轨迹
                    for i in range(max_shou):
                        if i not in used:
                            pinghua_qis[i].reset()
                            last_hands[i] = None
                            last_speed[i] = 0.0

                # 手离开时刀光逐渐消失
                for i in range(max_shou):
                    if last_hands[i] is None and len(dao_trails[i]) > 0:
                        for _ in range(min(4, len(dao_trails[i]))):
                            if dao_trails[i]:
                                dao_trails[i].popleft()

                # ---------- 画刀光 ----------
                pk_colors = [(0, 255, 255), (255, 0, 255)]
                pt_colors = [(0, 255, 0), (0, 255, 255), (255, 0, 255),
                             (255, 255, 0), (255, 100, 100)]
                for i in range(max_shou):
                    if moshi == 'pk':
                        t_color = pk_colors[0] if i < (max_shou // 2) else pk_colors[1]
                    else:
                        t_color = pt_colors[i % len(pt_colors)]

                    for j in range(1, len(dao_trails[i])):
                        if dao_trails[i][j-1] and dao_trails[i][j]:
                            cv2.line(frame, dao_trails[i][j-1], dao_trails[i][j], t_color, 3)

                # ---------- 固定 30Hz 步进：与显示帧率解耦，换电脑难度一致 ----------
                now_t = time.time()
                step_acc += min(now_t - last_step_t, 0.1)
                last_step_t = now_t
                steps = 0
                while step_acc >= 1.0 / 30 and steps < 3:
                    game.update(dao_trails)
                    game.check_collisions(dao_trails)
                    step_acc -= 1.0 / 30
                    steps += 1
                frame_counter += 1

                # 每约 300 帧记录一次真实帧率，方便排查"画面卡"
                if frame_counter % 300 == 0:
                    my_log.info(
                        f"运行帧率 采集 {capture_thread.fps:.0f}FPS / 识别 {vision_thread.fps:.0f}FPS")

                # ---------- 绘制游戏元素 ----------
                game.draw(frame)

                # 显示模式信息
                mode_name = "增强" if vision_engine.get_mode() == "BOOST" else "正常"
                config.add_cn_text(
                    f"视觉模式：{mode_name}（{vision_engine.get_delegate()}）",
                    (40, 90),
                    font_size=28,
                    color=(255, 255, 0),
                    bg_color=(0, 0, 0)
                )
                config.add_cn_text(
                    "按 C 键切换环境模式",
                    (40, 130),
                    font_size=22,
                    color=(200, 200, 200),
                    bg_color=None
                )
                config.add_cn_text(
                    f"采集 {capture_thread.fps:.0f} FPS ｜ 识别 {vision_thread.fps:.0f} FPS",
                    (40, 170),
                    font_size=22,
                    color=(150, 255, 150),
                    bg_color=(0, 0, 0)
                )
                config.flush_cn_texts(frame)

                cv2.imshow('Swift-Fruit-Slice', frame)

                # ---------- 按键处理 ----------
                key = cv2.waitKey(1) & 0xFF
                if key == ord('c'):
                    vision_engine.toggle_environment_mode()

                if _window_closed():   # 点右上角 × 关闭窗口，等价于返回菜单
                    quit_to_menu = True
                    break

                if key == ord('q'):
                    quit_to_menu = True
                    break

            # ---------- 游戏结束，停止视觉线程和采集线程 ----------
            if vision_thread is not None:
                vision_thread.stop()
                vision_thread.join(timeout=1.5)
                if vision_thread.is_alive():
                    my_log.warning("识别线程未在超时内退出（daemon 线程，不阻塞进程）")
                vision_thread = None
            if capture_thread is not None:
                capture_thread.stop()
                capture_thread.join(timeout=1.5)
                if capture_thread.is_alive():
                    # 驱动阻塞在 read() 里时线程自己退不出来，释放设备句柄促使它返回
                    my_log.warning("采集线程未在超时内退出，已强制释放摄像头")
                    try:
                        cap.release()
                    except Exception:
                        pass
                    capture_thread.join(timeout=1.0)
                    if game_err is None:
                        game_err = "摄像头驱动无响应，已强制释放设备"
                capture_thread = None

            # ---------- 设备故障：先尝试重连摄像头，成功则回主菜单，失败才退出 ----------
            if game_err:
                my_log.error(game_err)
                _show_splash(_render_message(
                    "设备异常，游戏已暂停",
                    [game_err,
                     "按任意键重新连接摄像头并返回主菜单",
                     "按 Esc 或关闭窗口退出游戏"],
                ))
                retry = True
                for _ in range(100):   # 最多等 10 秒，超时也尝试重连一次
                    k = cv2.waitKey(100) & 0xFF
                    if _window_closed() or k == 27:
                        retry = False
                        break
                    if k != 255:
                        break

                if retry:
                    my_log.info("尝试重新连接摄像头")
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap, used_idx = _open_camera_auto(config.SETTINGS["camera"]["index"])
                    if cap is not None and cap.isOpened():
                        _apply_camera_settings(cap)
                        my_log.info(f"摄像头已重连 index={used_idx}，返回主菜单")
                        quit_to_menu = True   # 复用"回主菜单"分支
                        break
                    my_log.error("摄像头重连失败")
                    _show_splash(_render_message(
                        "摄像头重连失败",
                        ["请检查设备是否被其他程序占用 / 是否插好",
                         "按任意键退出游戏"],
                    ))
                    for _ in range(100):
                        if cv2.waitKey(100) != -1 or _window_closed():
                            break

                is_playing = False
                break

            # ---------- 按 Q / 关闭窗口：回到主菜单（不同于结算里的"退出游戏"） ----------
            if quit_to_menu:
                my_log.info("返回主菜单")
                continue

            # ---------- 结算 ----------
            if is_playing:
                action = jiesuan_ui(cap, game)
                if action is None:
                    # 结算界面读不到画面：按设备故障处理，避免"建局→超时→再建局"死循环
                    my_log.error("结算界面读不到画面，退出对局")
                    is_playing = False
                    break
                if action == 'menu':
                    break
                elif action == 'quit':
                    is_playing = False

        # 如果用户选择退出，跳出外层大循环
        if not is_playing:
            break

    # ---------- 释放资源 ----------
    if vision_thread is not None:
        vision_thread.stop()
        vision_thread.join(timeout=1.5)
    if capture_thread is not None:
        capture_thread.stop()
        capture_thread.join(timeout=1.5)
    try:
        vision_engine.close_det()   # 真正释放检测器资源
    except Exception:
        pass
    try:
        cap.release()
    except Exception:
        pass
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()