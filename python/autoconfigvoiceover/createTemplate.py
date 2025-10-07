# coding=utf-8
"""
    此模块负责通过modsSettingsApi绘制UI，并实现语音切换与试听。
"""
from constants import (DEFAULT_PNG, UPDATE_PNG, MY_LOG_PATH, WHERE_ARE_PARENT, CURRENT_VOLUME,
                       CONFIG_TEMPLATE, INFO_TEMPLATE, PLAY_EVENTS_TEMPLATE, GAME_SOUND_MODES_TEMPLATE,
                       DEFAULT_MODES_JSON, CONFIG_JSON, PLAY_EVENTS_JSON, GAME_SOUND_MODES_JSON, INFO_JSON)
from gui import SystemMessages
from gui.impl.dialogs.builders import WarningDialogBuilder
from gui.impl.pub.dialog_window import DialogButtons
from gui.shared.personality import ServicesLocator
from gui.game_control.special_sound_ctrl import SpecialSoundCtrl
from gui.battle_control import avatar_getter
from frameworks.wulf import WindowLayer
from wg_async import wg_await, wg_async
from BWUtil import AsyncReturn
from Account import PlayerAccount
from fileSearch import g_search
from updateFile import g_update
from myLogger import mylogger
from tools import override
import BigWorld
import ResMgr
import SoundGroups
import traceback
import time
import json
try:
    from gui.modsSettingsApi import g_modsSettingsApi
except ImportError:
    pass


