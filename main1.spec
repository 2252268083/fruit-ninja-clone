# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# 让 spec 能 import 项目根目录下的 version.py（SPECPATH 是 spec 所在目录）
try:
    _spec_dir = SPECPATH
except NameError:
    _spec_dir = os.getcwd()
if isinstance(_spec_dir, (list, tuple)):
    _spec_dir = _spec_dir[0]
sys.path.insert(0, _spec_dir)

from version import __version__

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('mediapipe')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# 【包体积优化】项目里用不到的重型库，全部排除，不打进包里
# 注意：matplotlib 虽然"游戏代码"没用，但 mediapipe 的 drawing_utils.py 顶层就
# import matplotlib.pyplot，打包后 mediapipe 一导入就会 ModuleNotFoundError，
# 所以 matplotlib 绝对不能排除（已踩坑验证）。
# 项目实际只用到：cv2 / numpy / mediapipe / PyYAML / Pillow / pygame / matplotlib(被mediapipe间接引用)
unused_libs = [
    'torch', 'torchvision', 'tensorflow', 'torchaudio',      # 深度学习全家桶（mediapipe 推理不需要）
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter',       # GUI 框架（游戏窗口用的是 cv2.imshow）
    'scipy', 'pandas', 'sympy',                              # 科学计算（仅 mediapipe 自带 test 模块引用，运行时不会加载）
    'IPython', 'jupyter', 'notebook', 'ipykernel',           # Notebook 环境
    'pytest', 'sphinx', 'pygments',                          # 测试/文档工具
    'numpy.distutils', 'numpy.f2py', 'numpy.testing',        # numpy 的构建与测试子模块
]

a = Analysis(
    ['main1.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=unused_libs,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # 【启动优化】关闭UPX：压缩过的DLL每次启动都要先解压，还容易被杀毒软件深度扫描，反而更慢
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,          # 同上，两处UPX全部关闭
    upx_exclude=[],
    name=f'main1_v{__version__}',   # 【版本】交付目录名带上版本号，例如 dist/main1_v2.1.0
)
