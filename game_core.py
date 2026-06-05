import cv2
import math
import random
import time
from collections import deque
import config

class Player:
    def __init__(self):
        self.score = 0

class Fruit:
    def __init__(self):
        self.x = random.randint(100, config.WINDOW_WIDTH - 100)
        self.y = config.WINDOW_HEIGHT + 50
        self.fruit_type = random.choice(config.FRUIT_TYPES)
        self.images = config.FRUIT_IMAGES.get(self.fruit_type)
        if self.images and self.images['whole'] is not None:
            h, w = self.images['whole'].shape[:2]
            self.radius = max(w, h) // 2
        else:
            self.radius = 50
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-19, -15)
        self.gravity = 0.32
        self.rot = random.uniform(0, 360)
        self.rot_spd = random.uniform(-5, 5)
        self.is_cut = False
        self.cut_pieces = []
        self.entered = False

    def update(self):
        if not self.is_cut:
            self.vy += self.gravity
            self.x += self.vx
            self.y += self.vy
            self.rot += self.rot_spd
            if not self.entered and 0 <= self.y <= config.WINDOW_HEIGHT - 50:
                self.entered = True
        else:
            for p in self.cut_pieces:
                p['vy'] += self.gravity * 2.0
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['rot'] += p['rot_spd']
                p['alpha'] -= 4

    def draw(self, frame):
        if not self.is_cut:
            if self.images and self.images['whole'] is not None:
                config.overlay_image(frame, self.images['whole'], int(self.x), int(self.y), self.rot)
            else:
                cv2.circle(frame, (int(self.x), int(self.y)), 40, (0, 255, 255), -1)
        else:
            for p in self.cut_pieces:
                if p['alpha'] > 0:
                    config.overlay_image(frame, p['image'], int(p['x']), int(p['y']),
                                         p['rot'], p['alpha'] / 255.0)

    def cut(self, _=0):
        self.is_cut = True
        if not self.images:
            return
        for img, dx in [(self.images['left'], -1), (self.images['right'], 1)]:
            if img is not None:
                self.cut_pieces.append({
                    'x': self.x, 'y': self.y, 'image': img,
                    'vx': random.uniform(4, 7) * dx,
                    'vy': random.uniform(-3, 2),
                    'rot': self.rot,
                    'rot_spd': random.uniform(4, 8) * dx,
                    'alpha': 255
                })

    def out(self):
        if not self.is_cut:
            return self.y > config.WINDOW_HEIGHT + 150
        return all(p['alpha'] <= 0 or p['y'] > config.WINDOW_HEIGHT + 150 for p in self.cut_pieces)

    def check_collision(self, trail):
        if self.is_cut or len(trail) < 2:
            return False
        for pt in list(trail)[-15:]:
            if pt and math.hypot(pt[0] - self.x, pt[1] - self.y) < self.radius * 0.85:
                return True
        return False


