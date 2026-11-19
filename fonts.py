"""中文字体加载（config 与启动画面共用，只依赖 PIL，不引入重模块）"""
import os

from PIL import ImageFont

_ziti_huancun = {}


def get_ziti(size: int):
    """按字号取中文字体，带缓存；找不到系统字体时退回 PIL 默认字体"""
    if size in _ziti_huancun:
        return _ziti_huancun[size]
    # 随便找几个系统自带的字体试试
    ziti_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for p in ziti_paths:
        if os.path.exists(p):
            try:
                font = ImageFont.truetype(p, size)
                _ziti_huancun[size] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _ziti_huancun[size] = font
    return font
