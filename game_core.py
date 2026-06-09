"""
游戏的核心逻辑，包括水果、炸弹、玩家、特效等所有游戏内实体的定义与行为。
物理引擎、碰撞检测、计分规则、游戏主循环的更新与绘制。
"""
import cv2
import math
import random
import time
import config

class my_wanjia:
    # 玩家类，存分数的
    def __init__(self):
        self.score = 0

class my_shuiguo: # 定义单个水果的属性和行为
    # 简单的单个水果
    def __init__(self): # 初始化一个水果
        self.x = random.randint(100, config.WINDOW_WIDTH - 100) # 水果的初始x坐标，从屏幕下方冒出
        self.y = config.WINDOW_HEIGHT + 50 # 水果的初始y坐标
        self.fruit_type = random.choice(config.FRUIT_TYPES) # 随机选一种水果类型
        self.images = config.FRUIT_IMAGES.get(self.fruit_type) # 从配置中获取该水果的图片
        if self.images and self.images['whole'] is not None:
            h, w = self.images['whole'].shape[:2]
            self.radius = max(w, h) // 2 # 根据图片大小计算碰撞半径
        else:
            self.radius = 50 # 如果没有图片，给一个默认半径
            
        # 物理引擎参数：模拟抛物线运动（真实）
        self.vx = random.uniform(-2, 2) # 水平速度
        self.vy = random.uniform(-19, -15) # 垂直初速度（向上抛）
        self.gravity = 0.32 # 重力加速度
        self.rot = random.uniform(0, 360) # 初始旋转角度
        self.rot_spd = random.uniform(-5, 5) # 旋转速度
        self.is_cut = False # 是否被切开的标志
        self.cut_pieces = [] # 存放切开后碎片的列表
        self.entered = False # 是否已经完全进入屏幕的标志

    def update(self): # 每帧更新水果的状态
        if not self.is_cut: # 如果水果还没被切开
            self.vy += self.gravity # 模拟重力，垂直速度增加
            self.x += self.vx # 更新水平位置
            self.y += self.vy # 更新垂直位置
            self.rot += self.rot_spd # 更新旋转角度
            # 判断有没有进屏幕，没进的话就不算漏掉
            if not self.entered and 0 <= self.y <= config.WINDOW_HEIGHT - 50:
                self.entered = True # 标记为已进入屏幕
        else:
            # 如果被切开了，则更新所有碎片的状态
            for p in self.cut_pieces:
                p['vy'] += self.gravity * 2.0 # 碎片的重力加速度更大，掉落更快
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['rot'] += p['rot_spd']
                p['alpha'] -= 4 # 碎片逐渐消失

    def draw(self, frame): # 把水果画到屏幕上
        if not self.is_cut: # 如果没被切开
            if self.images and self.images['whole'] is not None:
                # 调用config里的函数，把完整的带旋转的水果图片贴到游戏画面上
                config.overlay_image(frame, self.images['whole'], int(self.x), int(self.y), self.rot)
            else:
                # 没图片就画个圆圈代替一下，方便调试
                cv2.circle(frame, (int(self.x), int(self.y)), 40, (0, 255, 255), -1)
        else:
            # 如果切开了，就画所有的碎片
            for p in self.cut_pieces:
                if p['alpha'] > 0: # 只画没完全消失的碎片
                    config.overlay_image(frame, p['image'], int(p['x']), int(p['y']), p['rot'], p['alpha'] / 255.0)

    def cut(self, _=0): # 水果被切开的逻辑
        self.is_cut = True # 标记为已切开
        if not self.images: return # 如果没有图片，直接返回
        
        # 分成左右两半，给一个随机弹开的速度
        for img, dx in [(self.images['left'], -1), (self.images['right'], 1)]:
            if img is not None:
                self.cut_pieces.append({ # 添加一个碎片到列表
                    'x': self.x, 'y': self.y, 'image': img,
                    'vx': random.uniform(4, 7) * dx, # 水平弹开速度
                    'vy': random.uniform(-3, 2), # 垂直弹开速度
                    'rot': self.rot,
                    'rot_spd': random.uniform(4, 8) * dx, # 旋转速度
                    'alpha': 255 # 初始透明度为不透明
                })

    def is_out(self): # 判断水果是否已经掉出屏幕外
        # 看看是不是掉出屏幕下面了
        if not self.is_cut:
            return self.y > config.WINDOW_HEIGHT + 150 # 完整水果的判断
        return all(p['alpha'] <= 0 or p['y'] > config.WINDOW_HEIGHT + 150 for p in self.cut_pieces) # 所有碎片都掉出去了

    def check_hit(self, trail): # 检查是否被刀光轨迹切中
        if self.is_cut or len(trail) < 2: return False # 如果已切开或轨迹点太少，则不判断
        
        # 简化的碰撞检测：只判断刀光轨迹上的点是否在水果的半径内
        # TODO: 以后试试算线段和圆的交点，现在只算点到圆心的距离，偶尔会漏切
        for pt in list(trail)[-15:]: # 取最新的15个轨迹点进行检测
            if pt and math.hypot(pt[0] - self.x, pt[1] - self.y) < self.radius * 0.85: # 勾股定理算距离
                return True # 如果距离小于半径，则认为切中
        return False

