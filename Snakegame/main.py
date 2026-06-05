import math
import cv2
import numpy as np
import os
import cvzone
import random
import time
import threading
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options
import mediapipe as mp
import json

# 新手不懂这俩啥意思，网上抄来去警告的
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['AUTOGRAPH_VERBOSITY'] = '0'

my_mulu = os.path.dirname(os.path.abspath(__file__))
zong_mulu = os.path.dirname(my_mulu)
save_wenjian = os.path.join(my_mulu, "snake_save.json")

# 每一关的分数，本来想写个很复杂的字典，算了先这样
LEVEL_CONFIG = [
    {"level": 1, "score": 5},
    {"level": 2, "score": 10},
]

class my_shoushi_shibie:
    def __init__(self, my_con=0.5, max_shou=1):
        # 找模型文件
        model_path = os.path.join(zong_mulu, 'models', 'hand_landmarker.task')
        # print("模型路径是:", model_path) # 调试用
        
        # 这一坨是配置，官方文档抄的
        opts = vision.HandLandmarkerOptions(
            base_options=base_options.BaseOptions(model_asset_path=model_path, delegate=base_options.BaseOptions.Delegate.CPU),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_shou,
            min_hand_detection_confidence=my_con, # 试了几次，传进来的这个数值最合适
            min_hand_presence_confidence=my_con,
            min_tracking_confidence=my_con,
        )
        self.detector = vision.HandLandmarker.create_from_options(opts)
        self.last_time = 0 

    def find_shou(self, img):
        # 必须转成RGB，不然报错
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

        now_time = int(time.time() * 1000)
        if now_time <= self.last_time:
            now_time = self.last_time + 1
        self.last_time = now_time

        jieguo = self.detector.detect_for_video(mp_img, now_time)
        
        all_shou = []
        if jieguo.hand_landmarks:
            for shou_lm in jieguo.hand_landmarks:
                yige_shou = {'lmList': []}
                h, w, _ = img.shape
                for lm in shou_lm:
                    # 转换坐标，坑死我了之前没乘宽和高
                    yige_shou['lmList'].append([int(lm.x * w), int(lm.y * h), int(lm.z * w)])
                all_shou.append(yige_shou)
                
                # 画点
                for lm in yige_shou['lmList']:
                    cv2.circle(img, (lm[0], lm[1]), 5, (225, 0, 255), cv2.FILLED)
        return all_shou, img

class my_shexiangtou:
    # 搞个多线程摄像头，不然游戏太卡了
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.cap.set(3, 1280)
        self.cap.set(4, 720)
        self.ok, self.frame = self.cap.read()
        self.is_stop = False
        self.suo = threading.Lock() # 加锁防崩溃

    def start(self):
        threading.Thread(target=self.gengxin, daemon=True).start()
        return self

    def gengxin(self):
        while not self.is_stop:
            ok, frame = self.cap.read()
            if ok:
                with self.suo:
                    self.ok = ok
                    self.frame = frame
            else:
                self.is_stop = True

    def get_img(self):
        with self.suo:
            if self.frame is not None:
                return self.ok, self.frame.copy()
            return self.ok, None

    def stop(self):
        self.is_stop = True
        self.cap.release()

