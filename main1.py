import os
import warnings
import threading
import queue
import time

# 去掉警告看着烦
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['GLOG_minloglevel'] = '2'
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf.symbol_database')

import cv2
import numpy as np

from version import __version__  # 版本号统一在 version.py 里维护

from PIL import Image, ImageDraw, ImageFont

# ---------- 启动画面皮肤：渐变背景 + 步骤卡片 + 底部进度条（全中文，PIL 绘制） ----------
_SPLASH_W, _SPLASH_H = 1280, 720

_ziti_cache = {}

def _get_ziti(size):
    if size in _ziti_cache:
        return _ziti_cache[size]
    for p in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
              "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _ziti_cache[size] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _ziti_cache[size] = f
    return f

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

def _open_camera(idx):
    # 打开摄像头：Windows 优先 DSHOW 后端，防止卡死5-10秒
    if os.name == 'nt':
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)
    else:
        cap = cv2.VideoCapture(idx)
    return cap


# ======================== 视觉线程类 ========================
class VisionThread(threading.Thread):
    """
    独立线程：不断读取摄像头、缩放、推理，返回归一化手部坐标和显示帧。
    """
    def __init__(self, cap, result_queue, infer_width=320, infer_height=240,
                 display_width=1280, display_height=720, max_hands=4, mirror=True):
        super().__init__()
        self.cap = cap
        self.result_queue = result_queue          # 存放 (hands_norm, frame_display)
        self.infer_w = infer_width
        self.infer_h = infer_height
        self.disp_w = display_width
        self.disp_h = display_height
        self.max_hands = max_hands
        self.mirror = mirror
        self.running = True

    def run(self):
        import vision_engine  # 延迟导入，避免阻塞主线程启动
        # 预热模型（第一次调用会加载，耗时但只一次）
        dummy = np.zeros((self.infer_h, self.infer_w, 3), dtype=np.uint8)
        vision_engine.detect_hands(dummy)

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # 镜像翻转（与原来保持一致）
            if self.mirror:
                frame = cv2.flip(frame, 1)

            # 1. 推理用的缩小帧
            infer_frame = cv2.resize(frame, (self.infer_w, self.infer_h))
            rgb = cv2.cvtColor(infer_frame, cv2.COLOR_BGR2RGB)

            # 2. 执行推理（在子线程，不阻塞主界面）
            lm_list, _ = vision_engine.detect_hands(rgb)

            # 3. 提取归一化坐标（只取食指指尖，索引8）
            hands_norm = []
            if lm_list:
                for lm in lm_list[:self.max_hands]:
                    x = lm[8].x   # 0~1
                    y = lm[8].y
                    hands_norm.append((x, y))

            # 4. 生成显示用的帧（缩放至窗口大小）
            display_frame = cv2.resize(frame, (self.disp_w, self.disp_h))

            # 5. 放入队列（只保留最新数据，丢弃旧数据）
            if self.result_queue.qsize() > 0:
                try:
                    self.result_queue.get_nowait()
                except queue.Empty:
                    pass
            self.result_queue.put((hands_norm, display_frame))

            # 避免忙等吃满CPU
            time.sleep(0.001)

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

    cv2.imshow('Swift-Fruit-Slice', _render_loading(step_texts, 0))
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
            cap = _open_camera(my_cam)
            used_idx = my_cam
            if not cap.isOpened():
                for idx in range(4):
                    if idx == my_cam:
                        continue
                    cap2 = _open_camera(idx)
                    if cap2.isOpened():
                        cap = cap2
                        used_idx = idx
                        my_log.warning(f"配置的摄像头 index={my_cam} 打不开，已自动改用 index={idx}")
                        break
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FPS, 60)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.SETTINGS["camera"]["width"])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.SETTINGS["camera"]["height"])
                my_log.info(f"摄像头打开成功 index={used_idx}")
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
        cv2.imshow('Swift-Fruit-Slice', _render_loading(step_texts, state['step']))
        cv2.waitKey(30)

    # 加载失败：中文提示错误原因，5秒后退出
    if state['error'] is not None:
        cv2.imshow('Swift-Fruit-Slice', _render_loading(step_texts, state['step'], err=state['error']))
        cv2.waitKey(5000)
        cv2.destroyAllWindows()
        raise state['error']

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
        cv2.imshow('Swift-Fruit-Slice', _render_message(
            "未检测到可用的摄像头！",
            [f"settings.yaml 里 camera.index 当前是 {cam_idx}",
             "请检查摄像头是否被占用 / 未接好",
             "处理完后按任意键退出，再重新打开游戏"],
        ))
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return

    # 视觉线程的队列（线程安全，只存最新数据）
    result_queue = queue.Queue(maxsize=1)
    vision_thread = None   # 游戏循环中启动

    while True:   # 游戏大循环（可以无限次重新开始）
        # --- 1. 选模式 ---
        moshi = xuanze_moshi_ui(cap)
        if moshi == 'quit':
            break

        # --- 2. 选刀光 ---
        my_dao = xuanze_daoguang_ui(cap)

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

            # ============ 启动视觉线程 ============
            vision_thread = VisionThread(
                cap,
                result_queue,
                infer_width=320,          # 推理分辨率，可调（越小越快）
                infer_height=240,
                display_width=config.WINDOW_WIDTH,
                display_height=config.WINDOW_HEIGHT,
                max_hands=max_shou,
                mirror=config.SETTINGS["camera"].get("mirror", True)
            )
            vision_thread.start()
            # ====================================

            frame_counter = 0   # 用于隔帧更新物理（保持手感）

            while not game.game_over:
                # ---------- 从视觉线程获取最新数据 ----------
                hands_norm = None
                frame = None
                try:
                    hands_norm, frame = result_queue.get_nowait()
                except queue.Empty:
                    # 如果队列为空（极少发生），使用上一帧（但为了安全，我们让帧保持上一次的）
                    # 这里为了简化，如果拿不到数据，就跳过这一帧的绘制（但会闪屏）
                    # 更好的做法：缓存上一次的 frame，但通常在子线程持续运行下不会空。
                    # 所以我们如果拿不到，就继续使用上一帧（但需要外部变量缓存）
                    # 为了简单，我们直接 continue 等待下一帧（可能造成短暂卡顿，但几乎不会发生）
                    continue

                # 将归一化坐标映射到屏幕坐标
                now_hands = []
                if hands_norm is not None:
                    for (x, y) in hands_norm:
                        rx = int(x * config.WINDOW_WIDTH)
                        ry = int(y * config.WINDOW_HEIGHT)
                        now_hands.append({'rx': rx, 'ry': ry})

                # ---------- 防串线算法（与原来完全一致） ----------
                if not now_hands:   # 没检测到手
                    for i in range(max_shou):
                        pinghua_qis[i].reset()
                        last_hands[i] = None
                else:
                    used = set()
                    assigned = {}
                    unassigned = []

                    for h in now_hands:
                        is_left = h['rx'] < 640
                        if moshi == 'pk':
                            half = max(1, max_shou // 2)
                            choose_range = range(0, half) if is_left else range(half, max_shou)
                        else:
                            choose_range = range(max_shou)

                        best_i, min_dist = -1, float('inf')
                        for i in choose_range:
                            if last_hands[i] is not None and i not in assigned.values():
                                dist = math.hypot(h['rx'] - last_hands[i][0],
                                                  h['ry'] - last_hands[i][1])
                                if dist < 250 and dist < min_dist:
                                    min_dist, best_i = dist, i

                        if best_i != -1:
                            assigned[id(h)] = best_i
                            used.add(best_i)
                            sx, sy = pinghua_qis[best_i].smooth(h['rx'], h['ry'])
                            # 卡路里计算
                            if len(dao_trails[best_i]) > 0:
                                last_pt = dao_trails[best_i][-1]
                                dist = math.hypot(sx - last_pt[0], sy - last_pt[1])
                                game.add_distance(dist, best_i, max_shou)
                            dao_trails[best_i].append((sx, sy))
                            last_hands[best_i] = (h['rx'], h['ry'])
                        else:
                            unassigned.append((h, choose_range))

                    # 未分配的手给空闲的刀光
                    for h, choose_range in unassigned:
                        for i in choose_range:
                            if i not in used:
                                used.add(i)
                                sx, sy = pinghua_qis[i].smooth(h['rx'], h['ry'])
                                dao_trails[i].append((sx, sy))
                                last_hands[i] = (h['rx'], h['ry'])
                                break

                    # 没出现的手清空轨迹
                    for i in range(max_shou):
                        if i not in used:
                            pinghua_qis[i].reset()
                            last_hands[i] = None

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

                # ---------- 隔帧更新物理（保持 30fps 手感） ----------
                if frame_counter % 2 == 0:
                    game.update(dao_trails)
                    game.check_collisions(dao_trails)
                frame_counter += 1

                # ---------- 绘制游戏元素 ----------
                game.draw(frame)

                # 显示模式信息
                mode_name = "增强" if vision_engine.get_mode() == "BOOST" else "正常"
                config.add_cn_text(
                    f"视觉模式：{mode_name}",
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
                config.flush_cn_texts(frame)

                cv2.imshow('Swift-Fruit-Slice', frame)

                # ---------- 按键处理 ----------
                key = cv2.waitKey(1) & 0xFF
                if key == ord('c'):
                    vision_engine.toggle_environment_mode()

                if key == ord('q'):
                    is_playing = False
                    break

            # ---------- 游戏结束，停止视觉线程 ----------
            if vision_thread is not None:
                vision_thread.stop()
                vision_thread.join()
                vision_thread = None

            # ---------- 结算 ----------
            if is_playing:
                action = jiesuan_ui(cap, game)
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
        vision_thread.join()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()