import os
import sys
import cv2
import yaml
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from logger import my_log
from fonts import get_ziti

def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_base_dir():
    # 改为始终返回 exe 所在目录，这样游戏运行时就会去读外部的 assets 和 models
    return get_exe_dir()

"""
加载配置文件 把各种内容读取到内存 把照片转成透明通道 超出部分裁剪 （照片的处理与读取）和背景音乐
"""

FRUIT_IMAGES = {}
FRUIT_TYPES = []
MULTI_FRUIT_TYPES = ['watermelon', 'dragonfruit']
MULTI_FRUIT_IMAGES = {}
# 找配置文件
my_setting_file = os.path.join(get_exe_dir(), 'settings.yaml')

def duqu_peizhi():#默认配置
    # 默认给个配置
    mo_ren = {
        "camera": {"index": 0, "width": 1280, "height": 720, "fps": 60, "mirror": True},
        "game": {
            "window_width": 1280,
            "window_height": 720,
            "spawn_interval": 12,  # 水果生成速度
            "min_spawn_interval": 4,  # 难度提升后允许的最小生成间隔
            "max_on_screen": 12,  # 初始同时存在的物体数
            "max_on_screen_cap": 25,  # 难度提升后物体数上限
            "difficulty_step_time": 10,  # 每隔多少秒提升一次难度
            "total_time": 30,  # 双人pk的时候，时长调整
            "fruit_theme": "default",  # 默认主题开关
            "max_missed": 15,  # 最大允许漏掉数
            "max_bombs_hit": 4,  # 最大允许碰到炸弹数
            "bomb_chance": 0.22,  # 生成炸弹的概率
            "deadly_chance": 0.25,  # 生成致命炸弹的概率
            "multi_chance": 0.15,  # 生成多块水果的概率
            "max_consec_bombs": 2,  # 最大连续生成炸弹数
        },
        "ai": {
            "max_hands": 4,  # 最高识别几只手
            "delegate": "auto",  # auto=优先 GPU，失败退回 CPU
            "infer_width": 320,  # 推理输入宽度（高度按摄像头比例自动算）
        },
        "paths": {
            "assets_dir": "assets",
            "models_dir": "models",
            "model_name": "hand_landmarker.task",
            "bgm_name": "1.mp3"
        },
        "ads": {"scale": 0.7, "custom_scales": {}},
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
    try:
        pygame.mixer.init()
        HAS_SOUND = True
    except Exception as e:
        # 常见原因：没有扬声器/耳机、默认音频设备被拔出（蓝牙耳机断开、HDMI 无输出）
        my_log.warning(f"音频设备初始化失败：{e}")
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        # 退化到 dummy 声卡：仍然可以加载音效，只是没有声音，游戏照常运行
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        try:
            pygame.mixer.init()
            my_log.warning("已切换为静音模式（dummy 音频驱动），插上音频设备后重启即可恢复声音")
        except Exception as e2:
            my_log.error(f"静音模式也初始化失败，游戏将无声运行：{e2}")
        HAS_SOUND = False
except ImportError:
    HAS_SOUND = False
    # my_log.warning("没装pygame，没声音，环境pip install pygame") # 

WINDOW_WIDTH  = SETTINGS["game"]["window_width"]
WINDOW_HEIGHT = SETTINGS["game"]["window_height"]


def get_infer_width():
    """推理输入宽度：只配宽度，高度按真实画面比例推导"""
    return max(64, int(SETTINGS["ai"].get("infer_width", 320)))


def get_preheat_shape():
    """预热零图尺寸：宽取配置，高按 16:9 推导（正式推理按摄像头真实比例）"""
    w = get_infer_width()
    return max(2, int(round(w * 9 / 16))), w

#处理中文显示的（OpenCV直接写中文会乱码 转成PIL画）

_wenzi_dui = []#文字堆

def add_cn_text(text: str, pos: tuple, font_size: int = 32,#opencv不能绘画
                color=(255, 255, 255), bg_color=None, padding: int = 8):
    _wenzi_dui.append((text, pos, font_size, color, bg_color, padding))

def _text_rect(text, pos, font, bg_c, pad, w, h):
    """文字（含背景框留白）在画面内的裁剪矩形；完全在画面外返回 None"""
    x, y = pos
    try:
        x0, y0, x1, y1 = font.getbbox(text)
    except Exception:
        return None
    r = [x + x0, y + y0, x + x1, y + y1]
    if bg_c is not None:
        r = [r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad]
    rx1, ry1 = max(0, int(r[0])), max(0, int(r[1]))
    # PIL 的 rectangle 两端都包含，右/下各多留 1px，避免裁掉边框最后一行一列
    rx2 = min(w, int(r[2] + 0.999) + 1)
    ry2 = min(h, int(r[3] + 0.999) + 1)
    if rx2 <= rx1 or ry2 <= ry1:
        return None
    return [rx1, ry1, rx2, ry2]


def _flush_full(frame, items):
    """整幅转换的兜底路径（矩形异常或碎片过多时使用）"""
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    for text, (x, y), f_size, color, bg_c, pad in items:
        font = get_ziti(f_size)
        if bg_c is not None:
            bbox = draw.textbbox((x, y), text, font=font)
            draw.rectangle(
                [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                fill=(bg_c[2], bg_c[1], bg_c[0])
            )
        draw.text((x, y), text, font=font, fill=(color[2], color[1], color[0]))
    np.copyto(frame, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))


def flush_cn_texts(frame: np.ndarray):#解决了中文不能绘画上去的问题
    global _wenzi_dui
    items = _wenzi_dui
    if not items: return
    _wenzi_dui = []

    h, w = frame.shape[:2]
    rects = []
    for text, pos, f_size, color, bg_c, pad in items:
        r = _text_rect(text, pos, get_ziti(f_size), bg_c, pad, w, h)
        if r is None:
            _flush_full(frame, items)
            return
        rects.append(r)

    # 相交的矩形合并，减少转换次数
    changed = True
    while changed:
        changed = False
        merged = []
        for r in rects:
            for o in merged:
                if r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3]:
                    o[0], o[1] = min(o[0], r[0]), min(o[1], r[1])
                    o[2], o[3] = max(o[2], r[2]), max(o[3], r[3])
                    changed = True
                    break
            else:
                merged.append(r)
        rects = merged

    # 碎片太多时整幅转换更划算
    if not rects or len(rects) > 8:
        _flush_full(frame, items)
        return

    for rx1, ry1, rx2, ry2 in rects:
        roi = frame[ry1:ry2, rx1:rx2]
        pil_img = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        rw, rh = rx2 - rx1, ry2 - ry1
        for text, (x, y), f_size, color, bg_c, pad in items:
            lx, ly = x - rx1, y - ry1
            font = get_ziti(f_size)
            bbox = draw.textbbox((lx, ly), text, font=font)
            # 只画与当前 ROI 有交集的文字
            if bbox[2] <= 0 or bbox[0] >= rw or bbox[3] <= 0 or bbox[1] >= rh:
                continue
            if bg_c is not None:
                draw.rectangle(
                    [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                    fill=(bg_c[2], bg_c[1], bg_c[0])
                )
            draw.text((lx, ly), text, font=font, fill=(color[2], color[1], color[0]))
        np.copyto(roi, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))



