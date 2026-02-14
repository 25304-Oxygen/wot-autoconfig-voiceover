# coding=utf-8
"""
    此模块负责实现游戏内语音包信息获取、语音包添加与切换等功能，并将信息保存进文件。
"""
import os.path

import constants
import ResMgr
import SoundGroups
from helpers.i18n import makeString as _ms
from constants import (MAIN_SOUND_MODES_XML, SPECIAL_VOICES_XML, TANKMEN_XML_ROOT_PATH, SETTINGS_JSON,
                       SETTINGS_JSON_COPY, GAME_SOUND_MODES_JSON, VOICEOVER_JSON, DEFAULT_PNG, GUP_SETTINGS_FILE)
from collectData import g_search
from template import Full_Crew_tag, Multi_Lingual_tag, translate
from tools import jsonDump
from myLogger import MyLogger

mylogger = MyLogger('updateFile')
default_sound_name = _ms('#settings:sound/soundModes/default')
default_nations = ['china', 'czech', 'france', 'germany', 'italy', 'japan', 'poland', 'sweden', 'uk', 'usa', 'ussr']
nations = []
commander_namelist = {}
namelist_by_nation = []
namelist_by_special = []


def _get_commander_data(section):
    tag = section.readString('tag')
    nickname = commander_namelist.get(tag, tag)
    # sound_mode: 该属性下的字符串值，该属性可能还包含<RU>、<CN>等代表不同语言的属性，其值也是声音模式名
    sound_mode = section.readString('languageMode')
    normal = {translate.get('default', default_sound_name): sound_mode}
    other_language = section['languageMode'].keys()
    if other_language:
        nickname += Multi_Lingual_tag
        normal.update(
            {translate.get(nation, nation): section['languageMode'].readString(nation) for nation in other_language}
        )
    if section.has_key('specialModes'):
        nickname += Full_Crew_tag
        full_crew = {default_sound_name: section['specialModes'].readString('isFullCrew')}
        other_language = section['specialModes']['isFullCrew'].keys()
        if other_language:
            full_crew.update(
                {nation: section['specialModes']['isFullCrew'].readString(nation)
                 for nation in other_language}
            )
        return {
            'voiceID': sound_mode,
            'nickName': nickname,
            'normal': normal,
            'full_crew': full_crew
        }
    return {
        'voiceID': sound_mode,
        'nickName': nickname,
        'normal': normal
    }


# 这个过程可能比较耗时，因为用于读取的 .xml 中保存着所有成员信息，而非仅特殊成员，加之特殊语音数量庞大
# 如果一个成员在招募时可以自选系别，那么他的信息就会出现在所有系别资源文件中
def _get_all_namelist():
    global commander_namelist
    for nation in nations:
        commanders = {}
        root_sec = ResMgr.openSection(TANKMEN_XML_ROOT_PATH + nation + '.xml')
        for item in root_sec['premiumGroups'].values():
            if not item.has_key('tags'):
                continue
            tags = item.readString('tags')
            last_space_index = tags.rfind(' ')
            name = tags[last_space_index + 1:]
            # if name.endswith('SpecialVoice'): <- 这样会遗漏很多名字
            first_names = item['firstNames']
            last_names = item['lastNames']
            key = first_names.keys()[0]
            first_n = _ms(first_names.readString(key))
            last_n = _ms(last_names.readString(key))
            if first_n and last_n:
                # 这里使用游戏默认的名字在前，姓氏在后
                # 姓氏在前名在后更符合东亚人习惯，但是许多名字大家已耳熟，加上亚洲成员并不多，这里保持默认
                # 不过你可以在gameSoundModes.json中对其二次编辑，这个文件通常情况下仅读取并扩充
                nickname = first_n + ' ' + last_n
            else:
                nickname = first_n + last_n
            # 我不能理解，为什么有的成员名字不在po文件中，它们的值居然是空值
            if nickname:
                commanders[name] = nickname
            else:
                commanders[name] = name
            commander_namelist.update(commanders)


# 为语音包创建可选选项，注册信息后，语音包将交由 WWISE 动态加载
def _load_sound_outside():
    voice_tuple_list = g_search.voice_info_tuple
    modes_dict = {}
    for voice in voice_tuple_list:
        bank_path = 'audioww/' + voice.path
        name = voice.name
        nickname = voice.nickName
        if not ResMgr.isFile(bank_path):
            mylogger.warn('语音包%s未能加载进游戏！' % voice.nickName)
            g_search.remove_outside_voice({'voiceID': name, 'nickName': nickname})
            continue
        new_sec = ResMgr.DataSection('mode')
        new_sec.write('name', name)
        new_sec.write('wwise_language', voice.language)
        new_sec.write('description', nickname)
        new_sec.write('invisible', voice.invisible)
        new_sec.write('wwbanks/bank', voice.path)
        newmode = SoundGroups.SoundModes.SoundModeDesc(new_sec)
        modes_dict.update({name: newmode})
    return modes_dict


def _save_subtitle_vices_info():
    sv_tuples = g_search.subtitle_info_tuple
    subtitles_list = []
    for sv in sv_tuples:
        bank_path = sv.path
        name = sv.name
        nickname = sv.nickName
        if not ResMgr.isFile(bank_path):
            g_search.remove_subtitle_voice({'voiceID': name, 'nickName': nickname})
            continue
        sbt_data = {"name": name, "language": sv.language, "wwbank": bank_path,
                    "characters": sv.characters, "sentences": sv.sentences, "visuals": sv.visuals}
        subtitles_list.append(sbt_data)
    json_data = jsonDump({"subtitles": subtitles_list})

    # if ResMgr.isFile(GUP_SETTINGS_FILE):
    #     src = ResMgr.openSection(GUP_SETTINGS_FILE)
    #     src.asString = json_data
    #     src.save()
    # else:
    #     with open(SETTINGS_JSON, 'w') as f:
    #         f.write(json_data)
    with open(SETTINGS_JSON_COPY, 'w') as f:
        f.write(json_data)


