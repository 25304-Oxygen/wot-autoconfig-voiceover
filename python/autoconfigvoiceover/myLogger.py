# coding=utf-8
"""
    “日志模块”，简单的文件读写，使运行中输出的信息独立于wot自己的日志文件。
"""
import os.path
import datetime
from constants import SCRIPT_LOG, MY_MODS_VERSION


def get_time():
    return str(datetime.datetime.now())[:23]


def init_log():
    with open(SCRIPT_LOG, 'w') as f:
        f.write('[autoConfigVoiceOver] 的日志文件，运行过程中可能产生的错误信息将会在这里输出。插件当前版本：%s'
                '\n> 如果日志没有更新记录，且进入游戏时收到冲突弹窗，说明插件因文件冲突而被客户端卸载，请移除冲突文件。'
                '\n> 客户端更新后，请前往“偶游坦克世界盒子”重新下载插件，或者手动将mod转移。\n' % MY_MODS_VERSION)


class MyLogger(object):
    def __init__(self, name=None):
        if name is not None:
            self.__name = name
        else:
            self.__name = __name__

    def __log(self, mys_type, msg):
        log_text = '[{0}][{1}][from: {2}]: {3}'.format(get_time(), mys_type, self.__name, msg)
        with open(SCRIPT_LOG, 'a') as f:
            f.write(log_text + '\n')

    def debug(self, msg):
        self.__log('DEBUG', msg)

    def info(self, msg):
        self.__log('通知信息', msg)

    def error(self, msg):
        self.__log('错误', msg)

    def warn(self, msg):
        self.__log('警告', msg)

    def exception(self, msg=''):
        import traceback
        stack_trace = traceback.format_exc()
        self.__log('发生异常', '{0}\n{1}: {2}'.format(msg, '异常信息', stack_trace))
