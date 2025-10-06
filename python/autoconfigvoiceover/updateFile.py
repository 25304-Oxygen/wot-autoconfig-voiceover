# coding=utf-8
"""
    此模块负责处理已知的语音模式，合并字幕语音包的json配置文件（如果安装了字幕语音的话）。
    这个过程中，会输出当前语音包状态的详细信息：已安装的语音包、移除的语音包和新增语音包。
    并且字幕语音包、普通语音包和游戏自带的语音包会进行分色显示。
"""
import os
import zipfile
import json
import traceback
import ResMgr
import SoundGroups
from constants import INFO_JSON, WHERE_AM_I, WHERE_ARE_PARENT, DEFAULT_MODES_JSON, INFO_TEMPLATE, CURRENT_VOLUME
from fileSearch import g_search
from myLogger import mylogger


class UpdateManager(object):
    def __init__(self):
        # code：0 无需更新；1 需要更新。安装的字幕语音包数量发生变化时，需要重写settings.json，并将生成的新文件替换旧文件，除此之外无需更新。
        self.code = 1
        # fileSearch模块为新安装的声音模式的language属性打上了前缀名“ORV_”（others voiceover)
        # 读取日志文件中保存的语音包安装历史信息，并将声音模式分为外部和内部，分别保存在_outside_voice_data、_inside_voice_data中
        # 如果这是插件第一次运行，那么对应文件尚不存在，settings.json也是空文件，此时_outside_voice_data和_sbtData应当是空列表
        self._outside_voice_data = []
        self._inside_voice_data = []
        self._sbt_voice_data = []
        self.updateInfo = ''
        self.namelist = {}
        self.del_vo_vo = []
        self.del_vo_gvo = []
        self.__origin_modes_list = {}
        self.__replaced_modes_list = {}
        self._myVolume = {}
        # 存储语音ID + 音量
        self._default_modes_volume = {}
        self._info_json_data = []
        # 保存非default_modes.json内语音音量偏好设置（你的语音包的音量）

    def read_from_saved_data(self):
        sbt_info_path = 'res/mods/gup.subtitles/settings.json'
        with zipfile.ZipFile(WHERE_AM_I, 'r') as zip_ref:
            if sbt_info_path in zip_ref.namelist():
                with zip_ref.open(sbt_info_path, 'r') as zip_json:
                    json_without_comments = ''
                    for line in zip_json:
                        json_without_comments += line.split('//')[0]
                    if json_without_comments:
                        try:
                            json_data = json.loads(json_without_comments, encoding='utf-8')
                            sbt_list = json_data['subtitles']
                            # 对于字幕语音，因为要写入需要用到字幕的语音包，所以可能出现非画外音语音包（如inbattle_communication.bnk)
                            # 它们会在fileSearch中被打上后缀名“_OTR”并被忽略
                            # 存入“name”值，这里只是碰巧name和language同值
                            if sbt_list:
                                for meta in sbt_list:
                                    self._sbt_voice_data.append(meta['language']) if not meta['language'].endswith(
                                        '_OTR') else None
                        except ValueError:
                            pass
                        except Exception:
                            stack_trace = traceback.format_exc()
                            mylogger.warn('updateFile', '读取自身json文件出现异常！')
                            mylogger.warn('updateFile', '堆栈信息：%s' % stack_trace)
            else:
                mylogger.warn('updateFile', '未能在mod中的指定位置找到settings.json！')
        json_without_comments = ''
        with open(INFO_JSON, 'r') as jf:
            for line in jf:
                json_without_comments += line.split('//')[0]
            if json_without_comments:
                try:
                    json_data = json.loads(json_without_comments, encoding='utf-8')
                    for mode in json_data:
                        name = mode['voiceID']
                        nickName = mode['nickName']
                        self._outside_voice_data.append(name) if name.startswith('ORV_') else self._inside_voice_data.append(name)
                        self.namelist.update({name: nickName})
                except ValueError:
                    stack_trace = traceback.format_exc()
                    mylogger.error('updateFile', 'info.json不是一个json对象！请检查json语法！')
                    mylogger.warn('updateFile', '堆栈信息：%s' % stack_trace)
                except Exception:
                    stack_trace = traceback.format_exc()
                    mylogger.warn('updateFile', '读取info.json文件时出现异常！')
                    mylogger.warn('updateFile', '堆栈信息：%s' % stack_trace)

    def compare(self):
        # 求得列表：已安装的[语音包/字幕语音包]、新增的[语音包/字幕语音包/游戏内语音包]、已移除的[语音包/字幕语音包/游戏内语音包]，并记录信息
        # namelist保存每个声音模式对应的名字，名字作为输出信息，代表这个声音模式
        new_namelist = {}
        new_vo_list = []
        new_sbt_list = []
        new_gvo_list = []
        vm = g_search.getVModes()
        sm = g_search.getSModes()
        gvm = g_search.getGameVMode()
        if vm:
            for vo in vm:
                name = vo.name
                description = vo.nickName
                new_vo_list.append(name)
                new_namelist.update({name: description})
        if sm:
            for sbt in sm:
                if sbt.isVoiceover:
                    name = sbt.language
                    description = sbt.nickName
                    new_sbt_list.append(name)
                    new_namelist.update({name: description})
        if gvm:
            for gvo in gvm:
                name = gvo.name
                description = gvo.nickName
                new_gvo_list.append(name)
                new_namelist.update({name: description})

        # old指插件info.json中保存的声音模式名列表，new指mods文件夹中新增的声音模式名列表（如果有的话）
        set_old_vo = set(self._outside_voice_data)
        set_new_vo = set(new_vo_list)
        set_old_sbt = set(self._sbt_voice_data)
        set_new_sbt = set(new_sbt_list)
        # 这里带“ORV”前缀的只有第三方普通语音包，不带前缀的_inside_voice_data保存了游戏内语音和第三方字幕语音包
        set_old_gvo = set(self._inside_voice_data) - set_old_sbt
        set_new_gvo = set(new_gvo_list)
        # 将新增语音中的普通画外音和带字幕的画外音分离，以便后续分色显示
        old_vo_only = set_old_vo
        new_vo_only = list(set_new_vo - set_new_sbt)
        current_vo_vo = old_vo_only
        current_vo_sbt = self._sbt_voice_data
        add_vo_vo = list(set(new_vo_only) - set(old_vo_only))
        add_vo_sbt = list(set_new_sbt - set_old_sbt)
        add_vo_gvo = list(set_new_gvo - set_old_gvo)
        self.del_vo_vo += list(set(old_vo_only) - set(new_vo_only))
        del_vo_sbt = list(set_old_sbt - set_new_sbt)
        self.del_vo_gvo += list(set_old_gvo - set_new_gvo)
        # code:  0 无需更新; 1 需要更新
        if not add_vo_sbt and not del_vo_sbt:
            self.code = 0
        self.updateInfo += '<br>已安装的语音包：'
        self._printMsg('#fffff0', current_vo_vo, self.namelist)
        self._printMsg('#fff0f5', current_vo_sbt, self.namelist)
        self.updateInfo += '<br>啊嘞？你没有装语音包吗？' if not current_vo_vo and not current_vo_sbt else ''
        self.updateInfo += '<br><br>新增语音：'
        self._printMsg('#e0ffff', add_vo_vo, new_namelist)
        self._printMsg('#ffe4e1', add_vo_sbt, new_namelist)
        self._printMsg('#f5ffff', add_vo_gvo, new_namelist)
        self.updateInfo += '<br>没有检测到新的语音包。' if not add_vo_vo and not add_vo_sbt and not add_vo_gvo else ''
        self.updateInfo += '<br><br>已移除的语音：' if not self.del_vo_vo and not del_vo_sbt and not self.del_vo_gvo else \
            '<br><br>以下语音/字幕未能加载：<br>原因：该语音没有找到/字幕信息未写入'
        self._printMsg('#d3d3d3', self.del_vo_vo, self.namelist)
        self._printMsg('#c0c0c0', del_vo_sbt, self.namelist)
        self._printMsg('#dcdcdc', self.del_vo_gvo, self.namelist)
        self.updateInfo += '<br>没有一个语音包受到迫害。' if not self.del_vo_vo and not del_vo_sbt and not self.del_vo_gvo else ''
        self.updateInfo += '<br><br><font color="#b22222">- 文件需要更新 -</font>' if self.code else '<br><br>- 无需更新 -'

    def _printMsg(self, color, vo_list, namelist):
        if vo_list:
            self.updateInfo += '<font color="' + color + '">'
            for vo in vo_list:
                if vo in namelist:
                    self.updateInfo += '<br>' + namelist[vo]
                else:
                    self.updateInfo += '<br>' + vo + '[字幕未移除]'
            self.updateInfo += '</font>'

    def getCode(self):
        return self.code

    def updateSoundMode(self):
        # 通过访问SoundGroups中受保护的声音模式列表，将列表内容覆盖。系别语音信息在另一个列表中，将被再次添加回去
        # 在更新信息前，读取并保存音量偏好
        modes_list = [{"name": "default", "lang": "", "nickName": "标准", "invisible": False, "bank": "voiceover.bnk"}]
        new_info_list = []
        json_without_comments = ''
        if not os.path.exists(DEFAULT_MODES_JSON):
            mylogger.warn('updateFile', 'default_modes.json已丢失！系别语音添加失败！系别语音已丢失！')
        with open(DEFAULT_MODES_JSON, 'r') as df:
            for line in df:
                json_without_comments += line.split('//')[0]
        if json_without_comments:
            try:
                json_data = json.loads(json_without_comments)
                update_file = False
                for mode in json_data:
                    volume = CURRENT_VOLUME
                    modes_list.append(
                        {"name": mode['name'], "lang": mode['wwise_language'], "nickName": mode['description'],
                         "invisible": True, "bank": mode['wwise_language'] + r'/voiceover.bnk'})
                    if 'volume' in mode:
                        volume = self.setVolume(mode['volume'], CURRENT_VOLUME)
                        self._default_modes_volume.update({mode['name'] + '_volume': volume})
                    else:
                        update_file = True
                    self._myVolume.update({mode['wwise_language']: volume})
                if update_file:
                    self._default_modes_volume = {'ZH_CH_volume': CURRENT_VOLUME,
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
                    template = INFO_TEMPLATE.format(**self._default_modes_volume)
                    with open(DEFAULT_MODES_JSON, 'w') as f:
                        f.write(template)
            except ValueError:
                stack_trace = traceback.format_exc()
                mylogger.error('updateFile', 'default_modes.json不是一个json对象！请检查json语法！')
                mylogger.warn('updateFile', '堆栈信息：%s' % stack_trace)
            except Exception:
                stack_trace = traceback.format_exc()
                mylogger.warn('updateFile', '读取default_modes.json文件时出现异常！')
                mylogger.warn('updateFile', '堆栈信息：%s' % stack_trace)
        else:
            mylogger.warn('updateFile', 'default_modes.json为空文件！系别语音添加失败！系别语音已丢失！')
        # 检查语音包路径是否正确，准备将其添加进游戏
        for mode in g_search.getVModes():
            bank_path = 'audioww/' + mode.bankPath
            if ResMgr.isFile(bank_path):
                modes_list.append({"name": mode.name, "lang": mode.language, "nickName": mode.nickName,
                                   "invisible": mode.invisible, "bank": mode.bankPath})
                new_info_list.append({"voiceID": mode.name, "nickName": mode.nickName})
            else:
                mylogger.error('updateFile', '语音包“%s”的bnk文件位置不正确！已将其移除！' % mode.nickName)
                g_search.remove_from_VMode(mode)
        for mode in g_search.getGameVMode():
            bank_path = 'audioww/' + mode.bankPath
            if ResMgr.isFile(bank_path):
                modes_list.append({"name": mode.name, "lang": mode.language, "nickName": mode.nickName,
                                   "invisible": mode.invisible, "bank": mode.bankPath})
                new_info_list.append({"voiceID": mode.name, "nickName": mode.nickName})
            else:
                mylogger.error('updateFile', '语音包“%s”的bnk文件位置不正确！已将其移除！' % mode.nickName)
                g_search.remove_from_GameVMode(mode)

        # 读取音量偏好
        with open(INFO_JSON, 'r') as f:
            json_without_comments = ''
            for line in f:
                json_without_comments += line.split('//')[0]
            # 第一次使用插件理应读取为空
            if not json_without_comments:
                for mode in new_info_list:
                    mode.update({'volume': CURRENT_VOLUME})
                    self._myVolume.update({mode['voiceID']: CURRENT_VOLUME})
            try:
                saved_data = json.loads(json_without_comments, encoding='utf-8')
                for mode in new_info_list:
                    vo = mode['voiceID']
                    volume = CURRENT_VOLUME
                    for item in saved_data:
                        if item.get('voiceID') == vo:
                            if 'volume' in item:
                                volume = self.setVolume(item['volume'], CURRENT_VOLUME)
                        continue
                    mode.update({'volume': volume})
                    self._myVolume.update({mode['voiceID']: volume})
            except ValueError as e:
                mylogger.error('updateFile', 'info.json不是一个json对象！请检查json语法！')
                mylogger.warn('updateFile', e)
            except Exception as e:
                mylogger.warn('updateFile', e)
        json_data = json.dumps(new_info_list, ensure_ascii=False, indent=4)
        self._info_json_data = new_info_list
        with open(INFO_JSON, 'w') as f:
            f.write(json_data)
        # 创建DataSection对象并使用SoundGroups的方法创建字典，并随时替换原字典
        for member in modes_list:
            new_sec = ResMgr.DataSection('mode')
            new_sec.write('name', member['name'])
            new_sec.write('wwise_language', member['lang'])
            new_sec.write('description', member['nickName'])
            new_sec.write('invisible', member['invisible'])
            new_sec.write('wwbanks/bank', member['bank'])
            newmode = SoundGroups.SoundModes.SoundModeDesc(new_sec)
            self.__replaced_modes_list.update({member['name']: newmode})

        self.__origin_modes_list = SoundGroups.g_instance.soundModes._SoundModes__modes

    def overrivedModes(self):
        SoundGroups.g_instance.soundModes._SoundModes__modes = self.__replaced_modes_list

    def recoverModes(self):
        SoundGroups.g_instance.soundModes._SoundModes__modes = self.__origin_modes_list

    def setVolume(self, volume, stander):
        volume = int(volume)
        if volume > 100 or volume < 0:
            return stander
        return volume

    def updateFile(self):
        # 在python2的标准库中，zipfile模块没有类似“remove”的方法。如今解决方案已经存在，由于缺少作者的贡献者协议并没有被python批准，且该模块属于python3
        # https://github.com/python/cpython/blob/659eb048cc9cac73c46349eb29845bc5cd630f09/Lib/zipfile.py
        # 所以这里将用于更新的文件和其他的文件一并放入临时压缩文件temp.zip中，压缩级别为“无压缩”，之后，等待fini方法执行，删除原文件并重命名临时文件
        mylogger.info('updateFile', '开始更新json文件。')
        sbt_list = g_search.getSModes()
        json_dict = {}
        subtitles = []
        json_data = ''
        if sbt_list:
            for sbt in sbt_list:
                sbt_data = {"name": sbt.language, "language": sbt.language, "wwbank": sbt.bankPath,
                            "characters": sbt.characters, "sentences": sbt.sentences, "visuals": sbt.visuals}
                subtitles.append(sbt_data)
            json_dict.update({"subtitles": subtitles})
            json_data = json.dumps(json_dict, indent=4)

        file_to_remove = 'res/mods/gup.subtitles/settings.json'
        with zipfile.ZipFile(WHERE_AM_I, 'r') as old_zip_ref:
            namelist = old_zip_ref.namelist()
            # 以追加文件的模式（“a”）打开，写入同名文件后，两个文件将会共存
            # 以写入模式（“w”）打开，原归档文件中所有内容会被清空，且由于文件被游戏后台程序打开，该操作同样无法完成
            # 这里选择以写入模式创建临时文件，放入mods文件夹中
            with zipfile.ZipFile(os.path.join(WHERE_ARE_PARENT, 'temp.zip'), 'w', zipfile.ZIP_STORED) as new_zip_ref:
                for item in namelist:
                    if item != file_to_remove:
                        new_zip_ref.writestr(item, old_zip_ref.read(item))
                new_zip_ref.writestr('res/mods/gup.subtitles/settings.json', json_data)
        mylogger.info('updateFile', '在%s创建临时文件temp.zip。' % WHERE_ARE_PARENT)

    def getInfo(self):
        return self.updateInfo

    def getMyVolume(self):
        return self._myVolume

    def getDefaultModesVolume(self):
        return self._default_modes_volume

    def getInfoJsonData(self):
        return self._info_json_data


g_update = UpdateManager()
