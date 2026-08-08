# coding=utf-8
"""voices —— 语音包数据子系统。

初始化阶段读取三路信息并合并为内存数据库：
  - pack_scanner:  扫描 VFS mods/voiceover/ 下的第三方语音包
  - game_reader:   读取游戏内语音包（系别 + 车长特殊语音）与本地化译名
  - storage:       与 jsons/ 已保存数据合并（继承用户改名与音量），进账号后落盘
之后：
  - sound_manager: 把通过加载校验的包注册进游戏声音模式表（fini 时还原）
  - active_voice:  当前活跃语音的会话对象与切换广播

对外只暴露两个单例（不使用 __all__ 星号导入）：
    from . import g_voice_repo, g_active_mgr
"""

from .repository import g_voice_repo  # noqa: F401
from .active_voice import g_active_mgr  # noqa: F401