class MultiFruit:
    def __init__(self):
        self.x = random.randint(100, config.WINDOW_WIDTH - 100)
        self.y = config.WINDOW_HEIGHT + 50
        self.fruit_type = random.choice(config.MULTI_FRUIT_TYPES)
        self.images = config.MULTI_FRUIT_IMAGES.get(self.fruit_type)
        if self.images and self.images['whole'] is not None:
            h, w = self.images['whole'].shape[:2]
            self.radius = max(w, h) // 2
        else:
            self.radius = 55
        self.vx = random.uniform(-1.5, 1.5)
        self.vy = random.uniform(-18, -14)
        self.gravity = 0.3
        self.rot = random.uniform(0, 360)
        self.rot_spd = random.uniform(-4, 4)
        self.is_cut = False
        self.cut_pieces = []
        self.entered = False

    def update(self):
        if not self.is_cut:
            self.vy += self.gravity
            self.x += self.vx
            self.y += self.vy
            self.rot += self.rot_spd
            if not self.entered and 0 <= self.y <= config.WINDOW_HEIGHT - 50:
                self.entered = True
        else:
            for p in self.cut_pieces:
                p['vy'] += self.gravity * 2.0
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['rot'] += p['rot_spd']
                p['alpha'] -= 4

    def draw(self, frame):
        if not self.is_cut:
            if self.images and self.images['whole'] is not None:
                config.overlay_image(frame, self.images['whole'], int(self.x), int(self.y), self.rot)
            else:
                cv2.circle(frame, (int(self.x), int(self.y)), 45, (0, 200, 200), -1)
        else:
            for p in self.cut_pieces:
                if p['alpha'] > 0:
                    config.overlay_image(frame, p['image'], int(p['x']), int(p['y']),
                                         p['rot'], p['alpha'] / 255.0)

    def cut(self, angle=0):
        self.is_cut = True
        if not self.images or 'pieces' not in self.images:
            return
        cnt = self.images['piece_count']
        step = 360 / cnt
        for i, img in enumerate(self.images['pieces']):
            a = math.radians(i * step)
            spd = random.uniform(5, 9)
            self.cut_pieces.append({
                'x': self.x, 'y': self.y, 'image': img,
                'vx': math.cos(a) * spd,
                'vy': math.sin(a) * spd - 1,
                'rot': self.rot + random.uniform(-30, 30),
                'rot_spd': random.uniform(-8, 8),
                'alpha': 255
            })

    def out(self):
        if not self.is_cut:
            return self.y > config.WINDOW_HEIGHT + 150
        return all(p['alpha'] <= 0 or p['y'] > config.WINDOW_HEIGHT + 150 for p in self.cut_pieces)

    def check_collision(self, trail):
        if self.is_cut or len(trail) < 2:
            return False
        for pt in list(trail)[-15:]:
            if pt and math.hypot(pt[0] - self.x, pt[1] - self.y) < self.radius * 0.85:
                return True
        return False


class Bomb:
    def __init__(self, bomb_type='normal'):
        self.x = random.randint(100, config.WINDOW_WIDTH - 100)
        self.y = config.WINDOW_HEIGHT + 50
        self.bomb_type = bomb_type
        self.image = config.BOMB_IMAGES.get('bomb2' if bomb_type == 'deadly' else 'bomb1')
        if self.image is not None:
            h, w = self.image.shape[:2]
            self.radius = max(w, h) // 2
        else:
            self.radius = 45
        self.vx = random.uniform(-1, 1)
        self.vy = random.uniform(-17, -13)
        self.gravity = 0.3
        self.rot = random.uniform(0, 360)
        self.rot_spd = random.uniform(-4, 4)
        self.is_exploded = False
        self.entered = False
        self.exp_frame = 0
        self.exp_max = 20

    def update(self):
        if not self.is_exploded:
            self.vy += self.gravity
            self.x += self.vx
            self.y += self.vy
            self.rot += self.rot_spd
            if not self.entered and 0 <= self.y <= config.WINDOW_HEIGHT - 50:
                self.entered = True
        else:
            self.exp_frame += 1

    def draw(self, frame):
        if not self.is_exploded:
            if self.image is not None:
                config.overlay_image(frame, self.image, int(self.x), int(self.y), self.rot)
            else:
                color = (0, 0, 255) if self.bomb_type == 'deadly' else (0, 0, 0)
                cv2.circle(frame, (int(self.x), int(self.y)), 40, color, -1)
        elif self.exp_frame < self.exp_max:
            key = 'explosion1' if self.exp_frame % 4 < 2 else 'explosion2'
            img = config.BOMB_IMAGES.get(key)
            if img is not None:
                a = 1.0 - self.exp_frame / self.exp_max
                config.overlay_image(frame, img, int(self.x), int(self.y), 0, a)

    def explode(self):
        self.is_exploded = True
        self.exp_frame = 0

    def out(self):
        if not self.is_exploded:
            return self.y > config.WINDOW_HEIGHT + 150
        return self.exp_frame >= self.exp_max

    def check_collision(self, trail):
        if self.is_exploded or len(trail) < 2:
            return False
        for pt in list(trail)[-15:]:
            if pt and math.hypot(pt[0] - self.x, pt[1] - self.y) < self.radius * 0.85:
                return True
        return False


