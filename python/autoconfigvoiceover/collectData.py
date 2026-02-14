# coding=utf-8
"""
    此模块负责解析wotmod文件，读取语音包的各种信息并保存在类的实例化对象中，以便后续操作。
    此外，还将从：gameSoundModes.json, playEvent.json, settings.json, voiceover.json中读取信息。
"""
import os.path
import zipfile
import constants
from collections import namedtuple
from constants import VOICEOVER_JSON, GAME_SOUND_MODES_JSON, SETTINGS_JSON, SETTINGS_JSON_COPY, PLAY_EVENTS_JSON, DEFAULT_VOLUME
from tools import jsonLoad, jsonDump, add_new_dict_only
from template import PLAY_EVENTS_TEMPLATE
from myLogger import MyLogger

mylogger = MyLogger('collectData')
# 创建命名元组保存读取的信息
VoiceInfo = namedtuple('VoiceInfo', 'name, language, nickName, path, invisible')
SubtitleInfo = namedtuple('SubtitleInfo', 'name, language, nickName, path, characters, sentences, visuals')


# 由于大量使用了列表生成式创建列表，可能出现列表嵌套的情况，需要通过递归取得全部元素
def _tuple_in_list(obj_list):
    tuples = []

    def _handle(data):
        for item in data:
            if isinstance(item, list):
                _handle(item)
            else:
                tuples.append(item)

    _handle(obj_list)
    return tuples


def _get_voice_info(v_type, data, filename):
    if not data.has_key('nickName'):
        raise WrongJsonFile
    if v_type == 'sbt':
        nickname = data['nickName']
        path = data['voiceover_Path']
        if len(path) <= 22:
            raise UnsupportedBnkPath
        # 去除 “audioww/” 和 “/voiceover.bnk”
        language = path[8:-14]
        name = language
        invisible = True
        characters = data['characters']
        sentences = data['sentences']
        visuals = data['visuals']
        mylogger.info('在%s中读取到字幕语音包' % filename)
        return [
            VoiceInfo(name, language, nickname, path[8:], invisible),
            SubtitleInfo(name, language, nickname, path, characters, sentences, visuals)
        ]
    elif v_type == 'vo':
        nickname = data['nickName']
        path = data['bankPath']
        if path <= 14:
            raise UnsupportedBnkPath
        # 去除 “/voiceover.bnk”
        language = path[:-14]
        name = language
        invisible = True
        mylogger.info('在%s中读取到语音包' % filename)
        return VoiceInfo(name, language, nickname, path, invisible)


def _read_from_modfile(path):
    with zipfile.ZipFile(path, 'r') as zip_ref:
        namelist = zip_ref.namelist()
        basename = os.path.basename(path)
        mylogger.debug('正在处理语音包文件：%s' % basename)
        filename = basename[10:-7]
        if not filter(lambda x: x.startswith('res/'), namelist):
            mylogger.warn('语音包文件%s打包方式不正确！压缩包内目录下应直接包含“res”文件夹！' % filename)
            return []

        for item in namelist:
            item_prefix = os.path.basename(item).split('_')[0]
            if item_prefix in ['sbtlist', 'volist']:
                item_prefix = item_prefix[:-4]
            if item_prefix in ['sbt', 'vo'] and item.endswith('.json'):
                try:
                    json_data = jsonLoad(zip_ref.read(item))

                    # 纠正之前制定的没有意义的规则，以列表方式写入信息将不再要求你使用不同后缀的json文件
                    # 你可以把 vo_.json 当做 volist_.json 来使用，反之亦可以
                    if isinstance(json_data, list):
                        return [_get_voice_info(item_prefix, data, filename) for data in json_data]

                    return _get_voice_info(item_prefix, json_data, filename)

                except UnsupportedBnkPath:
                    mylogger.warn('语音包文件%s的语音包路径存在错误，请将路径移至audioww中的独立文件夹中！' % filename)
                    return []
                except (KeyError, SyntaxError):
                    mylogger.exception('在处理%s时json文件解析错误！' % filename)
                    return []
                except WrongJsonFile:
                    continue
        mylogger.warn('语音包文件%s未能读取到信息！' % filename)


def _get_saved_subtitles():
    if os.path.exists(SETTINGS_JSON_COPY):
        with open(SETTINGS_JSON_COPY, 'r') as src:
            json_data = src.read()
            return jsonLoad(json_data).get('subtitles', [])

    return []


# 为读取到的语音包列表添加已保存的音量方案
def _set_volume(volume, update_list, src_list=None, add_only=False):
    if volume is None:
        volume = DEFAULT_VOLUME
    if add_only:
        return [
            dict(item, volume=volume) if 'volume' not in item else item
            for item in update_list
        ]
    if src_list:
        volume_map = {item['voiceID']: item['volume'] for item in src_list}
        return [
            dict(item, volume=volume_map.get(item['voiceID'], volume))
            for item in update_list
        ]
    return [
        dict(item, volume=volume) for item in update_list
    ]