def _save_ingame_voices_info(obj):
    copy = obj[:]   # 这是完全没有必要的
    json_data = jsonDump(copy)
    with open(GAME_SOUND_MODES_JSON, 'w') as f:
        f.write(json_data)


def _save_outside_voices_info(obj):
    copy = obj[:]
    json_data = jsonDump(copy)
    with open(VOICEOVER_JSON, 'w') as f:
        f.write(json_data)


class UpdateManager(object):
    def __init__(self):
        # 包含游戏内语音的所有重要信息的复杂列表
        self._ingame_sound_modes_desc = []
        self._nation_voices = []

        self.__origin_sound_modes_dict = {}
        self.__extra_dict = {}

    def _new_ingame_voices_list(self):
        global namelist_by_special
        nation_voice_list = [
            {'voiceID': item['voiceID'], 'nickName': item['nickName']} for item in self._nation_voices
        ]
        ingame_voice_list = [
            {'voiceID': item['voiceID'], 'nickName': item['nickName']} for item in self._ingame_sound_modes_desc
        ]
        namelist_by_special = [item['voiceID'] for item in ingame_voice_list]
        # 确保系别语音永远排在前面，具体的顺序取决于读取并写入列表时的顺序
        return nation_voice_list + ingame_voice_list

    def run(self):
        global nations, namelist_by_nation
        constants.CURRENT_VOLUME = int(SoundGroups.g_instance.getVolume('voice') * 100)

        self._nation_voices = [
            {
                'voiceID': 'default',
                'nickName': default_sound_name,
                'normal': {
                    default_sound_name: 'default'
                }
            }
        ]
        namelist_by_nation.append('default')
        root_sec = ResMgr.openSection(MAIN_SOUND_MODES_XML)
        nation_sec = root_sec['nationalPresets']['preset']['nations']
        if not root_sec.has_key('nationalPresets') or nation_sec is None:
            nations = default_nations
        else:
            for item in nation_sec.values():
                nation = item.readString('name')

                # 这个在客户端中是“默认”系别语音，需要单独处理
                if nation == 'default':
                    nation = 'ussr'

                nations.append(nation)
                sound_mode = item.readString('soundMode')
                namelist_by_nation.append(sound_mode)
                self._nation_voices.append({
                    'voiceID': sound_mode,
                    'nickName': _ms('#nations:' + nation),
                    'normal': {default_sound_name: sound_mode}
                })

        # 从 special_voices.xml 中获取所有车长语音，
        special_root_sec = ResMgr.openSection(SPECIAL_VOICES_XML)
        voiceover_sec = special_root_sec['voiceover']
        if voiceover_sec:
            _get_all_namelist()
            self._ingame_sound_modes_desc = [_get_commander_data(commander) for commander in voiceover_sec.values()]

        g_search._ingame_voices = self._new_ingame_voices_list()
        self.__extra_dict = _load_sound_outside()
        self.__origin_sound_modes_dict = SoundGroups.g_instance.soundModes._SoundModes__modes.copy()
        g_search.compare()

    def get_voice_data_from_iv(self, mode_name):
        voice_data = {}
        if mode_name in namelist_by_nation:
            index = namelist_by_nation.index(mode_name)
            vo_dict = self._nation_voices[index]
            voice_data['nation_voice'] = True
        else:
            index = namelist_by_special.index(mode_name)
            vo_dict = self._ingame_sound_modes_desc[index]
        tag_list = [{'label': ml} for ml in vo_dict['normal'].keys()]
        voice_data.update({
            'voiceID': mode_name,
            'language_tag_list': tag_list,
            'full_crew': vo_dict.has_key('full_crew'),
            'icon': DEFAULT_PNG,
            'custom_msg': [],
            'remap': {},
            'rmp_msg': ''
        })
        return voice_data

    def get_mode(self, voice, is_full_crew, multi_lingual):
        if voice in namelist_by_nation:
            return voice
        if voice in namelist_by_special:
            index = namelist_by_special.index(voice)
            data = self._ingame_sound_modes_desc[index]
            if is_full_crew:
                return data['full_crew'][multi_lingual]
            return data['normal'][multi_lingual]

    def get_default_tag(self):
        return {'label': self._nation_voices[0]['normal'].keys()[0]}

    # SoundGroups 类没有为私有属性 modes 设置 setter
    def replace_sound_modes(self):
        SoundGroups.g_instance.soundModes._SoundModes__modes.update(self.__extra_dict)

    def recover_sound_modes(self):
        SoundGroups.g_instance.soundModes._SoundModes__modes = self.__origin_sound_modes_dict

    def reset_display_name(self, voice_list):
        key_list = SoundGroups.g_instance.soundModes._SoundModes__modes.keys()
        for data in voice_list:
            vid = data['voiceID']
            i10n = data['nickName']
            if vid in key_list:
                SoundGroups.g_instance.soundModes._SoundModes__modes[vid].description = i10n
        mylogger.debug('已修改内置语音显示名称。')

    def save_files(self):
        _save_subtitle_vices_info()
        _save_ingame_voices_info(g_search._ingame_voices)
        _save_outside_voices_info(g_search.outside_voices)


g_update = UpdateManager()
