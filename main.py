import os
import cv2
import math
from collections import deque
import warnings

# 抑制各种无用警告
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['GLOG_minloglevel'] = '2'
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf.symbol_database')

import config
import math_utils
import vision_engine
import game_core
from logger import logger
from ui_screens import mode_selection_screen, blade_selection_screen, end_game_menu_visual

def main():
    camera_index = config.SETTINGS["camera"]["index"]
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.SETTINGS["camera"]["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.SETTINGS["camera"]["height"])
    cv2.namedWindow('Swift-Fruit-Slice')

    while True:
        mode = mode_selection_screen(cap)
        if mode == 'quit': break
        
        selected_blade = blade_selection_screen(cap)
        
        logger.info(f"游戏模式: {'双手模式' if mode == 'dual' else ('双人PK' if mode == 'pk' else '单手模式')}")
        logger.info(f"刀光: {selected_blade}")
        
        game_running = True
        while game_running:
            game = game_core.Game(selected_blade=selected_blade, mode=mode)
            
            # 使用配置文件中定义的槽位数量
            n_hands = config.SETTINGS["ai"].get("max_hands", 4)
            trail_list = [deque(maxlen=15) for _ in range(n_hands)]
            smoothers = [math_utils.FingerSmoother(method='ewma', alpha=0.45, adaptive=True) for _ in range(n_hands)]
            last_pos = [None] * n_hands

            while not game.game_over:
                ret, frame = cap.read()
                if not ret: break
                
                frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
                frame = cv2.flip(frame, 1)
                
                # 如果是PK模式，画出分界线
                if mode == 'pk':
                    cv2.line(frame, (640, 0), (640, 720), (100, 100, 100), 2)
                
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                lm_list, _ = vision_engine.detect_hands(rgb)
                
                # ==========================
                # 核心防串线追踪逻辑
                # ==========================
                if not lm_list:
                    for i in range(n_hands):
                        smoothers[i].reset()
                        last_pos[i] = None
                else:
                    raw_hands = [{'rx': int(lm[8].x * config.WINDOW_WIDTH), 'ry': int(lm[8].y * config.WINDOW_HEIGHT)} for lm in lm_list[:n_hands]]
                    active_slots = set()
                    assigned_slots = {}
                    unassigned = []
                    
                    # 优先贪心匹配已有的轨迹
                    for h in raw_hands:
                        is_left = h['rx'] < 640
                        # 只有在 PK 模式下，才把手限制在左右屏幕；否则全局分配
                        if mode == 'pk':
                            half_hands = max(1, n_hands // 2)
                            candidate_range = range(0, half_hands) if is_left else range(half_hands, n_hands)
                        else:
                            candidate_range = range(n_hands)
                        
                        best_slot, best_dist = -1, float('inf')
                        for i in candidate_range:
                            if last_pos[i] is not None and i not in assigned_slots.values():
                                dist = math.hypot(h['rx'] - last_pos[i][0], h['ry'] - last_pos[i][1])
                                if dist < 250 and dist < best_dist:
                                    best_dist, best_slot = dist, i
                        
                        if best_slot != -1:
                            assigned_slots[id(h)] = best_slot
                            active_slots.add(best_slot)
                            sx, sy = smoothers[best_slot].smooth(h['rx'], h['ry'])
                            trail_list[best_slot].append((sx, sy))
                            last_pos[best_slot] = (h['rx'], h['ry'])
                        else:
                            unassigned.append((h, candidate_range))
                    
                    # 将新进入画面的手，分配到空的槽位
                    for h, candidate_range in unassigned:
                        for i in candidate_range:
                            if i not in active_slots:
                                active_slots.add(i)
                                sx, sy = smoothers[i].smooth(h['rx'], h['ry'])
                                trail_list[i].append((sx, sy))
                                last_pos[i] = (h['rx'], h['ry'])
                                break
                    
                    # 清理未匹配到的槽位
                    for i in range(n_hands):
                        if i not in active_slots:
                            smoothers[i].reset()
                            last_pos[i] = None

                # 优雅的刀光渐隐 (关键修复！不能直接 clear)
                for i in range(n_hands):
                    if last_pos[i] is None and len(trail_list[i]) > 0:
                        # 每帧弹出最多 4 个点，让断触的刀光平滑消失，而不是瞬间灭掉
                        for _ in range(min(4, len(trail_list[i]))): 
                            if trail_list[i]: trail_list[i].popleft()

                # 渲染最终轨迹
                pk_colors = [(0, 255, 255), (255, 0, 255)]  # 左边黄色，右边紫色
                normal_colors = [(0, 255, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0), (255, 100, 100), (100, 255, 100), (100, 100, 255), (200, 200, 200)]
                for idx in range(n_hands):
                    if mode == 'pk':
                        # PK模式下，前一半的槽位给左边(黄色)，后一半给右边(紫色)
                        t_color = pk_colors[0] if idx < (n_hands // 2) else pk_colors[1]
                    else:
                        # 正常模式循环使用颜色
                        t_color = normal_colors[idx % len(normal_colors)]
                        
                    for i in range(1, len(trail_list[idx])):
                        if trail_list[idx][i-1] and trail_list[idx][i]:
                            cv2.line(frame, trail_list[idx][i-1], trail_list[idx][i], t_color, 3)

                game.update(trail_list)
                game.check_collisions(trail_list)
                game.draw(frame)
                
                config.flush_cn_texts(frame)
                cv2.imshow('Swift-Fruit-Slice', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'): 
                    game_running = False
                    break
            
            # 结算界面跳转
            if game_running:
                action = end_game_menu_visual(cap, game)
                if action == 'menu':
                    break
                elif action == 'quit':
                    game_running = False

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()