# (多切块水果和炸弹逻辑差不多，照着上面改一下名字)
class my_duo_shuiguo: # 定义能切成多块的水果（如西瓜）
    # 比如西瓜这种能切好几块的
    def __init__(self): # 初始化一个多块水果
        self.x = random.randint(100, config.WINDOW_WIDTH - 100)
        self.y = config.WINDOW_HEIGHT + 50
        self.fruit_type = random.choice(config.MULTI_FRUIT_TYPES) # 从多块水果类型中随机选一个
        self.images = config.MULTI_FRUIT_IMAGES.get(self.fruit_type) # 获取对应的图片资源
        if self.images and self.images['whole'] is not None:
            h, w = self.images['whole'].shape[:2]
            self.radius = max(w, h) // 2 # 计算碰撞半径
        else:
            self.radius = 55 # 默认半径
        self.vx = random.uniform(-1.5, 1.5) # 水平速度
        self.vy = random.uniform(-18, -14) # 垂直速度
        self.gravity = 0.3 # 重力
        self.rot = random.uniform(0, 360) # 旋转
        self.rot_spd = random.uniform(-4, 4) # 旋转速度
        self.is_cut = False # 是否被切开
        self.cut_pieces = [] # 切开的碎片
        self.entered = False # 是否已进入屏幕

    def update(self): # 每帧更新状态
        if not self.is_cut: # 如果没被切开，做抛物线运动
            self.vy += self.gravity
            self.x += self.vx
            self.y += self.vy
            self.rot += self.rot_spd
            if not self.entered and 0 <= self.y <= config.WINDOW_HEIGHT - 50:
                self.entered = True
        else: # 如果被切开了，更新所有碎块的状态
            for p in self.cut_pieces:
                p['vy'] += self.gravity * 2.0
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['rot'] += p['rot_spd']
                p['alpha'] -= 4 # 碎块逐渐消失

    def draw(self, frame): # 绘制水果到屏幕
        if not self.is_cut: # 如果没被切开，画完整的水果
            if self.images and self.images['whole'] is not None:
                config.overlay_image(frame, self.images['whole'], int(self.x), int(self.y), self.rot)
            else:
                cv2.circle(frame, (int(self.x), int(self.y)), 45, (0, 200, 200), -1) # 没图就画个圈
        else: # 如果切开了，画所有碎块
            for p in self.cut_pieces:
                if p['alpha'] > 0:
                    config.overlay_image(frame, p['image'], int(p['x']), int(p['y']), p['rot'], p['alpha'] / 255.0)

    def cut(self, angle=0): # 切开的逻辑
        self.is_cut = True
        if not self.images or 'pieces' not in self.images: return
        
        cnt = self.images['piece_count'] # 获取碎块数量
        step = 360 / cnt # 计算每个碎块之间的角度
        for i, img in enumerate(self.images['pieces']): # 遍历所有碎块图片
            a = math.radians(i * step) # 计算每个碎块的初始弹飞角度
            spd = random.uniform(5, 9) # 随机的弹飞速度
            self.cut_pieces.append({
                'x': self.x, 'y': self.y, 'image': img,
                'vx': math.cos(a) * spd, # 根据角度计算水平速度
                'vy': math.sin(a) * spd - 1, # 根据角度计算垂直速度
                'rot': self.rot + random.uniform(-30, 30),
                'rot_spd': random.uniform(-8, 8),
                'alpha': 255
            })

    def is_out(self): # 判断是否掉出屏幕
        if not self.is_cut: return self.y > config.WINDOW_HEIGHT + 150
        return all(p['alpha'] <= 0 or p['y'] > config.WINDOW_HEIGHT + 150 for p in self.cut_pieces)

    def check_hit(self, trail): # 碰撞检测
        if self.is_cut or len(trail) < 2: return False
        for pt in list(trail)[-15:]:
            if pt and math.hypot(pt[0] - self.x, pt[1] - self.y) < self.radius * 0.85: return True
        return False


