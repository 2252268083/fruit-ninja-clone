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

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['AUTOGRAPH_VERBOSITY'] = '0'

# 获取当前脚本所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

class HandDetectorShim:

    def __init__(self,detectionCon=0.5,maxHands=1):
        '''
    手部识别检测的
    进行识别模型 用的是mediapipe库来寻找和识别手部的关键点
        '''


        #找出模型的文件
        model_path = os.path.join(PROJECT_ROOT, 'models', 'hand_landmarker.task')
        if not os.path.exists(model_path):
            print("模型文件不存在") 

        #然后进行模型的识别器参数的调整
        '''
        options = vision.HandLandmarkerOptions(
    base_options=...,                     # 基础配置
    running_mode=...,                     # 运行模式
    num_hands=...,                        # 最大识别手数
    min_hand_detection_confidence=...,    # 手检测置信度阈值
    min_hand_presence_confidence=...,    # 手存在置信度阈值
    min_tracking_confidence=...           # 手跟踪置信度阈值
        '''
        options = vision.HandLandmarkerOptions(
            base_options=base_options.BaseOptions(model_asset_path=model_path,delegate=base_options.BaseOptions.Delegate.CPU),#意思就是告诉他的大脑在哪里 然后用cpu进行计算
            running_mode= vision.RunningMode.VIDEO,#处理的视频流
            num_hands=maxHands,#能识别几只手
            min_hand_detection_confidence=detectionCon,#手部检测的置信度阈值
            min_hand_presence_confidence=detectionCon,#手部存在的置信度阈值
            min_tracking_confidence=detectionCon,#手部跟踪的置信度阈值
        )

        #根据上面配置的手势识别器来进行一个实例化
        self.detector = vision.HandLandmarker.create_from_options(options)
        self.last_timestamp = 0#初始化时间戳
    

    def findHands(self,img,draw=True,flipType=True):
        """
        这个主要就是输入图像，然后把骨骼都关键点画出来
        filptype主要是为了和cvzone的接口一致，保留下来了
        """
        
        #可是mediapipe的图像是rgb的 和opencv的有点不一样 这里要进行一个转换：
        rgb_img = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb_img)#你的普通图像数据转换成 MediaPipe 能处理的图像格式

        #mediapipe处理视频的时候有一个严格的递增的时间戳，=
        timestamp = int(time.time() *1000)#获取当前时间作为时间戳（单位是毫秒）
        if timestamp <= self.last_timestamp:#如果当前时间戳还没有上一帧大 那么手动加一帧
            timestamp = self.last_timestamp + 1
        self.last_timestamp = timestamp

        #调用识别的进行检测
        results = self.detector.detect_for_video(mp_img,timestamp)#调用进行识别 第一个是图像 第二个是时间戳

        #创建一个列表进行存储
        all_hands = []

        if results.hand_landmarks:#如果检测到手
            for landmark in results.hand_landmarks:#遍历所有的手的关键点
                hand = {'lmList':[]}#创建一个字典进行存储
                h,w,_=img.shape#获取图像的高宽
                for lm in landmark:
                    #这里的xyhw是mediapipe的坐标不是上面的高宽哦
                    hand['lmList'].append([int(lm.x*w),int(lm.y*h),int(lm.z*w)])#把mediapipe的坐标转换成opencv的坐标,
                all_hands.append(hand)#把字典添加到列表中
                if draw:
                    #然后现在在画面上进行绘画
                    for lm in hand['lmList']:
                        cv2.circle(img,(lm[0],lm[1]),5,(225,0,255),cv2.FILLED)
                        '''
                        cv2.circle(
    image,               # 目标图像，想在这个图像上画圆
    center,              # 圆心坐标，格式 (x, y)，单位像素
    radius,              # 圆半径，单位像素
    color,               # 颜色，BGR 格式，例如 (蓝, 绿, 红)
    thickness=cv2.FILLED # 线宽，cv2.FILLED 表示填充圆内部
)                       '''
        return all_hands  ,img#返回所有手和画好的图像           


#进行运行
HandDetector = HandDetectorShim