def load_dynamic_ads(base_dir, theme_folder="ads", scale=0.7, custom_scales=None):
    if custom_scales is None:
        custom_scales = {}
    ads_path = os.path.join(
        get_base_dir(),
        base_dir, "sucai", theme_folder
    )
    loaded_imgs = {}

    if not os.path.exists(ads_path):
        my_log.warning(f"广告文件夹不存在: {ads_path}")
        return loaded_imgs

    for filename in os.listdir(ads_path):
        if not filename.lower().endswith(".png"):
            continue
        if filename.lower().endswith("l.png") or filename.lower().endswith("r.png"):
            continue

        name = os.path.splitext(filename)[0]
        p_whole = os.path.join(ads_path, filename)
        p_left = os.path.join(ads_path, f"{name}l.png")
        p_right = os.path.join(ads_path, f"{name}r.png")

        img_w = cv2.imread(p_whole, cv2.IMREAD_UNCHANGED)
        img_l = cv2.imread(p_left, cv2.IMREAD_UNCHANGED)
        img_r = cv2.imread(p_right, cv2.IMREAD_UNCHANGED)

        if img_w is None:
            my_log.warning(f"完整图读取失败: {p_whole}")
            continue
        if img_l is None or img_r is None:
            my_log.warning(f"素材缺失: {name} 缺少切开部分，跳过该素材")
            continue

        item_scale = custom_scales.get(name, scale)
        my_log.info(f"广告 [{name}] 准备缩放，使用的比例是: {item_scale}") # 记录缩放比例
        if item_scale != 1.0:
            img_w = cv2.resize(img_w, (0, 0), fx=item_scale, fy=item_scale)
            img_l = cv2.resize(img_l, (0, 0), fx=item_scale, fy=item_scale)
            img_r = cv2.resize(img_r, (0, 0), fx=item_scale, fy=item_scale)

        loaded_imgs[name] = {'whole': img_w, 'left': img_l, 'right': img_r}

    return loaded_imgs


SUIGUO_ZHUTI = SETTINGS["game"].get("fruit_theme", "default")

