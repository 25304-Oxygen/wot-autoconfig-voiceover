# coding=utf-8
"""
    此模块负责mod初始化。
    绝大部分代码是文件处理相关的，只有少数地方用到了客户端API接口，可以说是相当简单（刨除学习成本的话）且实用的脚本。
"""
# No i18n for now :(    maybe in the future :)  or not
# Characters "语音包" means "voiceover soundbank(s)" or Voice pack(s)
from autoconfigvoiceover import *
from gui import SystemMessages
from gui.SystemMessages import SM_TYPE
mylogger = MyLogger('autoConfigVoiceOver')
text = '插件初始化失败'
text_type = SM_TYPE.WarningHeader
header = '<font color="#cc9933"><b>语音包管理插件</b></font>'
msg_sent = False


# 等待客户端统一调用的方法，除此之外还有 fini 和部分事件的同名函数：
# onConnected、onAccountBecomePlayer、onAccountShowGUI、onAccountBecomeNonPlayer、onDisconnected
def init():
    global text, text_type
    if not isApiPresent:
        text = '缺少依赖mod，请检查mods文件夹中是否安装：ModsSettingsApi、ModsListApi与openwg_gameface！'
        mylogger.error('程序初始化终止。插件运行状态：' + text)
        return
    if not where_am_i:
        text = '插件无法获取自身存储的信息，请检查插件中meta.xml是否丢失！'
        mylogger.error('没有找到autoConfigVoiceOver，请检查插件中meta.xml是否丢失或插件是否被修改！')
    mylogger.info('正在获取语音包信息……')
    g_search.run()
    mylogger.info('正在加载信息……')
    g_update.run()
    mylogger.debug('语音包信息：' + g_search.message)
    mylogger.info('正在绘制UI……')
    g_template.run()
    text = '你现在可以管理和启用特定语音包了！<br>打开下方插件管理器进入管理界面<br>插件当前版本：' + myModsVersion
    text_type = SM_TYPE.MessageHeader
    mylogger.info('初始化已完成。插件运行状态：' + text)
    try:
        from gui.mods import mod_gup_subtitles as gup_mod
        gup_mod.SETTINGS_FILE = SETTINGS_JSON_COPY
        gup_mod.init()
        mylogger.debug('字幕信息更新完毕。')
    except ImportError:
        mylogger.warn('无法导入字幕插件！字幕不可用！')


# 在你成功进入游戏后被调用
def onAccountBecomePlayer():
    global msg_sent
    if not msg_sent:
        msg_sent = True
        SystemMessages.pushMessage(text=text, type=text_type, messageData={'header': header})
        if not isApiPresent:
            return
        g_update.save_files()
        mylogger.info('语音包信息已保存。')


def fini():
    mylogger.info('程序正常退出。')
