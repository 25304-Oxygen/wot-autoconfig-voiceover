# coding=utf-8
"""
    “日志模块”，简单的文件读写，使运行中输出的信息独立于wot自己的日志文件。
"""
import os
import datetime
from constants import MODS_ROOT_PATH, CONFIGS_ROOT_PATH, GAME_ROOT_PATH, MY_LOG_PATH, MY_MODS_VERSION


def get_time():
    return str(datetime.datetime.now())[:23]


class MyLogger(object):
    def __init__(self):
        self.logfile = os.path.join(MY_LOG_PATH, 'script.log')
        if not os.path.exists(MY_LOG_PATH):
            os.chdir(MODS_ROOT_PATH)
            if not os.path.exists('configs'):
                os.makedirs('configs')
            os.chdir(CONFIGS_ROOT_PATH)
            os.makedirs('autoConfigVoiceOver')
            os.chdir(GAME_ROOT_PATH)
            open(self.logfile, 'w').close()
            self._init_log()
            self.info('myLogger', '已创建日志文件。')
        else:
            self._init_log()

    def _init_log(self):
        with open(self.logfile, 'w') as f:
            f.write('[autoConfigVoiceOver] 的日志文件，运行过程中可能产生的错误信息将会在这里输出。插件当前版本：%s'
                    '\n> 如果日志没有更新记录，且进入游戏时收到冲突弹窗，说明插件因文件冲突而被客户端卸载，请移除冲突文件。'
                    '\n> 客户端更新后，请前往“偶游坦克世界盒子”重新下载插件，或者手动将mod转移。\n' % MY_MODS_VERSION)

    def info(self, name, msg):
        with open(self.logfile, 'a') as f:
            f.write('[%s][通知信息][from: %s]: %s\n' % (get_time(), name, msg))

    def error(self, name, msg):
        with open(self.logfile, 'a') as f:
            f.write('[%s][错误][from: %s]: %s\n' % (get_time(), name, msg))

    def warn(self, name, msg):
        with open(self.logfile, 'a') as f:
            f.write('[%s][警告][from: %s]: %s\n' % (get_time(), name, msg))


mylogger = MyLogger()
