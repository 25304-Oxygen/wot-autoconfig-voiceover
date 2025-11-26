# coding=utf-8
"""
    此模块负责通过modsSettingsApi绘制UI，并负责语音切换与试听等功能的具体实现。
"""
from gui import SystemMessages
from gui.SystemMessages import SM_TYPE
from gui.game_control.special_sound_ctrl import SpecialSoundCtrl
from gui.battle_control import avatar_getter
from Account import PlayerAccount
from collectData import g_search
from updateFile import g_update
from myLogger import MyLogger
from tools import override, jsonLoad, jsonDump, save_config
import itertools
import constants
import template
import ResMgr
import SoundGroups

mylogger = MyLogger('createTemplate')
modLinkage = constants.MY_MODS_LINKAGE
displayName = template.MY_MODS_DISPLAY_NAME
isRemapCtrlPresent = False
default_lang = SoundGroups.g_instance.soundModes._SoundModes__modes['default'].voiceLanguage
clone_iv_list = []
clone_ov_list = []
iv_labels = []
ov_labels = []
vo_list_with_default = []
info_type = SM_TYPE.InformationHeader
message_type = SM_TYPE.MessageHeader
header = ''
text = '插件运行时出现意外。'
text_type = SM_TYPE.ErrorSimple
msg_sent = False

try:
    from gui.modsSettingsApi import g_modsSettingsApi
    constants.IS_API_PRESENT = g_modsSettingsApi is not None
    if not constants.IS_API_PRESENT:
        mylogger.error('modsSettingsApi似乎出了问题：实例对象返回了None。请检查插件版本是否需要更新。')
except ImportError:
    mylogger.error('无法导入modsSettingsApi！请确保安装了openwg_gameface、ModsSettingsApi和modsListApi！')
try:
    from gui.mods.mod_soundRemapping import g_remap_ctrl
    isRemapCtrlPresent = True
except ImportError:
    mylogger.error('无法导入动态重映射模块！请确保安装了soundRemapping！')


def _save_ingame_voices_info():
    copy = clone_iv_list[:]
    json_data = jsonDump(copy)
    with open(constants.GAME_SOUND_MODES_JSON, 'w') as f:
        f.write(json_data)


def _save_outside_voices_info():
    copy = clone_ov_list[:]
    json_data = jsonDump(copy)
    with open(constants.VOICEOVER_JSON, 'w') as f:
        f.write(json_data)


def _remap_from_xml(rmp_path):
    root_sec = ResMgr.openSection(rmp_path)
    if not root_sec.has_key('events'):
        return {}
    return {
        item.readString('name'): item.readString('mod')
        for item in root_sec['events'].values()
    }


# 获取第三方语音包语音文件路径下的资源文件，并生成一个包含该语音各项信息的字典
def _get_custom_data(language):
    src_path = 'audioww/' + language
    result = {'voiceID': language}
    icon_path = src_path + '/default.png'
    if ResMgr.isFile(icon_path):
        result['icon'] = '../../' + icon_path
    elif ResMgr.isFile(constants.DEFAULT_PNG):
        result['icon'] = constants.DEFAULT_PNG
    else:
        result['icon'] = '../../' + constants.MY_MODS_RES_DEFAULT_PNG

    msg_path = src_path + '/msg.json'
    result['custom_msg'] = []
    if ResMgr.isFile(msg_path):
        json_str = ResMgr.openSection(msg_path).asString
        try:
            json_data = jsonLoad(json_str)
            result['custom_msg'] = [item.get('text') for item in json_data]
        except (TypeError, ValueError):
            pass
    else:
        msg_path = src_path + '/msg.txt'
        if ResMgr.isFile(msg_path):
            # 若以HTML标签开头，ResMgr会自动吞掉HTML标签，并尝试将数据解析为XML，并丢弃后续标签的内容
            # 例如<font color='xxx'>ABC</font> <xxx>xxx</xxx>，只会得到ABC和一个“color”键（值为颜色代码）
            # 因此使用txt文本要求你用任意一个非空格字符开头，这个字符将在读取时被舍弃
            msg = ResMgr.openSection(msg_path).asString
            result['custom_msg'] = [msg[1:]]

    rmp_path = src_path + '/audio_mods.xml'
    result['remap'] = {}
    if ResMgr.isFile(rmp_path):
        result['remap'] = _remap_from_xml(rmp_path)
    else:
        rmp_path = src_path + '/remapping.json'
        if ResMgr.isFile(rmp_path):
            json_str = ResMgr.openSection(rmp_path).asString
            try:
                result['remap'] = jsonLoad(json_str)
            except (KeyError, SyntaxError):
                mylogger.warn('无法应用语音重映射：json读取错误！')

    rmp_info_path = src_path + '/remap_msg.txt'
    result['rmp_msg'] = ''
    if ResMgr.isFile(rmp_info_path):
        info_str = ResMgr.openSection(rmp_info_path).asString
        result['rmp_msg'] = info_str[1:]
    result['language_tag_list'] = [g_update.get_default_tag()]
    result['full_crew'] = False
    return result


