import logging
import logging.handlers
import sys
import os

# 用来打印日志的（控制台 + 文件双输出）

def get_exe_dir():
    # 打包后 exe 所在目录；源码运行时就是本文件所在目录
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_my_logger(name="SwiftFruitSlice"):
    my_log = logging.getLogger(name)
    if not my_log.handlers:
        my_log.setLevel(logging.INFO)
        fm = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s',
                               datefmt='%Y-%m-%d %H:%M:%S')

        # 1. 控制台输出
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fm)
        my_log.addHandler(ch)

        # 2. 文件输出：写到 exe 旁边的 logs/game.log，方便打包交付后远程查问题
        #    单文件超过 1MB 自动轮转成 game.log.1 / .2 / .3，防止无限变大
        try:
            log_dir = os.path.join(get_exe_dir(), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, 'game.log'),
                maxBytes=1 * 1024 * 1024,   # 1MB
                backupCount=3,              # 最多留 3 个历史文件
                encoding='utf-8'
            )
            fh.setFormatter(fm)
            my_log.addHandler(fh)
        except Exception:
            # 日志文件建不了（比如目录只读）也不影响游戏运行
            pass

    return my_log

my_log = get_my_logger()
