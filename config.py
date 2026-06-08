import os
import cv2
import yaml
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from logger import my_log

# 找配置文件
my_setting_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.yaml')

def duqu_peizhi():#默认配置
    # 默认给个配置
    mo_ren = {
        "camera": {"index": 0, "width": 1280, "height": 720},
        "game": {
            "window_width": 1280, 
            "window_height": 720,
            "spawn_interval": 12, # 水果生成速度
            "max_on_screen": 15#当次的数量多少
        },
        "ai": {
            "max_hands": 4#最高识别几只手
        },
        "paths": {
            "assets_dir": "assets",
            "models_dir": "models",
            "model_name": "hand_landmarker.task",
            "bgm_name": "1.mp3"
        }
    }
    if not os.path.exists(my_setting_file):
        try:
            with open(my_setting_file, 'w', encoding='utf-8') as f:
                yaml.dump(mo_ren, f, default_flow_style=False, allow_unicode=True)
            my_log.info(f"没找到配置，自动建了一个: {my_setting_file}")
        except Exception as e:
            my_log.error(f"创建配置文件失败了: {e}")
        return mo_ren

    try:
        with open(my_setting_file, 'r', encoding='utf-8') as f:
            user_peizhi = yaml.safe_load(f)
            #合并一下
            if user_peizhi is None:
                user_peizhi = {}
            for k, v in mo_ren.items():
                if k not in user_peizhi:
                    user_peizhi[k] = v
                elif isinstance(v, dict):
                    if not isinstance(user_peizhi[k], dict):
                        user_peizhi[k] = {}
                    for sub_k, sub_v in v.items():
                        if sub_k not in user_peizhi[k]:
                            user_peizhi[k][sub_k] = sub_v
            return user_peizhi
    except Exception as e:
        my_log.error(f"读配置文件失败，只能用默认的了: {e}")
        return mo_ren

SETTINGS = duqu_peizhi()

try:
    import pygame
    pygame.mixer.init()
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False
    # my_log.warning("没装pygame，没声音，环境pip install pygame") # 

WINDOW_WIDTH  = SETTINGS["game"]["window_width"]
WINDOW_HEIGHT = SETTINGS["game"]["window_height"]

#处理中文显示的（OpenCV直接写中文会乱码 转成PIL画）

_ziti_huancun = {}

def get_ziti(size: int) -> ImageFont.ImageFont:
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
            except:
                continue
    font = ImageFont.load_default()
    _ziti_huancun[size] = font
    return font

_wenzi_dui = []#文字堆

def add_cn_text(text: str, pos: tuple, font_size: int = 32,
                color=(255, 255, 255), bg_color=None, padding: int = 8):
    _wenzi_dui.append((text, pos, font_size, color, bg_color, padding))

def flush_cn_texts(frame: np.ndarray):
    global _wenzi_dui
    if not _wenzi_dui: return
    # 转RGB 不然颜色是反的
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    
    for text, (x, y), f_size, color, bg_c, pad in _wenzi_dui:
        font = get_ziti(f_size)
        if bg_c is not None:
            bbox = draw.textbbox((x, y), text, font=font)
            draw.rectangle(
                [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                fill=(bg_c[2], bg_c[1], bg_c[0])
            )
        draw.text((x, y), text, font=font, fill=(color[2], color[1], color[0]))
        
    _wenzi_dui = []
    np.copyto(frame, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))

#  加载图片和声音素材
FRUIT_TYPES = ['banana', 'boluo', 'iceBanana', 'Mango', 'mugua', 'peach', 'pear', 'pineapple', 'strawberry', 'b1']
MULTI_FRUIT_TYPES = ['watermelon', 'dragonfruit']

def load_shuiguo_imgs():
    imgs = {}
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS["paths"]["assets_dir"], 'sucai')
    for name in FRUIT_TYPES:
        w_path = os.path.join(base_dir, f'{name}.png')
        if name == 'b1':
            l_path = os.path.join(base_dir, 'bl.png')
            r_path = os.path.join(base_dir, 'br.png')#柠檬
        else:
            l_path = os.path.join(base_dir, f'{name}l.png')
            r_path = os.path.join(base_dir, f'{name}r.png')#找不到就看 其他水果的左边或者右边 就是一半一半
            
        if os.path.exists(w_path):#检查完整
            wi = cv2.imread(w_path, cv2.IMREAD_UNCHANGED)
            li = cv2.imread(l_path, cv2.IMREAD_UNCHANGED)
            ri = cv2.imread(r_path, cv2.IMREAD_UNCHANGED)  
            # 校验三张图片是否都成功读取
            if wi is not None and li is not None and ri is not None:
                imgs[name] = {'whole': wi, 'left': li, 'right': ri}
            else:
                from logger import my_log#防止检测不到照片直接程序卡死
                my_log.warning(f"水果 {name} 的图片素材不完整或损坏识别不到 已跳过加载")
    return imgs

