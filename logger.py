import logging
import sys

def get_my_logger(name="SwiftFruitSlice"):
    # 自己封装的打印，比print好用，能带时间
    my_log = logging.getLogger(name)
    if not my_log.handlers:
        my_log.setLevel(logging.INFO)
        # TODO: 以后可以考虑把日志存到文件里，方便查bug
        fm = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fm)
        my_log.addHandler(ch)
    return my_log

my_log = get_my_logger()
