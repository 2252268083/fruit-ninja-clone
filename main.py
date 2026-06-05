import os
import cv2
import math
from collections import deque
import warnings

# 去掉烦人的警告
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['GLOG_minloglevel'] = '2'
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf.symbol_database')

import config
import math_utils
import vision_engine
import game_core
from logger import my_log
from ui_screens import xuanze_moshi_ui, xuanze_daoguang_ui, jiesuan_ui

def main():
    my_cam = config.SETTINGS["camera"]["index"]
    cap = cv2.VideoCapture(my_cam)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.SETTINGS["camera"]["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.SETTINGS["camera"]["height"])
    cv2.namedWindow('Swift-Fruit-Slice')

    while True:
        # TODO: 把界面搞得更好看点，现在有点简陋
        moshi = xuanze_moshi_ui(cap)
        if moshi == 'quit': break
        
        my_dao = xuanze_daoguang_ui(cap)
        
        my_log.info(f"选了模式: {moshi}")
        my_log.info(f"选了刀光: {my_dao}")
        
        is_playing = True
        while is_playing:
            game = game_core.Game(selected_blade=my_dao, mode=moshi)
            
            # 最大手部数量
            max_shou = config.SETTINGS["ai"].get("max_hands", 4)
            # 存刀光轨迹，15个点差不多了
            dao_trails = [deque(maxlen=15) for _ in range(max_shou)]
            pinghua_qis = [math_utils.FingerSmoother(method='ewma', alpha=0.45, adaptive=True) for _ in range(max_shou)]
            last_hands = [None] * max_shou

            while not game.game_over:
                ok, frame = cap.read()
                if not ok: break
                
                frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
                frame = cv2.flip(frame, 1) # 像照镜子一样
                
                # 双人PK画条线
                if moshi == 'pk':
                    cv2.line(frame, (640, 0), (640, 720), (100, 100, 100), 2)
                
                rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                lm_list, _ = vision_engine.detect_hands(rgb_img)
                
                # ==========================
                # 追踪手势，防串线（写了好久，终于不乱飞了）
                # ==========================
                if not lm_list:
                    for i in range(max_shou):
                        pinghua_qis[i].reset()
                        last_hands[i] = None
                else:
                    # 获取每只手的食指尖坐标
                    now_hands = [{'rx': int(lm[8].x * config.WINDOW_WIDTH), 'ry': int(lm[8].y * config.WINDOW_HEIGHT)} for lm in lm_list[:max_shou]]
                    yong_le_de = set()
                    fenpei_hao = {}
                    meifenpei = []
                    
                    # 先就近匹配，贪心算法
                    for h in now_hands:
                        is_left = h['rx'] < 640
                        if moshi == 'pk':
                            # PK模式强制分左右边
                            half = max(1, max_shou // 2)
                            xuanze_fanwei = range(0, half) if is_left else range(half, max_shou)
                        else:
                            xuanze_fanwei = range(max_shou)
                        
                        best_i, min_juli = -1, float('inf')
                        for i in xuanze_fanwei:
                            if last_hands[i] is not None and i not in fenpei_hao.values():
                                juli = math.hypot(h['rx'] - last_hands[i][0], h['ry'] - last_hands[i][1])
                                if juli < 250 and juli < min_juli: # 距离太远肯定是另一只手
                                    min_juli, best_i = juli, i
                        
                        if best_i != -1:
                            fenpei_hao[id(h)] = best_i
                            yong_le_de.add(best_i)
                            sx, sy = pinghua_qis[best_i].smooth(h['rx'], h['ry'])
                            dao_trails[best_i].append((sx, sy))
                            last_hands[best_i] = (h['rx'], h['ry'])
                        else:
                            meifenpei.append((h, xuanze_fanwei))
                    
                    # 剩下的随便分给空位
                    for h, xuanze_fanwei in meifenpei:
                        for i in xuanze_fanwei:
                            if i not in yong_le_de:
                                yong_le_de.add(i)
                                sx, sy = pinghua_qis[i].smooth(h['rx'], h['ry'])
                                dao_trails[i].append((sx, sy))
                                last_hands[i] = (h['rx'], h['ry'])
                                break
                    
                    # 没用到的位置清空
                    for i in range(max_shou):
                        if i not in yong_le_de:
                            pinghua_qis[i].reset()
                            last_hands[i] = None

                # 修复：手离开屏幕时刀光突然消失很难看，改成了渐隐
                for i in range(max_shou):
                    if last_hands[i] is None and len(dao_trails[i]) > 0:
                        for _ in range(min(4, len(dao_trails[i]))): 
                            if dao_trails[i]: dao_trails[i].popleft()

                # 画刀光
                pk_yanse = [(0, 255, 255), (255, 0, 255)]  # 左边黄，右边紫
                pt_yanse = [(0, 255, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0), (255, 100, 100)]
                for i in range(max_shou):
                    if moshi == 'pk':
                        t_color = pk_yanse[0] if i < (max_shou // 2) else pk_yanse[1]
                    else:
                        t_color = pt_yanse[i % len(pt_yanse)]
                        
                    for j in range(1, len(dao_trails[i])):
                        if dao_trails[i][j-1] and dao_trails[i][j]:
                            cv2.line(frame, dao_trails[i][j-1], dao_trails[i][j], t_color, 3)

                game.update(dao_trails)
                game.check_collisions(dao_trails)
                game.draw(frame)
                
                config.flush_cn_texts(frame)
                cv2.imshow('Swift-Fruit-Slice', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'): 
                    is_playing = False
                    break
            
            # 死掉了去结算
            if is_playing:
                # print(f"当前分数: {game.score}") # 测试
                caozuo = jiesuan_ui(cap, game)
                if caozuo == 'menu':
                    break
                elif caozuo == 'quit':
                    is_playing = False

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
