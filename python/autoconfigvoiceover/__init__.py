# coding=utf-8
"""
    软件包的构造模块，限制了导入变量。
    初始化常量、目录、文件，未初始化的文件：gameSoundModes.json, playEvent.json, settings.json及其副本
"""
__all__ = ['SETTINGS_JSON_COPY', 'myModsVersion', 'isApiPresent', 'where_am_i', 'MyLogger', 'Notifier', 'override', 'g_search', 'g_update', 'g_template']

import shutil
from myLogger import *
from constants import *
from collectData import *
from updateFile import *
from createTemplate import *
from tools import *
from notifier import Notifier

mylogger = MyLogger('__init__')
PATHS = [MY_PNG_PATH, MY_JSON_PATH, MY_TEMPLATE_PATH]
myModsVersion = MY_MODS_VERSION
isApiPresent = constants.IS_API_PRESENT
where_am_i = None
meta = {
    'id': MY_MODS_ID,
    'version': MY_MODS_VERSION
}


# 将部分已有数据迁移，而非全部初始化。本次更新改动了配置文件夹，旧的文件和目录将在此被移除。
# 你所保存的第三方语音包信息，你所添加的图片将被保留并迁移。
def data_migration(config):
    # new_config <- config + new (keys, values) 最终放弃了这么做，有点麻烦
    save_config(DEFAULT_CONFIG)

    # 将旧版本插件保存的第三方语音包信息迁移至新路径
    if os.path.exists(INFO_JSON__):
        with open(INFO_JSON__, 'r') as src, open(VOICEOVER_JSON, 'w') as dest:
            json_data = jsonLoad(src.read())
            new_json_data = [
                dict(item, voiceID=item['voiceID'][4:] if item['voiceID'].startswith('ORV_') else item['voiceID'])
                for item in json_data
            ]
            dest.write(jsonDump(new_json_data))

    for item in os.listdir(MY_LOG_PATH):
        if item == 'config.json':
            continue
        item_path = os.path.join(MY_LOG_PATH, item)
        if item == 'default.png':
            shutil.move(item_path, DEFAULT_PNG)
        # 移除原目录下生成的旧的文件
        if item in ['default.png', 'update.png', 'gameSoundModes.json', 'playEvents.json']:
            try:
                os.remove(item_path)
            except OSError:
                pass

    # 移除旧文件夹
    try:
        if os.path.exists(TEMPLATE_JSON_PATH__):
            shutil.rmtree(TEMPLATE_JSON_PATH__)
        if os.path.exists(VOICEOVER_INFO_PATH__):
            shutil.rmtree(VOICEOVER_INFO_PATH__)
    except OSError:
        pass


# 返回 False: 检查并补回缺失文件，对旧版本中保存的数据进行迁移。否则视当前环境为：首次安装插件并运行。
def support_old_version():
    if not os.path.exists(CONFIG_JSON):
        return True
    try:
        with open(CONFIG_JSON, 'r') as src:
            config = jsonLoad(src.read())
        if config['__version__'] < MY_MODS_CONFIG_VERSION:
            if config['__version__'] < 2:
                data_migration(config)
            with open(PLAY_EVENTS_JSON, 'w') as src:
                json_str = jsonDump(PLAY_EVENTS_TEMPLATE)
                src.write(json_str)
            config['__version__'] = MY_MODS_CONFIG_VERSION
            save_config(config)

        constants.SHOW_DETAILS = config['show_details']
    except (TypeError, ValueError):
        save_config(DEFAULT_CONFIG)
        mylogger.warn('配置信息读取出错，已生成默认的配置文件。')
        return False
    return False


# 初始化文件、版本支持
def init_files():
    if not constants.WHERE_AM_I:
        mylogger.warn('找不到mod！检查wotmod文件是否丢失meta.xml！')
        return

    with zipfile.ZipFile(constants.WHERE_AM_I, 'r') as zip_ref:
        try:
            json_data = zip_ref.read(PATHS_JSON)
        except KeyError:
            mylogger.warn('在%s中找不到paths.json！' % constants.WHO_AM_I)
            return

        extract_all = support_old_version()
        paths = jsonLoad(json_data)

        # 绝对路径需要先从 constants 中获取前缀并拼接形成
        # 这里从字典中生成新字典，取出文件名并将它们的相对路径转换为绝对路径，最后合并字典
        f_loca = paths['location']
        f_dest = dict(
            [(obj, MY_LOG_PATH + '/' + dest) for obj, dest in paths['mods'].iteritems()]
        )
        extract_mapping = {
            item: (f_loca[item], f_dest[item])
            for item in set(f_loca) & set(f_dest)
        }

        # 被认定为“首次安装并运行”
        if extract_all:
            for item, (data, extr_path) in extract_mapping.iteritems():
                if data in zip_ref.namelist():
                    with open(extr_path, 'wb') as f:
                        f.write(zip_ref.read(data))
                else:
                    mylogger.warn('在mod中找不到文件%s' % os.path.basename(item))

            # 此处继续完成初始化，因为配置文件不存在
            save_config(DEFAULT_CONFIG)
            mylogger.info('\n~~~~~~~~~~~~~~~~~~~~~~~~~'
                          '\n欢迎下载和使用语音包管理插件'
                          '\n~~~~~~~~~~~~~~~~~~~~~~~~~')
            return

        # 部分文件恢复为默认
        file_list = {'default.png', 'audio_mods.xml', 'remapping.json', 'msg.json', 'msg.txt', 'sbt_.json', 'vo_.json'}
        missing_file = list(
            file_list - set(os.listdir(MY_PNG_PATH)) - set(os.listdir(MY_TEMPLATE_PATH)) - set(os.listdir(RES_MODS_ROOT_PATH))
        )
        for item in missing_file:
            data, extr_path = extract_mapping[item]
            if data in zip_ref.namelist():
                with open(extr_path, 'wb') as f:
                    f.write(zip_ref.read(data))
            else:
                mylogger.warn('在mod中找不到文件%s' % os.path.basename(item))


# 模块级代码由此开始，初始化目录与常量
for parent, dir_names, filenames in os.walk(MODS_PATH):
    constants.MOD_FILES_DICT.update({
        obj_file: os.path.join(parent, obj_file) for obj_file in filenames
        if obj_file.endswith('.wotmod')
    })

for name, path in constants.MOD_FILES_DICT.iteritems():
    if check_from_meta(path, meta):
        constants.WHO_AM_I = name
        constants.WHERE_AM_I = path
        constants.WHERE_ARE_PARENT = os.path.dirname(path)
        where_am_i = path
        break

for path in PATHS:
    if not os.path.exists(path):
        os.makedirs(path)

init_log()
mylogger.debug('mod所在位置：%s' % constants.WHERE_AM_I)

init_files()
