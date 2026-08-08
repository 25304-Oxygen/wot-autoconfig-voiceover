# coding=utf-8
"""字幕子包：数据加载 + 状态机 + 排队策略。

loader    — 样式/句子文件双语键名解析
base      — BaseSubtitleManager 基类
assembler — 渲染数据组装（Entry → Flash dict）
merger    — Entry 合并为 CompoundItem（S3/S4 共用）
queue_s1  — S1 串行-原子策略
queue_s2  — S2 并行-原子策略
queue_s3  — S3 串行-合并策略
queue_s4  — S4 并行-合并策略
host      — SWF 宿主 + Manager 生命周期 + 策略切换
"""

# —— 数据加载（loader）——
from .loader import (
    SubtitleStyle,
    SubtitleEntry,
    SubtitleData,
    is_subtitle_available,
    load_style,
    load_sentence,
    load_offsets,
    save_offsets,
    load_template_sentence,
    get_pack_id,
    collect_style_images,
)

# —— 基类 ——
from .base import BaseSubtitleManager

# —— 策略 ——
from .queue_s1 import S1Manager
from .queue_s2 import S2Manager
from .queue_s3 import S3Manager
from .queue_s4 import S4Manager

# —— 旧 manager.py 保留兼容（逐步废弃）——
from .manager import (
    SubtitleManager,
    RendererState,
    SubtitleSession,
    DEFAULT_SLOT_HEIGHT,
)
