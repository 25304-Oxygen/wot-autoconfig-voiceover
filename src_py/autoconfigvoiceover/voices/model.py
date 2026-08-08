# coding=utf-8
"""数据模型与语音包目录结构约定。

PackInfo 只保留扫描期的核心信息（懒加载策略）：
目录内部可选资源不在扫描期探测入模型，约定固化为下方路径常量；
语音包活跃时由消费方（字幕/换肤/详情页）经 pack_res / find_first
现场用 ResMgr 探测与解析——VFS 运行期不可变，现场探测永远准确。
"""

from collections import namedtuple

import ResMgr

# ═════════════════════════════════════════════════════════════
# 核心模型
# ═════════════════════════════════════════════════════════════

PackInfo = namedtuple('PackInfo', (
    'pack_id',    # 目录名，即 voiceID（天然唯一）
    'nick_name',  # pack.json 的 name——语音包中文名称
    'bank',       # pack.json 的 path——从 res/ 出发指向 voiceover.bnk 的 VFS 路径
    'root',       # 'mods/voiceover/<pack_id>/'——包内资源根（VFS）
))
"""扫描期只读取不校验；bank 存在性在加载阶段验证，无效包直接移除。
注册所需字段：name=pack_id、description=nick_name、wwbanks/bank=bank、
wwise_language 由 bank 路径现场推导（仅注册处使用，不入模型）。"""

# ═════════════════════════════════════════════════════════════
# 目录结构约定（路径相对包根 root；语音包活跃时按需探测）
# ═════════════════════════════════════════════════════════════

PACK_JSON = 'pack.json'
"""基础信息入口（★唯一必需项），仅 path/name 两键"""

# — 字幕子树 —
SUB_STYLES_DIR = 'subtitles/'          # 样式文件（目录下第一个 .json）
SUB_SENTENCES_DIR = 'subtitles/sentences/'
SUB_IMAGES_DIR = 'subtitles/images/'

# — 菜单换肤 —
BGIMGS_DIR = 'bgimgs/'   # menu.png / page.png / panel.png
ICONS_DIR = 'icons/'     # help.png / settings.png / voice.png

# — 其他可选项（候选列表按优先级排列，用 find_first 探测）—
ATTACH_JSON = 'attach.json'
THEME_JSON = 'theme.json'
EVENTS_JSON = 'events.json'
REMAP_CANDIDATES = ['remap.json', 'audio_mods.xml']
INFO_CANDIDATES = ['info.html', 'info.txt']

# ═════════════════════════════════════════════════════════════
# 显示名约定（移植旧版 template.py）
# ═════════════════════════════════════════════════════════════
# 车长名 tag（[含车组]/[多语言]）与多语言显示名（默认语种/英语/俄语/普通话）
# 已移至 l10n 词典（voice_switch/tag/*、voice_switch/lang/*），随客户端语言
# 读取时烘焙，见 game_reader._lang_label 与 l10n.text_for_client()。


# ═════════════════════════════════════════════════════════════
# 取路径辅助（消费方在语音包活跃时调用）
# ═════════════════════════════════════════════════════════════

def pack_res(pack, relpath):
    """拼出包内资源的 VFS 路径。

    返回值以 mods/ 开头，Flash 端 ImageCache.load() 可直接消费
    （自动补 ../../ 转为 SWF 相对路径）。
    """
    return pack.root + relpath


def find_first(pack, candidates):
    """按优先级探测候选文件，返回第一个存在者的 VFS 路径；都不存在返回 None。"""
    for name in candidates:
        path = pack.root + name
        if ResMgr.isFile(path):
            return path
    return None