class my_zhadan: # 定义炸弹的属性和行为
    # 炸弹，切到了扣分或者直接死
    def __init__(self, bomb_type='normal'): # 初始化一个炸弹
        self.x = random.randint(100, config.WINDOW_WIDTH - 100)
        self.y = config.WINDOW_HEIGHT + 50
        self.bomb_type = bomb_type # 炸弹类型（'normal' 普通, 'deadly' 致命）
        self.image = config.BOMB_IMAGES.get('bomb2' if bomb_type == 'deadly' else 'bomb1') # 根据类型获取图片
        if self.image is not None:
            h, w = self.image.shape[:2]
            self.radius = max(w, h) // 2 # 计算碰撞半径
        else:
            self.radius = 45 # 默认半径
        self.vx = random.uniform(-1, 1) # 水平速度
        self.vy = random.uniform(-17, -13) # 垂直速度
        self.gravity = 0.3 # 重力
        self.rot = random.uniform(0, 360) # 旋转
        self.rot_spd = random.uniform(-4, 4) # 旋转速度
        self.is_exploded = False # 是否已爆炸
        self.entered = False # 是否已进入屏幕
        self.exp_frame = 0 # 爆炸动画的当前帧
        self.exp_max = 20 # 爆炸动画的总持续帧数

    def update(self): # 每帧更新炸弹状态
        if not self.is_exploded: # 如果没爆炸，就做物理运动
            self.vy += self.gravity
            self.x += self.vx
            self.y += self.vy
            self.rot += self.rot_spd
            if not self.entered and 0 <= self.y <= config.WINDOW_HEIGHT - 50:
                self.entered = True
        else: # 如果爆炸了，就播放爆炸动画
            self.exp_frame += 1

    def draw(self, frame): # 绘制炸弹
        if not self.is_exploded: # 如果没爆炸，画炸弹本身
            if self.image is not None:
                config.overlay_image(frame, self.image, int(self.x), int(self.y), self.rot)
            else: # 没图就画个圈
                color = (0, 0, 255) if self.bomb_type == 'deadly' else (0, 0, 0)
                cv2.circle(frame, (int(self.x), int(self.y)), 40, color, -1)
        elif self.exp_frame < self.exp_max: # 如果正在爆炸，画爆炸特效
            key = 'explosion1' if self.exp_frame % 4 < 2 else 'explosion2' # 两张爆炸图片交替，形成闪烁效果
            img = config.BOMB_IMAGES.get(key)
            if img is not None:
                a = 1.0 - self.exp_frame / self.exp_max # 透明度随时间递减
                config.overlay_image(frame, img, int(self.x), int(self.y), 0, a)

    def explode(self): # 触发爆炸
        self.is_exploded = True
        self.exp_frame = 0

    def is_out(self): # 判断是否飞出屏幕
        if not self.is_exploded: return self.y > config.WINDOW_HEIGHT + 150
        return self.exp_frame >= self.exp_max # 爆炸动画播放完毕也算飞出

    def check_hit(self, trail): # 碰撞检测
        if self.is_exploded or len(trail) < 2: return False
        for pt in list(trail)[-15:]:
            if pt and math.hypot(pt[0] - self.x, pt[1] - self.y) < self.radius * 0.85: return True
        return False


