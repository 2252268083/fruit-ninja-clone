# Swift-Fruit-Slice (AI 切水果)

基于 MediaPipe 和 OpenCV 的 AI 视觉互动切水果游戏。通过摄像头捕捉手势进行游玩，支持单手、双手以及双人 PK 模式。

## 目录结构
- `main.py`: 游戏主程序入口
- `config.py`: 游戏配置与资源加载模块
- `game_core.py`: 游戏核心逻辑与实体定义 (水果、炸弹、特效等)
- `vision_engine.py`: 基于 MediaPipe 的手部关键点追踪模块
- `math_utils.py`: 坐标平滑与防抖算法 (EWMA / Kalman)
- `ui_screens.py`: 游戏 UI 界面组件 (模式选择、刀光选择、结算界面)
- `logger.py`: 标准化日志系统
- `assets/`: 游戏图像与音效素材目录
- `models/`: MediaPipe AI 模型目录

## 环境要求与安装
确保已安装 Python 3.9+。
使用以下命令安装依赖：
```bash
pip install -r requirements.txt
```

## 运行游戏
```bash
python main.py
```

## 玩法说明
1. **模式选择**：单手模式、双手模式、双人PK模式（两人同屏对战 30 秒）。
2. **操作方式**：将食指举在镜头前充当“刀刃”，在屏幕上挥动切割弹出的水果。
3. **避开炸弹**：切到普通炸弹会扣分，切到致命炸弹直接结束游戏。