class Search(object):
    def __init__(self):
        # 信息来自：游戏内读取，mod文件读取（元组），mod文件读取（元组）
        self._voice_info_tuple = []
        self._subtitle_info_tuple = []
        # 以读取到的信息为基准，保存的历史信息仅用于计算语音增减情况
        # 元组中包含全部重要信息，列表中只会包含 {voiceID、nickName、volume}

        # 获取和修改游戏内的语音需要导入新的模块，这个列表将在 updateFile 模块中完成赋值
        # 需要对这个属性读写，其余列表在类外只读取，不修改
        self._ingame_voices = []
        self._outside_voices = []
        # 上面两个列表还将用于创建语音选择下拉列表，以及文件写入

        self._subtitle_voices = []

        # 保存的信息分别位于：gameSoundModes.json, voiceover.json, settings.json
        # 字幕语音包 (subtitle_vo) 的信息总是包含在第三方语音包 (outside_vo) 信息列表中的
        self._saved_ingame_voices = []
        self._saved_outside_voices = []
        self._saved_subtitle_voices = []

        self._removed_voices = []

        self._event_list = {}
        self._compare_message = ''
        self.notify_ingame_voices_change = False

    # 等待调用的方法，为各个属性赋值
    def run(self):
        # 从 mod 文件、游戏中读取
        modlist = constants.MOD_FILES_DICT
        tuple_list = []
        for mod, path in modlist.iteritems():
            if mod.startswith('voiceover_'):
                tuple_list.append(_read_from_modfile(path))
        result = _tuple_in_list(tuple_list)
        for item in result:
            if type(item).__name__ == 'VoiceInfo':
                self._voice_info_tuple.append(item)
            else:
                self._subtitle_info_tuple.append(item)

        self._outside_voices = [
            {'voiceID': item.name, 'nickName': item.nickName} for item in self._voice_info_tuple
        ]
        self._subtitle_voices = [
            {'voiceID': item.name, 'nickName': item.nickName} for item in self._subtitle_info_tuple
        ]

        # 从保存的信息中读取
        if os.path.exists(VOICEOVER_JSON):
            with open(VOICEOVER_JSON, 'r') as src:
                self._saved_outside_voices = jsonLoad(src.read())

        self._saved_subtitle_voices = _get_saved_subtitles()

        if os.path.exists(GAME_SOUND_MODES_JSON):
            try:
                with open(GAME_SOUND_MODES_JSON, 'r') as src:
                    self._saved_ingame_voices = jsonLoad(src.read())
                    self.notify_ingame_voices_change = True
            except (ValueError, SyntaxError):
                mylogger.warn('读取已保存的游戏内语音包信息出错！信息将重置为默认！')

        # 获取事件播放列表
        self._event_list = PLAY_EVENTS_TEMPLATE
        if not os.path.exists(PLAY_EVENTS_JSON):
            with open(PLAY_EVENTS_JSON, 'w') as src:
                json_str = jsonDump(PLAY_EVENTS_TEMPLATE)
                src.write(json_str)
        else:
            try:
                with open(PLAY_EVENTS_JSON, 'r') as src:
                    self._event_list = jsonLoad(src.read())
            except (ValueError, SyntaxError):
                with open(PLAY_EVENTS_JSON, 'w') as src:
                    json_str = jsonDump(PLAY_EVENTS_TEMPLATE)
                    src.write(json_str)

    # 等待调用的方法，依据 language 属性（voiceID）求得列表，并记录信息：
    # 已安装的[语音包/字幕语音包]、新增的[语音包/字幕语音包/游戏内语音包]、已移除的[语音包/字幕语音包]
    # 没什么用，但这很酷。
    def compare(self):
        # 游戏内语音应当是只增不减的（在你没有使用其他来源的 main_sound_modes.xml 的情况下）
        # 使用 for 循环获取列表元素时，无需考虑列表为空的分支处理
        set_iv = set(item['voiceID'] for item in self._ingame_voices)
        set_ov = set(item['voiceID'] for item in self._outside_voices)
        set_sv = set(item['voiceID'] for item in self._subtitle_voices)
        set_saved_iv = set(item['voiceID'] for item in self._saved_ingame_voices)
        set_saved_ov = set(item['voiceID'] for item in self._saved_outside_voices)
        set_saved_sv = set(item['language'] for item in self._saved_subtitle_voices)
        set_removed_vo = set(item['voiceID'] for item in self._removed_voices)

        notify_saved_vo = '<br>已安装的语音包：'
        saved_ov_msg = ''
        saved_sv_msg = ''
        count_ov = 0
        count_sv = 0

        voice_namelist = {voice['voiceID']: voice['nickName'] for voice in self._saved_outside_voices}
        temp_set = (set_ov & set_saved_ov) - (set_sv & set_saved_sv)
        for vo in self._saved_outside_voices:
            if vo['voiceID'] in temp_set:
                if vo['voiceID'] in voice_namelist:
                    saved_ov_msg += '<br>%s' % voice_namelist[vo['voiceID']]
                    count_ov += 1

        temp_set = set_sv & set_saved_sv
        for item in self._saved_subtitle_voices:
            if item['language'] in temp_set:
                if item['language'] in voice_namelist:
                    saved_sv_msg += '<br>%s' % voice_namelist[item['language']]
                    count_sv += 1

        if saved_ov_msg or saved_sv_msg:
            if constants.SHOW_DETAILS:
                notify_saved_vo += '<font color="#edeaea">%s</font><font color="#fff0f5">%s</font><br>' % (saved_ov_msg, saved_sv_msg)
            else:
                if count_ov:
                    notify_saved_vo += '<br><font color="#edeaea">%s</font>' % ('语音包：' + str(count_ov))
                if count_sv:
                    notify_saved_vo += '<br><font color="#fff0f5">%s</font>' % ('字幕语音包：' + str(count_sv))
                notify_saved_vo += '<br>'
        else:
            notify_saved_vo += '<br>啊嘞？你没有装语音包吗？<br>'

        notify_add_vo = '<br>新增语音包：'
        add_iv_msg = ''
        add_ov_msg = ''
        add_sv_msg = ''

        voice_namelist = {voice['voiceID']: voice['nickName'] for voice in self._outside_voices}
        sv_list = list(set_sv) + list(set_saved_sv)
        for vo in list(set_ov - set_saved_ov):
            if vo not in sv_list:
                add_ov_msg += '<br>%s' % voice_namelist[vo]
        for vo in list(set_sv - set_saved_sv):
            add_sv_msg += '<br>%s' % voice_namelist[vo]

        if self.notify_ingame_voices_change:
            voice_namelist.update({voice['voiceID']: voice['nickName'] for voice in self._ingame_voices})
            for vo in list(set_iv - set_saved_iv):
                add_iv_msg = '<br>%s' % voice_namelist[vo] + add_iv_msg

        if add_iv_msg or add_ov_msg or add_sv_msg:
            notify_saved_vo += ('%s<font color="#f5ffff">%s</font>'
                                '<font color="#e0ffff">%s</font>'
                                '<font color="#ffe4e1">%s</font><br>'
                                % (notify_add_vo, add_iv_msg, add_ov_msg, add_sv_msg))
        else:
            notify_saved_vo += notify_add_vo + '<br>没有检测到新的语音包。<br>'

        notify_del_vo = '<br>已移除的语音包：'
        del_vo_msg = ''
        voice_namelist = {voice['voiceID']: voice['nickName'] for voice in self._removed_voices}
        voice_namelist.update({voice['voiceID']: voice['nickName'] for voice in self._saved_outside_voices})

        for vo in list(set_removed_vo) + list(set_saved_ov - set_ov):
            del_vo_msg += '<br>%s' % voice_namelist[vo]
        if del_vo_msg:
            notify_saved_vo += '%s<font color="#dcdcdc">%s</font><br>' % (notify_del_vo, del_vo_msg)

        self._compare_message = notify_saved_vo
        # 仅更新已保存的游戏内语音信息，这样可以保留对语音包名称的修改
        copy = self._saved_ingame_voices[:]
        self._ingame_voices = add_new_dict_only(copy, self._ingame_voices, 'voiceID')
        mylogger.info('加载语音包音量方案……')
        self._ingame_voices = _set_volume(100, self._ingame_voices, add_only=True)
        copy = self._outside_voices[:]
        self._outside_voices = _set_volume(constants.CURRENT_VOLUME, copy, self._saved_outside_voices)

    def get_default_voice(self):
        for item in self._ingame_voices:
            if item['voiceID'] == 'default':
                return item

    # 将方法转换为属性，就得到了一个只读属性
    @property
    def voice_info_tuple(self):
        return self._voice_info_tuple

    @property
    def subtitle_info_tuple(self):
        return self._subtitle_info_tuple

    @property
    def outside_voices(self):
        return self._outside_voices

    @property
    def event_list(self):
        return self._event_list

    @property
    def message(self):
        return self._compare_message

    def remove_outside_voice(self, voice):
        self._outside_voices.remove(voice)
        self._removed_voices.append(voice)

    def remove_subtitle_voice(self, voice):
        self._subtitle_voices.remove(voice)


# 自定义异常，当语音包所在的路径不正确时抛出此异常
class UnsupportedBnkPath(Exception):
    pass


# 当其他json误用vo_/sbt_标识符时，抛出异常以继续读取其他json
class WrongJsonFile(Exception):
    pass


# 类的实例化对象
g_search = Search()
