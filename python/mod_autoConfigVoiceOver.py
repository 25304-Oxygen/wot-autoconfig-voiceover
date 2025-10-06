# coding=utf-8
"""
    此模块负责mod初始化。
    会先进行文件遍历，冲突检测，然后将语音包信息添加到游戏中，最后通过modsSettingsApi绘制UI，其余功能通过UI实现。
    绝大部分代码是文件处理和逻辑判断相关的，只有少数地方用到了客户端API接口，可以说是相当简单（刨除学习成本的话）且实用的脚本。
    由于字幕配置文件settings.json位于mod内，对其更新时需要结束游戏进程。暂时需要你手动重启。
"""
# tips: no i18n, without English comments.
# characters "语音包" means "voiceover soundbank(s)"
from autoconfigvoiceover import *
from gui import SystemMessages
from Account import PlayerAccount
import subprocess
import traceback
import os.path
import zipfile
acv_text = ''
acv_text_type = ''
acv_header = ''
_isApiPresent = False
acv_sent_msg = True


# 检测api是否存在，并在日志中输出可能产生的警示信息。声明了此处修改的是当前模块全局变量：_isApiPresent
def _api_support():
    global _isApiPresent
    try:
        from gui.modsSettingsApi import g_modsSettingsApi
        _isApiPresent = g_modsSettingsApi is not None
        if not _isApiPresent:
            mylogger.warn('autoConfigVoiceOver', 'modsSettingsApi似乎出了问题：实例对象返回了None。请检查依赖文件是否缺失。')
    except ImportError:
        stack_trace = traceback.format_exc()
        mylogger.error('autoConfigVoiceOver', '无法导入modsSettingsApi！请安装modssettingsapi和modslistapi！')
        mylogger.warn('autoConfigVoiceOver', '堆栈信息：%s' % stack_trace)
        return
    try:
        import openwg_gameface
        _isApiPresent = True
    except ImportError:
        stack_trace = traceback.format_exc()
        mylogger.error('autoConfigVoiceOver', '缺少依赖mod：net.openwg.gameface！模组无法工作！')
        mylogger.warn('autoConfigVoiceOver', '堆栈信息：%s' % stack_trace)
        return


# 准备问候消息，用到了全局声明以修改函数外的参数，问候消息的内容是有关产生冲突的文件、打包不合规的语音包（如果有的话）的信息
def prepare_hello_message():
    _api_support()
    global acv_text, acv_text_type, acv_header, _isApiPresent
    # state代码：0 存在语音丢失风险；1 一切正常。根据state选择要通知的信息，当api缺失时，也会生成专门的问候信息。
    g_search.conflict_check()
    state = g_search.getCode()
    heads = ['：语音包可能丢失语音', '', '']
    types = [SystemMessages.SM_TYPE.InformationHeader,
             SystemMessages.SM_TYPE.MessageHeader,
             SystemMessages.SM_TYPE.WarningHeader]
    greets = ['', '你现在可以管理和启用特定语音包了！<br>打开下方插件管理器进入管理界面',
              '缺少依赖mod，请检查mods文件夹中是否安装：ModsSettingsApi、ModsListApi与openwg_gameface！']
    text_body = g_search.getReport()
    greet = greets[state] if _isApiPresent else greets[2]
    # 消息类型为：xxxHeader时，才会显示你设置的标题
    acv_header = '<font color="#cc9933"><b>语音包管理插件%s</b></font>' % heads[state]
    acv_text = text_body + greet + '<br>插件当前版本：' + MY_MODS_VERSION
    acv_text_type = types[state] if _isApiPresent else types[2]


