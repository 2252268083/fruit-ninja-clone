import os
import cv2
import yaml
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from logger import logger

# ============================================================
#  加载配置文件 (支持热插拔)
# ============================================================
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.yaml')

def load_settings():
    default_settings = {
        "camera": {"index": 0, "width": 1280, "height": 720},
        "game": {
            "window_width": 1280, 
            "window_height": 720,
            "spawn_interval": 12,
            "max_on_screen": 15
        },
        "ai": {
            "max_hands": 4
        },
        "paths": {
            "assets_dir": "assets",
            "models_dir": "models",
            "model_name": "hand_landmarker.task",
            "bgm_name": "1.mp3"
        }
    }
    if not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(default_settings, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"已创建默认配置文件: {SETTINGS_FILE}")
        except Exception as e:
            logger.error(f"创建配置文件失败: {e}")
        return default_settings

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            user_settings = yaml.safe_load(f)
            # 简单合并默认值，防止缺失字段
            if user_settings is None:
                user_settings = {}
            for k, v in default_settings.items():
                if k not in user_settings:
                    user_settings[k] = v
                elif isinstance(v, dict):
                    if not isinstance(user_settings[k], dict):
                        user_settings[k] = {}
                    for sub_k, sub_v in v.items():
                        if sub_k not in user_settings[k]:
                            user_settings[k][sub_k] = sub_v
            return user_settings
    except Exception as e:
        logger.error(f"读取配置文件失败，使用默认配置: {e}")
        return default_settings

SETTINGS = load_settings()

try:
    import pygame
    pygame.mixer.init()
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False
    logger.warning("提示: 安装pygame可启用音效 (pip install pygame)")

# ============================================================
#  窗口逻辑尺寸 (统一渲染坐标系)
# ============================================================
WINDOW_WIDTH  = SETTINGS["game"]["window_width"]
WINDOW_HEIGHT = SETTINGS["game"]["window_height"]

# ============================================================
#  中文字体系统（批量渲染，每帧只做一次 BGR↔RGB 转换）
# ============================================================
_font_cache: dict = {}

def get_cn_font(size: int) -> ImageFont.ImageFont:
    if size in _font_cache:
        return _font_cache[size]
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode MS.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[size] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font

_text_queue: list = []

def add_cn_text(text: str, pos: tuple, font_size: int = 32,
                color=(255, 255, 255), bg_color=None, padding: int = 8):
    _text_queue.append((text, pos, font_size, color, bg_color, padding))

def flush_cn_texts(frame: np.ndarray):
    global _text_queue
    if not _text_queue:
        return
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    for text, (x, y), font_size, color, bg_color, padding in _text_queue:
        font = get_cn_font(font_size)
        if bg_color is not None:
            bbox = draw.textbbox((x, y), text, font=font)
            draw.rectangle(
                [bbox[0] - padding, bbox[1] - padding,
                 bbox[2] + padding, bbox[3] + padding],
                fill=(bg_color[2], bg_color[1], bg_color[0])
            )
        draw.text((x, y), text, font=font,
                  fill=(color[2], color[1], color[0]))
    _text_queue = []
    np.copyto(frame, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))

# ============================================================
#  素材加载
# ============================================================
FRUIT_TYPES = [
    'banana', 'boluo', 'iceBanana', 'Mango',
    'mugua', 'peach', 'pear', 'pineapple', 'strawberry', 'b1'
]
MULTI_FRUIT_TYPES = ['watermelon', 'dragonfruit']

def load_fruit_images():
    fruit_images = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, SETTINGS["paths"]["assets_dir"], 'sucai')
    for name in FRUIT_TYPES:
        whole_path = os.path.join(assets_dir, f'{name}.png')
        if name == 'b1':
            left_path  = os.path.join(assets_dir, 'bl.png')
            right_path = os.path.join(assets_dir, 'br.png')
        else:
            left_path  = os.path.join(assets_dir, f'{name}l.png')
            right_path = os.path.join(assets_dir, f'{name}r.png')
        if os.path.exists(whole_path):
            wi = cv2.imread(whole_path, cv2.IMREAD_UNCHANGED)
            li = cv2.imread(left_path,  cv2.IMREAD_UNCHANGED)
            ri = cv2.imread(right_path, cv2.IMREAD_UNCHANGED)
            fruit_images[name] = {'whole': wi, 'left': li, 'right': ri}
    return fruit_images

