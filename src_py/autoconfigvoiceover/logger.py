# coding=utf-8
"""ACV mod 日志模块。

将 mod 自身日志写入独立文件（constants.SCRIPT_LOG），与 WoT 主日志分离。
"""

import datetime

from ._metadata import MOD_VERSION
from .constants import SCRIPT_LOG


# ═════════════════════════════════════════════════════════════
# 日志级别过滤:  0=ERROR, 1=WARN, 2=INFO, 3=DEBUG
# （与 settings_page._get_log_level_options() 索引一致）
# ═════════════════════════════════════════════════════════════

_min_log_level = 2


def set_log_level(index):
    """设置全局最低日志级别。

    :param index: 0=仅ERROR, 1=WARNING及以上, 2=INFO及以上, 3=DEBUG及以上
    """
    global _min_log_level
    _min_log_level = int(index)


# ═════════════════════════════════════════════════════════════
# 内部工具
# ═════════════════════════════════════════════════════════════

def _timestamp():
    """当前时间戳，精确到毫秒。"""
    return str(datetime.datetime.now())[:23]


# ═════════════════════════════════════════════════════════════
# 日志文件初始化
# ═════════════════════════════════════════════════════════════

def init_log():
    """创建日志文件，写入文件头。"""
    import os

    log_dir = os.path.dirname(SCRIPT_LOG)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    with open(SCRIPT_LOG, 'w') as f:
        f.write(
            '[autoConfigVoiceOver] 的日志文件，运行过程中可能产生的错误信息将会在这里输出。插件当前版本：{ver}\n'
            '> 旧的语音包 wotmod 打包格式仅保留语音包注册，不再支持字幕和重映射等功能，请及时使用新格式打包。\n'
            '> 客户端更新后，请前往“偶游坦克世界盒子”重新下载插件，或者手动将 Mod 转移。\n'
            .format(ver=MOD_VERSION)
        )


# ═════════════════════════════════════════════════════════════
# Logger
# ═════════════════════════════════════════════════════════════

class Logger(object):
    """将日志写入独立文件的简单 Logger。

    用法::

        from autoconfigvoiceover.logger import Logger
        log = Logger('模块名')
        log.info('初始化完成')
    """

    def __init__(self, name=None):
        self._name = name or 'acv'

    # — 内部方法 —

    @staticmethod
    def _fmt(msg, args):
        """安全的 % 格式化——处理字节串/unicode 混用。

        Python 2 陷阱: 含中文的字节串格式 % unicode 参数会触发
        对格式串的隐式 ASCII 解码，抛 UnicodeDecodeError（Flash
        经 DAAPI 传来的字符串是 unicode）。此处统一转 unicode 再格式化。

        注意：args 中的字节串可能不是 utf-8（如 Windows CN 文件系统
        返回 GBK 编码的中文路径），decode 使用 replace 容错模式。
        """
        if not args:
            return msg
        try:
            return msg % args
        except UnicodeDecodeError:
            if isinstance(msg, str):
                msg = msg.decode('utf-8', 'replace')
            args = tuple(
                a.decode('utf-8', 'replace') if isinstance(a, str) else a
                for a in args
            )
            return msg % args

    def _write(self, level, msg):
        # 日志级别过滤
        _levels = {'ERROR': 0, 'EXCEPTION': 0, 'WARN': 1, 'INFO': 2, 'DEBUG': 3}
        if _levels.get(level, 0) > _min_log_level:
            return

        try:
            line = u'[{time}] [{level}] [Python:{name}]: {msg}'.format(
                time=_timestamp(), level=level, name=self._name,
                msg=msg.decode('utf-8') if isinstance(msg, str) else msg
            )
        except UnicodeError:
            # msg 可能含 GBK 等非 UTF-8 字节（如 VFS 中文路径经 %s
            # 格式化混入），utf-8 严格解码会抛异常。用 replace 容错，
            # 替换字符比整条日志消失强。
            line = u'[{time}] [{level}] [Python:{name}]: {msg}'.format(
                time=_timestamp(), level=level, name=self._name,
                msg=msg.decode('utf-8', 'replace') if isinstance(msg, str) else msg
            )
        try:
            with open(SCRIPT_LOG, 'a') as f:
                f.write(line.encode('utf-8') + '\n')
        except (IOError, UnicodeError):
            pass  # 日志写入失败不应影响游戏运行

    # — 公开方法 —

    def debug(self, msg, *args):
        """调试信息，仅在 show_details 开启时值得关注。"""
        self._write('DEBUG', self._fmt(msg, args))

    def info(self, msg, *args):
        """常规运行时信息。"""
        self._write('INFO', self._fmt(msg, args))

    def warn(self, msg, *args):
        """警告——不影响功能但值得注意。"""
        self._write('WARN', self._fmt(msg, args))

    def error(self, msg, *args):
        """错误——某个功能无法正常工作。"""
        self._write('ERROR', self._fmt(msg, args))

    def exception(self, msg='', *args):
        """记录异常并附带完整调用栈。"""
        import traceback
        msg = self._fmt(msg, args)
        stack = traceback.format_exc()
        self._write('EXCEPTION', u'{0}\n调用栈: {1}'.format(
            msg.decode('utf-8') if isinstance(msg, str) else msg,
            stack.decode('utf-8', 'replace') if isinstance(stack, str) else stack
        ))

    def raw(self, msg):
        """写入原始消息——添加时间戳但保留 Flash 端的 [ACV][等级] 格式。

        Flash Log 格式: [LEVEL] [Flash:name]: message
        解析 LEVEL 并应用 _min_log_level 过滤，确保日志等级设置对
        Flash 端日志同样生效。
        """
        msg_str = msg.decode('utf-8') if isinstance(msg, str) else msg

        # 解析 Flash 日志等级 [DEBUG] / [INFO] / [WARN] / [ERROR]
        _levels = {'ERROR': 0, 'EXCEPTION': 0, 'WARN': 1, 'INFO': 2, 'DEBUG': 3}
        if msg_str.startswith('['):
            end = msg_str.find(']')
            if end > 1:
                lvl_name = msg_str[1:end]
                if lvl_name in _levels and _levels[lvl_name] > _min_log_level:
                    return  # 低于当前最低等级，丢弃
        elif _min_log_level < _levels['DEBUG']:
            return  # 日志等级低于 DEBUG 时不打印信号量

        line = u'[{time}] {msg}'.format(
            time=_timestamp(),
            msg=msg_str
        )
        try:
            with open(SCRIPT_LOG, 'a') as f:
                f.write(line.encode('utf-8') + '\n')
        except (IOError, UnicodeError):
            pass