# 等待客户端统一调用的方法，除此之外还有 fini 和 event
def init():
    global _isApiPresent
    mylogger.info('autoConfigVoiceOver', '获取问候信息：%s' % acv_text)
    if not _isApiPresent:
        mylogger.info('autoConfigVoiceOver', '程序初始化终止。')
        return
    if not WHERE_AM_I:
        mylogger.error('autoConfigVoiceOver', '没有找到autoConfigVoiceOver，无法找到要读取的信息！请检查插件名称是否被修改！')
    mylogger.info('autoConfigVoiceOver', '获取已安装的语音包信息……')
    g_search.read_from_mod_files()
    mylogger.info('autoConfigVoiceOver', '读取gameSoundModes.json中的信息……')
    g_search.read_from_config_folder()
    mylogger.info('autoConfigVoiceOver', '获取语音包历史信息……')
    g_update.read_from_saved_data()
    g_update.compare()
    mylogger.info('autoConfigVoiceOver', '获取语音包信息：%s' % g_update.getInfo())
    mylogger.info('autoConfigVoiceOver', '初始化……')
    g_update.updateSoundMode()
    g_template.init_vo_list()
    g_template.read_config_data()
    g_template.init_after_read()
    g_template.registerApiSupport()
    mylogger.info('autoConfigVoiceOver', '初始化已完成。')


def fini():
    mylogger.info('autoConfigVoiceOver', '程序运行终止。开始检查文件是否需要更新。')
    # 更新文件信息，删除旧文件并重命名新文件
    # 由于游戏运行过程中，mod文件被打开，因此删除和替换工作需要在游戏进程将要结束后执行
    # 非强制性修改文件，只有当你在游戏中点击提示窗口的更新按钮之后，才会创建临时归档文件temp.zip
    # 无需更新的情况下，也可以通过快速单击图片3次打开更新窗口。
    # 之后会将settings.json移至res_mods，届时更新信息后游戏将能自动启动
    code = g_template.getCode()
    if code == 2:
        bat_path = os.path.join(WHERE_ARE_PARENT, REMOVE_PROCESS)
        temp_file = os.path.join(WHERE_ARE_PARENT, 'temp.zip')
        if not os.path.exists(bat_path):
            with zipfile.ZipFile(WHERE_AM_I, 'r') as zip_ref:
                try:
                    zip_ref.extract('remove_old_archive.bat', WHERE_ARE_PARENT)
                    mylogger.info('autoConfigVoiceOver', '已在mod所在文件夹中创建remove_old_archive.bat，等待游戏进程结束。')
                except IOError:
                    stack_trace = traceback.format_exc()
                    mylogger.error('autoConfigVoiceOver', '在mod中找不到可执行文件remove_old_archive.bat！')
                    mylogger.warn('autoConfigVoiceOver', '堆栈信息：%s' % stack_trace)
                    os.chdir(MODS_PATH)
                    return
        if not os.path.exists(temp_file):
            mylogger.error('autoConfigVoiceOver', '没有找到temp.zip，无法更新字幕信息！程序已退出。')
            return
        os.chdir(WHERE_ARE_PARENT)
        try:
            # 不知道为什么有些人遇到了WindowsError: [Error 2]，这里添加上一个shell=True
            # subprocess.Popen([REMOVE_PROCESS])
            mylogger.info('autoConfigVoiceOver', '调用%s' % REMOVE_PROCESS)
            subprocess.Popen(REMOVE_PROCESS, shell=True)
            mylogger.info('autoConfigVoiceOver', '字幕信息已更新并保存，程序正常退出。')
        except Exception:
            stack_trace = traceback.format_exc()
            mylogger.error('autoConfigVoiceOver', '调用失败！请手动执行批处理文件！位置：%s' % bat_path)
            mylogger.warn('autoConfigVoiceOver', '堆栈信息：%s' % stack_trace)
        os.chdir(MODS_PATH)
    elif code:
        mylogger.warn('autoConfigVoiceOver', '程序已退出，未进行必要的更新操作！')
    else:
        mylogger.info('autoConfigVoiceOver', '程序正常退出。')


prepare_hello_message()
mylogger.info('autoConfigVoiceOver', '问候消息已创建，等待发送至通知中心。')


@override(PlayerAccount, 'onBecomePlayer')
def new_onBecomePlayer(original_func, self):
    original_func(self)
    global acv_sent_msg, acv_text, acv_text_type, acv_header
    if acv_sent_msg:
        SystemMessages.pushMessage(text=acv_text, type=acv_text_type, messageData={'header': acv_header})
        acv_sent_msg = False
