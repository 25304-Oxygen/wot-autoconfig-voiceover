# coding=utf-8
"""游戏内语音包读取——ResMgr XML + i18n 本地化译名。

三个入口全部为纯函数：只返回值，不写任何模块外状态
（修复旧版 updateFile 反写 collectData.g_search 私有属性的坏味道）。
读取逻辑移植自旧版 my_wotmod updateFile.py 的 run() /
_get_commander_data / _get_all_namelist。

字符编码：makeString / readString 均直接返回 utf-8 字节串
（官方代码用 i18n.convert 解码 makeString 结果、用 asWideString
单独取 unicode 可证），无需额外转换。
"""

import re

import ResMgr
from helpers.i18n import makeString as _ms

from autoconfigvoiceover.constants import (MAIN_SOUND_MODES_XML,
                                           SPECIAL_VOICES_XML,
                                           TANKMEN_XML_DIR)
from autoconfigvoiceover.logger import Logger

logger = Logger('GameReader')

DEFAULT_NATIONS = ['china', 'czech', 'france', 'germany', 'italy', 'japan',
                   'poland', 'sweden', 'uk', 'usa', 'ussr']
"""main_sound_modes.xml 缺少 nationalPresets 时的兜底系别列表"""

# 特殊语音成员的 tag 匹配模式（premiumGroups 的 tags 中形如 xxxSpecialVoice）
_SPECIAL_VOICE_PATTERN = re.compile(r'\b(\w*SpecialVoice\w*)\b')


def _default_sound_name():
    """游戏对"标准"声音模式的本地化名（如国服客户端为"标准"）。"""
    return _ms('#settings:sound/soundModes/default')


# ═════════════════════════════════════════════════════════════
# 系别语音（main_sound_modes.xml）
# ═════════════════════════════════════════════════════════════

def read_nation_voices():
    """读取系别语音（含"默认"项，永远排在首位）。

    :return: (nation_rows, nations)
        nation_rows —— [{'voiceID','nickName','normal':{语言名:soundMode}}]
        nations     —— 系别名列表（供 read_commander_* 遍历 tankmen XML）
    """
    default_name = _default_sound_name()
    rows = [{'voiceID': 'default',
             'nickName': default_name,
             'normal': {default_name: 'default'},
             'voice_type': 'default'}]
    nations = []

    # 逐层判空——ResMgr 对缺失键返回 None，链式取值会抛 TypeError
    root_sec = ResMgr.openSection(MAIN_SOUND_MODES_XML)
    presets_sec = root_sec['nationalPresets'] if root_sec is not None else None
    preset_sec = presets_sec['preset'] if presets_sec is not None else None
    nations_sec = preset_sec['nations'] if preset_sec is not None else None

    if nations_sec is None:
        logger.warn('main_sound_modes.xml 缺少 nationalPresets，使用默认系别列表')
        nations = list(DEFAULT_NATIONS)
        return rows, nations

    for item in nations_sec.values():
        nation = item.readString('name')
        # 客户端把"默认"系别语音单独标记，它实际对应苏系
        if nation == 'default':
            nation = 'ussr'
        nations.append(nation)

        sound_mode = item.readString('soundMode')
        rows.append({
            'voiceID': sound_mode,
            'nickName': _ms('#nations:' + nation),
            'normal': {default_name: sound_mode},
            'voice_type': 'nation',
        })

    logger.debug('系别语音读取完成: %d 条（含默认）', len(rows))
    return rows, nations


# ═════════════════════════════════════════════════════════════
# 车长特殊语音（special_voices.xml + tankmen 人名表）
# ═════════════════════════════════════════════════════════════

def read_commander_voices(nations):
    """读取车长特殊语音明细（含载具条目，与旧版一致）。

    :param nations: read_nation_voices() 返回的系别列表（读人名表用）
    :return: [{'voiceID','nickName','normal':{语言名:soundMode},'full_crew':{…}?}]
    """
    special_sec = ResMgr.openSection(SPECIAL_VOICES_XML)
    voiceover_sec = special_sec['voiceover'] if special_sec is not None else None
    if voiceover_sec is None:
        logger.warn('无法读取 %s 的 voiceover 段', SPECIAL_VOICES_XML)
        return []

    namelist = read_commander_namelist(nations)

    rows = []
    for section in voiceover_sec.values():
        row = _read_commander_data(section, namelist)
        if row is not None:
            rows.append(row)

    logger.debug('车长特殊语音读取完成: %d 条（人名表 %d 条）',
                 len(rows), len(namelist))
    return rows


