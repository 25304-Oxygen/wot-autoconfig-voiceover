# coding=utf-8
"""ActiveVoice —— 表示"当前活跃语音包"的会话对象。

会话模式：切换语音时**重建**实例而非原地更新；构建/校验失败时
保持旧实例（不回退默认语音）。内置语音也构建（pack=None 空对象
模式），消费方永远面对同一接口。

构建期解析全部轻量 json（events/remap/msg/attach）；subtitles/ 子树
由字幕模块经 model 常量自行探测。

内置语音在读取期不可校验（special_voices.xml 是全服务器并集、
main_sound_modes.xml 可能被用户替换），因此构建时现场查
SoundGroups.g_instance.soundModes.modes 是否存在该模式名。
"""

import Event

from autoconfigvoiceover.logger import Logger
from autoconfigvoiceover.utils import load_vfs_json, to_utf8
from . import model

logger = Logger('ActiveVoice')


class ActiveVoice(object):
    """当前活跃语音包的全部业务信息（不可变会话对象，切换时重建）。"""

    def __init__(self, voice_id, pack, events, remap, attach_data,
                 info_html=None, theme=None):
        self.voice_id = voice_id      # str  语音 ID（模式名/包目录名）
        self.pack = pack              # PackInfo | None（None = 内置语音）
        self.events = events          # [{'text','event'}] 合并后的试听事件
        self.remap = remap            # {event: new_event} 声音重映射表
        self.attach_data = attach_data  # dict | None 绑定方案（attach.json 已解析）
        self.info_html = info_html    # str | None 语音包信息面板 HTML
        self.theme = theme            # dict | None 语音包内嵌主题色板

    @property
    def is_builtin(self):
        """是否为游戏内置语音（空对象模式：pack 为 None）。"""
        return self.pack is None


# ═════════════════════════════════════════════════════════════
# 构建
# ═════════════════════════════════════════════════════════════

def build(voice_id):
    """构建 ActiveVoice 实例；校验失败返回 None（调用方保持旧实例）。"""
    from .repository import g_voice_repo

    pack = g_voice_repo.get_pack(voice_id)
    if pack is None and not _builtin_exists(voice_id):
        logger.warn('声音模式 %s 在当前客户端不存在，构建失败', voice_id)
        return None

    events = _load_events(pack)
    remap = _load_remap(pack)
    attach_data = _load_attach_data(pack)
    info_html = _load_info(pack)
    theme = _load_pack_theme(pack)

    logger.info('活跃语音已构建: %s（%s，事件 %d、重映射 %d%s%s%s）',
                voice_id, '第三方' if pack else '内置', len(events),
                len(remap),
                '、含绑定方案' if attach_data else '',
                '、含信息面板' if info_html else '',
                '、含内嵌主题' if theme else '')
    return ActiveVoice(voice_id, pack, events, remap, attach_data,
                       info_html=info_html, theme=theme)


def _builtin_exists(voice_id):
    """内置语音的切换期校验：查游戏声音模式表是否有该模式名。"""
    try:
        import SoundGroups
        return voice_id in SoundGroups.g_instance.soundModes.modes
    except Exception:
        logger.exception('查询声音模式表失败')
        return False


def _load_events(pack):
    """读取语音包的试听事件列表。

    优先从语音包 VFS 中的 events.json 直接读取，不进行合并。
    若读取失败（无文件/格式异常/无有效条目）则回退到全局 playEvent.json。
    """
    if pack is not None:
        extra = load_vfs_json(pack.root + model.EVENTS_JSON)
        if extra is not None and isinstance(extra, list):
            events = [dict(evt) for evt in extra
                      if isinstance(evt, dict) and evt.get('text') and evt.get('event')]
            if events:
                logger.debug('语音包 %s 的 events.json: %d 条事件',
                             pack.pack_id, len(events))
                return events
            logger.warn('语音包 %s 的 events.json 无有效条目，回退到 playEvent.json',
                        pack.pack_id)
        else:
            logger.debug('语音包 %s 无 events.json，回退到 playEvent.json',
                         pack.pack_id)

    # 回退：全局 playEvent.json
    from .repository import g_voice_repo
    return [dict(evt) for evt in g_voice_repo.play_events
            if isinstance(evt, dict) and evt.get('text') and evt.get('event')]


