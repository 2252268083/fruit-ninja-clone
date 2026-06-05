import math
from collections import deque

class FingerSmoother:
    """手指坐标平滑处理 - EWMA + 自适应速度调整"""

    def __init__(self, method='ewma', alpha=0.5, buffer_size=5, adaptive=True):
        self.method = method
        self.alpha = alpha
        self.buffer_size = buffer_size
        self.adaptive = adaptive
        self.smoothed_pos = None
        self.prev_raw_pos = None
        self.position_buffer = deque(maxlen=buffer_size)
        self.kalman_x = None
        self.kalman_y = None
        if method == 'kalman':
            self._init_kalman()

    def _init_kalman(self):
        self.kalman_x = {'x': 0, 'v': 0, 'P': [[1, 0], [0, 1]], 'Q': 0.001, 'R': 0.1}
        self.kalman_y = {'x': 0, 'v': 0, 'P': [[1, 0], [0, 1]], 'Q': 0.001, 'R': 0.1}

    def _kalman_update(self, k, m):
        k['x'] += k['v']
        k['P'][0][0] += k['P'][1][1] + k['Q']
        k['P'][1][1] += k['Q']
        S = k['P'][0][0] + k['R']
        Kp, Kv = k['P'][0][0] / S, k['P'][1][1] / S
        e = m - k['x']
        k['x'] += Kp * e
        k['v'] += Kv * e
        k['P'][0][0] = (1 - Kp) * k['P'][0][0]
        k['P'][1][1] = (1 - Kv) * k['P'][1][1]
        return k['x']

    def _speed(self, x, y):
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
        
        if self.method == 'ewma':
            if self.smoothed_pos is None:
                self.smoothed_pos = (x, y)
                return x, y
            a = self._adaptive_alpha(speed) if self.adaptive and speed > 0 else self.alpha
            sx = a * x + (1 - a) * self.smoothed_pos[0]
            sy = a * y + (1 - a) * self.smoothed_pos[1]
            self.smoothed_pos = (sx, sy)
            return int(sx), int(sy)
        elif self.method == 'moving_avg':
            self.position_buffer.append((x, y))
            pts = list(self.position_buffer)[-2:] if (self.adaptive and speed > 20) else list(self.position_buffer)
            return int(sum(p[0] for p in pts) / len(pts)), int(sum(p[1] for p in pts) / len(pts))
        elif self.method == 'kalman':
            if self.kalman_x is None:
                self._init_kalman()
                self.kalman_x['x'], self.kalman_y['x'] = x, y
                return x, y
            return int(self._kalman_update(self.kalman_x, x)), int(self._kalman_update(self.kalman_y, y))
        return x, y

    def reset(self):
        self.smoothed_pos = None
        self.prev_raw_pos = None
        self.position_buffer.clear()
        if self.method == 'kalman':
            self._init_kalman()