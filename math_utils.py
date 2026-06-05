import math
from collections import deque

class FingerSmoother:
    # 之前坐标跳来跳去，查资料加了个平滑器
    def __init__(self, method='ewma', alpha=0.5, buffer_size=5, adaptive=True):
        self.method = method
        self.alpha = alpha
        self.adaptive = adaptive
        self.smoothed_pos = None
        self.prev_raw_pos = None
        # buffer主要是给moving_avg用的，kalman太复杂了暂时没用到
        self.position_buffer = deque(maxlen=buffer_size)

    def _speed(self, x, y):
        # 算一下手挥动的速度
        if self.prev_raw_pos is None:
            return 0
        return math.hypot(x - self.prev_raw_pos[0], y - self.prev_raw_pos[1])

    def _adaptive_alpha(self, speed):
        # 速度快的时候不能平滑太多，不然刀光跟不上手
        if speed > 50: return 0.85
        if speed > 20: return 0.55
        return self.alpha

    def smooth(self, x, y):
        speed = self._speed(x, y)
        self.prev_raw_pos = (x, y)
        
        # print(f"手速: {speed}") # 调试用的，留着
        
        if self.method == 'ewma':
            if self.smoothed_pos is None:
                self.smoothed_pos = (x, y)
                return x, y
            # 动态调整平滑系数
            a = self._adaptive_alpha(speed) if self.adaptive and speed > 0 else self.alpha
            sx = a * x + (1 - a) * self.smoothed_pos[0]
            sy = a * y + (1 - a) * self.smoothed_pos[1]
            self.smoothed_pos = (sx, sy)
            return int(sx), int(sy)
            
        elif self.method == 'moving_avg':
            self.position_buffer.append((x, y))
            # 速度太快就少取点历史记录
            pts = list(self.position_buffer)[-2:] if (self.adaptive and speed > 20) else list(self.position_buffer)
            return int(sum(p[0] for p in pts) / len(pts)), int(sum(p[1] for p in pts) / len(pts))
            
        return x, y

    def reset(self):
        self.smoothed_pos = None
        self.prev_raw_pos = None
        self.position_buffer.clear()