def _load_remap(pack):
    """解析重映射表（remap.json 优先，audio_mods.xml 兜底）。

    remap.json —— 平面 {原事件: 新事件或空串}；
    audio_mods.xml —— 官方格式，仅读 events/event 的 name→mod，
    忽视 <loadBanks>，插件暂不支持此功能。
    """
    if pack is None:
        return {}
    path = model.find_first(pack, model.REMAP_CANDIDATES)
    if path is None:
        return {}

    if path.endswith('.json'):
        data = load_vfs_json(path)
        if not isinstance(data, dict):
            logger.warn('语音包 %s 的 remap.json 不是对象，已忽略', pack.pack_id)
            return {}
        return data

    return _remap_from_xml(path, pack.pack_id)


def _remap_from_xml(path, pack_id):
    """从 audio_mods.xml 读 events/event 的 name→mod 映射。"""
    import ResMgr
    remap = {}
    root_sec = ResMgr.openSection(path)
    events_sec = root_sec['events'] if root_sec is not None else None
    if events_sec is None:
        logger.warn('语音包 %s 的 audio_mods.xml 缺少 events 段，已忽略', pack_id)
        return remap
    for item in events_sec.values():
        name = item.readString('name')
        mod = item.readString('mod')
        if name:
            remap[name] = mod
    return remap


def _read_vfs_text(path):
    """读取 VFS 文本文件的全部内容（utf-8）。

    约定：info.html / info.txt 文件第一个字符为无效保护位——
    防止 ResMgr 将以 '<' 开头的 HTML 内容当作 XML 解析。
    保护位必须是非空格字符（空格会被 ResMgr 跳过，仍触发 XML 解析）。
    保护位统一要求，无论扩展名，读取时丢弃首字符。
    """
    import ResMgr
    section = ResMgr.openSection(path)
    if section is None:
        return None
    try:
        text = to_utf8(section.asBinary.decode('utf-8-sig', 'replace'))
    except Exception:
        logger.warn('读取文本失败: %s', path)
        return None
    if text:
        text = text[1:]  # 去掉保护字节
    return text


def _load_info(pack):
    """解析语音包信息面板内容（info.html 优先，info.txt 兜底）。

    返回字符串（HTML 或纯文本）；内置语音返回 None。
    """
    if pack is None:
        return None
    path = model.find_first(pack, model.INFO_CANDIDATES)
    if path is None:
        return None
    return _read_vfs_text(path)


def _load_pack_theme(pack):
    """解析语音包内嵌主题（theme.json）。

    返回纯颜色 dict（不含 name/pack_id 元数据键）；内置语音/无文件返回 None。
    """
    if pack is None:
        return None
    path = model.find_first(pack, [model.THEME_JSON])
    if path is None:
        return None
    data = load_vfs_json(path)
    if not isinstance(data, dict):
        logger.warn('语音包 %s 的 theme.json 不是对象，已忽略', pack.pack_id)
        return None
    # 返回纯颜色键值（过滤元数据）
    theme = {k: v for k, v in data.items()
             if k not in ('name', 'pack_id')}
    return theme if theme else None


def _load_attach_data(pack):
    """解析语音包绑定方案（attach.json）；无文件/非对象/空方案返回 None。

    与 _load_pack_theme 同构：绑定引擎据此判断"语音包有无有效绑定方案"。
    无方案时 sound.py 将绑定引擎置空。
    """
    if pack is None:
        return None
    path = model.find_first(pack, [model.ATTACH_JSON])
    if path is None:
        return None
    data = load_vfs_json(path)
    if not isinstance(data, dict):
        logger.warn('语音包 %s 的 attach.json 不是对象，已忽略', pack.pack_id)
        return None
    return data if data else None


# ═════════════════════════════════════════════════════════════
# 管理器（单例 g_active_mgr）
# ═════════════════════════════════════════════════════════════

class ActiveVoiceManager(object):
    """活跃语音的持有者与切换广播源。"""

    def __init__(self):
        self._current = None
        self.onActiveVoiceChanged = Event.Event()
        """切换完成广播（参数：新 ActiveVoice 实例）——
        消费方：菜单重推播放列表、字幕重载、换肤等"""

    @property
    def current(self):
        """当前活跃语音（ActiveVoice | None，初始激活前为 None）。"""
        return self._current

    def activate(self, voice_id):
        """构建并切换活跃语音；失败保持旧实例。

        :return: True 成功切换（已广播）；False 构建失败
        """
        new_voice = build(voice_id)
        if new_voice is None:
            return False
        self._current = new_voice
        self.onActiveVoiceChanged(new_voice)
        return True


# 模块级单例——经 voices/__init__ 导出
g_active_mgr = ActiveVoiceManager()