"""
进行定义摄像头，优化摄像头
"""
class VideoSteam:
    def __init__(self,src):
        """
        初始化摄像头
        stc摄像头编号，0通常 1可能外接
        为了能让画面显示完整，设置分辨率为1280*720，防止线程阻塞
        """
        self.cap = cv2.VideoCapture(src)
        self.cap.set(3,1280)
        self.cap.set(4,720)
        self.status, self.frame = self.cap.read()#先读一帧试试
        self.stopped = False#初始化停止标志
        self.lock = threading.Lock()#线程锁,防止多线程读写数据时发生混乱 作用： 同一时间只允许一个线程使用

    def start(self):
        """
        启动后台读取线程
        """
        #创建一个线程，让它去执行update方法
        threading.Thread(target=self.update,args=(),daemon=True).start()
        return self

    def update(self ):
        """这个方法会在后台线程会一直循环运行"""
        while not self.stopped:#只要这个不是停止，那就一直跑
            #读取摄像头数据
            status, frame = self.cap.read()
            if status:#如果这个帧是正常的、
                with self.lock:#线程锁，防止多线程读写数据时发生混乱
                    self.status = status#更新状态
                    self.frame = frame#更新帧数据
            else:

                self.stopped = True#如果获取不到数据就停止

    def read(self):
        """
        主程序通过这个来获取最新的图像"""
        with self.lock:#线程锁，防止多线程读写数据时发生混乱
            return self.status , self.frame.copy() if self .frame is not None else None #如果frame有数据就返回，没有数据就返回None

    def stop (self):
        """停止摄像头的读取"""
        self.stopped = True
        self.cap.release()#释放摄像头资源

LEVEL_CONFIG = [#每一关的点数
    {"level": 1, "score": 5, },
    {"level": 2, "score": 10,},
]

# 存档文件路径
SAVE_FILE = os.path.join(CURRENT_DIR, "snake_save.json")