class tanchishe_game:
    def __init__(self, food_pic, save_file):
        if not os.path.exists(save_file):
            self.data = {"level": 1, "score": 0}
        else:
            with open(save_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)

        self.is_win = False
        self.is_over = False
        self.she_points = []
        self.she_longs = []
        self.now_len = 0
        self.max_len = 150
        self.last_head = (0, 0)

        self.food_img = cv2.imread(food_pic, cv2.IMREAD_UNCHANGED)
        self.fh, self.fw, _ = self.food_img.shape
        self.food_x = 0
        self.food_y = 0
        self.suiji_food()

        self.level = self.data["level"]
        self.score = self.data["score"]
        self.mubiao_score = self.level * 5

    def save_baocun(self, lv, sc):
        d = {"level": lv, "score": sc}
        with open(save_wenjian, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)

    def suiji_food(self):
        # 随便给个范围
        self.food_x = random.randint(250, 1000)
        self.food_y = random.randint(150, 550)

    def run_logic(self, img, head_pos):
        if self.is_win:
            cvzone.putTextRect(img, "YOU ARE VERY GOOD", (340, 450), scale=5, thickness=5, offset=20)
            return img
        
        if self.is_over:
            cvzone.putTextRect(img, "GAME OVER", (415, 300), scale=5, thickness=5, offset=20)
            cvzone.putTextRect(img, f"YOU Score:{self.score}", [340, 450], scale=5, thickness=5, offset=20)
            cvzone.putTextRect(img, "Start Game PRESS R", [340, 600], scale=5, thickness=5, offset=20)
            return img
            
        hx, hy = head_pos
        lx, ly = self.last_head

        self.she_points.append([hx, hy])
        juli = math.hypot(hx - lx, hy - ly) # 勾股定理算距离
        self.she_longs.append(juli)
        self.now_len += juli
        self.last_head = (hx, hy)

        # 蛇太长了就切尾巴
        if self.now_len > self.max_len:
            for i, l in enumerate(self.she_longs):
                self.now_len -= l
                self.she_longs.pop(i)
                self.she_points.pop(i)
                if self.now_len < self.max_len:
                    break

        # 判断吃没吃到
        if (self.food_x - self.fw//2 < hx < self.food_x + self.fw//2) and (self.food_y - self.fh//2 < hy < self.food_y + self.fh//2):
            self.suiji_food()
            self.max_len += 50
            self.score += 1
            # print("吃到啦！分数:", self.score)

        if len(self.she_points) > 1:
            pts = np.array(self.she_points, np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(img, [pts], False, (0, 0, 255), 20)

            # 画个头
            if self.she_points:
                cv2.circle(img, self.she_points[-1], 20, (200, 0, 200), cv2.FILLED)

            # 画食物，之前没减一半导致位置有点偏，现在修复了
            img = cvzone.overlayPNG(img, self.food_img, (self.food_x - self.fw//2, self.food_y - self.fh//2))

            cvzone.putTextRect(img, f"Score:{self.score}", [50, 80], scale=3, thickness=5, offset=10)
            cvzone.putTextRect(img, f"Level:{self.level}", [50, 150], scale=3, thickness=5, offset=10)

        # 过关
        if self.score >= self.mubiao_score:
            self.is_win = True
            # cv2.imwrite(f"./photo/{self.score}.png", img) # TODO: 以后加个截图功能，先注释掉报错
            self.level += 1
            self.save_baocun(self.level, self.score)
            self.mubiao_score = self.level * 5

        return img

# ================= 游戏主循环 =================
if __name__ == "__main__":
    cam = my_shexiangtou(0).start()
    my_ai = my_shoushi_shibie(my_con=0.8, max_shou=1)
    
    cv2.namedWindow("Food", cv2.WINDOW_NORMAL)
    food_path = os.path.join(my_mulu, "donut.png")
    
    my_game = tanchishe_game(food_path, save_wenjian)
    my_game.is_over = True # 一开始先卡在结束画面等按R

    while True:
        ok, img = cam.get_img()
        if not ok or img is None:
            continue
            
        img = cv2.flip(img, 1) # 像照镜子一样
        
        hands, img = my_ai.find_shou(img)
        
        if hands:
            # 用食指 (第8个点) 当蛇头
            shizhi_x = hands[0]['lmList'][8][0]
            shizhi_y = hands[0]['lmList'][8][1]
            img = my_game.run_logic(img, (shizhi_x, shizhi_y))
            
        cv2.imshow("Food", img)
        an_jian = cv2.waitKey(1)
        
        if my_game.is_win:
            if an_jian != -1: # 随便按个键继续
                my_game.is_win = False
                my_game.is_over = True
        elif an_jian == ord('r'):
            if my_game.is_over:
                my_game.is_over = False
                my_game.max_len = 150
                my_game.she_longs = []
                my_game.she_points = []
                my_game.now_len = 0
                my_game.last_head = (0, 0)
                my_game.suiji_food()
        elif an_jian == ord('q'):
            cam.stop()
            break
            
    cv2.destroyAllWindows()