class DrawUi(object):
    def __init__(self):
        self.modLinkage = 'auto_config_voiceover'
        self.my_template = {}
        self.apply_vo = 'default'
        self.lang = ''
        self.vo_name = '默认语音'
        self._previewSound = None
        self._preview_event = 'vo_selected'
        self._last_click_time = 0.0
        self._click_times = 0
        self.settings = {
            'enabled': True,
            'vo_type_acv': 0,
            'vo_selector_acv': 'default',
            'vo_test_acv': 0,
            'vo_visible_acv': False,
            'big_button_acv': True,
            'vo_volume_acv': True
        }
        self.index = self.settings['vo_type_acv']
        self.eventList = []
        self._myVolume = {}
        self._default_modes_volume = {}
        self._info_json_data = []
        self.code = 0
        self.header = ''
        self.text = ''
        self.comments = [
            {
                'tips1': '游戏内语音',
                'tips2': '安装的语音'
            },
            {
                'tips1': '游戏内语音',
                'tips2': '安装的语音（点击右侧图片更新mod）'
            }
        ]
        self.outside_vo_list = [{'vo': 'default', 'language': 'default', 'name': '默认语音'}]
        self.inside_vo_list = [
            {'vo': 'default', 'language': '', 'name': '默认语音'},
            {'vo': 'ZH_CH', 'language': 'china', 'name': '中系'},
            {'vo': 'RU', 'language': 'ussr', 'name': '苏系'},
            {'vo': 'DE', 'language': 'germany', 'name': '德系'},
            {'vo': 'EN', 'language': 'usa', 'name': '美系'},
            {'vo': 'UK', 'language': 'uk', 'name': '英系'},
            {'vo': 'FR', 'language': 'france', 'name': '法系'},
            {'vo': 'CS', 'language': 'czech', 'name': '捷克'},
            {'vo': 'SV', 'language': 'sweden', 'name': '瑞典'},
            {'vo': 'PL', 'language': 'poland', 'name': '波兰'},
            {'vo': 'IT', 'language': 'italy', 'name': '意大利'},
            {'vo': 'JA', 'language': 'japan', 'name': '日系'}
        ]
        # 用于在下拉列表中显示的语音模式名，分别归属外部语音和内部语音
        self._outside_vo_option = [{'label': '默认语音'}]
        self._inside_vo_option = [
            {'label': '默认语音'},
            {'label': '中系'},
            {'label': '苏系'},
            {'label': '德系'},
            {'label': '美系'},
            {'label': '英系'},
            {'label': '法系'},
            {'label': '捷克'},
            {'label': '瑞典'},
            {'label': '波兰'},
            {'label': '意大利'},
            {'label': '日系'}
        ]

    def init_vo_list(self):
        for vo in g_search.getVModes():
            self.outside_vo_list.append({'vo': vo.name, 'language': vo.language, 'name': vo.nickName})
            self._outside_vo_option.append({'label': vo.nickName})
        for gvo in g_search.getGameVMode():
            self.inside_vo_list.append({'vo': gvo.name, 'language': gvo.language, 'name': gvo.nickName})
            self._inside_vo_option.append({'label': gvo.nickName})

    def read_config_data(self):
        # 获取原始的json信息
        # 读取版本号并进行更新
        if ResMgr.isFile(CONFIG_JSON):
            self.settings = g_search.getConfig()
            if self.settings['version'] < 2:
                mylogger.info('createTemplate', '更新config.json。')
                self._saveAll()
                mylogger.info('createTemplate', '更新playEvents.json。')
                with open(PLAY_EVENTS_JSON, 'w') as f:
                    f.write(PLAY_EVENTS_TEMPLATE)
                mylogger.info('createTemplate', '更新gameSoundModes.json。')
                with open(GAME_SOUND_MODES_JSON, 'w') as f:
                    f.write(GAME_SOUND_MODES_TEMPLATE)
        else:
            mylogger.info('createTemplate', '创建config.json。')
            # 根据构造生成的模板创建模板。写入文件均用_saveAll，因为它可以忽略selector的值（可能是声音模式名或列表索引值），将其写入为self.apply_vo
            # 这样增加了可读性
            self._saveAll()

    def init_after_read(self):
        self.apply_vo = self.settings['vo_selector_acv']
        self.eventList = g_search.getEventList()
        # 获取所有语音历史音量偏好设置
        # 另外获取系别语音音量偏好设置
        self._myVolume = g_update.getMyVolume()
        self._default_modes_volume = g_update.getDefaultModesVolume()
        self._info_json_data = g_update.getInfoJsonData()
        if self.settings['enabled']:
            g_update.overrivedModes()
        # 将配置文件保存的历史语音应用
        self._updateSettings()
        self._setVisible()
        # 0 无需更新；1 需要更新；2 在重启前被修改，告诉程序有临时的.zip需要处理
        self.code = g_update.getCode()
        self.header = '<font color="#cc9933"><b>当前语音：</b></font><font color="#e0ffff"><b>%s</b></font>' % self.vo_name
        self.text = g_update.getInfo()
        mylogger.info('createTemplate', '启用中的语音：%s' % self.vo_name)

    # 根据模板绘制UI，当模板需要刷新时，会重新调用该方法
    def registerApiSupport(self):
        self.my_template = {
            'modDisplayName': '语音包管理插件',
            'enabled': self.settings['enabled'],
            'column1': self._createLabel() + self._createRadioButton() + self._createDropdown1() + self._createDropdown2(),
            'column2': self._createBigButtion()
        }
        g_modsSettingsApi.setModTemplate(self.modLinkage, self.my_template, self.onModSettingsChanged,
                                         self.onButtonClicked)

    def _updateSettings(self):
        # 此函数只运行一次，从原始的json数据中读取vo_selector_acv作为apply_vo的值，旨在
        # 在_vo_option中寻找apply_vo，并修改vo_selector_acv为正确的索引值
        # 如果不存在apply_vo，则修改为默认的default
        name = self.apply_vo
        list1 = []
        list2 = []
        self.lang = ''
        for item in self.outside_vo_list:
            list1.append(item['vo'])
        for item in self.inside_vo_list:
            list2.append(item['vo'])
        if name in list2:
            index = list2.index(name)
            self.settings.update({'vo_selector_acv': index})
            self.vo_name = self.inside_vo_list[index]['name']
            self.lang = self.inside_vo_list[index]['language']
            self.settings['vo_type_acv'] = 0
        elif name in list1:
            index = list1.index(name)
            self.settings.update({'vo_selector_acv': index})
            # vo_name 是汉字
            self.vo_name = self.outside_vo_list[index]['name']
            self.lang = self.outside_vo_list[index]['language']
            self.settings['vo_type_acv'] = 1
            self.index = 1
        else:
            self.settings.update({'vo_selector_acv': 0})
            self.apply_vo = 'default'
        # 这里我注意到，在声音模式不存在的时候（即便它的信息未被写入游戏内，如果它的文件并未被移除），仍然能通过设置lang属性来切换语音
        # 也就是说，语音包那三个bnk是不需要预加载，或者说可以直接通过Wwise预加载然后加载到内存。那么，添加任意一个语音包，也是不需要登记在xml文件中的
        # 因为我们可以直接访问SoundGroups实例中受保护的成员变量，为其手动创建声音模式并更新声音模式列表（手动实现读取xml所做的事）。
        if self.apply_vo in SoundGroups.g_instance.soundModes._SoundModes__modes.keys():
            SoundGroups.g_instance.soundModes._SoundModes__modes['default'].voiceLanguage = self.lang
            SoundGroups.g_instance.soundModes.setMode(self.apply_vo)
        else:
            self.apply_vo = 'default'
            self.vo_name = self.inside_vo_list[0]['name']
            self.index = 0
            self.settings.update({'vo_selector_acv': 0})
            self.settings['vo_type_acv'] = 0
        self._setVolume(self._getSetVolume())

    def _createLabel(self):
        return [
            {
                'type': 'Label',
                'text': '简介：太长了我放旁边的tooltip里了',
                'tooltip': ('{HEADER}语音包管理插件{/HEADER}'
                            '{BODY}这个插件可以允许你安装多个画外音语音包，同时不必手动处理语音包之间的冲突，例如不同语音包相互覆盖的问题，或者字幕语音包彼此不兼容的问题。'
                            '\n插件会清除游戏中大部分已有声音模式，并将选定的语音包设置为默认的语音，这样将会屏蔽特殊成员语音。你可以修改%s中的配置文件补回特殊语音，'
                            '之后，这些补回的语音也会收录进可选语音。\n\n为了减少不必要的读写操作，'
                            '直接重启游戏并不会更新插件中字幕语音的配置json文件保存的内容，你需要在弹出的窗口中主动选择更新。{/BODY}') % MY_LOG_PATH
            },
            {
                'type': 'Label',
                'text': '> 关于mod生成的文件',
                'tooltip': ('{HEADER}文件信息说明{/HEADER}{BODY}配置文件所在路径：%s\n\n> config.json\n当前的设置信息。'
                            '\n> gameSoundModes.json\n为游戏已有的语音包创建声音模式，用于补回特殊成员语音。'
                            '\n> playEvents.json\n测试声音时选择播放的事件。'
                            '\n> script.log\n日志文件。'
                            '\n> template_json文件夹\n模板文件用于创建可读的语音包打包文件。'
                            '\n> voiceover_info文件夹\n保存上次运行时语音模式列表。'
                            '\n\n文件替换程序：remove_old_archive.bat'
                            '\n更新归档文件信息。这是必须的，否则无法移除旧的json文件。'
                            '\n所在路径：%s'
                            '\n\n{/BODY}{NOTE}要使配置文件恢复默认，请删除对应文件并重启客户端。{/NOTE}') % (MY_LOG_PATH, WHERE_ARE_PARENT)
            }
        ]

    def _createRadioButton(self):
        return [
            {
                'type': 'RadioButtonGroup',
                'text': '当前语音列表',
                'tooltip': '{HEADER}语音包列表{/HEADER}{BODY}已安装的语音包视为“外部”语音包\n游戏自带的语音包视为“内部”语音包'
                           '\n选择并点击切换后，重新打开插件管理器即可刷新列表。{/BODY}',
                'options': [
                    {'label': '内部'},
                    {'label': '外部'}
                ],
                'button': {
                    'width': 60,
                    'height': 24,
                    'offsetTop': 0,
                    'offsetLeft': 0,
                    'text': '切换',
                    'iconSource': '',
                    'iconOffsetTop': 0,
                    'iconOffsetLeft': 1
                },
                'value': self.index,
                'varName': 'vo_type_acv'
            }
        ]

    def _createDropdown1(self):
        return [
            {
                'type': 'Label',
                'text': '_____________________________________________'
            },
            {
                'type': 'Dropdown',
                'text': self.comments[self.code]['tips2'] if self.index else self.comments[self.code]['tips1'],
                'tooltip': '{HEADER}已安装了语音包但是找不到？/字幕语音包没有字幕？{/HEADER}{BODY}找不到对应的语音包：\n\n1.安装的语音包没有打包成wotmod文件\n'
                           '插件只能识别指定方式打包的语音包，并读取压缩文件中的信息来为其创建声音模式。'
                           '\n2.语音包打包的方式不正确或者读取语音包信息时出现了错误\n插件运行过程中可能出现的错误信息会被输出到日志文件，请检查日志。'
                           '\n\n没有字幕：\n\n1.不是所有语音包都有显示字幕的功能。'
                           '\n2.首次使用插件或者安装新的字幕语音包时，你会在登录游戏后收到更新通知，'
                           '此时右侧图片会发生变化。点击图片弹出重启窗口，点击更新文件并重启后，等待文件更新，然后手动启动游戏。\n{/BODY}'
                           '{NOTE}bilibili搜索“下一个车站等你”发布的相关视频，了解插件详细介绍与语音包打包方式{/NOTE}',
                'options': self._get_vo_option(),
                'button': {
                    'width': 60,
                    'height': 24,
                    'offsetTop': 0,
                    'offsetLeft': 0,
                    'text': '应用',
                    'iconSource': '',
                    'iconOffsetTop': 0,
                    'iconOffsetLeft': 1
                },
                'width': 200,
                'value': self.settings['vo_selector_acv'],
                'varName': 'vo_selector_acv'
            }
        ]

    def _createDropdown2(self):
        return [
            {
                'type': 'Dropdown',
                'text': '测试声音',
                'tooltip': '{HEADER}声音没有播放？{/HEADER}{BODY}通过Wwsie事件名来播放语音包中的指定语音。'
                           '\n如果没有声音，则可能该语音包没有制作对应的语音，或是该语音所在的语音包在车库中不加载。'
                           '此外，为了更好的语音效果，这个插件修改了部分事件名，也会导致原本的事件不能播放。如果选定的事件已被移除或者有拼写错误，也将无法播放。'
                           '\n\n被修改的事件详见playEvents.json中注释部分。{/BODY}',
                'options': self._get_event_option(),
                'button': {
                    'width': 60,
                    'height': 24,
                    'offsetTop': 0,
                    'offsetLeft': 0,
                    'iconSource': '../maps/icons/buttons/sound.png',
                    'iconOffsetTop': 0,
                    'iconOffsetLeft': 1
                },
                'width': 200,
                'value': self.settings['vo_test_acv'],
                'varName': 'vo_test_acv'
            },
            {
                'type': 'Slider',
                'text': '调整音量',
                'tooltip': '{HEADER}单独为该语音包调节音量{/HEADER}'
                           '{BODY}滑块作用和你在设置界面的效果是一样的，点击右侧按钮后，音量改动将立即生效。'
                           '\n切换为未设置音量的语音包时，会将音量同步为你之前设置的音量大小。'
                           '\n切换为已设定音量的语音包时，重新打开界面即可刷新面板。\n{/BODY}'
                           '{NOTE}你也可以在voiceover_info文件夹中直接修改对应文件。对配置文件直接改动，则无需再次打开游戏修改。{/NOTE}',
                'button': {
                    'width': 60,
                    'height': 24,
                    'offsetTop': 0,
                    'offsetLeft': 0,
                    'text': '设定',
                    'iconSource': '',
                    'iconOffsetTop': 0,
                    'iconOffsetLeft': 1
                },
                'minimum': 0,
                'maximum': 100,
                'snapInterval': 1,
                'value': self._getSetVolume(),
                'format': '{{value}}',
                'varName': 'vo_slider_acv'
            },
            {
                'type': 'CheckBox',
                'text': '切换语音包时自动应用音量偏好',
                'tooltip': '{HEADER}为每个语音包单独设定音量偏好{/HEADER}'
                           '{BODY}勾选并保存设置后，在切换语音包时，会替你自动修改战斗语音的音量。'
                           '\n切换语音包并重新打开界面，音量滑块将正确的显示当前语音包音量设置。\n{/BODY}'
                           '{ATTENTION}只有通过插件切换语音才能同步修改音量。{/ATTENTION}',
                'value': self.settings['vo_volume_acv'],
                'varName': 'vo_volume_acv'
            }
        ]

    def _createBigButtion(self):
        return [
            {
                'type': 'CheckBox',
                'text': '使所有语音在设置菜单中可见',
                'tooltip': '{HEADER}语音是否可见{/HEADER}{BODY}勾选并保存设置后，你可以在设置菜单的语音选择中，找到已创建的声音模式，并随时更改。\n{/BODY}'
                           '{ATTENTION}开启后将暂时关闭屏蔽特殊语音的功能。{/ATTENTION}',
                'value': self.settings['vo_visible_acv'],
                'varName': 'vo_visible_acv'
            },
            {
                'type': 'CheckBox',
                'text': '切换语音后展示语音包信息',
                'tooltip': '{HEADER}接受自定义的通知信息{/HEADER}{BODY}勾选后，在选定语音包并应用后，除了语音切换通知外，你还将收到一条来自语音包'
                           '的自定义通知信息（如果有的话）。取消勾选后，将仅接收语音切换通知。点击下方图片可以手动获取当前语音包的自定义通知信息。'
                           '\n\n在勾选接收自定义通知信息后，点击图片获取信息的同时，还会播放一条自定义问候语音。（如果有的话）取消勾选后点击图片不会播放该声音。\n\n{/BODY}'
                           '{NOTE}PS：下面的图片其实是一个巨大的按钮。{/NOTE}',
                'button': {
                    'width': 300,
                    'height': 300,
                    'offsetTop': 30,
                    'offsetLeft': -200,
                    'iconSource': self._getIcon(),
                    'iconOffsetTop': 0,
                    'iconOffsetLeft': 1
                },
                'value': self.settings['big_button_acv'],
                'varName': 'big_button_acv'
            }
        ]

    # 获取声音模式列表，用于显示在对应下拉列表中。0 代表游戏自带的语音包，存放在inside_vo_list和_inside_vo_option中
    def _get_vo_option(self):
        return self._outside_vo_option if self.index else self._inside_vo_option

    # 获取事件列表，用于显示在对应下拉列表中
    def _get_event_option(self):
        elist = []
        for event in self.eventList:
            elist.append({'label': event['name']})
        return elist

    # 获取大按钮的图标
    def _getIcon(self):
        if self.code:
            return UPDATE_PNG
        else:
            icon_path = 'audioww/' + self.lang + '/default.png'
            if ResMgr.isFile(icon_path):
                return '../../' + icon_path
            else:
                return DEFAULT_PNG

    def getNotify(self):
        return self.text

    def getHeader(self):
        return self.header

    def getCode(self):
        return self.code

    def _saveAll(self):
        # 使用字典格式化字符串，不过要先将“{”、“}”进行转义，其中“vo_test_acv”属性不会进行保存，从文件读取或从模板中创建时会创建属性并将其赋值为0
        template = '{' + CONFIG_TEMPLATE + '}'
        msg = {
            'enabled': 'true' if self.settings['enabled'] else 'false',
            'vo_type_acv': self.settings['vo_type_acv'],
            'vo_selector_acv': '"%s"' % self.apply_vo,
            'vo_visible_acv': 'true' if self.settings['vo_visible_acv'] else 'false',
            'big_button_acv': 'true' if self.settings['big_button_acv'] else 'false',
            'vo_volume_acv': 'true' if self.settings['vo_volume_acv'] else 'false'
        }
        template = template.format(**msg)
        with open(CONFIG_JSON, 'w') as f:
            f.write(template)

    # 通知中心发送语音包的自定义通知信息
    def _push_vo_msg(self, info=False):
        text = g_search.getNotify(self.lang)
        if text:
            SystemMessages.pushMessage(text, SystemMessages.SM_TYPE.GameGreeting)
        elif info:
            SystemMessages.pushMessage(text='<br>再怎么点也没有啦',
                                       type=SystemMessages.SM_TYPE.MessageHeader,
                                       messageData={'header': '<font color="#00bfff"><b>这个语音没有自定义消息</b></font>'})

    def _playPreviewSound(self, event):
        if event != self._preview_event:
            self._preview_event = event
            mylogger.info('createTemplate', '播放声音：%s' % event)
        self._clearPreviewSound()
        self._previewSound = SoundGroups.g_instance.getSound2D(event)
        if self._previewSound is None:
            mylogger.warn('createTemplate', '声音无法播放：%s' % event)
        else:
            self._previewSound.play()

    def _clearPreviewSound(self):
        if self._previewSound is not None:
            self._previewSound.stop()
            self._previewSound = None

    def _getSetVolume(self):
        if self.apply_vo in self._myVolume:
            return self._myVolume[self.apply_vo]
        else:
            return CURRENT_VOLUME

    def _setVolume(self, volume):
        value = float(volume) / 100
        SoundGroups.g_instance.setVolume('voice', value, True)

    def _setVisible(self):
        visible = self.settings['vo_visible_acv']
        modes = SoundGroups.g_instance.soundModes._SoundModes__modes.keys()
        if visible:
            for mode in modes:
                SoundGroups.g_instance.soundModes._SoundModes__modes[mode].invisible = False
        else:
            for mode in modes:
                SoundGroups.g_instance.soundModes._SoundModes__modes[mode].invisible = True
            SoundGroups.g_instance.soundModes._SoundModes__modes['default'].invisible = False
        mylogger.info('createTemplate', '设置显示属性：%s' % visible)

    @wg_async
    def _tryRestart(self, dialogText, dialogTitile):
        mylogger.info('createTemplate', '正在准备重启客户端。')
        builder = WarningDialogBuilder().setFormattedMessage(dialogText).setFormattedTitle(dialogTitile)
        # 设置焦点，True 代表这个按钮将是一个预选中的状态
        builder.addButton(DialogButtons.RESEARCH, None, True, rawLabel='更新并手动重启')
        builder.addButton(DialogButtons.SUBMIT, None, False, rawLabel='暂时不')
        try:
            parent = ServicesLocator.appLoader.getApp().containerManager.getContainer(WindowLayer.VIEW).getView()
        except (AttributeError, TypeError):
            parent = None
            mylogger.info('createTemplate', '在调用确认窗口时发生错误：%s' % traceback.format_exc())
        result = yield wg_await(self._show(builder.build(parent)))
        if result.result == DialogButtons.RESEARCH:
            mylogger.info('createTemplate', '确认重启客户端。')
            g_update.updateFile()
            mylogger.info('createTemplate', '已创建临时存档。')
            # code 2：稍后将尝试寻找归档文件并替换旧文件
            self.code = 2
            BigWorld.savePreferences()
            BigWorld.quit()

    # 由于modsSettingsApi的UI使用的窗口布局非常靠顶层（仅次于WindowLayer.SERVICE_LAYOUT）
    # 这里我们改写了dialogs模块中的show方法，修改简单对话框的默认窗口布局，将其改为最顶层的布局
    @wg_async
    def _show(self, dialog):
        dialog.setLayer(WindowLayer.SERVICE_LAYOUT)
        dialog.load()
        result = yield wg_await(dialog.wait())
        dialog.destroy()
        raise AsyncReturn(result)

    def onModSettingsChanged(self, linkage, new_settings):
        if linkage != self.modLinkage:
            return
        self.settings = new_settings
        self.index = self.settings['vo_type_acv']
        self._saveAll()
        self.registerApiSupport()
        self._setVisible()
        mylogger.info('createTemplate', '接收通知信息：%s' % self.settings['big_button_acv'])
        mylogger.info('createTemplate', '应用音量偏好：%s' % self.settings['vo_volume_acv'])
        mylogger.info('createTemplate', '插件启用状态：%s' % self.settings['enabled'])
        if self.settings['enabled']:
            g_update.overrivedModes()
            if self.settings['vo_volume_acv']:
                self._setVolume(self._getSetVolume())
            SoundGroups.g_instance.soundModes._SoundModes__modes['default'].voiceLanguage = self.lang
            SoundGroups.g_instance.soundModes.setMode(self.apply_vo)
            mylogger.info('createTemplate', '语音恢复为：%s' % self.apply_vo)
        else:
            g_update.recoverModes()
            SoundGroups.g_instance.soundModes.setMode('ZH_CH')
            SoundGroups.g_instance.soundModes.setMode('default')

    def onButtonClicked(self, linkage, varName, value):
        if linkage != self.modLinkage:
            return
        if varName == 'vo_type_acv':
            self.settings['vo_type_acv'] = value
            self.index = value
            self.settings.update({'vo_selector_acv': 0})
            self.registerApiSupport()
        elif varName == 'vo_selector_acv':
            # 和前文提到的一样，0代表“内部语音”，存放在inside_vo_list和_inside_vo_option中
            # 因为要用到更多的信息，所以没有通过_get_event_option方法获取列表
            vo_list = self.outside_vo_list if self.index else self.inside_vo_list
            if value >= len(vo_list):
                value = 0
            vo_msg = vo_list[value]
            old_apply_name = self.apply_vo
            old_vo_name = self.vo_name
            old_volume = self._getSetVolume()
            self.apply_vo = vo_msg['vo']
            if self.settings['vo_volume_acv']:
                self._setVolume(self._getSetVolume())
            self.vo_name = vo_msg['name']
            self.lang = vo_msg['language']
            # 切换语音原理：访问SoundGroups实例并修改它内部受保护的成员变量值，将default字段重新赋值
            # 这里是一个字典 {string: SoundGroups.SoundModeDesc}
            # 直接修改“default”对应的SoundGroups.SoundModeDesc自身的属性即可，只需要更改“voiceLanguage”
            # SoundGroups模块在游戏进程中只有这一个实例，对它的改动将是全局的
            # 同样的，一旦SoundGroups被实例化，main_sound_mods.xml也就不再被需要了，对它的任何改动都是徒劳无功的
            if self.apply_vo != old_apply_name:
                header = '<font color="#cc9933"><b>切换语音：%s</b></font>' % self.vo_name
                text = ''
                if self.apply_vo in SoundGroups.g_instance.soundModes._SoundModes__modes:
                    # 这里我们设置好的声音模式可能因为各种原因变回默认，此时需要先切换语音模式，更改lang属性，再切回默认，才能刷新默认语音
                    # 也正是因为有这个不确定因素，更改语音时，不仅会修改声音模式为指定语音，还会将默认的语音也改为指定语音，避免突然切回默认导致更改失效
                    if self.apply_vo == 'default':
                        SoundGroups.g_instance.soundModes.setMode('ZH_CH')
                    SoundGroups.g_instance.soundModes._SoundModes__modes['default'].voiceLanguage = self.lang
                    SoundGroups.g_instance.soundModes.setMode(self.apply_vo)
                    self.apply_vo = vo_msg['vo']
                    self.vo_name = vo_msg['name']
                    mylogger.info('createTemplate', '切换语音：%s [%s]' % (self.vo_name, self.apply_vo))
                    if self.settings['big_button_acv']:
                        self._push_vo_msg()
                else:
                    mylogger.error('createTemplate', '无法切换声音模式%s：该声音尚不存在！请检查语音包路径信息是否错误，或bnk文件是否存在！' % self.apply_vo)
                    text += '<br><font color="#b22222">无法切换！声音模式不存在！</font>'
                    self.apply_vo = old_apply_name
                    self.vo_name = old_vo_name
                    self._setVolume(old_volume)
                SystemMessages.pushMessage(text=text,
                                           type=SystemMessages.SM_TYPE.MessageHeader,
                                           messageData={'header': header})
                self.settings['vo_selector_acv'] = value
                self._saveAll()
                self.registerApiSupport()
            # 如果语音没变化，不会重复展示切换通知，仅播放自定义问候语音vo_selected，并将这条信息写入日志
            self._playPreviewSound('vo_selected')
        elif varName == 'vo_test_acv':
            event = self.eventList[value]['id']
            self.settings['vo_test_acv'] = value
            self._playPreviewSound(event)
            self.registerApiSupport()
        elif varName == 'big_button_acv':
            if self.code:
                dialog_text = '你安装的字幕语音包有变化！准备向配置文件添加新的字幕语音信息，信息修改后需要重启游戏客户端才能生效。是否需要更新文件并重启？'
                dialog_title = '为加载新的字幕语音信息重启游戏'
                self._tryRestart(dialog_text, dialog_title)
            # 实现按钮连点3次后弹出更新选择
            else:
                click_time = time.time()
                if click_time - self._last_click_time < 0.5:
                    self._click_times += 1
                else:
                    self._click_times = 0
                self._last_click_time = click_time
                if self._click_times == 2:
                    self._click_times = 0
                    dialog_text = '准备向配置文件更新字幕语音信息，信息修改后需要重启游戏客户端才能生效。是否需要更新文件并重启？'
                    dialog_title = '再次更新文件并重启游戏'
                    self._tryRestart(dialog_text, dialog_title)
                else:
                    self._push_vo_msg(True)
                    if value:
                        self._playPreviewSound('vo_selected')
        elif varName == 'vo_slider_acv':
            voice = self.apply_vo + '_volume'
            if voice in self._default_modes_volume:
                self._setVolume(value)
                self._default_modes_volume.update({voice: value})
                # 保存进文件
                with open(DEFAULT_MODES_JSON, 'w') as f:
                    template = INFO_TEMPLATE.format(**self._default_modes_volume)
                    f.write(template)
            else:
                for item in self._info_json_data:
                    if item['voiceID'] == self.apply_vo:
                        item['volume'] = value
                    continue
                # 保存进文件
                with open(INFO_JSON, 'w') as f:
                    f.write(json.dumps(self._info_json_data, ensure_ascii=False, indent=4))
            self._myVolume.update({self.apply_vo: value})
            self._setVolume(value)