# 返回有关当前语音包所需的全部信息的标准字典
# 这里的标准字典：{ "voiceID" -> str, "nickName" -> str, "volume" -> int,
# "language_tag_list" -> list, "full_crew" -> bool, "icon" -> str,
# "custom_msg" -> list, "remap" -> dict, "rmp_msg" -> str,
# "option" -> int, "index" -> int } 这两项对应其在列表中的位置
def _get_voice_data(config):
    index = config['current_voice']
    # 它只会运行一次。写入文件时将这一项值由索引保存为字符串，好处多多，现在将其重新解析为索引
    if isinstance(index, (str, unicode)):
        mylogger.debug('读取上次保存的语音包的信息：%s' % index)
        if config['vo_list_option']:
            namelist = [item['voiceID'] for item in vo_list_with_default]
        else:
            namelist = [item['voiceID'] for item in clone_iv_list]
        try:
            index = namelist.index(index)
            config['current_voice'] = index
        except ValueError:
            # 对可变列表的每次一值传递都是危险的地址传递
            # 但有时，这也可以转化为一种优势
            index = 0
            config['current_voice'] = 0
            config['vo_list_option'] = 0

    list_option = config['vo_list_option']
    if list_option:
        vo_dict = vo_list_with_default[index]
        language = vo_dict['voiceID']
        if language == 'default':
            # 返回一个包含游戏内语音各项信息的字典
            voice_data = g_update.get_voice_data_from_iv(language)
        else:
            # 返回一个包含第三方语音各项信息的字典
            voice_data = _get_custom_data(language)
    else:
        vo_dict = clone_iv_list[index]
        language = vo_dict['voiceID']
        voice_data = g_update.get_voice_data_from_iv(language)

    voice_data['nickName'] = vo_dict['nickName']
    voice_data['volume'] = vo_dict['volume']
    voice_data['option'] = config['vo_list_option']
    voice_data['index'] = index
    return voice_data


# 当设置改变时，应用设置中的属性（注：大部分属性仅在对应按钮按下时被解析，因此这里仅需处理以下两项）
def _analyse_config(new_config, enabled=True):
    # 禁用时全部设置为不可见
    key_list = SoundGroups.g_instance.soundModes._SoundModes__modes.keys()
    namelist = [item['voiceID'] for item in clone_iv_list]
    namelist.remove('default')
    invisible = True

    mylogger.info('游戏内语音包可见：%s、已安装的语音包可见：%s' % (
        new_config['ingame_voice_visible'], new_config['outside_voice_visible'])) if enabled else None

    if enabled and new_config['ingame_voice_visible']:
        invisible = False
    for vo in namelist:
        if vo in key_list:
            SoundGroups.g_instance.soundModes._SoundModes__modes[vo].invisible = invisible

    namelist = [item['voiceID'] for item in clone_ov_list]
    invisible = True
    if enabled and new_config['outside_voice_visible']:
        invisible = False
    for vo in namelist:
        if vo in key_list:
            SoundGroups.g_instance.soundModes._SoundModes__modes[vo].invisible = invisible


