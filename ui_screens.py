import cv2
import config
import math_utils
import vision_engine
import time
"""
游戏主页面的ui选择 界面
"""
def draw_jindu_tiao(frame, area, progress):
    #画那个绿色的加载条 特效
    x, y, w, h = area['x'], area['y'], area['w'], area['h']
    bx, by = x + 10, y + h + 15
    bw, bh = w - 20, 25
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (60, 60, 60), -1)
    cv2.rectangle(frame, (bx, by), (bx + int(bw * progress), by + bh), (0, 220, 0), -1)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (200, 200, 200), 2)

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
    
    hover_time = {k: 0 for k in areas}
    max_hover = 30#停多久算确认 大概30帧
    now_hover = None
    
    #之前手太抖选不中 加个平滑器
    my_smoother = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)

    labels  = {'single': '单手模式', 'dual': '双手模式', 'pk': '双人PK'}
    descs   = {'single': '一只手切水果', 'dual': '双手同时切水果', 'pk': '两人对战 30秒'}
    colors  = {'single': (255, 220, 80), 'dual': (80, 220, 255), 'pk': (255, 100, 100)}
    key_map = {'1': 'single', '2': 'dual', '3': 'pk'}

    while True:
        ok, frame = cap.read()
        if not ok: 
            return 'single'#读不到图就默认单手吧
            
        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        frame = cv2.flip(frame, 1)
        
        #搞个半透明遮罩看起来高级点
        zhezhao = frame.copy()
        cv2.rectangle(zhezhao, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(zhezhao, 0.55, frame, 0.45, 0, frame)

        config.add_cn_text('选择游戏模式', (config.WINDOW_WIDTH//2 - 180, 55),  font_size=60, color=(255, 220, 0))
        config.add_cn_text('悬停食指 3 秒确认', (config.WINDOW_WIDTH//2 - 160, 140), font_size=34, color=(200, 200, 200))

        #画框框
        for k, a in areas.items():
            x, y, w, h = a['x'], a['y'], a['w'], a['h']
            is_hover = (now_hover == k)
            p = hover_time[k] / max_hover if is_hover else 0
            b_color = (0, 255, 0) if is_hover else (160, 160, 160)
            t_thick = 5 if is_hover else 2
            
            cv2.rectangle(frame, (x, y), (x + w, y + h), b_color, t_thick)
            if is_hover:
                hl = frame.copy()
                cv2.rectangle(hl, (x, y), (x + w, y + h), (0, 70, 0), -1)
                cv2.addWeighted(hl, 0.25, frame, 0.75, 0, frame)

            config.add_cn_text(labels[k], (x + 30, y + 70),  font_size=44, color=colors[k])
            config.add_cn_text(descs[k],  (x + 20, y + 155), font_size=26, color=(200, 200, 200))

            if is_hover and p > 0:
                draw_jindu_tiao(frame, a, p)

        config.add_cn_text('快捷键: 1=单手  2=双手  3=双人PK  | Esc键退出游戏',
                           (config.WINDOW_WIDTH//2 - 320, config.WINDOW_HEIGHT - 55),
                           font_size=24, color=(140, 140, 140))

        #找手
        rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        lm_list, _ = vision_engine.detect_hands(rgb_img)
        now_hover = None
        
        if lm_list:
            #拿食指尖(点8)
            tip = lm_list[0][8]
            rx, ry = int(tip.x * config.WINDOW_WIDTH), int(tip.y * config.WINDOW_HEIGHT)
            sx, sy = my_smoother.smooth(rx, ry)
            
            #画个圈提示位置
            cv2.circle(frame, (sx, sy), 22, (0, 255, 255), 3)
            cv2.circle(frame, (sx, sy), 12, (0, 255, 0), cv2.FILLED)
            
            for k, a in areas.items():
                if a['x'] <= sx <= a['x'] + a['w'] and a['y'] <= sy <= a['y'] + a['h']:
                    now_hover = k
                    hover_time[k] += 1
                    if hover_time[k] >= max_hover:
                        config.flush_cn_texts(frame)
                        return k
                else:
                    hover_time[k] = max(0, hover_time[k] - 2)
        else:
            my_smoother.reset()
            for k in hover_time: 
                hover_time[k] = max(0, hover_time[k] - 2)

        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27: return 'quit'
        if chr(key) in key_map: return key_map[chr(key)]


def xuanze_daoguang_ui(cap) -> str:
    #选刀光 后续  加入（彩虹刀特效）
    areas = {
        'dao1': {'x': 200, 'y': 280, 'w': 300, 'h': 300},
        'dao2': {'x': 780, 'y': 280, 'w': 300, 'h': 300},
    }
    hover_time   = {'dao1': 0, 'dao2': 0}
    max_hover     = 30
    now_hover = None
    my_smoother      = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)
    labels        = {'dao1': '经典冷冽刀光', 'dao2': '狂暴烈焰刀光'}

    while True:
        ok, frame = cap.read()
        if not ok: return 'dao1'
        
        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        frame = cv2.flip(frame, 1)
        
        zhezhao = frame.copy()
        cv2.rectangle(zhezhao, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
        cv2.addWeighted(zhezhao, 0.55, frame, 0.45, 0, frame)

        config.add_cn_text('选择刀光样式', (config.WINDOW_WIDTH//2 - 160, 60), font_size=60, color=(0, 220, 255))
        config.add_cn_text('悬停食指 3 秒确认选择', (config.WINDOW_WIDTH//2 - 200, 148), font_size=34, color=(200, 200, 200))

        for k, a in areas.items():
            x, y, w, h = a['x'], a['y'], a['w'], a['h']
            is_hover = (now_hover == k)
            p = hover_time[k] / max_hover if is_hover else 0
            b_color   = (0, 255, 0) if is_hover else (200, 200, 200)
            t_thick    = 5 if is_hover else 2
            
            cv2.rectangle(frame, (x, y), (x + w, y + h), b_color, t_thick)
            if is_hover:
                hl = frame.copy()
                cv2.rectangle(hl, (x, y), (x + w, y + h), (0, 80, 0), -1)
                cv2.addWeighted(hl, 0.25, frame, 0.75, 0, frame)

            dao_img = config.BLADE_IMAGES.get(k)
            if dao_img is not None:
                dh, dw = dao_img.shape[:2]
                sc = min((w - 40) / dw, (h - 40) / dh, 1.0)
                sized_dao = cv2.resize(dao_img, (int(dw * sc), int(dh * sc)))
                config.overlay_image(frame, sized_dao, x + w // 2, y + h // 2, 0, 1.0)

            config.add_cn_text(labels[k], (x + 30, y - 55), font_size=30, color=(255, 255, 255))
            if is_hover and p > 0:
                draw_jindu_tiao(frame, a, p)

        config.add_cn_text('快捷键: 1=样式一  2=样式二', (config.WINDOW_WIDTH//2 - 160, config.WINDOW_HEIGHT - 55), font_size=24, color=(140, 140, 140))

        rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        lm_list, _ = vision_engine.detect_hands(rgb_img)
        now_hover = None
        
        if lm_list:
            tip = lm_list[0][8]
            rx, ry = int(tip.x * config.WINDOW_WIDTH), int(tip.y * config.WINDOW_HEIGHT)
            sx, sy = my_smoother.smooth(rx, ry)
            
            cv2.circle(frame, (sx, sy), 22, (0, 255, 255), 3)
            cv2.circle(frame, (sx, sy), 12, (0, 255, 0), cv2.FILLED)
            
            for k, a in areas.items():
                if a['x'] <= sx <= a['x'] + a['w'] and a['y'] <= sy <= a['y'] + a['h']:
                    now_hover = k
                    hover_time[k] += 1
                    if hover_time[k] >= max_hover:
                        config.flush_cn_texts(frame)
                        return k
                else:
                    hover_time[k] = max(0, hover_time[k] - 2)
        else:
            my_smoother.reset()
            for k in hover_time: 
                hover_time[k] = max(0, hover_time[k] - 2)

        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('1') or key == ord('q'): return 'dao1'
        elif key == ord('2'): return 'dao2'


def jiesuan_ui(cap, game_obj) -> str:
    #死了之后的结算页面
    areas = {
        'restart': {'x': 300, 'y': 380, 'w': 300, 'h': 200},
        'menu':    {'x': 680, 'y': 380, 'w': 300, 'h': 200}
    }
    hover_time = {'restart': 0, 'menu': 0}
    max_hover = 30
    my_smoother = math_utils.FingerSmoother(method='ewma', alpha=0.4, adaptive=True)
    
    start_t = time.time()
    wait_s = 2.0  #刚死的时候不能马上点 防误触
    
    while True:
        ok, frame = cap.read()
        if not ok: break
        
        frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        frame = cv2.flip(frame, 1)
        
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


        #延迟显示选项
        if time.time() - start_t > wait_s:
            for k, a in areas.items():
                x, y, w, h = a['x'], a['y'], a['w'], a['h']
                p = hover_time[k] / max_hover
                b_color = (0, 255, 0) if p > 0 else (100, 100, 100)
                cv2.rectangle(frame, (x, y), (x + w, y + h), b_color, 3)
                
                txt = '重新开始' if k == 'restart' else '主菜单'
                config.add_cn_text(txt, (x + 50, y + 110), 40, (255, 255, 255))
                if p > 0:
                    draw_jindu_tiao(frame, a, p)

            rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            lm_list, _ = vision_engine.detect_hands(rgb_img)
            
            if lm_list:
                tip = lm_list[0][8]
                sx, sy = my_smoother.smooth(int(tip.x * config.WINDOW_WIDTH), int(tip.y * config.WINDOW_HEIGHT))
                cv2.circle(frame, (sx, sy), 15, (0, 255, 255), -1)
                
                for k, a in areas.items():
                    if a['x'] <= sx <= a['x'] + a['w'] and a['y'] <= sy <= a['y'] + a['h']:
                        hover_time[k] += 1
                        if hover_time[k] >= max_hover: 
                            config.flush_cn_texts(frame)
                            return k
                    else:
                        hover_time[k] = max(0, hover_time[k] - 2)
            else:
                my_smoother.reset()
                for k in hover_time:
                    hover_time[k] = max(0, hover_time[k] - 2)
        else:
            shengyu = int(wait_s - (time.time() - start_t)) + 1
            config.add_cn_text(f'即将显示选项... {shengyu}', (config.WINDOW_WIDTH//2 - 130, 450), 30, (150, 150, 150))
        
        config.flush_cn_texts(frame)
        cv2.imshow('Swift-Fruit-Slice', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('r'): return 'restart'
        if key == ord('m'): return 'menu'
        if key == ord('q') or key == 27: return 'quit'
