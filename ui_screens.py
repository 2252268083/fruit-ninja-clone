import cv2
import config
import math_utils
import vision_engine
import time
"""
游戏主页面的ui选择 界面
"""
def _read_frame(cap, retries=15):
    """读一帧；部分设备/驱动刚打开时偶尔返回失败，重试一小会儿再判定真失败"""
    for _ in range(retries):
        ok, frame = cap.read()
        if ok and frame is not None:
            return frame
        time.sleep(0.02)
    return None


HOVER_SECONDS = 1.5      # 悬停确认时长（真实时间，不再按帧数）
HOVER_DECAY = 2.0        # 手指移开后每秒回退的进度秒数


def _window_closed():
    """用户点了窗口右上角 × 时返回 True（连续两次确认，避免误判）"""
    def _visible():
        try:
            return cv2.getWindowProperty('Swift-Fruit-Slice', cv2.WND_PROP_VISIBLE)
        except cv2.error:
            return -1

    if _visible() >= 1:
        return False
    time.sleep(0.1)
    return _visible() < 1


def _placeholder(text='摄像头暂无画面，正在重试...'):
    """读帧失败时的占位画面，避免界面直接消失或替你选择"""
    import numpy as np
    frame = np.zeros((config.WINDOW_HEIGHT, config.WINDOW_WIDTH, 3), dtype=np.uint8)
    config.add_cn_text(text, (config.WINDOW_WIDTH // 2 - 260, config.WINDOW_HEIGHT // 2),
                       font_size=36, color=(200, 200, 200))
    config.flush_cn_texts(frame)
    return frame

def draw_jindu_tiao(frame, area, progress):
    #画那个绿色的加载条 特效
    x, y, w, h = area['x'], area['y'], area['w'], area['h']
    bx, by = x + 10, y + h + 15
    bw, bh = w - 20, 25
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (60, 60, 60), -1)
    cv2.rectangle(frame, (bx, by), (bx + int(bw * progress), by + bh), (0, 220, 0), -1)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (200, 200, 200), 2)


def _detect_tip(frame):
    """按推理宽度缩小后再检测（归一化坐标与分辨率无关），返回屏幕像素坐标或 None"""
    w = config.get_infer_width()
    h = max(2, int(round(frame.shape[0] * w / frame.shape[1])))
    try:
        lm_list, _ = vision_engine.detect_hands(
            cv2.cvtColor(cv2.resize(frame, (w, h)), cv2.COLOR_BGR2RGB))
    except Exception:
        # 识别引擎异常时菜单只是选不中，不能直接崩掉整个程序
        return None
    if not lm_list:
        return None
    tip = lm_list[0][8]
    return int(tip.x * config.WINDOW_WIDTH), int(tip.y * config.WINDOW_HEIGHT)


def _update_hover(areas, sx, sy, hover_time, dt):
    """用本轮指尖位置更新悬停计时，返回本轮悬停项（不在任何区域则为 None）"""
    now_hover = None
    for k, a in areas.items():
        if a['x'] <= sx <= a['x'] + a['w'] and a['y'] <= sy <= a['y'] + a['h']:
            now_hover = k
            hover_time[k] += dt
        else:
            hover_time[k] = max(0.0, hover_time[k] - HOVER_DECAY * dt)
    return now_hover


def _decay_hover(hover_time, dt):
    for k in hover_time:
        hover_time[k] = max(0.0, hover_time[k] - HOVER_DECAY * dt)


def _draw_hover_box(frame, a, is_hover, progress, idle_color=(160, 160, 160),
                    fill_color=(0, 70, 0)):
    x, y, w, h = a['x'], a['y'], a['w'], a['h']
    b_color = (0, 255, 0) if is_hover else idle_color
    cv2.rectangle(frame, (x, y), (x + w, y + h), b_color, 5 if is_hover else 2)
    if is_hover:
        hl = frame.copy()
        cv2.rectangle(hl, (x, y), (x + w, y + h), fill_color, -1)
        cv2.addWeighted(hl, 0.25, frame, 0.75, 0, frame)
    if is_hover and progress > 0:
        draw_jindu_tiao(frame, a, progress)


def _draw_tip(frame, sx, sy, radius=22):
    cv2.circle(frame, (sx, sy), radius, (0, 255, 255), 3)
    cv2.circle(frame, (sx, sy), max(4, radius - 10), (0, 255, 0), cv2.FILLED)