def _set_volume(volume):
    value = float(volume) / 100
    SoundGroups.g_instance.setVolume('voice', value, True)


def override_default(language=default_lang):
    SoundGroups.g_instance.soundModes._SoundModes__modes['default'].voiceLanguage = language


class DrawUi(object):
    def __init__(self):
        self.config = constants.DEFAULT_CONFIG
        self.voice_data = {}
        self._preview_event = ''
        self._preview_sound = None
        self._cycler = None
        self.apply_vo = 'default'
        self._last_click_time = 0
        self._click_times = 0

    def _clear_preview_sound(self):
        if self._preview_sound is not None:
            self._preview_sound.stop()
            self._preview_sound = None

    def _play_preview_sound(self, event):
        if event == constants.VOICE_SELECTED_EVENT:
            pass
        elif event != self._preview_event:
            self._preview_event = event
            mylogger.debug('播放声音：%s' % event)

        self._clear_preview_sound()
        self._preview_sound = SoundGroups.g_instance.getSound2D(event)
        if self._preview_sound is None:
            mylogger.warn('声音无法播放：%s' % event)
        else:
            self._preview_sound.play()

    def apply_gender_switch(self):
        if self.voice_data.has_key('nation_voice'):
            # 0: male, 1: female
            gender = SoundGroups.CREW_GENDER_SWITCHES.GENDER_ALL[g_template.config['nation_voice_gender']]
        else:
            gender = SoundGroups.CREW_GENDER_SWITCHES.DEFAULT
        SoundGroups.g_instance.setSwitch(SoundGroups.CREW_GENDER_SWITCHES.GROUP, gender)

    def _push_hello_message(self, tips=False):
        if self._cycler:
            msg = next(self._cycler)
            SystemMessages.pushMessage(msg, SM_TYPE.GameGreeting)
            mylogger.debug(msg)
        elif tips:
            msg = '<br>再怎么点也没有啦'
            head = '<font color="#e0ffff"><b>这个语音没有自定义消息</b></font>'
            SystemMessages.pushMessage(msg, type=info_type, messageData={'header': head})

    # 刷新界面
    def _on_voice_load(self, value):
        if value:
            column_a = template.column_a_outside_voices(self.config, ov_labels, self.voice_data)
            column_b = template.column_b_outside_voices(self.config, self.voice_data)
        else:
            column_a = template.column_a_ingame_voices(self.config, iv_labels, self.voice_data)
            column_b = template.column_b_ingame_voices(self.config, self.voice_data)
        my_template = {
            'modDisplayName': displayName,
            'enabled': self.config['enabled'],
            'column1': column_a,
            'column2': column_b
        }
        g_modsSettingsApi.setModTemplate(modLinkage, my_template, self.on_save_btn_clicked, self.on_other_btn_clicked)

    # 切换语音，并在最后刷新界面，self.apply_vo 在此被赋值
    def _on_voice_selected(self, value=None, check=True, notify=True):
        voice_changed = False
        if self.config['vo_list_option'] != self.voice_data['option']:
            voice_changed = True
        else:
            if value != self.config['current_voice']:
                voice_changed = True
        if voice_changed:
            # 非语音切换按钮触发时，不初始化信息（因为已经初始化过了）
            if check:
                self.config['current_voice'] = value
                mylogger.debug('请求切换语音：来自列表%s，索引%s' % (self.config['vo_list_option'], value))
                self.voice_data = _get_voice_data(self.config)

        # 切换语音的具体过程
        tag_list = self.voice_data['language_tag_list']
        if self.config['full_crew'] and not self.voice_data['full_crew']:
            mylogger.error('这个语音没有车组语音。')
            self.config['full_crew'] = 0
        if self.config['language_tag'] >= len(tag_list):
            mylogger.error('这个语音没有这个语言版本。')
            self.config['language_tag'] = 0

        # 确定语音模式名称
        tag = self.voice_data['language_tag_list'][self.config['language_tag']]['label']
        cl = template.CREW_VO_LABEL[self.config['full_crew']]['label']
        mylogger.debug('\noption: %s\nnickname: %s\nvoiceID: %s\nindex: %s' %
                       (self.voice_data['option'], self.voice_data['nickName'], self.voice_data['voiceID'], self.voice_data['index']))
        if self.voice_data['option']:
            mode_name = self.voice_data['voiceID']
        else:
            mode_name = g_update.get_mode(self.voice_data['voiceID'], self.config['full_crew'], tag)

        preview_mode = SoundGroups.g_instance.soundModes.currentMode

        # 声音切换、重映射（刚进入游戏从其他语音切换到默认语音时，等价于从默认切换为默认）
        if preview_mode != mode_name or preview_mode == mode_name == 'default':
            self.apply_vo = mode_name
            if mode_name != 'default':
                new_lang = SoundGroups.g_instance.soundModes._SoundModes__modes[mode_name].voiceLanguage
                mylogger.info('切换语音了，切换的是%s，原声音%s' % (mode_name, SoundGroups.g_instance.soundModes.currentMode))
            else:
                new_lang = default_lang
                SoundGroups.g_instance.soundModes.setMode('ZH_CH')

            override_default(new_lang)
            SoundGroups.g_instance.soundModes.setMode(mode_name)

            msg = '' if self.voice_data['option'] else '[%s][%s]' % (cl, tag)
            head = '<font color="#cc9933"><b>切换语音：%s</b></font>' % self.voice_data['nickName']
            if notify and preview_mode != mode_name:
                SystemMessages.pushMessage(msg, type=message_type, messageData={'header': head})
            # 创建一个无限迭代器，用于依次获取下一条元素
            if self.voice_data['custom_msg']:
                self._cycler = itertools.cycle(self.voice_data['custom_msg'])
            else:
                self._cycler = None

        self.apply_gender_switch()
        _set_volume(self.voice_data['volume'])
        if isRemapCtrlPresent:
            if self.config['auto_remapping']:
                g_remap_ctrl.reset_remapping(self.voice_data['remap'])
            else:
                g_remap_ctrl.reset_remapping()
        if check:
            self._play_preview_sound(constants.VOICE_SELECTED_EVENT)
            if self.config['info_notify']:
                self._push_hello_message()
        self._on_voice_load(self.config['vo_list_option'])

        # 保存信息
        copy = self.config.copy()
        copy['current_voice'] = self.voice_data['voiceID']
        save_config(copy)

    def on_save_btn_clicked(self, linkage, new_config, notify=True):
        if linkage != modLinkage:
            return
        for key, value in self.config.items():
            new_config.setdefault(key, value)

        if new_config['vo_list_option'] == self.voice_data['option']:
            new_config['current_voice'] = self.voice_data['index']
        else:
            new_config['current_voice'] = 0

        if not self.config['enabled'] and new_config['enabled']:
            g_update.replace_sound_modes()
            self.config['enabled'] = True
            mylogger.info('插件已启用。')
            self._on_voice_selected(check=False)
            if notify:
                SystemMessages.pushMessage('试试各种语音包吧！', type=message_type, messageData={'header': '插件已启用'})
        elif not new_config['enabled']:
            # 该状态可随时复原
            g_update.recover_sound_modes()
            g_remap_ctrl.reset_remapping() if isRemapCtrlPresent else None
            SoundGroups.g_instance.soundModes.setMode('ZH_CH')
            override_default()
            SoundGroups.g_instance.soundModes.setMode('default')
            gender = SoundGroups.CREW_GENDER_SWITCHES.DEFAULT
            SoundGroups.g_instance.setSwitch(SoundGroups.CREW_GENDER_SWITCHES.GROUP, gender)
            _set_volume(constants.CURRENT_VOLUME)
            _analyse_config(new_config, enabled=False)
            self.config = new_config
            new_config['current_voice'] = self.voice_data['voiceID']
            save_config(new_config)
            mylogger.info('插件已禁用。')
            if notify:
                SystemMessages.pushMessage('游戏语音状态将恢复为默认。', type=info_type, messageData={'header': '插件已禁用'})
            # 刷新界面
            self._on_voice_load(self.config['vo_list_option'])
            return

        # 从禁用到启用时，手动应用重映射方案
        if new_config['auto_remapping'] != self.config['auto_remapping'] and isRemapCtrlPresent:
            if new_config['auto_remapping']:
                g_remap_ctrl.reset_remapping(self.voice_data['remap'])
            else:
                g_remap_ctrl.reset_remapping()
        if self.config['ingame_voice_visible'] != new_config['ingame_voice_visible'] or self.config['outside_voice_visible'] != new_config['outside_voice_visible']:
            _analyse_config(new_config)

        self.config = new_config
        new_config['current_voice'] = self.voice_data['voiceID']
        save_config(new_config)
        # 刷新界面
        self._on_voice_load(self.config['vo_list_option'])

    def on_other_btn_clicked(self, linkage, varName, value):
        if linkage != modLinkage:
            return

        if varName == 'vo_list_option':
            if value == self.config['vo_list_option']:
                return
            self.config['vo_list_option'] = value
            if value == self.voice_data['option']:
                self.config['current_voice'] = self.voice_data['index']
            else:
                self.config['current_voice'] = 0
            self._on_voice_load(value)

        elif varName == 'current_voice':
            self._on_voice_selected(value)

        elif varName == '__event__':
            self.config['__event__'] = value
            event = template.PLAY_EVENTS_TEMPLATE[value]['id']
            self._play_preview_sound(event)
            self._on_voice_load(self.config['vo_list_option'])

        elif varName == 'volume':
            # 由于列表顺序不会改变，我们可以直接定位到该语音所对应元素的所在位置
            if self.voice_data['volume'] == value:
                return
            global clone_iv_list, clone_ov_list
            self.voice_data['volume'] = value
            option = self.config['current_voice']
            if not self.config['current_voice'] or not self.config['vo_list_option']:
                # 默认语音的音量方案均保存在 gameSoundModes.json
                clone_iv_list[option]['volume'] = value
                _save_ingame_voices_info()
            else:
                clone_ov_list[option - 1]['volume'] = value
                _save_outside_voices_info()
            _set_volume(value)

        elif varName == 'nation_voice_gender':
            self.config['nation_voice_gender'] = value
            self.apply_gender_switch()
            copy = self.config.copy()
            copy['current_voice'] = self.voice_data['voiceID']
            save_config(copy)

        elif varName == 'full_crew':
            if not self.voice_data['full_crew'] and value:
                SystemMessages.pushMessage('', type=info_type, messageData={'header': '这个语音没有车组专属语音。'})
                self.config['full_crew'] = 0
                return
            self.config['full_crew'] = value
            self._on_voice_selected(check=False)

        elif varName == 'language_tag':
            tag_list = self.voice_data['language_tag_list']
            if value >= len(tag_list):
                SystemMessages.pushMessage('', type=info_type, messageData={'header': '这个语音没有该语言版本。'})
                self.config['language_tag'] = 0
                return
            self.config['language_tag'] = value
            self._on_voice_selected(check=False)

        elif varName == 'auto_remapping':
            if not self.config['auto_remapping']:
                SystemMessages.pushMessage('', type=info_type, messageData={'header': '动态重映射功能未开启。'})
                return
            if not isRemapCtrlPresent:
                msg = '找不到该模块。请检查是否安装了soundRemapping'
                head = '无法启用动态重映射'
                msg_type = SM_TYPE.ErrorHeader
                SystemMessages.pushMessage(msg, type=msg_type, messageData={'header': head})
                return
            if not self.voice_data['remap']:
                SystemMessages.pushMessage('', type=info_type, messageData={'header': '这个语音包没有使用重映射。'})
                return
            if not self.voice_data['rmp_msg']:
                SystemMessages.pushMessage('', type=info_type, messageData={'header': '这个语音包作者很懒，没有给出语音替换说明。'})
                return
            msg = self.voice_data['rmp_msg']
            SystemMessages.pushMessage(msg, type=message_type, messageData={
                'header': '<font color="#e0ffff"><b>重映射信息</b></font>'})
            mylogger.debug(msg)

        elif varName == 'info_notify':
            # 某些情况下，当前语音会意外变更，此时将其修正，并重置自定义消息
            if self.apply_vo != SoundGroups.g_instance.soundModes.currentMode:
                SoundGroups.g_instance.soundModes.setMode(self.apply_vo)
                if self.voice_data['custom_msg']:
                    self._cycler = itertools.cycle(self.voice_data['custom_msg'])
                else:
                    self._cycler = None
            self._push_hello_message(tips=True)
            if self.config['info_notify']:
                self._play_preview_sound(constants.VOICE_SELECTED_EVENT)

    def run(self):
        global clone_iv_list, clone_ov_list, vo_list_with_default, header, text, text_type, iv_labels, ov_labels
        with open(constants.CONFIG_JSON, 'r') as src:
            self.config = jsonLoad(src.read())
        # 这个不加也行，后面这个属性自己会出现
        self.config['__event__'] = 0

        clone_iv_list = g_search._ingame_voices
        iv_labels = [{'label': item['nickName']} for item in clone_iv_list]
        clone_ov_list = g_search.outside_voices

        # 为“已安装的语音包”下拉列表添加默认语音项，该项将单独视为位于“游戏内语音包”下拉列表
        vo_list_with_default = [g_search.get_default_voice()] + clone_ov_list
        ov_labels = [{'label': item['nickName']} for item in vo_list_with_default]

        g_update.replace_sound_modes()
        self.voice_data = _get_voice_data(self.config)
        self._on_voice_selected(check=False, notify=False)
        # 不知何故，此时切换声音，等车库界面加载后（晚于信息发送），会被重置为默认。
        # 之前的版本是替换了默认语音，所以没有注意到这个问题，因此决定也继续替换默认语音

        if not self.config['enabled']:
            copy = self.config.copy()
            self.on_save_btn_clicked(modLinkage, copy, notify=False)
            text = '准备就绪<br><br><font color="#ff0000">- 插件禁用中 -</font>'
            text_type = info_type
        else:
            mylogger.info('启用中的语音：%s' % self.voice_data['nickName'])
            header = ('<font color="#cc9933"><b>当前语音：</b></font>'
                      '<font color="#e0ffff"><b>%s</b></font>') % self.voice_data['nickName']
            text = g_search.message + '<br><font color="#00ff00">- 插件启用中 -</font>'
            text_type = message_type

        # 不知何故，需要为添加的新语音再次设置显示效果，否则默认将可见
        _analyse_config(self.config)

        # 在版本更新后，初始化字幕插件以获取字幕效果支持。此处两个json的绝对路径均可
        if g_search.update:
            try:
                from gui.mods import mod_gup_subtitles as gup_mod
                gup_mod.SETTINGS_FILE = constants.SETTINGS_JSON_COPY
                gup_mod.init()
                mylogger.debug('字幕信息更新完毕。')
            except ImportError:
                mylogger.warn('无法导入字幕插件！字幕不可用！')


g_template = DrawUi()


# 覆盖此方法，特殊语音将使用插件设定的语音
@override(SpecialSoundCtrl, 'setPlayerVehicle')
def new_setPlayerVehicle(original_func, self, vehiclePublicInfo, isPlayerVehicle):
    original_func(self, vehiclePublicInfo, isPlayerVehicle)
    # 在战场被创建后才可执行
    arena = avatar_getter.getArena()
    if arena is None or not g_template.config['enabled']:
        return
    g_template.apply_gender_switch()
    # 若开启了“使所有语音在设置菜单中可见”，可能需要关闭特殊语音覆盖功能。更换语音有时不应只依靠插件实现
    if g_template.config['ingame_voice_visible'] or g_template.config['outside_voice_visible']:
        # 先前已使用过setMode方法，这里直接结束
        return
    # 放在最后执行，无论前面设置了什么语音，最后会被改为 apply_vo
    SoundGroups.g_instance.soundModes.setMode(g_template.apply_vo)


@override(PlayerAccount, 'onBecomePlayer')
def new_onBecomePlayer(original_func, self):
    original_func(self)
    global msg_sent
    if not msg_sent:
        SystemMessages.pushMessage(text=text, type=text_type, messageData={'header': header})
        msg_sent = True
