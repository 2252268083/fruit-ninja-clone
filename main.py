import os
"""
整个游戏最开始跑的地方
主要就是打开摄像头 调出选模式和刀光的界面
然后再不停地抓画面 找手的位置 划线切水果
"""
import cv2
import math
from collections import deque
import warnings

#去掉警告看着烦
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

def main():#游戏的主函数
    my_cam = config.SETTINGS["camera"]["index"]#从配置里拿摄像头的序号
    cap = cv2.VideoCapture(my_cam)#打开摄像头
    #设一下摄像头的长宽
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.SETTINGS["camera"]["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.SETTINGS["camera"]["height"])
    cv2.namedWindow('Swift-Fruit-Slice')#搞个窗口
    
    config.play_bgm()#游戏一开始就把背景音乐放起来

    while True:#游戏大循环 可以无限次重新开始
        # --- 1. 选模式 ---
        #界面搞得更好看点 现在有点简陋
        moshi = xuanze_moshi_ui(cap)#等玩家选模式
        if moshi == 'quit': break#退出就不玩了
        
        # --- 2. 选刀光 ---
        my_dao = xuanze_daoguang_ui(cap)
        
        my_log.info(f"选了模式: {moshi}")
        my_log.info(f"选了刀光: {my_dao}")
        
        # --- 3. 开始玩 ---
        is_playing = True
        while is_playing:#单局循环
            game = game_core.Game(selected_blade=my_dao, mode=moshi)#弄个新游戏
            
            #准备点追踪手的变量
            max_shou = config.SETTINGS["ai"].get("max_hands", 4)#最多找几只手
            #给每只手建个列表存刀光
            dao_trails = [deque(maxlen=15) for _ in range(max_shou)]
            #搞个平滑器不然刀光乱抖
            pinghua_qis = [math_utils.FingerSmoother(method='ewma', alpha=0.45, adaptive=True) for _ in range(max_shou)]
            #存一下上一帧手在哪 防串线用的
            last_hands = [None] * max_shou

            while not game.game_over:#没死就一直循环
                ok, frame = cap.read()#拿一张图
                if not ok: break
                
                frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))#缩放到固定大小
                frame = cv2.flip(frame, 1)#像照镜子一样翻转一下
                
                #如果是PK中间画条线
                if moshi == 'pk':
                    cv2.line(frame, (640, 0), (640, 720), (100, 100, 100), 2)
                
                rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)#模型要RGB的
                lm_list, _ = vision_engine.detect_hands(rgb_img)#找手
                
                #防串线算法
                #主要是怕两只手交叉的时候认错
                if not lm_list:#没找到手
                    for i in range(max_shou):
                        pinghua_qis[i].reset()#清空平滑器
                        last_hands[i] = None#清空上一帧
                else:
                    #拿到所有食指指尖的坐标
                    now_hands = [{'rx': int(lm[8].x * config.WINDOW_WIDTH), 'ry': int(lm[8].y * config.WINDOW_HEIGHT)} for lm in lm_list[:max_shou]]
                    yong_le_de = set()#记一下哪些刀光分出去了
                    fenpei_hao = {}#当前手对应哪个刀光
                    meifenpei = []#没找到对应刀光的手
                    
                    #遍历当前的手 找上一帧离得最近的
                    for h in now_hands:
                        is_left = h['rx'] < 640#在左边还是右边
                        if moshi == 'pk':
                            #PK的话手不能过界
                            half = max(1, max_shou // 2)
                            xuanze_fanwei = range(0, half) if is_left else range(half, max_shou)
                        else:
                            xuanze_fanwei = range(max_shou)#普通的随便动
                        
                        best_i, min_juli = -1, float('inf')
                        for i in xuanze_fanwei:#在范围里找
                            if last_hands[i] is not None and i not in fenpei_hao.values():
                                #算一下跟上一帧的距离
                                juli = math.hypot(h['rx'] - last_hands[i][0], h['ry'] - last_hands[i][1])
                                if juli < 250 and juli < min_juli:#近的话就当成是同一只手
                                    min_juli, best_i = juli, i
                        
                        if best_i != -1:#找到了
                            fenpei_hao[id(h)] = best_i
                            yong_le_de.add(best_i)
                            sx, sy = pinghua_qis[best_i].smooth(h['rx'], h['ry'])#平滑一下
                            #新增卡路里计算
                            if len(dao_trails[best_i])>0:#如果有滑动
                                last_pt = dao_trails[best_i][-1]#上一帧的坐标点
                                dist = math.hypot(sx - last_pt[0],sy-last_pt[1])#勾股定理计算移动距离
                                game.add_distance(dist , best_i,max_shou)#加入总时长


                            dao_trails[best_i].append((sx, sy))#存进轨迹里
                            last_hands[best_i] = (h['rx'], h['ry'])#更新一下这只手的位置
                        else:
                            meifenpei.append((h, xuanze_fanwei))#没找到就先放着
                    
                    #剩下的手随便分个空闲的刀光
                    for h, xuanze_fanwei in meifenpei:
                        for i in xuanze_fanwei:
                            if i not in yong_le_de:
                                yong_le_de.add(i)
                                sx, sy = pinghua_qis[i].smooth(h['rx'], h['ry'])
                                dao_trails[i].append((sx, sy))
                                last_hands[i] = (h['rx'], h['ry'])
                                break
                    
                    #这一帧没检测到的手就把刀光清了
                    for i in range(max_shou):
                        if i not in yong_le_de:
                            pinghua_qis[i].reset()
                            last_hands[i] = None

                #手拿开的时候刀光一点点消失 比较好看
                for i in range(max_shou):
                    if last_hands[i] is None and len(dao_trails[i]) > 0:
                        for _ in range(min(4, len(dao_trails[i]))):#每次少一点点
                            if dao_trails[i]: dao_trails[i].popleft()

                #画刀光
                pk_yanse = [(0, 255, 255), (255, 0, 255)]#PK模式左黄右紫
                pt_yanse = [(0, 255, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0), (255, 100, 100)]#普通模式花里胡哨的颜色
                for i in range(max_shou):
                    if moshi == 'pk':
                        t_color = pk_yanse[0] if i < (max_shou // 2) else pk_yanse[1]
                    else:
                        t_color = pt_yanse[i % len(pt_yanse)]
                        
                    for j in range(1, len(dao_trails[i])):
                        if dao_trails[i][j-1] and dao_trails[i][j]:
                            cv2.line(frame, dao_trails[i][j-1], dao_trails[i][j], t_color, 3)

                #更新游戏画面
                game.update(dao_trails)#检测切到没
                game.check_collisions(dao_trails)#刷水果和判断掉下去没
                game.draw(frame)#把东西画上去
                mode_name = "增强" if vision_engine.get_mode() == "BOOST" else "正常"
                config.add_cn_text(
                  f"视觉模式：{mode_name}",
                      (40, 90),   # 往下移，避开得分区域
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
                config.flush_cn_texts(frame)#把中文一起画了

                cv2.imshow('Swift-Fruit-Slice', frame)#显示画面


                key = cv2.waitKey(1) & 0xFF
                if key == ord('c'):
                    vision_engine.toggle_environment_mode()

                #按Q退出
                if cv2.waitKey(1) & 0xFF == ord('q'): 
                    is_playing = False
                    break
            
            #死了进结算
            if is_playing:
                #print(f"当前分数: {game.score}")#测试的
                caozuo = jiesuan_ui(cap, game)#调结算UI
                if caozuo == 'menu':#回主菜单
                    break
                elif caozuo == 'quit':#退出游戏
                    is_playing = False

    #关掉所有的东西
    cap.release()#放开摄像头
    cv2.destroyAllWindows()#关窗口

if __name__ == '__main__':
    main()
