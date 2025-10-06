# coding=utf-8
"""
    此模块负责读取mods文件夹中的wotmod文件，获取语音信息列表、可播放的事件列表、检测结果，顺带读取一下config.json。
    通过zipfile，我们可以在不解压的情况下获取压缩包中的任意信息。收集语音包信息并汇总，进行冲突检测并保存信息。
    可能产生冲突的位置：res_mods中的audio_modes.xml。产生冲突时可能会丢失部分语音。
"""
import os
import zipfile
import json
import traceback
from constants import RES_MODS_AUDIOWW, GAME_SOUND_MODES_JSON, OBJ_FILES, PLAY_EVENTS_JSON, CONFIG_JSON
from collections import namedtuple
from myLogger import mylogger

# 创建命名元组保存读取的信息
VoiceMode = namedtuple('VoiceMode', 'name, language, nickName, bankPath, invisible')
VoiceMode.__new__.__defaults__ = ('default', 'default', '标准', 'voiceover.bnk', True)
SubtitleInfo = namedtuple('SubtitleInfo',
                          'isVoiceover, language, nickName, bankPath, characters, sentences, visuals')


class Search(object):
    def __init__(self):
        # 分别保存以下元组：外部语音包（包含字幕语音包）、内部语音包、字幕语音包
        self.outside_voices = []
        self.inside_voices = []
        self.subtitles = []
        # 插件包含audio_mods.xml，但是不包含main_sound_modes.xml，与炮声mod这类使用了第一个xml的插件冲突，
        # 因为冲突时插件被卸载，如果被卸载的是另一个冲突mod，那插件可以正常运行，故不需要相关检测代码
        # 不过呢，检查一下res_mods，提前预告一下可能出现的语音丢失会比较好
        # code：0 语音可能丢失；1 一切正常
        self.code = 1
        self.report = ''
        # 保存语音包的自定义通知信息（如果有的话）
        self.infoNotify = {}

    def conflict_check(self):
        if os.path.exists(RES_MODS_AUDIOWW):
            for f in os.listdir(RES_MODS_AUDIOWW):
                if f.endswith('.xml'):
                    self.code = 0
                    self.report += '<br><font color="#d3d3d3">在' + RES_MODS_AUDIOWW + '目录下找到了xml文件，该文件可能是audio_mods.xml</font>'
                    mylogger.warn('fileSearch', '在%s目录下找到了xml文件，该文件可能是audio_mods.xml。' % RES_MODS_AUDIOWW)
                    break
        if not self.code:
            self.report += '<br><font color="#cc9933">语音包中的个别语音（如：被点亮）可能丢失声音。<br>暂不支持语音包同音效包的冲突处理，请期待未来的更新。</font>'
            mylogger.warn('fileSearch', '语音包中的个别语音（如：被点亮）可能丢失声音，请考虑是否将产生冲突的audio_mods.xml删除。')

    def read_from_mod_files(self):
        for wot_mod in OBJ_FILES:
            filename = wot_mod['filename'].split('.wotmod')[0]
            if filename.startswith('voiceover_'):
                path = wot_mod['path']
                with zipfile.ZipFile(path, 'r') as zip_ref:
                    zip_namelist = zip_ref.namelist()
                    if not filter(lambda x: x.startswith('res/'), zip_namelist):
                        mylogger.error('fileSearch', '语音包%s打包方式不正确！压缩包内目录下应直接包含“res”文件夹。' % filename)
                        continue
                    found = False
                    info_file = ''
                    for item in zip_ref.namelist():
                        if item.startswith('sbt_') or item.startswith('sbtlist_') or item.startswith('vo_') or item.startswith('volist_'):
                            info_file = item
                            found = True
                            with zip_ref.open(info_file, 'r') as f:
                                json_data = ''
                                json_without_comments = ''
                                vo_list_to_check = []
                                for line in f:
                                    json_without_comments += line.split('//')[0]
                                try:
                                    json_data = json.loads(json_without_comments, encoding='utf-8')
                                    vo_list_to_check = self._loadJson(info_file, json_data, filename)
                                except KeyError:
                                    stack_trace = traceback.format_exc()
                                    mylogger.error('fileSearch', '在%s中发现不正确的json文件，请检查json语法！' % filename)
                                    mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
                                except Exception:
                                    stack_trace = traceback.format_exc()
                                    mylogger.error('fileSearch', '在处理%s中的json文件时捕获到异常！' % filename)
                                    mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
                                    break
                                if vo_list_to_check:
                                    for vo_lang in vo_list_to_check:
                                        msg_path = 'res/audioww/' + vo_lang + '/msg.txt'
                                        if msg_path in zip_namelist:
                                            with zip_ref.open(msg_path, 'r') as zip_txt:
                                                text = zip_txt.read().decode('utf-8')
                                                self.infoNotify.update({vo_lang: text})
                            break
                    if not found:
                        mylogger.warn('fileSearch', '语音包%s中未找到json文件，无法为其创建声音模式。' % filename)

    def read_from_config_folder(self):
        # 读取内部语音包，也就是为wot自带的语音包创建声音模式
        with open(GAME_SOUND_MODES_JSON, 'r') as f:
            json_without_comments = ''
            json_data = {}
            for line in f:
                json_without_comments += line.split('//')[0]
            try:
                json_data = json.loads(json_without_comments, encoding='utf-8')
            except ValueError:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch', 'gameSoundModes.json不是一个json对象！请检查json语法！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
                return
            except Exception:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch', '读取gameSoundModes.json时出错！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
                return
            modes = json_data['modes']
            try:
                for mode in modes:
                    name = mode['voiceID']
                    nickName = mode['name']
                    bankPath = mode['bankPath']
                    language = bankPath.split('/voiceover.bnk')[0]
                    # 客户端根据声音模式的名字来调用，Wwise会根据名字获取当前它所对应的wwise_language，然后将语音包加载进内存。
                    # wwise_language是指向语音包的简化的路径名，这里我将其称为“wwiseID”，二者之间关系如下：
                    # wwiseID：语音包所在路径（audioww文件夹下开始算）
                    # bankPath：语音包所在路径 + r'/voiceover.bnk'
                    # 测试发现，如想使用游戏自带的语音，那么填入正确的wwiseID即可。默认语音的wwise_language是空值。
                    # 游戏使用ResMgr检查bankPath所指向的bnk是否存在，之后便不再使用bankPath，而是使用wwiseID。
                    # 游戏将通过wwiseID加载如下文件：voiceover.bnk、inbattle_communication_pc.bnk、inbattle_communication_npc.bnk，后两个如有缺失就向上寻找。
                    # 一旦你填入了正确的voiceID和bankPath，这个特殊语音将不能被覆盖。可行方法是挂接一个函数，在进入战斗之后显式修改语音。
                    # 另一种方法是自己给voiceID重新起个名字，这样特殊成员语音就因为找不到这个ID而无法切换，从而被屏蔽。
                    # ps：如果游戏语音切换失败（没有这个名字对应的声音），将会切换声音模式为默认，这也就是屏蔽特殊成员的原理。
                    if not language:
                        mylogger.warn('fileSearch', '从gameSoundModes中读取到的语音包“%s”可能有问题！它没有位于单独的文件夹中。' % nickName)
                    else:
                        self.inside_voices.append(VoiceMode(name, language, nickName, bankPath))
            except KeyError:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch',
                               '在处理gameSoundModes.json时发现异常，无法创建声音模式！请检查gameSoundModes.json中键值对是否缺失！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
            except Exception:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch', '在处理gameSoundModes.json中的信息时出错，无法添加声音！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)

    def _loadJson(self, filename, json_data, obj):
        # volist.json/sbtlist.json：批量创建声音模式
        # sbt.json：为字幕语音包创建声音模式（会将信息同步添加到语音包列表和字幕语音包列表中），vo.json：创建声音模式的最简单文件
        # 语音ID通过bankPath属性获得，例如asumi/voiceover.bnk，则该语音包ID为asumi，无需手动填写
        # vo_list用于寻找语音包的自定义通知信息（如果有的话）
        vo_list = []
        try:
            if filename.startswith('volist_'):
                mylogger.info('fileSearch', '在%s中读取到语音包列表。' % obj)
                for info in json_data:
                    nickName = info['nickName']
                    bankPath = info['bankPath']
                    language = bankPath.split('/voiceover.bnk')[0]
                    name = 'ORV_' + language
                    if not language or language == 'voiceover.bnk':
                        raise NoSoundFileError('[bnk文件位置不正确]语音包没有位于自定义文件夹中！')
                    self.outside_voices.append(VoiceMode(name, language, nickName, bankPath))
                    vo_list.append(language)
            elif filename.startswith('sbtlist_'):
                mylogger.info('fileSearch', '在%s中读取到字幕语音包列表。' % obj)
                for info in json_data:
                    nickName = info['nickName']
                    bankPath = info['voiceover_Path']
                    characters = info['characters']
                    sentences = info['sentences']
                    visuals = info['visuals']
                    language = bankPath.split('audioww/')[1].split('/voiceover.bnk')[0]
                    if not language or language == 'voiceover.bnk' or bankPath.split('/')[0] != 'audioww':
                        raise NoSoundFileError('[bnk文件位置不正确]语音包没有位于自定义文件夹中！')
                    self.outside_voices.append(VoiceMode(language, language, nickName, bankPath.split('audioww/')[1]))
                    self.subtitles.append(SubtitleInfo(True, language, nickName, bankPath, characters, sentences, visuals))
                    vo_list.append(language)
                    if "otherBanks" in json_data and json_data['otherBanks']:
                        for bnk in json_data['otherBanks']:
                            lang = language + '_OTR'
                            bankPath = bnk['bankLocation']
                            characters = bnk['characters']
                            sentences = bnk['sentences']
                            visuals = bnk['visuals']
                            self.subtitles.append(
                                SubtitleInfo(False, lang, '', bankPath, characters, sentences, visuals))
                            language = lang
            elif filename.startswith('sbt_'):
                mylogger.info('fileSearch', '在%s中读取到字幕语音包。' % obj)
                nickName = json_data['nickName']
                bankPath = json_data['voiceover_Path']
                characters = json_data['characters']
                sentences = json_data['sentences']
                visuals = json_data['visuals']
                language = bankPath.split('audioww/')[1].split('/voiceover.bnk')[0]
                if not language or language == 'voiceover.bnk' or bankPath.split('/')[0] != 'audioww':
                    raise NoSoundFileError('[bnk文件位置不正确]语音包没有位于自定义文件夹中！')
                self.outside_voices.append(VoiceMode(language, language, nickName, bankPath.split('audioww/')[1]))
                self.subtitles.append(SubtitleInfo(True, language, nickName, bankPath, characters, sentences, visuals))
                vo_list.append(language)
                if "otherBanks" in json_data and json_data['otherBanks']:
                    for info in json_data['otherBanks']:
                        lang = language + '_OTR'
                        bankPath = info['bankLocation']
                        characters = info['characters']
                        sentences = info['sentences']
                        visuals = info['visuals']
                        self.subtitles.append(SubtitleInfo(False, lang, '', bankPath, characters, sentences, visuals))
                        language = lang
            elif filename.startswith('vo_'):
                mylogger.info('fileSearch', '在%s中读取到语音包。' % obj)
                nickName = json_data['nickName']
                bankPath = json_data['bankPath']
                language = bankPath.split('/voiceover.bnk')[0]
                name = 'ORV_' + language
                if not language or language == 'voiceover.bnk':
                    raise NoSoundFileError('[bnk文件位置不正确]语音包没有位于自定义文件夹中！')
                self.outside_voices.append(VoiceMode(name, language, nickName, bankPath))
                vo_list.append(language)
        except KeyError:
            stack_trace = traceback.format_exc()
            mylogger.warn('fileSearch',
                          '在处理%s时发现异常，无法为其创建声音模式！请检查%s中的键值对是否缺失！' % (obj, filename))
            mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
        except NoSoundFileError:
            stack_trace = traceback.format_exc()
            mylogger.warn('fileSearch',
                          '在处理%s时语音包不在自定义路径中，请将其放入自定义文件夹，并同步修改%s中语音包的路径。' % (
                              obj, filename))
            mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
        except Exception:
            stack_trace = traceback.format_exc()
            mylogger.warn('fileSearch', '在处理%s时捕获到异常！' % obj)
            mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
        return vo_list

    # 用于获取playEvents.json中的事件列表
    def getEventList(self):
        elist = []
        with open(PLAY_EVENTS_JSON) as f:
            json_without_comments = ''
            for line in f:
                json_without_comments += line.split('//')[0]
            try:
                json_data = json.loads(json_without_comments, encoding='utf-8')
                info_list = json_data['eventList']
                for event in info_list:
                    elist.append({'id': event['id'], 'name': event['name']})
            except ValueError:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch', 'playEvents.json不是一个json对象！请检查json语法！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
            except Exception:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch', '在处理playEvents.json中的信息时出错，未能获取播放事件列表！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
        return elist

    # 用于获取config.json中的信息。其中modeName保存的是声音模式名，需要在使用前将其修改为声音列表索引值（int）才能用于保存UI中的偏好
    def getConfig(self):
        settings = {}
        with open(CONFIG_JSON) as f:
            json_without_comments = ''
            for line in f:
                json_without_comments += line.split('//')[0]
            try:
                json_data = json.loads(json_without_comments, encoding='utf-8')
                settings.update(
                    {'enabled': json_data['enabled'],
                     'vo_type_acv': json_data['currentMode'],
                     'vo_selector_acv': json_data['modeName'],
                     'vo_test_acv': 0,
                     'vo_visible_acv': json_data['visibleAll'],
                     'big_button_acv': json_data['infoNotify'],
                     'version': json_data['__version__']
                     }
                )
                if 'autoVolume' in json_data:
                    settings.update({'vo_volume_acv': json_data['autoVolume']})
                else:
                    settings.update({'vo_volume_acv': True})
            except ValueError:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch', 'config.json不是一个json对象！请检查json语法！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
            except Exception:
                stack_trace = traceback.format_exc()
                mylogger.error('fileSearch', '在处理配置文件时出错！')
                mylogger.warn('fileSearch', '堆栈信息：%s' % stack_trace)
        return settings

    def getVModes(self):
        return self.outside_voices

    def getGameVMode(self):
        return self.inside_voices

    def getSModes(self):
        return self.subtitles

    def getCode(self):
        return self.code

    def getReport(self):
        return self.report

    def getNotify(self, name):
        if name in self.infoNotify:
            return self.infoNotify[name]
        else:
            return ''

    def remove_from_VMode(self, mode):
        self.outside_voices.remove(mode)

    def remove_from_GameVMode(self, mode):
        self.inside_voices.remove(mode)


# 自定义异常，当语音包所在的文件夹名字不正确时抛出此异常
class NoSoundFileError(Exception):
    pass


# 类的实例化对象
g_search = Search()
