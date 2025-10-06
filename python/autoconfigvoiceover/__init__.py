# coding=utf-8
"""
    软件包的构造模块，限制了导入变量。
    主要作用是初始化一些文件和常量。
"""
__all__ = ['MODS_PATH', 'WHERE_AM_I', 'MY_MODS_VERSION', 'REMOVE_PROCESS', 'WHERE_ARE_PARENT',
           'g_search', 'g_update', 'g_template', 'mylogger', 'override']

from collections import Counter
from constants import *
from myLogger import mylogger
from fileSearch import *
from updateFile import *
from tools import *
try:
    from createTemplate import *
except ImportError:
    pass

mylogger.info('__init__', 'mod所在位置：%s' % WHERE_AM_I)
# 以下代码用于初始化日志文件夹
if not os.path.exists(TEMPLATE_JSON_PATH):
    os.chdir(MY_LOG_PATH)
    os.makedirs('template_json')
    os.chdir(GAME_ROOT_PATH)

if not os.path.exists(VOICEOVER_INFO_PATH):
    os.chdir(MY_LOG_PATH)
    os.makedirs('voiceover_info')
    os.chdir(GAME_ROOT_PATH)

if not os.path.exists(GAME_SOUND_MODES_JSON):
    with open(GAME_SOUND_MODES_JSON, 'w') as f:
        f.write(GAME_SOUND_MODES_TEMPLATE)
    mylogger.info('__init__', '已创建gameSoundModes.json。')

if not os.path.exists(PLAY_EVENTS_JSON):
    with open(PLAY_EVENTS_JSON, 'w') as f:
        f.write(PLAY_EVENTS_TEMPLATE)
    mylogger.info('__init__', '已创建playEvents.json。')

if not os.path.exists(INFO_JSON):
    open(INFO_JSON, 'w').close()
    mylogger.info('__init__', '已创建空的info.json。')

if not os.path.exists(DEFAULT_MODES_JSON):
    msg = {'ZH_CH_volume': CURRENT_VOLUME,
           'RU_volume': CURRENT_VOLUME,
           'DE_volume': CURRENT_VOLUME,
           'EN_volume': CURRENT_VOLUME,
           'UK_volume': CURRENT_VOLUME,
           'FR_volume': CURRENT_VOLUME,
           'CS_volume': CURRENT_VOLUME,
           'SV_volume': CURRENT_VOLUME,
           'PL_volume': CURRENT_VOLUME,
           'IT_volume': CURRENT_VOLUME,
           'JA_volume': CURRENT_VOLUME}
    template = INFO_TEMPLATE.format(**msg)
    with open(DEFAULT_MODES_JSON, 'w') as f:
        f.write(template)
    mylogger.info('__init__', '已创建default_modes.json。')

if Counter(['msg.txt', 'sbtlist_.json', 'sbt_.json', 'volist_.json', 'vo_.json']) != Counter(os.listdir(TEMPLATE_JSON_PATH)):
    with zipfile.ZipFile(WHERE_AM_I, 'r') as zip_ref:
        files = ['template_json/msg.txt', 'template_json/sbt_.json', 'template_json/sbtlist_.json', 'template_json/vo_.json', 'template_json/volist_.json']
        for obj in files:
            if obj in zip_ref.namelist():
                zip_ref.extract(obj, MY_LOG_PATH)
                mylogger.info('__init__', '已将%s解压至日志文件。' % obj)
            else:
                mylogger.warn('__init__', '未在mod文件中找到模板文件%s！' % obj.split('/')[1])

if not os.path.exists(DEFAULT_PNG):
    with zipfile.ZipFile(WHERE_AM_I, 'r') as zip_ref:
        obj = 'default.png'
        if obj in zip_ref.namelist():
            zip_ref.extract(obj, MY_LOG_PATH)
        else:
            mylogger.warn('__init__', '未在mod文件中找到默认图片default.png。')

if not os.path.exists(UPDATE_PNG):
    with zipfile.ZipFile(WHERE_AM_I, 'r') as zip_ref:
        obj = 'update.png'
        if obj in zip_ref.namelist():
            zip_ref.extract(obj, MY_LOG_PATH)
        else:
            mylogger.warn('__init__', '未在mod文件中找到默认图片update.png')