class ComboEffect:
    def __init__(self, combo):
        self.x = config.WINDOW_WIDTH // 2
        self.y = config.WINDOW_HEIGHT // 2 - 100
        self.alpha = 0
        self.scale = 0.5
        self.frame = 0
        self.dur = 45
        self.key = ('combo3' if combo >= 12 else 'combo2' if combo >= 7 else 'combo1' if combo >= 3 else None)

    def update(self):
        self.frame += 1
        if self.frame < 10:
            self.alpha = int(255 * self.frame / 10)
            self.scale = 0.5 + self.frame / 10 * 0.5
        elif self.frame < 35:
            self.alpha = 255
            self.scale = 1.0
        else:
            p = (self.frame - 35) / 10
            self.alpha = int(255 * (1 - p))
            self.scale = 1.0 + p * 0.15

    def done(self): return self.frame >= self.dur

    def draw(self, frame):
        if not self.key or self.key not in config.COMBO_IMAGES:
            return
        img = config.COMBO_IMAGES[self.key]
        h, w = img.shape[:2]
        sc = cv2.resize(img, (int(w * self.scale), int(h * self.scale)))
        config.overlay_image(frame, sc, int(self.x), int(self.y), 0, self.alpha / 255.0)


class SlashEffect:
    def __init__(self, x, y, angle):
        self.x = x; self.y = y; self.angle = angle
        self.alpha = 255; self.scale = 1.0
        self.frame = 0; self.dur = 15

    def update(self):
        self.frame += 1
        self.alpha = int(255 * (1 - self.frame / self.dur))
        self.scale = 1.0 + self.frame / self.dur * 0.25

    def done(self): return self.frame >= self.dur

    def draw(self, frame, blade_img):
        if blade_img is None: return
        h, w = blade_img.shape[:2]
        sc = cv2.resize(blade_img, (int(w * self.scale), int(h * self.scale)))
        config.overlay_image(frame, sc, int(self.x), int(self.y), self.angle, self.alpha / 255.0)


class JuiceEffect:
    def __init__(self, x, y, juice_img):
        self.x = x; self.y = y; self.img = juice_img
        self.alpha = 255; self.scale = 1.0
        self.frame = 0; self.dur = 18

    def update(self):
        self.frame += 1
        if self.frame < self.dur * 0.5:
            self.alpha = 255
        else:
            p = (self.frame - self.dur * 0.5) / (self.dur * 0.5)
            self.alpha = int(255 * (1 - p))
            self.scale = 1.0 + self.frame / self.dur * 0.5

    def done(self): return self.frame >= self.dur

    def draw(self, frame):
        if self.img is None: return
        h, w = self.img.shape[:2]
        sc = cv2.resize(self.img, (int(w * self.scale), int(h * self.scale)))
        config.overlay_image(frame, sc, int(self.x), int(self.y), 0, min(255, max(0, self.alpha)) / 255.0)


