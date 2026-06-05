import cv2
import config
import math_utils
import vision_engine

import time

def _draw_hover_bar(frame, area, progress):
    """绘制悬停确认的绿色进度条"""
    x, y, w, h = area['x'], area['y'], area['w'], area['h']
    bx, by = x + 10, y + h + 15
    bw, bh = w - 20, 25
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (60, 60, 60), -1)
    cv2.rectangle(frame, (bx, by), (bx + int(bw * progress), by + bh), (0, 220, 0), -1)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (200, 200, 200), 2)

def mode_selection_screen(cap) -> str:
    """完整的模式选择界面"""
    BOX_W, BOX_H = 320, 280
    GAP  = (config.WINDOW_WIDTH - 3 * BOX_W) // 4
    areas = {
        'single': {'x': GAP,              'y': 240, 'w': BOX_W, 'h': BOX_H},
        'dual':   {'x': GAP*2 + BOX_W,    'y': 240, 'w': BOX_W, 'h': BOX_H},
        'pk':     {'x': GAP*3 + BOX_W*2,  'y': 240, 'w': BOX_W, 'h': BOX_H},
    }
    hover_timer   = {k: 0 for k in areas}
    threshold     = 30
    current_hover = None
    smoother      = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)

    labels  = {'single': '单手模式', 'dual': '双手模式', 'pk': '双人PK'}
    descs   = {'single': '一只手切水果', 'dual': '双手同时切水果', 'pk': '两人对战 30秒'}
    colors  = {'single': (255, 220, 80), 'dual': (80, 220, 255), 'pk': (255, 100, 100)}
    key_map = {'1': 'single', '2': 'dual', '3': 'pk'}

    while True:
        ret, frame = cap.read()
        if not ret: return 'single'
        
        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        frame = cv2.flip(frame, 1)
        
        # 半透明背景遮罩
        ov = frame.copy()
        cv2.rectangle(ov, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)

        config.add_cn_text('选择游戏模式', (config.WINDOW_WIDTH//2 - 180, 55),  font_size=60, color=(255, 220, 0))
        config.add_cn_text('悬停食指 3 秒确认', (config.WINDOW_WIDTH//2 - 160, 140), font_size=34, color=(200, 200, 200))

        # 绘制所有方块
        for key, area in areas.items():
            x, y, w, h = area['x'], area['y'], area['w'], area['h']
            hovering = (current_hover == key)
            progress = hover_timer[key] / threshold if hovering else 0
            bcolor   = (0, 255, 0) if hovering else (160, 160, 160)
            thick    = 5 if hovering else 2
            
            cv2.rectangle(frame, (x, y), (x + w, y + h), bcolor, thick)
            if hovering:
                hl = frame.copy()
                cv2.rectangle(hl, (x, y), (x + w, y + h), (0, 70, 0), -1)
                cv2.addWeighted(hl, 0.25, frame, 0.75, 0, frame)

            config.add_cn_text(labels[key], (x + 30, y + 70),  font_size=44, color=colors[key])
            config.add_cn_text(descs[key],  (x + 20, y + 155), font_size=26, color=(200, 200, 200))

            if hovering and progress > 0:
                _draw_hover_bar(frame, area, progress)

        config.add_cn_text('快捷键: 1=单手  2=双手  3=双人PK  | Esc键退出游戏',
                           (config.WINDOW_WIDTH//2 - 320, config.WINDOW_HEIGHT - 55),
                           font_size=24, color=(140, 140, 140))

        # 视觉检测与悬停判定
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        lm_list, _ = vision_engine.detect_hands(rgb)
        current_hover = None
        
        if lm_list:
            tip = lm_list[0][8]
            rx, ry = int(tip.x * config.WINDOW_WIDTH), int(tip.y * config.WINDOW_HEIGHT)
            sx, sy = smoother.smooth(rx, ry)
            cv2.circle(frame, (sx, sy), 22, (0, 255, 255), 3)
            cv2.circle(frame, (sx, sy), 12, (0, 255, 0), cv2.FILLED)
            for key, area in areas.items():
                if area['x'] <= sx <= area['x'] + area['w'] and area['y'] <= sy <= area['y'] + area['h']:
                    current_hover = key
                    hover_timer[key] += 1
                    if hover_timer[key] >= threshold:
                        config.flush_cn_texts(frame)
                        return key
                else:
                    hover_timer[key] = max(0, hover_timer[key] - 2)
        else:
            smoother.reset()
            for k in hover_timer: hover_timer[k] = max(0, hover_timer[k] - 2)

        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)
        
        kp = cv2.waitKey(1) & 0xFF
        if kp == 27: return 'quit'
        if chr(kp) in key_map: return key_map[chr(kp)]


def blade_selection_screen(cap) -> str:
    """完整的刀光选择界面"""
    areas = {
        'dao1': {'x': 200, 'y': 280, 'w': 300, 'h': 300},
        'dao2': {'x': 780, 'y': 280, 'w': 300, 'h': 300},
    }
    hover_timer   = {'dao1': 0, 'dao2': 0}
    threshold     = 30
    current_hover = None
    smoother      = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)
    labels        = {'dao1': '经典冷冽刀光', 'dao2': '狂暴烈焰刀光'}

    while True:
        ret, frame = cap.read()
        if not ret: return 'dao1'
        
        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        frame = cv2.flip(frame, 1)
        ov = frame.copy()
        cv2.rectangle(ov, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)

        config.add_cn_text('选择刀光样式', (config.WINDOW_WIDTH//2 - 160, 60), font_size=60, color=(0, 220, 255))
        config.add_cn_text('悬停食指 3 秒确认选择', (config.WINDOW_WIDTH//2 - 200, 148), font_size=34, color=(200, 200, 200))

        for key, area in areas.items():
            x, y, w, h = area['x'], area['y'], area['w'], area['h']
            hovering = (current_hover == key)
            progress = hover_timer[key] / threshold if hovering else 0
            bcolor   = (0, 255, 0) if hovering else (200, 200, 200)
            thick    = 5 if hovering else 2
            
            cv2.rectangle(frame, (x, y), (x + w, y + h), bcolor, thick)
            if hovering:
                hl = frame.copy()
                cv2.rectangle(hl, (x, y), (x + w, y + h), (0, 80, 0), -1)
                cv2.addWeighted(hl, 0.25, frame, 0.75, 0, frame)

            blade_img = config.BLADE_IMAGES.get(key)
            if blade_img is not None:
                bh, bw = blade_img.shape[:2]
                sc = min((w - 40) / bw, (h - 40) / bh, 1.0)
                sized = cv2.resize(blade_img, (int(bw * sc), int(bh * sc)))
                config.overlay_image(frame, sized, x + w // 2, y + h // 2, 0, 1.0)

            config.add_cn_text(labels[key], (x + 30, y - 55), font_size=30, color=(255, 255, 255))
            if hovering and progress > 0:
                _draw_hover_bar(frame, area, progress)

        config.add_cn_text('快捷键: 1=样式一  2=样式二', (config.WINDOW_WIDTH//2 - 160, config.WINDOW_HEIGHT - 55), font_size=24, color=(140, 140, 140))

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        lm_list, _ = vision_engine.detect_hands(rgb)
        current_hover = None
        
        if lm_list:
            tip = lm_list[0][8]
            rx, ry = int(tip.x * config.WINDOW_WIDTH), int(tip.y * config.WINDOW_HEIGHT)
            sx, sy = smoother.smooth(rx, ry)
            cv2.circle(frame, (sx, sy), 22, (0, 255, 255), 3)
            cv2.circle(frame, (sx, sy), 12, (0, 255, 0), cv2.FILLED)
            for key, area in areas.items():
                if area['x'] <= sx <= area['x'] + area['w'] and area['y'] <= sy <= area['y'] + area['h']:
                    current_hover = key
                    hover_timer[key] += 1
                    if hover_timer[key] >= threshold:
                        config.flush_cn_texts(frame)
                        return key
                else:
                    hover_timer[key] = max(0, hover_timer[key] - 2)
        else:
            smoother.reset()
            for k in hover_timer: hover_timer[k] = max(0, hover_timer[k] - 2)

        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)
        kp = cv2.waitKey(1) & 0xFF
        if kp == ord('1') or kp == ord('q'): return 'dao1'
        elif kp == ord('2'): return 'dao2'


def end_game_menu_visual(cap, game) -> str:
    """完整的游戏结算界面，包含延迟和分数显示"""
    areas = {
        'restart': {'x': 300, 'y': 380, 'w': 300, 'h': 200},
        'menu':    {'x': 680, 'y': 380, 'w': 300, 'h': 200}
    }
    hover_timer = {'restart': 0, 'menu': 0}
    threshold = 30
    smoother = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)
    
    start_time = time.time()
    delay_seconds = 2.0  # 延迟 2 秒后才显示交互按钮
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        frame = cv2.flip(frame, 1)
        
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        config.add_cn_text('游戏结束', (config.WINDOW_WIDTH//2 - 120, 80), 80, (255, 255, 255))
        
        # 显示得分与结果
        if game.mode == 'pk':
            if game.winner == 'p1':
                config.add_cn_text('🏆 玩家一获胜！', (config.WINDOW_WIDTH//2 - 170, 200), 50, (255, 200, 0))
            elif game.winner == 'p2':
                config.add_cn_text('🏆 玩家二获胜！', (config.WINDOW_WIDTH//2 - 170, 200), 50, (100, 200, 255))
            else:
                config.add_cn_text('🤝 双方平局！', (config.WINDOW_WIDTH//2 - 150, 200), 50, (240, 240, 240))
            config.add_cn_text(f'玩家一: {game.p1.score}分   玩家二: {game.p2.score}分', (config.WINDOW_WIDTH//2 - 230, 280), 30, (200, 200, 200))
        else:
            config.add_cn_text(f'本次得分: {game.score}', (config.WINDOW_WIDTH//2 - 150, 180), 50, (0, 255, 255))
            if game.game_over_reason:
                config.add_cn_text(game.game_over_reason, (config.WINDOW_WIDTH//2 - 160, 260), 30, (255, 100, 100))

        # 延迟逻辑
        if time.time() - start_time > delay_seconds:
            for key, area in areas.items():
                x, y, w, h = area['x'], area['y'], area['w'], area['h']
                progress = hover_timer[key] / threshold
                color = (0, 255, 0) if progress > 0 else (100, 100, 100)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
                
                label = '重新开始' if key == 'restart' else '主菜单'
                config.add_cn_text(label, (x + 50, y + 110), 40, (255, 255, 255))
                if progress > 0:
                    _draw_hover_bar(frame, area, progress)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            lm_list, _ = vision_engine.detect_hands(rgb)
            
            if lm_list:
                tip = lm_list[0][8]
                sx, sy = smoother.smooth(int(tip.x * config.WINDOW_WIDTH), int(tip.y * config.WINDOW_HEIGHT))
                cv2.circle(frame, (sx, sy), 15, (0, 255, 255), -1)
                
                for key, area in areas.items():
                    if area['x'] <= sx <= area['x'] + area['w'] and area['y'] <= sy <= area['y'] + area['h']:
                        hover_timer[key] += 1
                        if hover_timer[key] >= threshold: 
                            config.flush_cn_texts(frame)
                            return key
                    else:
                        hover_timer[key] = max(0, hover_timer[key] - 2)
            else:
                smoother.reset()
                for k in hover_timer:
                    hover_timer[k] = max(0, hover_timer[k] - 2)
        else:
            remain = int(delay_seconds - (time.time() - start_time)) + 1
            config.add_cn_text(f'即将显示选项... {remain}', (config.WINDOW_WIDTH//2 - 130, 450), 30, (150, 150, 150))
        
        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)

        kp = cv2.waitKey(1) & 0xFF
        if kp == ord('r'): return 'restart'
        if kp == ord('m'): return 'menu'
        if kp == ord('q') or kp == 27: return 'quit'
