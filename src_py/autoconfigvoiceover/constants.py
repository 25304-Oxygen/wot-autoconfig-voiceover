# coding=utf-8
"""ACV mod 常量与路径配置。

所有游戏运行时的文件系统路径在此集中定义，通过 ResMgr 解析。
"""

import os
import ResMgr

# ═════════════════════════════════════════════════════════════
# Wwise 事件
# ═════════════════════════════════════════════════════════════

VOICE_SELECTED_EVENT = 'vo_selected'  # 切换语音后播放的确认音效

# ═════════════════════════════════════════════════════════════
# 游戏资源路径（ResMgr 虚拟路径，不要在前面加 res/）
# ═════════════════════════════════════════════════════════════

TANKMEN_XML_DIR = 'scripts/item_defs/tankmen/'
SPECIAL_VOICES_XML = 'scripts/item_defs/special_voices.xml'
MAIN_SOUND_MODES_XML = 'gui/soundModes/main_sound_modes.xml'

# ═════════════════════════════════════════════════════════════
# 文件系统路径（运行时由 ResMgr.resolveToAbsolutePath 解析）
# ═════════════════════════════════════════════════════════════

GAME_ROOT_PATH = os.path.normpath(ResMgr.resolveToAbsolutePath('../..'))
"""游戏根目录，例如 F:/World_of_Tanks_CN"""

RES_MODS_ROOT_PATH = os.path.normpath(ResMgr.resolveToAbsolutePath('.'))
"""res_mods 版本目录，例如 F:/World_of_Tanks_CN/res_mods/2.0.0.0"""

MODS_ROOT_PATH = os.path.join(GAME_ROOT_PATH, 'mods')
"""mods 根目录，例如 F:/World_of_Tanks_CN/mods"""

MODS_PATH = RES_MODS_ROOT_PATH.replace('res_', '')

CONFIGS_ROOT_PATH = os.path.join(MODS_ROOT_PATH, 'configs')
"""mod 配置根目录，例如 F:/World_of_Tanks_CN/mods/configs"""

# — Mod 自身数据目录 —
MY_CONFIG_FOLDER = os.path.join(CONFIGS_ROOT_PATH, 'autoConfigVoiceOver')

MY_JSONS_FOLDER = os.path.join(MY_CONFIG_FOLDER, 'jsons')
MY_ICONS_FOLDER = os.path.join(MY_CONFIG_FOLDER, 'icons')
MY_BGIMGS_FOLDER = os.path.join(MY_CONFIG_FOLDER, 'bgimgs')
MY_SUBTITLES_FOLDER = os.path.join(MY_CONFIG_FOLDER, 'subtitles')

# Flash 端加载磁盘资源的路径前缀。
# ★ ImageCache.load 检测到 "mods/" 前缀会自动补 "../../"（见 ImageCache.as:91），
#   结果从 res/gui/flash/ 解析到 res/mods/configs/... 而非游戏根目录的 mods/configs/。
#   因此用 "../../../mods/configs/..." 绕过自动前缀：从 res/gui/flash/ 上溯 3 级
#   到达游戏根目录，再进入 mods/configs/autoConfigVoiceOver/。
DISK_FLASH_PREFIX = '../../../mods/configs/autoConfigVoiceOver'

# — 具体文件 —
CONFIG_FILE = os.path.join(MY_CONFIG_FOLDER, 'config.json')
"""用户配置文件"""

PERSONAL_SETTINGS_FILE = os.path.join(MY_JSONS_FOLDER, 'personal_settings.json')
"""个性设置配置文件——被点亮喊话、快捷消息替换等。"""

# — 语音包数据落盘（沿用 1.x 文件名，继承旧版用户数据，零迁移）—
GAME_SOUND_MODES_JSON = os.path.join(MY_JSONS_FOLDER, 'gameSoundModes.json')
"""内置语音行 [{'voiceID','nickName','volume'}]——用户可改名，回读继承"""

VOICEOVER_JSON = os.path.join(MY_JSONS_FOLDER, 'voiceover.json')
"""第三方语音行 + 音量方案"""

SCRIPT_LOG = os.path.join(MY_CONFIG_FOLDER, 'script.log')
"""Mod 独立日志文件"""

# ═════════════════════════════════════════════════════════════
# 语音包
# ═════════════════════════════════════════════════════════════

VOICEOVER_PACKS_DIR = 'mods/voiceover/'
"""约定的第三方语音包目录（VFS 虚拟路径）：
每个子目录 = 一个语音包，目录名即 voiceID，目录内必须有 pack.json"""

DEFAULT_VOLUME = 25
"""第三方语音包的兜底默认音量（读不到 voice 通道音量时使用）"""

# ═════════════════════════════════════════════════════════════
# VFS 资源路径（打包在 wotmod 内，Flash ImageCache 加载用）
# ═════════════════════════════════════════════════════════════

MOD_RES_ICONS_DIR = 'mods/autoconfigvoiceover/icons/'
MOD_RES_BGIMGS_DIR = 'mods/autoconfigvoiceover/bgimgs/'
MOD_RES_IMAGES_DIR = 'mods/autoconfigvoiceover/images/'

MODSLIST_RES_ICONS = MOD_RES_ICONS_DIR + 'icon.png'
"""ModsList 入口图标（VFS 路径；icon.png 不拷贝到磁盘，仅从 VFS 读取）。"""

PLAY_EVENTS_VFS = 'mods/autoconfigvoiceover/jsons/playEvent.json'
"""试听事件列表 [{'text','event'}]——随 mod 打包的只读资源，
暂时只从 VFS 读取（不在 configs/ 下生成、不落盘）"""

# ═════════════════════════════════════════════════════════════
# 磁盘资源路径（游戏根目录 mods/configs/autoConfigVoiceOver/）
# ═════════════════════════════════════════════════════════════

DEFAULT_MENU_IMAGES = {
    'bigCircle':    DISK_FLASH_PREFIX + '/bgimgs/menu.png',
    'semiPanel':    DISK_FLASH_PREFIX + '/bgimgs/panel.png',
    'fullPanel':    DISK_FLASH_PREFIX + '/bgimgs/page.png',
    'smallCircles': [DISK_FLASH_PREFIX + '/icons/settings.png',
                     DISK_FLASH_PREFIX + '/icons/voice.png',
                     DISK_FLASH_PREFIX + '/icons/help.png'],
}
"""菜单组件默认图片路径（指向磁盘副本，用户可替换）。
菜单就绪后经 as_setImagesS 推送；ensure_config_ready() 保证文件已就位。
只处理传入的键，图片加载失败时对应组件保持默认外观。"""

# — 下面按需扩展 —
# MOD_RES_SWF = 'gui/flash/autoConfigVoiceOverMenu.swf'