class SnakGameClass:
    """
    定义游戏的运行的逻辑了
    """

    def __init__(self,pothFood,file):#这个专门用来储存食物的图片的地址
        if not os.path.exists(file):
            self.load = {"level":1,"score":0}
        else:#如果存在
        
            with open(file, "r",encoding="utf-8") as f:
                self.load = json.load(f)

        self.gameWIN = False#游戏是否结束
        self.poins =[]#用于储存蛇的坐标
        self.longs = []#用于储存蛇的长度
        self.start_length = 0#实际的长度
        self.max_length = 150#最大蛇的长度
        self.previousHead = 0,0#用于几率上一个蛇的长度 用来计算蛇的距离

        self.imgfood = cv2.imread(pothFood,cv2.IMREAD_UNCHANGED)#读取食物的图片转换成透明通道
        self.hFood,self.wFood,_ = self.imgfood.shape#获取食物的高宽 获取食物的高宽
        self.foodPoints = 0,0#生成食物的一个坐标i始点
        self.randomFoodlocation()#随机生成食物的坐标,调用下面的函数

        self.current_level = self.load["level"]#获取当前的等级
        self.score = self.load["score"]#初始化分数 先初始化得分
        # self.score_1 = 9999999#初始化分数 先初始化得分
        self.gameOver = False#游戏结束标志
        self.score_1 = self.current_level * 5
    def save_progress(self,a1,a2):
        data = {"level": a1, "score": a2}
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def randomFoodlocation(self):
        """
        随机生成食物的坐标
        """
        self.foodPoints = random.randint(250,1000),random.randint(150,550)#生成食物的一个坐标i始点 生成的坐标在250-1000之间, 150-550之间

    def update(self ,imgmain,currentHead):
        """
        这里就是游戏的运行的逻辑
        imgmain的游戏主的画面
        currentHead当前的头部的坐标(还是得靠手势识别提供的坐标
        """

        if self.gameWIN:
            cvzone.putTextRect(imgmain,f"YOU ARE VRAY GOOD",(340, 450),scale=5,thickness=5,offset=20)
            return imgmain#返回游戏结束画面了
        if self.gameOver:#如果游戏结束了 就不用更新了
            #如果一下结束了就显示gameover和分数
            cvzone.putTextRect(imgmain,f"GAME OVER",(415,300),scale=5,thickness=5,offset=20)#自带底色的文字标签
            #cvzone.putTextRect(图像, "文字内容", [x, y], scale=缩放, thickness=粗细, offset=边距)
            cvzone.putTextRect(imgmain,f"YOU Score:{self.score}",[340, 450],scale=5,thickness=5,offset=20)#只能写英文
            cvzone.putTextRect(imgmain,f"Stert Game PRESS R",[340, 600],scale=5,thickness=5,offset=20)
        
        else:
            #游戏的运行的时候
            

            px , py = self.previousHead#获取上一次头部的坐标

            cx , cy = currentHead#获取当前的头部的坐标,从手势检测里面获取

            self.poins.append([cx,cy])#把当前的头部的坐标添加到蛇的坐标列表中
            a1 = math.hypot(cx-px,cy-py)#计算当前的头部的距离 像勾股定律 直接计算出两点的距离
            #蛇的长度
            self.longs.append(a1)
            self.start_length+=a1#计算蛇的长度
            self.previousHead = cx,cy#更新上一次的头部的坐标
            

    


            # "控制蛇的长度，如果蛇太长了 从尾巴开始缩短"
            if self.start_length > self.max_length:#如果蛇的长度大于最大长度
                for i ,length in enumerate(self.longs):#遍历蛇的长度#i获取到的是第几个元素 length获取到是第几个元素的长度
                    self.start_length-=length#从尾巴开始缩短
                    self.longs.pop(i)#删除蛇的第一个存储进去的长度
                    self.poins.pop(i)#删除蛇的坐标列表中的第一个坐标
                    if self.start_length < self.max_length:#如果蛇的长度小于最大长度
                        break#就退出循环
            

            #判读是否吃到了食物，再检查蛇头和食物的坐标是否重叠。
            if self.foodPoints[0]-self.wFood//2 <cx<self.foodPoints[0]+self.wFood//2 and self.foodPoints[1]-self.hFood//2 <cy<self.foodPoints[1]+self.hFood//2: #这里是创建图片的墙左墙 < 蛇头 X < 右墙 and 蛇头 Y < 下墙 b
                """如果碰到了"""
                self.randomFoodlocation()#随机生成食物的坐标
                self.max_length+=50#蛇的长度增加
                self.score+=1#分数增加

            if len(self.poins)>1:#如果蛇的坐标dictionary长度大于1

                #一次性画出整条蛇
                pts = np.array(self.poins, np.int32)#把蛇的坐标列表转换成numpy的数组
                pts = pts.reshape((-1,1,2))#把数组的维度变成2维
                cv2.polylines(imgmain,[pts],False,(0,0,255),20)#画出蛇的线条

                #画蛇的头
                if self.poins:
                    cv2.circle(imgmain,self.poins[-1],20,(200,0,200),cv2.FILLED)


                imgmain = cvzone.overlayPNG(imgmain,self.imgfood,
                (self.foodPoints[0]-self.wFood//2,self.foodPoints[1]-self.hFood//2)

                ) #将食物图片画在图片上

                cvzone.putTextRect(imgmain,f"Score:{self.score}",[50, 80],scale=3,thickness=5,offset=10)
                cvzone.putTextRect(imgmain,f"The :{self.current_level }Pass",[50,150],scale=3,thickness=5,offset=10)
            if self.score >=self.score_1:
                self.gameWIN = True
                

                cv2.imwrite(f"./photo/{self.score}.png",imgmain)#过关截图
                self.current_level+=1
                self.save_progress(self.current_level,self.score)
                self.score_1 =self.current_level*5


                
        return imgmain#返回后面的画面了

                



url=0#摄像头的编号
vs = VideoSteam(url).start()

#创建一个模型识别器
detector = HandDetector(detectionCon=0.8,maxHands=1)#创建手部识别器


#创建一个贪吃蛇的示例
cv2.namedWindow("Food",cv2.WINDOW_NORMAL)

#创建游戏的示例
game = SnakGameClass(os.path.join(CURRENT_DIR, "donut.png"), SAVE_FILE)

game.gameOver = True#默认游戏没有开始

while True:
    #读取摄像头数据
    status, img = vs.read()
    if not status or img is None:#如果摄像头没有数据了 或者 数据为空
        continue
    img = cv2.flip(img,1)#左右翻转图像

    hands ,img = detector.findHands(img,flipType=False)#进行手部识别


    if hands:#如果识别到了手
        lmList = hands[0]['lmList']#获取到手的关键点
        
        #我们用食指来确定蛇头
        paintdex =tuple(lmList[8][0:2])#获取食指的坐标
        img = game.update(img,paintdex)#更新游戏的画面

    cv2.imshow("Food",img)#显示图像
    key = cv2.waitKey(1)
    if game.gameWIN:
        if key != -1:
            game.gameWIN = False
            game.gameOver = True
            

    elif key == ord('r'):#如果按下r键 就重新开始游戏
        if game.gameOver:
           game.gameOver = False


           game.max_length = 150
           game.longs = []
           game.poins = []
           game.start_length = 0
           game.previousHead = 0,0
           game.randomFoodlocation()
    elif key == ord('q'):
        vs.stop()
        break
cv2.destroyAllWindows()#关闭所有窗口















        





        






                