def xuanze_moshi_ui(cap) -> str:
    #选模式的界面
    box_w, box_h = 320, 280
    gap  = (config.WINDOW_WIDTH - 3 * box_w) // 4
    
    #用字典存区域 免得写一堆if else
    areas = {
        'single': {'x': gap,              'y': 240, 'w': box_w, 'h': box_h},
        'dual':   {'x': gap*2 + box_w,    'y': 240, 'w': box_w, 'h': box_h},
        'pk':     {'x': gap*3 + box_w*2,  'y': 240, 'w': box_w, 'h': box_h},
    }
    
    hover_time = {k: 0.0 for k in areas}
    last_t = time.time()
    fail_since = None
    now_hover = None
    
    #之前手太抖选不中 加个平滑器
    my_smoother = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)

    labels  = {'single': '单手模式', 'dual': '双手模式', 'pk': '双人PK'}
    descs   = {'single': '一只手切水果', 'dual': '双手同时切水果', 'pk': '两人对战 30秒'}
    colors  = {'single': (255, 220, 80), 'dual': (80, 220, 255), 'pk': (255, 100, 100)}
    key_map = {'1': 'single', '2': 'dual', '3': 'pk'}

    while True:
        frame = _read_frame(cap)
        if frame is None:
            # 不再替玩家默认选择：显示重试提示，连续 10 秒无画面才退出
            if fail_since is None:
                fail_since = time.time()
            elif time.time() - fail_since > 10:
                return 'quit'
            cv2.imshow('Swift-Fruit-Slice', _placeholder())
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or _window_closed():
                return 'quit'
            if key in (ord('1'), ord('2'), ord('3')):
                return key_map[chr(key)]
            continue
        fail_since = None

        now_t = time.time()
        dt = now_t - last_t
        last_t = now_t

        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        if config.SETTINGS["camera"].get("mirror", True):
            frame = cv2.flip(frame, 1)

        # 先在未压暗的原帧上识别，再更新悬停状态：本帧的框用本帧的手，不再慢一帧
        tip = _detect_tip(frame)
        if tip:
            sx, sy = my_smoother.smooth(*tip)
            now_hover = _update_hover(areas, sx, sy, hover_time, dt)
        else:
            my_smoother.reset()
            _decay_hover(hover_time, dt)
            now_hover = None
            sx = sy = None
        confirmed = now_hover if (now_hover and hover_time[now_hover] >= HOVER_SECONDS) else None
        
        #搞个半透明遮罩看起来高级点
        zhezhao = frame.copy()
        cv2.rectangle(zhezhao, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(zhezhao, 0.55, frame, 0.45, 0, frame)

        config.add_cn_text('选择游戏模式', (config.WINDOW_WIDTH//2 - 180, 55),  font_size=60, color=(255, 220, 0))
        config.add_cn_text(f'悬停食指 {HOVER_SECONDS:g} 秒确认', (config.WINDOW_WIDTH//2 - 160, 140), font_size=34, color=(200, 200, 200))

        #画框框
        for k, a in areas.items():
            is_hover = (now_hover == k)
            p = min(1.0, hover_time[k] / HOVER_SECONDS) if is_hover else 0.0
            _draw_hover_box(frame, a, is_hover, p)
            config.add_cn_text(labels[k], (a['x'] + 30, a['y'] + 70),  font_size=44, color=colors[k])
            config.add_cn_text(descs[k],  (a['x'] + 20, a['y'] + 155), font_size=26, color=(200, 200, 200))

        config.add_cn_text('快捷键: 1=单手  2=双手  3=双人PK  | Esc键退出游戏',
                           (config.WINDOW_WIDTH//2 - 320, config.WINDOW_HEIGHT - 55),
                           font_size=24, color=(140, 140, 140))

        if sx is not None:
            _draw_tip(frame, sx, sy)

        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)
        if confirmed:
            return confirmed
        
        key = cv2.waitKey(1) & 0xFF
        if _window_closed(): return 'quit'
        if key == 27: return 'quit'
        if chr(key) in key_map: return key_map[chr(key)]


def xuanze_daoguang_ui(cap) -> str:
    #选刀光 后续  加入（彩虹刀特效）
    areas = {
        'dao1': {'x': 200, 'y': 280, 'w': 300, 'h': 300},
        'dao2': {'x': 780, 'y': 280, 'w': 300, 'h': 300},
    }
    hover_time   = {'dao1': 0.0, 'dao2': 0.0}
    last_t = time.time()
    fail_since = None
    now_hover = None
    my_smoother      = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)
    labels        = {'dao1': '经典冷冽刀光', 'dao2': '狂暴烈焰刀光'}

    # 素材尺寸固定，进循环前缩放一次，避免每帧 resize
    sized_dao = {}
    for k, a in areas.items():
        img = config.BLADE_IMAGES.get(k)
        if img is not None:
            dh, dw = img.shape[:2]
            sc = min((a['w'] - 40) / dw, (a['h'] - 40) / dh, 1.0)
            sized_dao[k] = cv2.resize(img, (int(dw * sc), int(dh * sc)))

    while True:
        frame = _read_frame(cap)
        if frame is None:
            # 读不到画面时不替玩家默认选刀光
            if fail_since is None:
                fail_since = time.time()
            elif time.time() - fail_since > 10:
                return 'quit'
            cv2.imshow('Swift-Fruit-Slice', _placeholder())
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q') or _window_closed():
                return 'quit'
            if key == ord('1'): return 'dao1'
            if key == ord('2'): return 'dao2'
            continue
        fail_since = None

        now_t = time.time()
        dt = now_t - last_t
        last_t = now_t

        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        if config.SETTINGS["camera"].get("mirror", True):
            frame = cv2.flip(frame, 1)

        # 先检测再画框，保证高亮与手指同步
        tip = _detect_tip(frame)
        if tip:
            sx, sy = my_smoother.smooth(*tip)
            now_hover = _update_hover(areas, sx, sy, hover_time, dt)
        else:
            my_smoother.reset()
            _decay_hover(hover_time, dt)
            now_hover = None
            sx = sy = None
        confirmed = now_hover if (now_hover and hover_time[now_hover] >= HOVER_SECONDS) else None
        
        zhezhao = frame.copy()
        cv2.rectangle(zhezhao, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(zhezhao, 0.55, frame, 0.45, 0, frame)

        config.add_cn_text('选择刀光样式', (config.WINDOW_WIDTH//2 - 160, 60), font_size=60, color=(0, 220, 255))
        config.add_cn_text(f'悬停食指 {HOVER_SECONDS:g} 秒确认选择', (config.WINDOW_WIDTH//2 - 200, 148), font_size=34, color=(200, 200, 200))

        for k, a in areas.items():
            is_hover = (now_hover == k)
            p = min(1.0, hover_time[k] / HOVER_SECONDS) if is_hover else 0.0
            _draw_hover_box(frame, a, is_hover, p, idle_color=(200, 200, 200),
                            fill_color=(0, 80, 0))

            dao_img = sized_dao.get(k)
            if dao_img is not None:
                config.overlay_image(frame, dao_img, a['x'] + a['w'] // 2, a['y'] + a['h'] // 2, 0, 1.0)

            config.add_cn_text(labels[k], (a['x'] + 30, a['y'] - 55), font_size=30, color=(255, 255, 255))

        config.add_cn_text('快捷键: 1=样式一  2=样式二', (config.WINDOW_WIDTH//2 - 160, config.WINDOW_HEIGHT - 55), font_size=24, color=(140, 140, 140))

        if sx is not None:
            _draw_tip(frame, sx, sy)

        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)
        if confirmed:
            return confirmed

        key = cv2.waitKey(1) & 0xFF
        if _window_closed(): return 'quit'
        if key == ord('1'): return 'dao1'
        elif key == ord('2'): return 'dao2'
        elif key == ord('q') or key == 27: return 'quit'


def jiesuan_ui(cap, game_obj) -> str:
    #死了之后的结算页面
    areas = {
        'restart': {'x': 300, 'y': 380, 'w': 300, 'h': 200},
        'menu':    {'x': 680, 'y': 380, 'w': 300, 'h': 200}
    }
    hover_time = {'restart': 0.0, 'menu': 0.0}
    last_t = time.time()
    fail_since = None
    my_smoother = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)
    
    start_t = time.time()
    wait_s = 2.0  #刚死的时候不能马上点 防误触
    
    while True:
        frame = _read_frame(cap)
        if frame is None:
            # 读不到画面超过 5 秒就返回 None，由 main 按设备故障退出，避免无限自动重开
            if fail_since is None:
                fail_since = time.time()
            elif time.time() - fail_since > 5:
                return None
            cv2.imshow('Swift-Fruit-Slice', _placeholder('结算界面取不到画面，正在重试...'))
            key = cv2.waitKey(1) & 0xFF
            if _window_closed():
                return 'menu'   # 关窗=返回上一级
            if key == ord('q') or key == 27:
                return 'quit'
            continue
        fail_since = None

        now_t = time.time()
        dt = now_t - last_t
        last_t = now_t
        waited = now_t - start_t > wait_s

        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        if config.SETTINGS["camera"].get("mirror", True):
            frame = cv2.flip(frame, 1)

        # 选项出现后才检测手；先检测再画，高亮与本帧同步
        sx = sy = None
        now_hover = None
        confirmed = None
        if waited:
            tip = _detect_tip(frame)
            if tip:
                sx, sy = my_smoother.smooth(*tip)
                now_hover = _update_hover(areas, sx, sy, hover_time, dt)
                if now_hover and hover_time[now_hover] >= HOVER_SECONDS:
                    confirmed = now_hover
            else:
                my_smoother.reset()
                _decay_hover(hover_time, dt)
        
        zhezhao = frame.copy()
        cv2.rectangle(zhezhao, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(zhezhao, 0.6, frame, 0.4, 0, frame)
        
        config.add_cn_text('游戏结束', (config.WINDOW_WIDTH//2 - 120, 80), 80, (255, 255, 255))
        
        #之前没传game对象导致分数全是0 注意bug 已修复
        if game_obj.mode == 'pk':#双人模式
            if game_obj.winner == 'p1':
                config.add_cn_text('🏆 玩家一获胜！', (config.WINDOW_WIDTH//2 - 170, 200), 50, (255, 200, 0))
            elif game_obj.winner == 'p2':
                config.add_cn_text('🏆 玩家二获胜！', (config.WINDOW_WIDTH//2 - 170, 200), 50, (100, 200, 255))
            else:
                config.add_cn_text('🤝 双方平局！', (config.WINDOW_WIDTH//2 - 150, 200), 50, (240, 240, 240))
            
            config.add_cn_text(f'玩家一: {game_obj.p1.score}分   玩家二: {game_obj.p2.score}分', (config.WINDOW_WIDTH//2 - 230, 280), 30, (200, 200, 200))
            cal1 = game_obj.p1.get_calories()#计算玩家一卡路里
            cal2 = game_obj.p2.get_calories()#计算玩家一卡路里
            config.add_cn_text(f' 玩家一消耗: {cal1:.1f} 卡路里   玩家二消耗: {cal2:.1f} 卡路里', (config.WINDOW_WIDTH//2 - 290, 330), 26, (255, 150, 50))


        else:
            config.add_cn_text(f'本次得分: {game_obj.score}', (config.WINDOW_WIDTH//2 - 150, 180), 50, (0, 255, 255))
            if getattr(game_obj, 'game_over_reason', None):
                config.add_cn_text(game_obj.game_over_reason, (config.WINDOW_WIDTH//2 - 160, 260), 30, (255, 100, 100))
            
            cal = game_obj.get_calories()
            # Y坐标设为 320，刚好填补中间的空白
            config.add_cn_text(f' 本局累计舒展肩颈，共消耗热量：{cal:.1f} 卡路里', (config.WINDOW_WIDTH//2 - 280, 320), 28, (255, 150, 50))


        if waited:
            for k, a in areas.items():
                is_hover = (now_hover == k)
                # 只有当前真的悬停才显示进度条：手指离开后不再留下绿框残影
                p = min(1.0, hover_time[k] / HOVER_SECONDS) if is_hover else 0.0
                _draw_hover_box(frame, a, is_hover, p, idle_color=(100, 100, 100))

                txt = '重新开始' if k == 'restart' else '主菜单'
                config.add_cn_text(txt, (a['x'] + 50, a['y'] + 110), 40, (255, 255, 255))

            if sx is not None:
                cv2.circle(frame, (sx, sy), 15, (0, 255, 255), -1)
        else:
            shengyu = int(wait_s - (now_t - start_t)) + 1
            config.add_cn_text(f'即将显示选项... {shengyu}', (config.WINDOW_WIDTH//2 - 130, 450), 30, (150, 150, 150))
        
        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)
        if confirmed:
            return confirmed

        key = cv2.waitKey(1) & 0xFF
        if _window_closed(): return 'menu'   # 关窗=返回主菜单，不再当成设备故障
        # Q / Esc 是"立刻想走"的语义，不受 2 秒防误触限制
        if key == ord('q') or key == 27: return 'quit'
        # R/M 仍过 2 秒防误触，避免手还在挥就误触重开
        if waited:
            if key == ord('r'): return 'restart'
            if key == ord('m'): return 'menu'
