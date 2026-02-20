# coding=utf-8
"""
    需要用到的一些常量。
"""
import os.path
import ResMgr
MY_MODS_ID = 'autoConfigVoiceOver'
MY_MODS_LINKAGE = 'auto_config_voiceover'
MY_MODS_VERSION = '0.0.7c'
MY_MODS_CONFIG_VERSION = 4
VOICE_SELECTED_EVENT = 'vo_selected'                                            # 选中语音并应用后，将播放的一个 Wwise 事件
TANKMEN_XML_ROOT_PATH = 'scripts/item_defs/tankmen/'                            # ResMgr 中的虚拟路径
SPECIAL_VOICES_XML = 'scripts/item_defs/special_voices.xml'                     # 游戏中保存特殊成员语音信息的资源文件
MAIN_SOUND_MODES_XML = 'gui/soundModes/main_sound_modes.xml'                    # 游戏中保存全部声音模式的资源文件
MY_MODS_RES_DEFAULT_PNG = 'mods/autoconfigvoiceover/png/default.png'            # 插件中的资源文件
PATHS_JSON = 'res/mods/autoconfigvoiceover/paths.json'
GUP_SETTINGS_FILE = 'mods/gup.subtitles/settings.json'                          # 已经不需要了
GAME_ROOT_PATH = os.path.normpath(ResMgr.resolveToAbsolutePath('../..'))        # F:/World_of_Tanks_CN 以坦克世界 2.0 版本为例
RES_MODS_ROOT_PATH = os.path.normpath(ResMgr.resolveToAbsolutePath('.'))        # F:/World_of_Tanks_CN/res_mods/2.0.0.0
RES_GUP_MODS_PATH = os.path.join(RES_MODS_ROOT_PATH, 'mods', 'gup.subtitles')   # ../2.0.0.0/mods/gup.subtitles
SETTINGS_JSON = os.path.join(RES_GUP_MODS_PATH, 'settings.json')                # ../gup.subtitles/settings.json
MODS_ROOT_PATH = os.path.join(GAME_ROOT_PATH, 'mods')                           # F:/World_of_Tanks_CN/mods
MODS_PATH = RES_MODS_ROOT_PATH.replace('res_', '')                              # F:/World_of_Tanks_CN/mods/2.0.0.0
CONFIGS_ROOT_PATH = os.path.join(MODS_ROOT_PATH, 'configs')                     # F:/World_of_Tanks_CN/mods/configs
MY_LOG_PATH = os.path.join(CONFIGS_ROOT_PATH, 'autoConfigVoiceOver')            # ../configs/autoConfigVoiceOver
CONFIG_JSON = os.path.join(MY_LOG_PATH, 'config.json')                          # ../config.json
SCRIPT_LOG = os.path.join(MY_LOG_PATH, 'script.log')                            # ../script.log
MY_PNG_PATH = os.path.join(MY_LOG_PATH, 'images')                               # ../autoConfigVoiceOver/images
DEFAULT_PNG = os.path.join(MY_PNG_PATH, 'default.png')                          # ../images/default.png
UPDATE_PNG = os.path.join(MY_PNG_PATH, 'update.png')                            # 已经不需要了
MY_JSON_PATH = os.path.join(MY_LOG_PATH, 'jsons')                               # ../autoConfigVoiceOver/jsons
GAME_SOUND_MODES_JSON = os.path.join(MY_JSON_PATH, 'gameSoundModes.json')       # ../gameSoundModes.json
VOICEOVER_JSON = os.path.join(MY_JSON_PATH, 'voiceover.json')                   # ../voiceover.json
PLAY_EVENTS_JSON = os.path.join(MY_JSON_PATH, 'playEvent.json')                 # ../playEvents.json
SETTINGS_JSON_COPY = os.path.join(MY_JSON_PATH, 'settings.json')                # ../settings.json  替换默认settings文件
MY_TEMPLATE_PATH = os.path.join(MY_LOG_PATH, 'templates')                       # ../autoConfigVoiceOver/templates
INFO_JSON__ = os.path.join(MY_LOG_PATH, 'voiceover_info', 'info.json')          # 旧的文件和目录——将会被自动移除
TEMPLATE_JSON_PATH__ = os.path.join(MY_LOG_PATH, 'template_json')
VOICEOVER_INFO_PATH__ = os.path.join(MY_LOG_PATH, 'voiceover_info')
CURRENT_VOLUME = None
DEFAULT_VOLUME = 25
IS_API_PRESENT = False
SHOW_DETAILS = True
WHO_AM_I = ''
WHERE_AM_I = ''
WHERE_ARE_PARENT = ''
MOD_FILES_DICT = {}
DEFAULT_CONFIG = {
    'enabled': True,
    'vo_list_option': 0,
    'current_voice': 0,
    '__event__': 0,
    'volume': DEFAULT_VOLUME,
    'nation_voice_gender': 0,
    'full_crew': 0,
    'language_tag': 0,
    'ingame_voice_visible': False,
    'outside_voice_visible': False,
    'auto_volume': True,
    'auto_remapping': True,
    'info_notify': True,
    'show_details': True,
    '__version__': MY_MODS_CONFIG_VERSION
}
