import math
from collections import deque
"""
手势的防抖算法
"""
class FingerSmoother:

    def __init__(self, method='ewma', alpha=0.5, buffer_size=5, adaptive=True):
        self.method = method
        self.alpha = alpha
        self.adaptive = adaptive
        self.smoothed_pos = None
        self.prev_raw_pos = None

        self.position_buffer = deque(maxlen=buffer_size)

    def _speed(self, x, y):
        #手挥动的速度
        if self.prev_raw_pos is None:
            return 0
        return math.hypot(x - self.prev_raw_pos[0], y - self.prev_raw_pos[1])

    def _adaptive_alpha(self, speed):

        if speed > 50: return 0.85
        if speed > 20: return 0.55
        return self.alpha

    def smooth(self, x, y):
        speed = self._speed(x, y)
        self.prev_raw_pos = (x, y)
        
        #print(f"手速: {speed}")#调试用的 留着 
        
        if self.method == 'ewma':
            if self.smoothed_pos is None:
                self.smoothed_pos = (x, y)#旧
                return x, y
            #动态调整平滑系数（主要能让刀平滑过去的算法）（算新坐标和旧坐标过渡）
            a = self._adaptive_alpha(speed) if self.adaptive and speed > 0 else self.alpha#是否开启自适应
            sx = a * x + (1 - a) * self.smoothed_pos[0]#x坐标（平滑）
            sy = a * y + (1 - a) * self.smoothed_pos[1]#y坐标，渐变过渡
            self.smoothed_pos = (sx, sy)#存 下次调用
            return int(sx), int(sy)
            
        elif self.method == 'moving_avg':#求平均 让抖动平均掉
            self.position_buffer.append((x, y))
            #速度太快就少取点历史记录
            pts = list(self.position_buffer)[-2:] if (self.adaptive and speed > 20) else list(self.position_buffer)
            return int(sum(p[0] for p in pts) / len(pts)), int(sum(p[1] for p in pts) / len(pts))
            
        return x, y

    def reset(self):
        self.smoothed_pos = None
        self.prev_raw_pos = None
        self.position_buffer.clear()


def point_segment_distance(px, py, ax, ay, bx, by):
    """点 (px,py) 到线段 AB 的最短距离（用于刀光线段切水果判定）"""
    abx, aby = bx - ax, by - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0:  # A、B 重合，退化成点
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * abx, ay + t * aby
    return math.hypot(px - cx, py - cy)