DEFAULT_FRUIT_TYPES = ['banana', 'boluo', 'iceBanana', 'Mango', 'mugua', 'peach', 'pear', 'pineapple', 'strawberry', 'b1']

if SUIGUO_ZHUTI == "ads":
    my_log.info(f"读取到的ads配置: {SETTINGS.get('ads', {})}") # 记录广告配置
    FRUIT_IMAGES = load_dynamic_ads(
        SETTINGS["paths"]["assets_dir"],
        "ads",
        scale=SETTINGS.get("ads", {}).get("scale", 0.7),
        custom_scales=SETTINGS.get("ads", {}).get("custom_scales", {})
    )

    my_log.info(f"广告素材加载成功：{list(FRUIT_IMAGES.keys())}")

    FRUIT_TYPES = list(FRUIT_IMAGES.keys())
    if not FRUIT_TYPES:
        # 广告目录为空时不能让 FRUIT_TYPES 变成空列表，否则 random.choice 直接崩溃
        my_log.warning("广告素材目录为空，已回退到默认水果主题")
        SUIGUO_ZHUTI = "default"
        FRUIT_TYPES = DEFAULT_FRUIT_TYPES
else:
    FRUIT_IMAGES = {}
    FRUIT_TYPES = DEFAULT_FRUIT_TYPES


def load_shuiguo_imgs():
    imgs = {}
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"], 'sucai')
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

if not FRUIT_IMAGES:
    FRUIT_IMAGES = load_shuiguo_imgs()

def load_duo_shuiguo_imgs():
    # 西瓜和火龙果这种能切成好几块的
    imgs = {}
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"], 'sucai')
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
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"], 'texiao')
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
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"], 'zhadan')
    for key, fname, sc in [('bomb1', 'boom1.png', 1.0), ('bomb2', 'boom2.png', 1.0), ('explosion1', 'zha01.png', 2.0), ('explosion2', 'zha02.png', 2.0)]:
        p = os.path.join(base_dir, fname)
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                imgs[key] = cv2.resize(img, None, fx=sc, fy=sc) if sc != 1.0 else img
    return imgs

def load_daoguang_imgs():#刀的皮肤
    imgs = {}
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"], 'daoguang')
    for name in ['dao1', 'dao2']:
        p = os.path.join(base_dir, f'{name}.png')
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is not None:
                imgs[name] = img
    return imgs

def load_combo_imgs():#特效的光效
    imgs = {}
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"], 'texiao')
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
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"], 'yinxiao')
    # 两个音效分别加载：一个失败不影响另一个
    try:
        sp = os.path.join(base_dir, 'qieshuiguoyinxiao.mp3')
        if os.path.exists(sp): sfx['slice'] = pygame.mixer.Sound(sp)
    except Exception as e:
        my_log.warning(f"切片音效加载失败：{e}")
    try:
        ep = os.path.join(base_dir, 'baozhayinxiao.mp3')
        if os.path.exists(ep): sfx['explosion'] = pygame.mixer.Sound(ep)
    except Exception as e:
        my_log.warning(f"爆炸音效加载失败：{e}")
    return sfx

def play_bgm():#播放背景音乐
    if not HAS_SOUND: return
    #从配置里拿音乐名字
    bgm_name = SETTINGS["paths"].get("bgm_name", "1.mp3")
    base_dir = os.path.join(get_base_dir(), SETTINGS["paths"]["assets_dir"])
    bgm_path = os.path.join(base_dir, bgm_name)
    try:
        if os.path.exists(bgm_path):
            pygame.mixer.music.load(bgm_path)#加载音乐
            pygame.mixer.music.set_volume(0.4)#声音稍微调小点 别盖过切水果的音效
            pygame.mixer.music.play(-1)#-1就是一直循环播放
        else:
            from logger import my_log
            my_log.warning(f"没找到背景音乐文件: {bgm_path}")
    except Exception as e:
        from logger import my_log
        my_log.error(f"播放背景音乐失败: {e}")

# 水果对应的果汁颜色
# 水果对应的果汁颜色
FRUIT_JUICE_MAP = {
    'banana': 'guozhi1', 'boluo': 'guozhi1', 'iceBanana': 'guozhi2',
    'Mango': 'guozhi1', 'mugua': 'guozhi1', 'peach': 'guozhi3',
    'pear': 'guozhi2', 'pineapple': 'guozhi1', 'strawberry': 'guozhi4',
    'watermelon': 'guozhi4', 'dragonfruit': 'guozhi3', 'b1': 'guozhi1',
    'shenwan_boluo': 'guozhi1',  # 新增：商业水果果汁1
    'huangpu_lawei': 'guozhi2',  # 新增：商业水果果汁2
}