g_template = DrawUi()
acv_sent_msg = True


# 覆盖此方法，特殊语音将使用插件设定的语音
@override(SpecialSoundCtrl, 'setPlayerVehicle')
def new_setPlayerVehicle(original_func, self, vehiclePublicInfo, isPlayerVehicle):
    original_func(self, vehiclePublicInfo, isPlayerVehicle)
    # 在战场被创建后才可执行
    arena = avatar_getter.getArena()
    if g_template.settings['vo_visible_acv'] or not g_template.settings['enabled'] or arena is None:
        return
    # 放在最后执行，无论前面设置了什么语音，最后会被改为 apply_vo
    # 若开启了“使所有语音在设置菜单中可见”，可能需要关闭特殊语音覆盖功能。更换语音有时不应只依靠插件实现
    SoundGroups.g_instance.soundModes.setMode(g_template.apply_vo)


@override(PlayerAccount, 'onBecomePlayer')
def new_onBecomePlayer(original_func, self):
    original_func(self)
    global acv_sent_msg
    if acv_sent_msg and g_template.settings['enabled']:
        acv_text = g_template.getNotify()
        if acv_text:
            acv_text_type = SystemMessages.SM_TYPE.MessageHeader
            acv_header = g_template.getHeader()
        else:
            acv_text = '插件运行时出现意外。'
            acv_text_type = SystemMessages.SM_TYPE.ErrorSimple
            acv_header = ''
        SystemMessages.pushMessage(text=acv_text, type=acv_text_type, messageData={'header': acv_header})
        acv_sent_msg = False