class Game:
    def __init__(self, selected_blade='dao1', mode='single'):
        self.fruits = []
        self.multi_fruits = []
        self.bombs = []
        self.slash_fx = []
        self.combo_fx = []
        self.juice_fx = []
        self.selected_blade = selected_blade
        self.mode = mode
        
        self.score = 0
        self.missed = 0
        self.bombs_hit = 0
        self.combo = 0
        self.max_combo = 0
        self.spawn_timer = 0
        # 减小生成间隔，加快水果生成速度
        self.spawn_interval = config.SETTINGS["game"].get("spawn_interval", 12)
        self.game_over = False
        self.game_over_reason = ""
        self.max_missed = 10
        self.max_bombs_hit = 3
        # 增加同屏最大水果数量
        self.max_on_screen = config.SETTINGS["game"].get("max_on_screen", 15)
        self.bomb_chance = 0.22
        self.deadly_chance = 0.25
        self.multi_chance = 0.15
        self.consec_bombs = 0
        self.max_consec_bombs = 2
        
        self.p1 = Player()
        self.p2 = Player()
        self.start_time = time.time()
        self.total_time = 30.0
        self.winner = ''
        
        self.spawn_single()

    def time_left(self) -> float:
        return max(0.0, self.total_time - (time.time() - self.start_time))

    def spawn_single(self):
        if self.consec_bombs >= self.max_consec_bombs:
            self._spawn_fruit()
            self.consec_bombs = 0
            return
            
        r = random.random()
        if r < self.bomb_chance:
            bt = 'deadly' if random.random() < self.deadly_chance else 'normal'
            self.bombs.append(Bomb(bt))
            self.consec_bombs += 1
        elif r < self.bomb_chance + self.multi_chance:
            self.multi_fruits.append(MultiFruit())
            self.consec_bombs = 0
        else:
            self.fruits.append(Fruit())
            self.consec_bombs = 0

    def _spawn_fruit(self):
        if random.random() < 0.3:
            self.multi_fruits.append(MultiFruit())
        else:
            self.fruits.append(Fruit())

    def check_collisions(self, trail_list):
        if self.game_over:
            return

        if self.mode == 'pk' and self.time_left() <= 0:
            self.game_over = True
            if self.p1.score > self.p2.score:
                self.winner = 'p1'
            elif self.p2.score > self.p1.score:
                self.winner = 'p2'
            else:
                self.winner = 'draw'
            return

        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0
            if len(self.fruits) + len(self.multi_fruits) + len(self.bombs) < self.max_on_screen:
                # 每次生成的水果数量从 1~2 个增加到 2~4 个
                for _ in range(random.randint(2, 4)):
                    self.spawn_single()

        for f in self.fruits:
            f.update()
            if not f.is_cut and f.out() and f.entered:
                if self.mode != 'pk':
                    self.missed += 1
                    self.combo = 0
                    if self.missed >= self.max_missed:
                        self.game_over = True
                        self.game_over_reason = "漏掉的水果太多啦！"
                        
        for mf in self.multi_fruits:
            mf.update()
            if not mf.is_cut and mf.out() and mf.entered:
                if self.mode != 'pk':
                    self.missed += 1
                    self.combo = 0
                    if self.missed >= self.max_missed:
                        self.game_over = True
                        self.game_over_reason = "漏掉的水果太多啦！"

        for b in self.bombs:
            b.update()

        self.fruits = [f for f in self.fruits if not f.out()]
        self.multi_fruits = [mf for mf in self.multi_fruits if not mf.out()]
        self.bombs = [b for b in self.bombs if not b.out()]

        for fx in self.slash_fx: fx.update()
        for fx in self.combo_fx: fx.update()
        for fx in self.juice_fx: fx.update()
        self.slash_fx = [fx for fx in self.slash_fx if not fx.done()]
        self.combo_fx = [fx for fx in self.combo_fx if not fx.done()]
        self.juice_fx = [fx for fx in self.juice_fx if not fx.done()]

    def _play(self, key):
        if config.HAS_SOUND and key in config.SOUND_EFFECTS:
            config.SOUND_EFFECTS[key].play()

    def update(self, trail_list):
        if self.game_over:
            return
            
        cut_something = False
        for idx, trail in enumerate(trail_list):
            if len(trail) < 2:
                continue
                
            for f in self.fruits:
                if not f.is_cut and f.check_collision(trail):
                    f.cut()
                    cut_something = True
                    self._play('slice')
                    if self.mode == 'pk':
                        if idx == 0: self.p1.score += 1
                        else: self.p2.score += 1
                    else:
                        self.score += 1
                        self.combo += 1
                    self.slash_fx.append(SlashEffect(f.x, f.y, random.uniform(0, 360)))
                    if config.JUICE_IMAGES.get('juice1') is not None:
                        self.juice_fx.append(JuiceEffect(f.x, f.y, config.JUICE_IMAGES['juice1']))

            for mf in self.multi_fruits:
                if not mf.is_cut and mf.check_collision(trail):
                    mf.cut()
                    cut_something = True
                    self._play('slice')
                    if self.mode == 'pk':
                        if idx == 0: self.p1.score += 2
                        else: self.p2.score += 2
                    else:
                        self.score += 2
                        self.combo += 1
                    self.slash_fx.append(SlashEffect(mf.x, mf.y, random.uniform(0, 360)))
                    if config.JUICE_IMAGES.get('juice2') is not None:
                        self.juice_fx.append(JuiceEffect(mf.x, mf.y, config.JUICE_IMAGES['juice2']))

            for b in self.bombs:
                if not b.is_exploded and b.check_collision(trail):
                    b.explode()
                    self._play('explosion')
                    if self.mode == 'pk':
                        if idx == 0: self.p1.score = max(0, self.p1.score - 4)
                        else: self.p2.score = max(0, self.p2.score - 4)
                    else:
                        self.combo = 0
                        if b.bomb_type == 'deadly':
                            self.game_over = True
                            self.game_over_reason = "切到了致命炸弹！"
                        else:
                            self.bombs_hit += 1
                            self.score = max(0, self.score - 3)
                            if self.bombs_hit >= self.max_bombs_hit:
                                self.game_over = True
                                self.game_over_reason = "触碰炸弹次数过多！"
                                
        if cut_something and self.mode != 'pk':
            if self.combo in [3, 7, 12] or (self.combo > 12 and self.combo % 5 == 0):
                self.combo_fx.append(ComboEffect(self.combo))

    def draw(self, frame):
        for f in self.fruits: f.draw(frame)
        for mf in self.multi_fruits: mf.draw(frame)
        for b in self.bombs: b.draw(frame)
        for fx in self.juice_fx: fx.draw(frame)
        
        b_img = config.BLADE_IMAGES.get(self.selected_blade)
        for fx in self.slash_fx: fx.draw(frame, b_img)
        for fx in self.combo_fx: fx.draw(frame)

        half = config.WINDOW_WIDTH // 2
        if self.mode == 'pk':
            config.add_cn_text(f"玩家一 得分: {self.p1.score}", (40, 20), font_size=32, color=(255, 150, 0))
            config.add_cn_text(f"玩家二 得分: {self.p2.score}", (config.WINDOW_WIDTH - 280, 20), font_size=32, color=(100, 200, 255))
            config.add_cn_text(f"时间: {self.time_left():.1f}s", (half - 90, 20), font_size=30, color=(255, 255, 255), bg_color=(40, 40, 40))

            if not self.game_over:
                if self.p1.score > self.p2.score:
                    config.add_cn_text('领先 ▶', (half - 220, 70), font_size=26, color=(255, 200, 0))
                elif self.p2.score > self.p1.score:
                    config.add_cn_text('◀ 领先', (half + 20, 70),  font_size=26, color=(255, 200, 0))
            else:
                ov = frame.copy()
                cv2.rectangle(ov, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
                cv2.addWeighted(ov, 0.60, frame, 0.40, 0, frame)
                cy = config.WINDOW_HEIGHT // 2
                if self.winner == 'p1':
                    config.add_cn_text('🏆  玩家一获胜！', (half - 200, cy - 130), font_size=54, color=(255, 200, 0))
                elif self.winner == 'p2':
                    config.add_cn_text('🏆  玩家二获胜！', (half - 200, cy - 130), font_size=54, color=(100, 200, 255))
                else:
                    config.add_cn_text('🤝  双方平局！', (half - 150, cy - 130), font_size=54, color=(240, 240, 240))
                config.add_cn_text('按 R 键重新对战 | 按 Q 键退出到菜单', (half - 260, cy + 30), font_size=28, color=(200, 200, 200))
        else:
            config.add_cn_text(f"得分: {self.score}", (40, 20), font_size=32, color=(0, 255, 0))
            config.add_cn_text(f"连击: {self.combo}", (220, 20), font_size=32, color=(255, 215, 0))
            config.add_cn_text(f"漏掉: {self.missed}/{self.max_missed}", (400, 20), font_size=32, color=(0, 100, 255))
            config.add_cn_text(f"触弹: {self.bombs_hit}/{self.max_bombs_hit}", (620, 20), font_size=32, color=(0, 0, 255))

            if self.game_over:
                ov = frame.copy()
                cv2.rectangle(ov, (0, 0), (config.WINDOW_WIDTH, config.WINDOW_HEIGHT), (0, 0, 0), -1)
                cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame)
                cy = config.WINDOW_HEIGHT // 2
                config.add_cn_text('Game Over', (half - 160, cy - 140), font_size=64, color=(0, 0, 255))
                config.add_cn_text(self.game_over_reason, (half - 180, cy - 40), font_size=30, color=(255, 255, 255))
                config.add_cn_text(f'最终总得分: {self.score}', (half - 130, cy + 30), font_size=34, color=(0, 255, 255))
                config.add_cn_text('按 R 重新开始 | 按 Q 退出到菜单', (half - 230, cy + 110), font_size=26, color=(190, 190, 190))