class Effect_Lianji: # 定义连击（Combo）特效
    def __init__(self, combo): # 初始化特效
        self.x = config.WINDOW_WIDTH // 2
        self.y = config.WINDOW_HEIGHT // 2 - 100
        self.alpha = 0 # 初始透明度
        self.scale = 0.5 # 初始缩放
        self.frame = 0 # 当前播放帧
        self.dur = 45 # 总持续帧数
        # 根据连击数选择不同的特效图片
        self.key = ('combo3' if combo >= 12 else 'combo2' if combo >= 7 else 'combo1' if combo >= 3 else None)

    def update(self): # 每帧更新特效状态（实现淡入淡出和缩放动画）
        self.frame += 1
        if self.frame < 10: # 0-10帧：淡入、放大
            self.alpha = int(255 * self.frame / 10)
            self.scale = 0.5 + self.frame / 10 * 0.5
        elif self.frame < 35: # 10-35帧：保持状态
            self.alpha = 255
            self.scale = 1.0
        else: # 35-45帧：淡出、放大
            p = (self.frame - 35) / 10
            self.alpha = int(255 * (1 - p))
            self.scale = 1.0 + p * 0.15

    def done(self): return self.frame >= self.dur # 判断特效是否播放完毕

    def draw(self, frame): # 绘制特效
        if not self.key or self.key not in config.COMBO_IMAGES: return
        img = config.COMBO_IMAGES[self.key]
        h, w = img.shape[:2]
        # 根据当前的缩放和透明度来绘制图片
        sc = cv2.resize(img, (int(w * self.scale), int(h * self.scale)))
        config.overlay_image(frame, sc, int(self.x), int(self.y), 0, self.alpha / 255.0)

class Effect_Daoguang: # 定义切水果时的刀光特效
    def __init__(self, x, y, angle): # 初始化
        self.x = x; self.y = y; self.angle = angle
        self.alpha = 255; self.scale = 1.0
        self.frame = 0; self.dur = 15 # 动画持续15帧

    def update(self): # 每帧更新
        self.frame += 1
        self.alpha = int(255 * (1 - self.frame / self.dur)) # 透明度随时间线性降低
        self.scale = 1.0 + self.frame / self.dur * 0.25 # 缩放随时间线性增大

    def done(self): return self.frame >= self.dur # 判断是否播放完毕

    def draw(self, frame, blade_img): # 绘制刀光
        if blade_img is None: return
        h, w = blade_img.shape[:2]
        sc = cv2.resize(blade_img, (int(w * self.scale), int(h * self.scale)))
        config.overlay_image(frame, sc, int(self.x), int(self.y), self.angle, self.alpha / 255.0)

class Effect_Guozhi: # 定义果汁喷溅特效
    def __init__(self, x, y, juice_img): # 初始化
        self.x = x; self.y = y; self.img = juice_img
        self.alpha = 255; self.scale = 1.0
        self.frame = 0; self.dur = 18 # 持续18帧

    def update(self): # 每帧更新
        self.frame += 1
        if self.frame < self.dur * 0.5: # 前半段时间，保持不透明
            self.alpha = 255
        else: # 后半段时间，逐渐消失
            p = (self.frame - self.dur * 0.5) / (self.dur * 0.5)
            self.alpha = int(255 * (1 - p))
            self.scale = 1.0 + self.frame / self.dur * 0.5 # 同时逐渐放大

    def done(self): return self.frame >= self.dur # 判断是否播放完毕

    def draw(self, frame): # 绘制果汁
        if self.img is None: return
        h, w = self.img.shape[:2]
        sc = cv2.resize(self.img, (int(w * self.scale), int(h * self.scale)))
        config.overlay_image(frame, sc, int(self.x), int(self.y), 0, min(255, max(0, self.alpha)) / 255.0)