if SUIGUO_ZHUTI == "ads":
    for name in FRUIT_TYPES:
        if name not in FRUIT_JUICE_MAP:
            FRUIT_JUICE_MAP[name] = "guozhi1"



def get_juice_color(fruit_type):
    c = FRUIT_JUICE_MAP.get(fruit_type)
    if c and c in JUICE_IMAGES:
        return c
    # 找不到就随便给个果汁
    return random.choice(list(JUICE_IMAGES.keys())) if JUICE_IMAGES else None

_ROT_CACHE = {}


def _rotate_cached(fg, rotation, cache_key):
    """旋转带透明通道的贴图：角度按 5° 量化缓存，避免水果每帧重复 warpAffine"""
    q = int(round(rotation / 5.0)) % 72
    key = (cache_key, fg.shape, q)
    ov = _ROT_CACHE.get(key)
    if ov is not None:
        return ov

    h, w = fg.shape[:2]
    cx, cy = w // 2, h // 2
    M = cv2.getRotationMatrix2D((cx, cy), q * 5.0, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw = int(h * sin + w * cos)
    nh = int(h * cos + w * sin)
    M[0, 2] += nw / 2 - cx
    M[1, 2] += nh / 2 - cy
    ov = cv2.warpAffine(fg, M, (nw, nh), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    while len(_ROT_CACHE) >= 512:   # 逐个淘汰最旧的，避免整体清空造成周期性卡顿
        _ROT_CACHE.pop(next(iter(_ROT_CACHE)), None)
    _ROT_CACHE[key] = ov
    return ov


def overlay_image(bg: np.ndarray, fg: np.ndarray, x: int, y: int, rotation: float = 0,
                  alpha_scale: float = 1.0, cache_key=None):
    # 把带透明通道的PNG贴到背景上，带旋转
    if fg is None: return#如果没有照片就无
    h, w = fg.shape[:2]#获取宽高
    if rotation != 0:#如果旋转，计算转后大小
        if cache_key is not None:
            ov = _rotate_cached(fg, rotation, cache_key)
        else:
            cx, cy = w // 2, h // 2
            M = cv2.getRotationMatrix2D((cx, cy), rotation, 1.0)
            cos, sin = abs(M[0, 0]), abs(M[0, 1])
            nw = int(h * sin + w * cos)
            nh = int(h * cos + w * sin)
            M[0, 2] += nw / 2 - cx
            M[1, 2] += nh / 2 - cy
            ov = cv2.warpAffine(fg, M, (nw, nh), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    else:
        ov = fg
        
    oh, ow = ov.shape[:2]#获取图片的宽和高
    x1, y1 = int(x - ow // 2), int(y - oh // 2)#左上角的坐标
    x2, y2 = x1 + ow, y1 + oh#右上角的坐标
    if x1 >= bg.shape[1] or y1 >= bg.shape[0] or x2 <= 0 or y2 <= 0: return#如果太大 完全超出屏幕 为空
    
    ox1, oy1 = max(0, -x1), max(0, -y1)#计算裁剪的左边，上边
    ox2 = ow - max(0, x2 - bg.shape[1])#右
    oy2 = oh - max(0, y2 - bg.shape[0])#下
    bx1 = max(0, x1); by1 = max(0, y1)#背景开始贴的位置
    bx2 = min(bg.shape[1], x2); by2 = min(bg.shape[0], y2)#结束位置
    if ox2 <= ox1 or oy2 <= oy1: return#无内容直接无

    crop_ov = ov[oy1:oy2, ox1:ox2]#剪去超出的部分剩下的
    crop_bg = bg[by1:by2, bx1:bx2]#背景:要被覆盖的区域

    # numpy 向量化混合，替代原来逐通道的 Python 循环
    if crop_ov.shape[2] == 4:#判断图片透明通道
        alpha = (crop_ov[:, :, 3:4].astype(np.float32) / 255.0) * alpha_scale
        crop_bg[:] = (crop_bg.astype(np.float32) * (1.0 - alpha)
                      + crop_ov[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)
    else:
        if alpha_scale == 1.0:
            bg[by1:by2, bx1:bx2] = crop_ov#完全覆盖
        else:
            crop_bg[:] = (crop_bg.astype(np.float32) * (1.0 - alpha_scale)
                          + crop_ov.astype(np.float32) * alpha_scale).astype(np.uint8)

# 全局预加载

MULTI_FRUIT_IMAGES = load_duo_shuiguo_imgs()
BOMB_IMAGES = load_zhadan_imgs()
BLADE_IMAGES = load_daoguang_imgs()
COMBO_IMAGES = load_combo_imgs()
JUICE_IMAGES = load_guozhi_imgs()
SOUND_EFFECTS = load_yinxiao()