def load_duo_shuiguo_imgs():
    # 西瓜和火龙果这种能切成好几块的
    imgs = {}
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS["paths"]["assets_dir"], 'sucai')
    suofang = 0.5
    
    # 1. 西瓜
    wp = os.path.join(base_dir, 'watermelon.png')
    if os.path.exists(wp):#检查文件在不在
        wi = cv2.imread(wp, cv2.IMREAD_UNCHANGED)#cv2专门检测照片能不能完整读取
        if wi is not None:#如果图片是完整的
            wi = cv2.resize(wi, None, fx=suofang, fy=suofang)#照片的缩放
            kuai = []#存一下照片的
            for i in range(1, 9):
                pp = os.path.join(base_dir, f'watermelon{i}.png')
                if os.path.exists(pp):
                    pi = cv2.imread(pp, cv2.IMREAD_UNCHANGED)#检查照片的完整
                    if pi is not None:
                        kuai.append(cv2.resize(pi, None, fx=suofang, fy=suofang))#完整就同比例缩放进列表里
            if len(kuai) == 8:
                imgs['watermelon'] = {'whole': wi, 'pieces': kuai, 'piece_count': 8}
                
    # 2. 火龙果 跟上面一样
    dp = os.path.join(base_dir, 'all.png')
    if os.path.exists(dp):
        wi = cv2.imread(dp, cv2.IMREAD_UNCHANGED)#检查
        if wi is not None:
            wi = cv2.resize(wi, None, fx=suofang, fy=suofang)
            kuai = []
            for i in range(1, 9):
                pp = os.path.join(base_dir, f'00{i}.png')
                if os.path.exists(pp):
                    pi = cv2.imread(pp, cv2.IMREAD_UNCHANGED)
                    if pi is not None:
                        kuai.append(cv2.resize(pi, None, fx=suofang, fy=suofang))
            if len(kuai) == 8:
                imgs['dragonfruit'] = {'whole': wi, 'pieces': kuai, 'piece_count': 8}
    return imgs

def load_guozhi_imgs():#果汁特效
    imgs = {}
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS["paths"]["assets_dir"], 'texiao')
    for i in range(1, 5):
        name = f'guozhi{i}'
        p = os.path.join(base_dir, f'{name}.png')
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                imgs[name] = img
    return imgs

def load_zhadan_imgs():#炸弹的
    imgs = {}
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS["paths"]["assets_dir"], 'zhadan')
    for key, fname, sc in [('bomb1', 'boom1.png', 1.0), ('bomb2', 'boom2.png', 1.0), ('explosion1', 'zha01.png', 2.0), ('explosion2', 'zha02.png', 2.0)]:
        p = os.path.join(base_dir, fname)
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                imgs[key] = cv2.resize(img, None, fx=sc, fy=sc) if sc != 1.0 else img
    return imgs

def load_daoguang_imgs():#刀的皮肤
    imgs = {}
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS["paths"]["assets_dir"], 'daoguang')
    for name in ['dao1', 'dao2']:
        p = os.path.join(base_dir, f'{name}.png')
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                imgs[name] = img
    return imgs

def load_combo_imgs():#特效的光效
    imgs = {}
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS["paths"]["assets_dir"], 'texiao')
    for name in ['combo1', 'combo2', 'combo3']:
        p = os.path.join(base_dir, f'{name}.png')
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                imgs[name] = img
    return imgs

def load_yinxiao():#读取打击特效时的音效
    sfx = {}
    if not HAS_SOUND: return sfx
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS["paths"]["assets_dir"], 'yinxiao')
    try:
        sp = os.path.join(base_dir, 'qieshuiguoyinxiao.mp3')
        if os.path.exists(sp): sfx['slice'] = pygame.mixer.Sound(sp)
        ep = os.path.join(base_dir, 'baozhayinxiao.mp3')
        if os.path.exists(ep): sfx['explosion'] = pygame.mixer.Sound(ep)
    except Exception:
        pass
    return sfx

# 水果对应的果汁颜色
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
    # 找不到就随便给个果汁
    return random.choice(list(JUICE_IMAGES.keys())) if JUICE_IMAGES else None

def overlay_image(bg: np.ndarray, fg: np.ndarray, x: int, y: int, rotation: float = 0, alpha_scale: float = 1.0):
    # 把带透明通道的PNG贴到背景上，带旋转
    if fg is None: return
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
        ov = cv2.warpAffine(ov, M, (nw, nh), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        
    oh, ow = ov.shape[:2]
    x1, y1 = int(x - ow // 2), int(y - oh // 2)
    x2, y2 = x1 + ow, y1 + oh
    if x1 >= bg.shape[1] or y1 >= bg.shape[0] or x2 <= 0 or y2 <= 0: return
    
    ox1, oy1 = max(0, -x1), max(0, -y1)
    ox2 = ow - max(0, x2 - bg.shape[1])
    oy2 = oh - max(0, y2 - bg.shape[0])
    bx1 = max(0, x1); by1 = max(0, y1)
    bx2 = min(bg.shape[1], x2); by2 = min(bg.shape[0], y2)
    if ox2 <= ox1 or oy2 <= oy1: return

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

# 全局预加载，不然游戏里卡顿
FRUIT_IMAGES = load_shuiguo_imgs()
MULTI_FRUIT_IMAGES = load_duo_shuiguo_imgs()
BOMB_IMAGES = load_zhadan_imgs()
BLADE_IMAGES = load_daoguang_imgs()
COMBO_IMAGES = load_combo_imgs()
JUICE_IMAGES = load_guozhi_imgs()
SOUND_EFFECTS = load_yinxiao()