_LANG_LABEL_KEYS = {
    'default': 'voice_switch/lang/default',
    'EN': 'voice_switch/lang/en',
    'RU': 'voice_switch/lang/ru',
    'CN': 'voice_switch/lang/cn',
}
"""语言代码 → 词典键（显示名随客户端语言）。未收录代码回退原文。"""


def _lang_label(lang):
    """把 XML 中的语言代码映射为客户端语言的显示名。

    与车长名同语言（均取自游戏本地化），故用 text_for_client 而非 text()。
    该显示名同时是 normal/full_crew 的键——读取与解析共用，保证 lang 下拉
    顺序与 resolve_mode 的位置索引一致。
    """
    from autoconfigvoiceover import l10n
    key = _LANG_LABEL_KEYS.get(lang)
    if key:
        return l10n.text_for_client(key)
    return lang  # 未收录语言代码（如 DE/JP）直接显示代码


def _read_commander_data(section, namelist):
    """解析单个 tankman/vehicle 条目（移植旧 _get_commander_data）。"""
    from autoconfigvoiceover import l10n
    tag = section.readString('tag')
    # languageMode: 属性值即声音模式名；其下可能还有 <RU>/<CN> 等
    # 子键代表不同语言版本，值同为声音模式名
    sound_mode = section.readString('languageMode')
    if not sound_mode:
        return None

    nickname = namelist.get(tag, tag)
    default_lang = _lang_label('default')
    normal = {default_lang: sound_mode}

    lang_sec = section['languageMode']
    other_language = lang_sec.keys() if lang_sec is not None else []
    if other_language:
        nickname += l10n.text_for_client('voice_switch/tag/multi_lingual')
        for lang in other_language:
            normal[_lang_label(lang)] = lang_sec.readString(lang)

    row = {'voiceID': sound_mode, 'nickName': nickname, 'normal': normal,
           'voice_type': 'commander'}

    # specialModes/isFullCrew: 满编原班车组时的替代声音模式
    if section.has_key('specialModes'):
        spec_sec = section['specialModes']
        full_crew = {default_lang: spec_sec.readString('isFullCrew')}
        fc_sec = spec_sec['isFullCrew']
        if fc_sec is not None:
            for lang in fc_sec.keys():
                full_crew[_lang_label(lang)] = fc_sec.readString(lang)
        row['nickName'] = nickname + l10n.text_for_client(
            'voice_switch/tag/full_crew')
        row['full_crew'] = full_crew

    return row


def read_commander_namelist(nations):
    """遍历 tankmen/<nation>.xml 的 premiumGroups，得 {tag: '名 姓'} 译名表。

    xml 中保存所有成员而非仅特殊成员；可自选系别的成员会在多个系别文件中
    重复出现（dict 天然去重）。若实测拖慢启动，可将此函数经 BigWorld.callback 后置。
    """
    namelist = {}
    for nation in nations:
        root_sec = ResMgr.openSection(TANKMEN_XML_DIR + nation + '.xml')
        groups_sec = root_sec['premiumGroups'] if root_sec is not None else None
        if groups_sec is None:
            continue

        for item in groups_sec.values():
            if not item.has_key('tags'):
                continue
            tags = item.readString('tags')
            match = _SPECIAL_VOICE_PATTERN.search(tags)
            if match:
                name = match.group(1)
            else:
                # 无 SpecialVoice 标记时取 tags 的最后一个词
                name = tags[tags.rfind(' ') + 1:]

            first_names = item['firstNames']
            last_names = item['lastNames']
            if first_names is None or last_names is None or not first_names.keys():
                continue
            key = first_names.keys()[0]
            first_n = _ms(first_names.readString(key))
            last_n = _ms(last_names.readString(key))
            if first_n and last_n:
                # 沿游戏默认的名前姓后（可在 gameSoundModes.json 中二次编辑）
                nickname = first_n + ' ' + last_n
            else:
                nickname = first_n + last_n
            # 部分成员名字不在 po 文件中（值为空）——回退用 tag 本身
            namelist[name] = nickname if nickname else name

    return namelist