class Game: # 游戏主控制类，管理整个游戏的逻辑、状态和实体
    # 游戏主控制类
    def __init__(self, selected_blade='dao1', mode='single'): # 初始化一局新游戏
        # 游戏实体列表
        self.fruits = [] # 普通水果
        self.multi_fruits = [] # 多块水果
        self.bombs = [] # 炸弹
        
        # 特效列表
        self.slash_fx = [] # 刀光特效
        self.combo_fx = [] # 连击特效
        self.juice_fx = [] # 果汁特效
        
        self.selected_blade = selected_blade # 当前选择的刀光皮肤
        self.mode = mode # 游戏模式 ('single', 'dual', 'pk')
        
        # 游戏状态变量
        self.score = 0 # 分数
        self.missed = 0 # 漏掉的水果数
        self.bombs_hit = 0 # 切到的炸弹数
        self.combo = 0 # 当前连击数
        self.max_combo = 0 # 本局最大连击数
        
        self.spawn_timer = 0 # 水果生成计时器
        self.spawn_interval = config.SETTINGS["game"].get("spawn_interval", 12) # 水果生成间隔
        
        self.game_over = False # 游戏是否结束
        self.game_over_reason = "" # 游戏结束原因
        self.max_missed = 10 # 最大允许漏掉数
        self.max_bombs_hit = 3 # 最大允许碰到炸弹数
        
        self.max_on_screen = config.SETTINGS["game"].get("max_on_screen", 15) # 屏幕上最多有多少个物体
        self.bomb_chance = 0.22 # 生成炸弹的概率
        self.deadly_chance = 0.25 # 生成致命炸弹的概率
        self.multi_chance = 0.15 # 生成多块水果的概率
        
        self.consec_bombs = 0 # 连续生成炸弹的计数器
        self.max_consec_bombs = 2 # 最大连续生成炸弹数，防止满屏都是炸弹
        
        # 双人PK模式专用变量
        self.p1 = my_wanjia() # 玩家1
        self.p2 = my_wanjia() # 玩家2
        self.start_time = time.time() # PK模式开始时间
        self.total_time = 30.0 # PK模式总时长
        self.winner = '' # 获胜者
        
        self.suiji_shengcheng() # 初始化时就生成第一波水果

    def get_time_left(self) -> float: # 获取PK模式的剩余时间
        return max(0.0, self.total_time - (time.time() - self.start_time))

    def suiji_shengcheng(self): # 随机生成一个游戏物体（水果或炸弹）
        # 随机扔个东西出来，不要连续扔太多炸弹
        if self.consec_bombs >= self.max_consec_bombs: # 如果连续生成的炸弹太多
            self._shengcheng_shuiguo() # 就强制生成一个水果
            self.consec_bombs = 0
            return
            
        r = random.random() # 生成一个0到1的随机数
        if r < self.bomb_chance: # 按概率生成炸弹
            bt = 'deadly' if random.random() < self.deadly_chance else 'normal' # 再按概率决定是普通炸弹还是致命炸弹
            self.bombs.append(my_zhadan(bt))
            self.consec_bombs += 1
        elif r < self.bomb_chance + self.multi_chance: # 按概率生成多块水果
            self.multi_fruits.append(my_duo_shuiguo())
            self.consec_bombs = 0
        else: # 否则生成普通水果
            self.fruits.append(my_shuiguo())
            self.consec_bombs = 0

    def _shengcheng_shuiguo(self): # 专门用于生成水果（普通或多块）
        if random.random() < 0.3: # 30%概率生成多块水果
            self.multi_fruits.append(my_duo_shuiguo())
        else: # 70%概率生成普通水果
            self.fruits.append(my_shuiguo())

    def check_collisions(self, trail_list): # 负责处理所有的碰撞检测和游戏逻辑更新
        if self.game_over: return # 游戏结束了就什么都不做

        # --- PK模式的胜负判断 ---
        if self.mode == 'pk' and self.get_time_left() <= 0:
            self.game_over = True
            if self.p1.score > self.p2.score:
                self.winner = 'p1'
            elif self.p2.score > self.p1.score:
                self.winner = 'p2'
            else:
                self.winner = 'draw'
            return

        # --- 游戏物体的生成 ---
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_interval: # 如果达到了生成间隔
            self.spawn_timer = 0
            if len(self.fruits) + len(self.multi_fruits) + len(self.bombs) < self.max_on_screen:
                # 每次多丢几个，不然太无聊了
                for _ in range(random.randint(2, 4)):
                    self.suiji_shengcheng()

        # --- 游戏物体的状态更新与越界判断 ---
        for f in self.fruits:
            f.update() # 更新水果位置
            if not f.is_cut and f.is_out() and f.entered: # 如果水果没被切到，但掉出屏幕了
                if self.mode != 'pk': # PK模式不计漏掉
                    self.missed += 1 # 漏掉数+1
                    self.combo = 0 # 连击清零
                    if self.missed >= self.max_missed: # 如果漏掉太多
                        self.game_over = True # 游戏结束
                        self.game_over_reason = "漏掉的水果太多啦！"
                        
        for mf in self.multi_fruits:
            mf.update()
            if not mf.is_cut and mf.is_out() and mf.entered:
                if self.mode != 'pk':
                    self.missed += 1
                    self.combo = 0
                    if self.missed >= self.max_missed:
                        self.game_over = True
                        self.game_over_reason = "漏掉的水果太多啦！"

        for b in self.bombs: b.update()

        # --- 清理掉出屏幕外的物体 ---
        self.fruits = [f for f in self.fruits if not f.is_out()]
        self.multi_fruits = [mf for mf in self.multi_fruits if not mf.is_out()]
        self.bombs = [b for b in self.bombs if not b.is_out()]

        # --- 清理播放完毕的特效 ---
        for fx in self.slash_fx: fx.update()
        for fx in self.combo_fx: fx.update()
        for fx in self.juice_fx: fx.update()
        self.slash_fx = [fx for fx in self.slash_fx if not fx.done()]
        self.combo_fx = [fx for fx in self.combo_fx if not fx.done()]
        self.juice_fx = [fx for fx in self.juice_fx if not fx.done()]

    def _bofang_yinxiao(self, key): # 播放音效的辅助函数
        if config.HAS_SOUND and key in config.SOUND_EFFECTS:
            config.SOUND_EFFECTS[key].play()

    def update(self, trail_list): # 这个update专门负责处理刀光轨迹和物体的碰撞
        if self.game_over: return
            
        cut_something = False # 标记本帧是否有物体被切到
        for idx, trail in enumerate(trail_list): # 遍历所有刀光（支持多手）
            if len(trail) < 2: continue # 刀光轨迹太短，不处理
                
            # --- 检测与普通水果的碰撞 ---
            for f in self.fruits:
                if not f.is_cut and f.check_hit(trail): # 如果水果没被切过，且被当前刀光轨迹碰撞
                    f.cut() # 执行水果的切开逻辑
                    cut_something = True
                    self._bofang_yinxiao('slice') # 播放切开音效
                    if self.mode == 'pk': # PK模式下，根据刀光索引给对应玩家加分
                        if idx == 0: self.p1.score += 1
                        else: self.p2.score += 1
                    else: # 普通模式
                        self.score += 1
                        self.combo += 1
                    self.slash_fx.append(Effect_Daoguang(f.x, f.y, random.uniform(0, 360))) # 添加一个刀光特效
                    if config.JUICE_IMAGES.get('juice1') is not None:
                        self.juice_fx.append(Effect_Guozhi(f.x, f.y, config.JUICE_IMAGES['juice1']))

            # --- 检测与多块水果的碰撞 ---
            for mf in self.multi_fruits:
                if not mf.is_cut and mf.check_hit(trail):
                    mf.cut()
                    cut_something = True
                    self._bofang_yinxiao('slice')
                    if self.mode == 'pk':
                        if idx == 0: self.p1.score += 2
                        else: self.p2.score += 2
                    else:
                        self.score += 2
                        self.combo += 1
                    self.slash_fx.append(Effect_Daoguang(mf.x, mf.y, random.uniform(0, 360)))
                    if config.JUICE_IMAGES.get('juice2') is not None:
                        self.juice_fx.append(Effect_Guozhi(mf.x, mf.y, config.JUICE_IMAGES['juice2']))

            # --- 检测与炸弹的碰撞 ---
            for b in self.bombs:
                if not b.is_exploded and b.check_hit(trail):
                    b.explode() # 炸弹爆炸
                    self._bofang_yinxiao('explosion') # 播放爆炸音效
                    if self.mode == 'pk': # PK模式下，切到炸弹给对方加分（或者不扣分）
                        if idx == 0: self.p1.score = max(0, self.p1.score - 4)
                        else: self.p2.score = max(0, self.p2.score - 4)
                    else: # 普通模式
                        self.combo = 0 # 连击清零
                        if b.bomb_type == 'deadly': # 如果是致命炸弹
                            self.game_over = True # 游戏直接结束
                            self.game_over_reason = "切到了致命炸弹！"
                        else: # 如果是普通炸弹
                            self.bombs_hit += 1 # 触弹次数+1
                            self.score = max(0, self.score - 3) # 扣分
                            if self.bombs_hit >= self.max_bombs_hit: # 如果触弹次数太多
                                self.game_over = True # 游戏结束
                                self.game_over_reason = "触碰炸弹次数过多！"
                                
        # --- 连击特效判断 ---
        # TODO: 后续把神湾菠萝的爆汁动效改得更逼真一点
        if cut_something and self.mode != 'pk':
            if self.combo in [3, 7, 12] or (self.combo > 12 and self.combo % 5 == 0): # 当达到特定连击数时
                self.combo_fx.append(Effect_Lianji(self.combo)) # 添加一个连击特效

    def draw(self, frame): # 绘制游戏的所有内容到屏幕上
        # --- 依次绘制所有游戏实体 ---
        for f in self.fruits: f.draw(frame)
        for mf in self.multi_fruits: mf.draw(frame)
        for b in self.bombs: b.draw(frame)
        for fx in self.juice_fx: fx.draw(frame)
        
        # --- 依次绘制所有特效 ---
        b_img = config.BLADE_IMAGES.get(self.selected_blade)
        for fx in self.slash_fx: fx.draw(frame, b_img)
        for fx in self.combo_fx: fx.draw(frame)

        half = config.WINDOW_WIDTH // 2
        # --- 绘制UI元素 ---
        if self.mode == 'pk': # PK模式的UI
            config.add_cn_text(f"玩家一 得分: {self.p1.score}", (40, 20), font_size=32, color=(255, 150, 0))
            config.add_cn_text(f"玩家二 得分: {self.p2.score}", (config.WINDOW_WIDTH - 280, 20), font_size=32, color=(100, 200, 255))
            config.add_cn_text(f"时间: {self.get_time_left():.1f}s", (half - 90, 20), font_size=30, color=(255, 255, 255), bg_color=(40, 40, 40))

            if not self.game_over:
                if self.p1.score > self.p2.score: # 根据分数判断谁领先
                    config.add_cn_text('领先 ▶', (half - 220, 70), font_size=26, color=(255, 200, 0))
                elif self.p2.score > self.p1.score:
                    config.add_cn_text('◀ 领先', (half + 20, 70),  font_size=26, color=(255, 200, 0))
            else: # PK模式游戏结束的界面
                ov = frame.copy()
                cv2.rectangle(ov, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
                cv2.addWeighted(ov, 0.60, frame, 0.40, 0, frame) # 加个半透明遮罩
                cy = config.WINDOW_HEIGHT // 2
                if self.winner == 'p1':
                    config.add_cn_text('🏆  玩家一获胜！', (half - 200, cy - 130), font_size=54, color=(255, 200, 0))
                elif self.winner == 'p2':
                    config.add_cn_text('🏆  玩家二获胜！', (half - 200, cy - 130), font_size=54, color=(100, 200, 255))
                else:
                    config.add_cn_text('🤝  双方平局！', (half - 150, cy - 130), font_size=54, color=(240, 240, 240))
                config.add_cn_text('按 R 键重新对战 | 按 Q 键退出到菜单', (half - 260, cy + 30), font_size=28, color=(200, 200, 200))
        else: # 普通模式的UI
            config.add_cn_text(f"得分: {self.score}", (40, 20), font_size=32, color=(0, 255, 0))
            config.add_cn_text(f"连击: {self.combo}", (220, 20), font_size=32, color=(255, 215, 0))
            config.add_cn_text(f"漏掉: {self.missed}/{self.max_missed}", (400, 20), font_size=32, color=(0, 100, 255))
            config.add_cn_text(f"触弹: {self.bombs_hit}/{self.max_bombs_hit}", (620, 20), font_size=32, color=(0, 0, 255))

            if self.game_over: # 普通模式游戏结束的界面
                ov = frame.copy()
                cv2.rectangle(ov, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
                cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame) # 加个半透明遮罩
                cy = config.WINDOW_HEIGHT // 2
                config.add_cn_text('Game Over', (half - 160, cy - 140), font_size=64, color=(0, 0, 255))
                config.add_cn_text(self.game_over_reason, (half - 180, cy - 40), font_size=30, color=(255, 255, 255))
                config.add_cn_text(f'最终总得分: {self.score}', (half - 130, cy + 30), font_size=34, color=(0, 255, 255))
                config.add_cn_text('按 R 重新开始 | 按 Q 退出到菜单', (half - 230, cy + 110), font_size=26, color=(190, 190, 190))