def load_multi_fruit_images():
    images = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, SETTINGS["paths"]["assets_dir"], 'sucai')
    sc = 0.5
    
    # 1. 西瓜
    wp = os.path.join(assets_dir, 'watermelon.png')
    if os.path.exists(wp):
        wi = cv2.imread(wp, cv2.IMREAD_UNCHANGED)
        if wi is not None:
            wi = cv2.resize(wi, None, fx=sc, fy=sc)
            pieces = []
            for i in range(1, 9):
                pp = os.path.join(assets_dir, f'watermelon{i}.png')
                if os.path.exists(pp):
                    pi = cv2.imread(pp, cv2.IMREAD_UNCHANGED)
                    if pi is not None:
                        pieces.append(cv2.resize(pi, None, fx=sc, fy=sc))
            if len(pieces) == 8:
                images['watermelon'] = {'whole': wi, 'pieces': pieces, 'piece_count': 8}
                
    # 2. 火龙果/全切块水果
    dp = os.path.join(assets_dir, 'all.png')
    if os.path.exists(dp):
        wi = cv2.imread(dp, cv2.IMREAD_UNCHANGED)
        if wi is not None:
            wi = cv2.resize(wi, None, fx=sc, fy=sc)
            pieces = []
            for i in range(1, 9):
                pp = os.path.join(assets_dir, f'00{i}.png')
                if os.path.exists(pp):
                    pi = cv2.imread(pp, cv2.IMREAD_UNCHANGED)
                    if pi is not None:
                        pieces.append(cv2.resize(pi, None, fx=sc, fy=sc))
            if len(pieces) == 8:
                images['dragonfruit'] = {'whole': wi, 'pieces': pieces, 'piece_count': 8}
    return images

def load_juice_images():
    images = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, SETTINGS["paths"]["assets_dir"], 'texiao')
    for i in range(1, 5):
        name = f'guozhi{i}'
        p = os.path.join(assets_dir, f'{name}.png')
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                images[name] = img
    return images

def load_bomb_images():
    images = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, SETTINGS["paths"]["assets_dir"], 'zhadan')
    for key, fname, sc in [('bomb1', 'boom1.png', 1.0), ('bomb2', 'boom2.png', 1.0), ('explosion1', 'zha01.png', 2.0), ('explosion2', 'zha02.png', 2.0)]:
        p = os.path.join(assets_dir, fname)
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                images[key] = cv2.resize(img, None, fx=sc, fy=sc) if sc != 1.0 else img
    return images

def load_blade_images():
    images = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, SETTINGS["paths"]["assets_dir"], 'daoguang')
    for name in ['dao1', 'dao2']:
        p = os.path.join(assets_dir, f'{name}.png')
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                images[name] = img
    return images

def load_combo_images():
    images = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, SETTINGS["paths"]["assets_dir"], 'texiao')
    for name in ['combo1', 'combo2', 'combo3']:
        p = os.path.join(assets_dir, f'{name}.png')
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                images[name] = img
    return images

def load_sound_effects():
    sfx = {}
    if not HAS_SOUND: return sfx
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sound_dir = os.path.join(script_dir, SETTINGS["paths"]["assets_dir"], 'yinxiao')
    try:
        sp = os.path.join(sound_dir, 'qieshuiguoyinxiao.mp3')
        if os.path.exists(sp): sfx['slice'] = pygame.mixer.Sound(sp)
        ep = os.path.join(sound_dir, 'baozhayinxiao.mp3')
        if os.path.exists(ep): sfx['explosion'] = pygame.mixer.Sound(ep)
    except Exception:
        pass
    return sfx

FRUIT_JUICE_MAP = {
    'banana': 'guozhi1', 'boluo': 'guozhi1', 'iceBanana': 'guozhi2',
    'Mango': 'guozhi1', 'mugua': 'guozhi1', 'peach': 'guozhi3',
    'pear': 'guozhi2', 'pineapple': 'guozhi1', 'strawberry': 'guozhi4',
    'watermelon': 'guozhi4', 'dragonfruit': 'guozhi3', 'b1': 'guozhi1',
}

def get_juice_color(fruit_type):
    c = FRUIT_JUICE_MAP.get(fruit_type)
    if c and c in JUICE_IMAGES:
        return c
    return random.choice(list(JUICE_IMAGES.keys())) if JUICE_IMAGES else None

def start_bgm():
    if HAS_SOUND:
        try:
            bgm_name = SETTINGS["paths"]["bgm_name"]
            assets_dir = SETTINGS["paths"]["assets_dir"]
            bgm_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), assets_dir, bgm_name)
            if not os.path.exists(bgm_path):
                bgm_path = f'{assets_dir}/{bgm_name}'
            pygame.mixer.music.load(bgm_path)
            pygame.mixer.music.play(-1)
            logger.info(f"背景音乐 {bgm_name} 已成功启动循环播放")
        except Exception as e:
            logger.error(f"无法启动背景音乐 {SETTINGS['paths']['bgm_name']}: {e}")

def stop_bgm():
    if HAS_SOUND:
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            logger.info("背景音乐已安全停止并释放资源")
        except Exception:
            pass

def overlay_image(bg: np.ndarray, fg: np.ndarray, x: int, y: int, rotation: float = 0, alpha_scale: float = 1.0):
    if fg is None:
        return
    h, w = fg.shape[:2]
    ov = fg.copy()
    if rotation != 0:
        cx, cy = w // 2, h // 2
        M = cv2.getRotationMatrix2D((cx, cy), rotation, 1.0)
        cos, sin = abs(M[0, 0]), abs(M[0, 1])
        nw = int(h * sin + w * cos)
        nh = int(h * cos + w * sin)
        M[0, 2] += nw / 2 - cx
        M[1, 2] += nh / 2 - cy
        ov = cv2.warpAffine(ov, M, (nw, nh),
                            borderMode=cv2.BORDER_CONSTANT,
                            borderValue=(0, 0, 0, 0))
    oh, ow = ov.shape[:2]
    x1, y1 = int(x - ow // 2), int(y - oh // 2)
    x2, y2 = x1 + ow, y1 + oh
    if x1 >= bg.shape[1] or y1 >= bg.shape[0] or x2 <= 0 or y2 <= 0:
        return
    ox1, oy1 = max(0, -x1), max(0, -y1)
    ox2 = ow - max(0, x2 - bg.shape[1])
    oy2 = oh - max(0, y2 - bg.shape[0])
    bx1 = max(0, x1); by1 = max(0, y1)
    bx2 = min(bg.shape[1], x2); by2 = min(bg.shape[0], y2)
    if ox2 <= ox1 or oy2 <= oy1:
        return

    crop_ov = ov[oy1:oy2, ox1:ox2]
    crop_bg = bg[by1:by2, bx1:bx2]
    
    if crop_ov.shape[2] == 4:
        alpha = (crop_ov[:, :, 3] / 255.0) * alpha_scale
        for c in range(3):
            crop_bg[:, :, c] = (1.0 - alpha) * crop_bg[:, :, c] + alpha * crop_ov[:, :, c]
    else:
        if alpha_scale == 1.0:
            bg[by1:by2, bx1:bx2] = crop_ov
        else:
            for c in range(3):
                crop_bg[:, :, c] = (1.0 - alpha_scale) * crop_bg[:, :, c] + alpha_scale * crop_ov[:, :, c]

# 全局预加载素材
FRUIT_IMAGES = load_fruit_images()
MULTI_FRUIT_IMAGES = load_multi_fruit_images()
BOMB_IMAGES = load_bomb_images()
BLADE_IMAGES = load_blade_images()
COMBO_IMAGES = load_combo_images()
JUICE_IMAGES = load_juice_images()
SOUND_EFFECTS = load_sound_effects()