# coding=utf-8
"""声音子系统：绑定 + 重映射。

═══════════════════════════════════════════════════════════════════════════════
声音绑定 (Sound Binding)
  当 Wwise 事件触发时，按 AND 关键词匹配规则附加播放自定义语音。
  方案由语音包自带（pack 内 attach.json）
  格式: [{"match": "kw"|["k1","k2"], "event": "evt"|["e1","e2"]}, ...]

  匹配逻辑: match 中所有关键词（AND 关系）必须全部包含在实际事件名中
  （大小写不敏感）。命中后通过 WW_eventGlobal 播放附加事件。
  可选的 "strict": true 改为完全相等匹配，用于区分共享前缀的事件。

声音重映射 (Sound Remapping)
  动态替换 Wwise 事件名——audio_mods.xml 的 Python 运行时等价物。
  方案由语音包自带（pack 内 remap.json / audio_mods.xml）
  源自 XVM 方案，优化修复了已知缺陷。

  覆盖路径（比原 XVM 方案多了 playSound / WW_eventGlobalSync /
  WW_playCameraOriented）:

    路径 A —— 一次性事件（直接替换事件名，无 .name 问题）:
      WW_eventGlobal          2D 音效 ★（默认保持 2D，仅白名单内转 3D）
      WW_eventGlobalPos       3D 位置音效
      WW_eventGlobalSync      同步 2D 音效 [NEW]
      WW_playCameraOriented   朝向 3D 音效 [NEW]
      playSound               碰撞/破坏音效 [NEW]

    WW_eventGlobal 使用白名单（_route_3d_events），只对绑定/重映射方案中
    命名的事件转 3D，让替换后的语音携带 marker 被字幕捕获。

    路径 B —— PySound 创建（替换事件名后调原始 C++ 函数）:
      WW_getSound             getSound2D/getSound3D 底层
      WW_getSoundPos          带位置的 PySound 创建
      WW_getSoundCallback     带回调的 PySound 创建

    重映射后 PySound.name 存的是替换后的名字 → 设置菜单 playPreviewSound()
    读 .name 做 .index() 查找会抛 ValueError → 预览只能播一次。
    通过 _patch_settings_preview_sound() 包装该函数修复（捕获 ValueError
    后 clearPreviewSound() 重试），而非包装 PySound 对象。
═══════════════════════════════════════════════════════════════════════════════
"""

import WWISE

from .logger import Logger

logger = Logger('Sound')

# ═══════════════════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════════════════


def _normalize_to_list(value):
    """将字符串或数组统一转为 list（保留 JSON 解析的原始类型）。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v]
    return [value]


def _get_listener_position():
    """获取听者位置（摄像机坐标），用于 2D→3D 路由。

    WW_eventGlobal 不创建带 marker listener 的 Game Object，
    改为走 WW_eventGlobalPos 让 Wwise 创建 3D GO 从而捕获音频内嵌名。
    位置取听者坐标，使 2D 音效在最近处播放（2D 事件本身无衰减，位置不影响音量）。

    :return: (x, y, z) 元组
    """
    try:
        import BigWorld
        cam = BigWorld.camera()
        if cam is not None:
            pos = cam.position
            return (pos.x, pos.y, pos.z)
    except Exception:
        pass
    return (0.0, 0.0, 0.0)


# Path B 钩子（WW_getSound 等）内部调用 _play_voice_event 时会产生
# 嵌套的 C++ WW_getSound 重入——可能破坏 Wwise 内部全局状态导致原声音静音。
# 此标志位让 _play_voice_event 在重入场景下跳过 WW_getSound，直接用
# WW_eventGlobalPos（fire-and-forget）播放绑定目标。
_inside_path_b = False


def _play_voice_event(event_name):
    """用 3D 路径播放语音事件，支持 marker。

    默认走 WW_getSound → PySound 路径（3D GO → marker listener 可携带
    音频内嵌名）。若当前在 Path B 钩子内部（_inside_path_b=True），则跳过
    WW_getSound（避免嵌套重入破坏 Wwise 状态），直接用 WW_eventGlobalPos。

    调用者（钩子、绑定引擎）通过此函数确保语音事件走 3D GO → 字幕等模块
    能捕获 marker 触发。
    """
    global _active_voice_sound
    pos = _get_listener_position()

    # Path B 重入保护：跳过 WW_getSound，直接走 fire-and-forget
    if _inside_path_b:
        return _originals['WW_eventGlobalPos'](event_name, pos)

    # 用 WW_getSound 获取 PySound 句柄（3D GO，支持 marker listener）
    try:
        sound = _originals['WW_getSound'](event_name, 'voice', None)
    except Exception:
        sound = None

    if sound is not None:
        try:
            sound.position = pos
            sound.play()
            _active_voice_sound = sound
            return sound
        except Exception:
            pass

    # 兜底：WW_getSound 失败 → 回退到 3D fire-and-forget 路径
    logger.warn('WW_getSound 失败，回退到 WW_eventGlobalPos: %s', event_name)
    return _originals['WW_eventGlobalPos'](event_name, pos)


# ═══════════════════════════════════════════════════════════════════════════
# BindingEngine —— AND 关键词匹配 → 附加语音事件
# ═══════════════════════════════════════════════════════════════════════════

class BindingEngine(object):
    """声音绑定引擎。通过关键词 AND 匹配将触发源映射到自定义语音。

    规则格式 (attach.json)：
      {
        "sound": [ {"match": "...", "event": "..."}, ... ],
        "cmd":   [ {"match": "...", "event": "..."}, ... ]
      }

    sound 规则：Wwise 事件触发 → match 中所有关键词（AND 关系）
    必须全部包含在实际事件名中（大小写不敏感），命中后通过
    WW_eventGlobal 播放 target 事件。

    cmd 规则：玩家发送快捷指令 → match 关键词 AND 匹配 i18n key
    （如 #ingame_gui:chat_shortcuts/affirmative），命中后播放 target。

    每条规则可选 "strict": true —— 严格模式下关键词必须与事件名
    完全相等（而非子串包含），用于区分共享前缀的事件/指令。
    """

    def __init__(self):
        self._rules = []       # sound: [(keywords_lower_list, target_events_list), ...]
        self._cmd_rules = []   # cmd:   [(keywords_lower_list, target_events_list), ...]
        self._enabled = True

    # ── 开关 ──

    @property
    def enabled(self):
        return self._enabled

    def set_enabled(self, enabled):
        """启用/禁用绑定引擎；返回旧状态。"""
        old = self._enabled
        self._enabled = bool(enabled)
        return old

    @property
    def has_rules(self):
        """是否有已加载的绑定规则（sound 或 cmd）。"""
        return bool(self._rules or self._cmd_rules)

    # ── 加载 ──

    def load_data(self, data):
        """从已解析的 JSON 数据加载绑定规则。返回加载的规则数。

        :param data: attach.json 的 dict（如 ActiveVoice.attach_data）
        """
        return self._load_from_data(data)

    def _load_from_data(self, data):
        """从已解析的 JSON 数据加载规则（load + load_data 共用）。

        非 dict（含 None）视为空规则。
        """
        if not isinstance(data, dict):
            self._rules = []
            self._cmd_rules = []
            return 0

        self._rules = self._parse_rules(data.get('sound', []))
        self._cmd_rules = self._parse_rules(data.get('cmd', []))
        return len(self._rules) + len(self._cmd_rules)

    @staticmethod
    def _parse_rules(items):
        """将规则列表解析为内部格式 [(keywords_lower, targets, strict), ...]。

        每项的 match → 关键词小写列表；event → 目标事件列表；
        strict → 是否严格匹配（默认 False，即 AND 子串包含）。
        无效项（缺 match/event、空列表等）自动跳过。
        """
        if not isinstance(items, list):
            return []

        rules = []
        for item in items:
            if not isinstance(item, dict):
                continue

            match_raw = item.get('match')
            if match_raw is None:
                continue
            keywords = _normalize_to_list(match_raw)
            keywords = [k.lower() for k in keywords if k]
            if not keywords:
                continue

            event_raw = item.get('event')
            if event_raw is None:
                continue
            targets = _normalize_to_list(event_raw)
            targets = [t for t in targets if t]
            if not targets:
                continue

            strict = item.get('strict', False)
            rules.append((keywords, targets, strict))
        return rules

    # ── 匹配 ──

    def match(self, event_name):
        """匹配事件名，返回所有命中的目标事件列表（去重保序）。

        :param event_name: 实际触发的 Wwise 事件名
        :return: [target_event, ...]
        """
        if not self._rules:
            return []

        name_lower = event_name.lower()
        results = []

        for keywords, targets, strict in self._rules:
            if strict:
                # 严格模式：事件名必须与每个关键词完全相等
                if all(k == name_lower for k in keywords):
                    results.extend(targets)
            else:
                # AND 逻辑：所有关键词必须包含在事件名中
                if all(k in name_lower for k in keywords):
                    results.extend(targets)

        # 去重但保持顺序
        seen = set()
        unique = []
        for t in results:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique

    # ── 事件回调 ──

    def on_event(self, event_name):
        """当声音事件触发时调用。匹配并播放绑定的语音。

        此方法被 WWISE 钩子直接调用（不需要通过 SoundHook listener）。

        绑定目标走 _play_voice_event（3D 路径 + WW_getSound），
        确保 Wwise 创建 3D GO → marker listener 可携带音频内嵌名 → 字幕模块
        能正常捕获 marker 并触发字幕。
        """
        if not self._enabled:
            return
        targets = self.match(event_name)
        for t in targets:
            try:
                _play_voice_event(t)
            except Exception:
                pass

    def on_command(self, command_key):
        """当玩家发送快捷指令时调用。匹配 cmd 规则并播放绑定音效。

        由 hooks.py 的 _ReceivedCmdDecorator.getCommandText override
        在 isSender() 分支中调用（仅玩家自己发送的指令触发）。

        绑定目标走 _play_voice_event（3D 路径），确保字幕能正常触发。

        :param command_key: i18n key，如 #ingame_gui:chat_shortcuts/affirmative
        """
        if not self._enabled or not self._cmd_rules:
            return

        key_lower = command_key.lower()
        for keywords, targets, strict in self._cmd_rules:
            if strict:
                if all(k == key_lower for k in keywords):
                    for t in targets:
                        try:
                            _play_voice_event(t)
                        except Exception:
                            pass
            else:
                # AND 逻辑：所有关键词必须包含在 i18n key 中
                if all(k in key_lower for k in keywords):
                    for t in targets:
                        try:
                            _play_voice_event(t)
                        except Exception:
                            pass


# ═══════════════════════════════════════════════════════════════════════════
# RemappingEngine —— 动态事件名替换
# ═══════════════════════════════════════════════════════════════════════════

class RemappingEngine(object):
    """声音重映射引擎。等价于 audio_mods.xml 的 Python 运行时版本。

    映射表只来自当前活跃语音包（load_dict），所有替换在 WWISE
    C++ 函数调用前完成——只在钩子层修改事件名字符串。
    """

    def __init__(self):
        self._remapping = {}   # {original_event: replacement_event}
        self._enabled = True

    # ── 开关 ──

    @property
    def enabled(self):
        return self._enabled

    def set_enabled(self, enabled):
        """启用/禁用重映射引擎；返回旧状态。"""
        old = self._enabled
        self._enabled = bool(enabled)
        return old

    # ── 加载 ──

    def load_dict(self, mapping):
        """运行时动态设置映射表。

        :param mapping: {original: replacement} dict，传 None 或非 dict 则清空
        """
        if not isinstance(mapping, dict):
            mapping = {}
        self._remapping = mapping

    # ── 查询 ──

    def replace(self, event):
        """替换事件名。如果事件在映射表中则返回替换后的名字，否则原样返回。

        禁用时始终返回原事件名（不替换）。

        :param event: 原始 Wwise 事件名
        :return: 替换后的事件名
        """
        if not self._enabled:
            return event
        return self._remapping.get(event, event)

    @property
    def remapping(self):
        """返回当前映射表的浅拷贝（只读）。"""
        return dict(self._remapping)


# ═══════════════════════════════════════════════════════════════════════════
# 模块级单例
# ═══════════════════════════════════════════════════════════════════════════

g_binding_engine = BindingEngine()
g_remapping_engine = RemappingEngine()

# ── Marker 监听器：捕获音频内嵌名（LIST chunk label）──
# 2D 音效走 WW_eventGlobal → Game Object 不带 marker listener，
# 改为全部走 3D 路径后 Wwise 创建 3D GO，marker 回调可携带音频
# 文件内嵌的名称，供字幕等模块使用。
_marker_listeners = []
_active_voice_sound = None  # PySound | None —— 保持引用，防止播放被 GC 中断


def add_marker_listener(callback):
    """注册 marker 监听器。回调签名为 callback(marker_str: str)。

    字幕模块通过此 API 订阅音频内嵌名，marker_str 为音频文件内部
    LIST chunk 的 label 文本（UTF-8 字节串）。
    """
    if callback not in _marker_listeners:
        _marker_listeners.append(callback)


def remove_marker_listener(callback):
    """注销 marker 监听器。"""
    try:
        _marker_listeners.remove(callback)
    except ValueError:
        pass


def _on_wwise_marker(marker):
    """全局 marker 回调——分发给所有订阅者。

    由 WW_addMarkerListener 注册，在 install 时安装、uninstall 时摘除。
    marker 参数类型取决于 Wwise SDK 绑定（PySound 或 bytes），统一转字符串。
    """
    try:
        marker_str = str(marker).strip()
    except Exception:
        return
    if not marker_str:
        return

    count = len(_marker_listeners)
    if count == 0:
        logger.debug('marker 已捕获但无订阅者: "%s"', marker_str)
    else:
        logger.debug('marker 分发给 %d 个订阅者: "%s"', count, marker_str)
        for cb in _marker_listeners:
            try:
                cb(marker_str)
            except Exception:
                pass


# ── 内部：钩子安装/卸载状态 ──
_originals = {}   # {func_name: original_cpp_func}
_hooked = False
_voice_changed_registered = False  # 是否已注册 onActiveVoiceChanged 监听
_route_3d_events = set()  # 2D→3D 路由白名单（见 _build_route_3d_events）


# ═══════════════════════════════════════════════════════════════════════════
# 语音切换 → 声音子系统联动
# ═══════════════════════════════════════════════════════════════════════════

def _build_route_3d_events(active_voice, se):
    """构建 2D→3D 路由白名单。

    语音包自身的语音都走 3D（getSound 系列），无需路由；只有被绑定或
    被重映射的声音可能本身走 2D（playSound2D），需要转 3D 才能让替换
    后的语音携带 marker 被字幕捕获。使用白名单保持 2D 不破坏游戏对象语义。

    匹配采用事件名精确命中（大小写不敏感，同时存原形与小写）。
    """
    global _route_3d_events
    events = set()
    if active_voice is not None:
        # —— 重映射：源与目标都纳入（源被路由后替换目标走 3D；
        #    目标也可能被游戏直接播放）——
        if se.get('soundRemap', False):
            for src, dst in active_voice.remap.items():
                events.add(src); events.add(src.lower())
                if dst:
                    events.add(dst); events.add(dst.lower())

        # —— 绑定方案：match 关键词与 event 目标都纳入 ——
        if se.get('soundBind', False):
            data = active_voice.attach_data
            if isinstance(data, dict):
                for section_key in ('sound', 'cmd'):
                    for rule in data.get(section_key, []):
                        if not isinstance(rule, dict):
                            continue
                        for name in (_normalize_to_list(rule.get('match'))
                                     + _normalize_to_list(rule.get('event'))):
                            name = (name or '').strip()
                            if name:
                                events.add(name); events.add(name.lower())

    _route_3d_events = events
    logger.debug('2D→3D 路由白名单: %d 个事件', len(events))


def _on_active_voice_changed(active_voice):
    """当用户切换语音包时，将新语音包的重映射表和绑定方案应用到引擎。

    此函数注册在 g_active_mgr.onActiveVoiceChanged 上，
    由 voice_switcher.switch_voice() → activate() 间接触发。

    声音绑定/重映射：方案只来自语音包，
    行为由 settings.soundRemap / settings.soundBind 控制：
      - 开关开启 → 应用语音包的 remap/attach
      - 开关关闭 → 引擎被禁用（replace 原样返回 / on_event 空转）
      - 语音包无方案（内置语音/无文件/解析失败/空）→ 置空（load_dict({})
        或 load_data(None)），不做任何替换/绑定
    """
    from .config import load_config
    se = load_config().get('settings', {})

    # ── 声音重映射 ──
    if se.get('soundRemap', False):
        if active_voice.remap:
            g_remapping_engine.load_dict(active_voice.remap)
            logger.info('已应用语音包重映射表 (%d 条)', len(active_voice.remap))
        else:
            g_remapping_engine.load_dict({})
            logger.debug('语音包无重映射，重映射表置空')
    else:
        logger.debug('soundRemap 关闭，跳过重映射切换')

    # ── 声音绑定 ──
    if se.get('soundBind', False):
        if active_voice.attach_data:
            count = g_binding_engine.load_data(active_voice.attach_data)
            if count:
                logger.info('已加载语音包绑定方案 (%d 条规则)', count)
            else:
                logger.debug('语音包绑定方案为空或解析失败')
        else:
            # 语音包无绑定方案 → 置空，而非回退到任何预设规则
            g_binding_engine.load_data(None)
            logger.debug('语音包无绑定方案，绑定引擎置空')
    else:
        logger.debug('soundBind 关闭，跳过绑定方案切换')

    # ── 更新 2D→3D 路由白名单 ──
    # 只对绑定/重映射方案中命名的事件转 3D；装填音效等游戏 SFX 保持 2D
    _build_route_3d_events(active_voice, se)

    # ── 字幕样式更新 ──
    # 切换语音包后，若战斗中字幕 View 已加载，更新其数据源
    # 同时通知菜单 Flash 端字幕功能是否可用（控制"字幕"按钮显隐）
    try:
        # 若当前正在编辑字幕位置，先兜底保存再切换
        from autoconfigvoiceover.pages.subtitle_settings_page import \
            ensure_saved_on_voice_switch
        ensure_saved_on_voice_switch()

        from autoconfigvoiceover.subtitle.host import update_subtitle_style as _upd_sub
        from autoconfigvoiceover.subtitle.loader import load_style, is_subtitle_available
        if not active_voice.is_builtin:
            pack_root = active_voice.pack.root
            style = load_style(pack_root)
            _upd_sub(pack_root, style)
            _available = is_subtitle_available(pack_root)
        else:
            _available = False

        # 通知菜单 Flash 端更新"字幕"按钮可见性
        from .menu import _view_instance as _menu_view
        if _menu_view is not None:
            _menu_view.as_setSubtitleAvailableS(_available)
    except Exception:
        pass  # 字幕模块未加载或加载失败，不影响声音子系统


def _hook_wwise(module, func_name, wrapper):
    """保存原始 C++ 函数并用 wrapper 替换。函数不存在时跳过并 warn。"""
    if hasattr(module, func_name):
        _originals[func_name] = getattr(module, func_name)
        setattr(module, func_name, wrapper)
    else:
        logger.warn('%s 不存在，跳过此钩子', func_name)


# ═══════════════════════════════════════════════════════════════════════════
# 钩子安装 / 卸载
# ═══════════════════════════════════════════════════════════════════════════

def _install_remapping_hooks():
    """安装 WWISE 钩子——Path A + Path B 全覆盖。

    钩子链设计（与 mod_test.SoundHook 共存时）:
      import 顺序: sound.py 先 → mod_test.py 后
      运行时: game code → SoundHook wrapper(log) → sound wrapper(remap+bind) → C++
      SoundHook 总是看到原始事件名（remap 之前），这对调试更友好。
    """
    global _hooked
    if _hooked:
        return

    if not WWISE.enabled:
        logger.warn('WWISE 未启用，跳过声音钩子安装')
        return

    # ═════════════════════════════════════════════════════════════
    # 路径 A: 一次性事件 —— 绑定 + 重映射后调原始 C++ 函数
    # ═════════════════════════════════════════════════════════════

    # ── ① WW_eventGlobal —— 2D 音效 ──
    # 默认保持 2D 播放（游戏中弹鼓装填音效的 complete 事件依赖 2D 对象
    # 身份去停止 almost_complete 循环，转 3D 会打断该停循环机制）。
    # 仅对白名单中的语音事件转 3D，让替换后的语音携带 marker 被字幕捕获。
    # 转 3D 后 Wwise 创建 3D GO → marker listener 可携带
    # 音频内嵌名 → 字幕系统能捕获 marker。
    #
    # 重映射在此层完成（替换事件名后传给原始 C++ 函数），不走
    # _play_voice_event。_play_voice_event 专用于绑定目标（需要 PySound
    # 句柄承载 marker/字幕），两者职责分离。
    def _hooked_WW_eventGlobal(eventName, checkSoundBankName=''):
        g_binding_engine.on_event(eventName)
        remapped = g_remapping_engine.replace(eventName)
        if eventName in _route_3d_events:
            # 绑定/重映射涉及的语音：转 3D 播放以携带 marker 被字幕捕获
            pos = _get_listener_position()
            return _originals['WW_eventGlobalPos'](remapped, pos)
        # 其余音效（装填音效等）保持 2D，不破坏游戏 2D 对象语义
        return _originals['WW_eventGlobal'](remapped, checkSoundBankName)
    _hook_wwise(WWISE, 'WW_eventGlobal', _hooked_WW_eventGlobal)

    # ── ② WW_eventGlobalPos —— 全部 3D 位置音效 ──
    def _hooked_WW_eventGlobalPos(eventName, position):
        g_binding_engine.on_event(eventName)
        remapped = g_remapping_engine.replace(eventName)
        return _originals['WW_eventGlobalPos'](remapped, position)
    _hook_wwise(WWISE, 'WW_eventGlobalPos', _hooked_WW_eventGlobalPos)

    # ── ③ WW_eventGlobalSync —— 同步 2D 音效（部分版本可能不存在）──
    def _hooked_WW_eventGlobalSync(eventName):
        g_binding_engine.on_event(eventName)
        remapped = g_remapping_engine.replace(eventName)
        return _originals['WW_eventGlobalSync'](remapped)
    _hook_wwise(WWISE, 'WW_eventGlobalSync', _hooked_WW_eventGlobalSync)

    # ── ④ WW_playCameraOriented —— 朝向相关 3D 音效 ──
    def _hooked_WW_playCameraOriented(eventName, position):
        g_binding_engine.on_event(eventName)
        remapped = g_remapping_engine.replace(eventName)
        return _originals['WW_playCameraOriented'](remapped, position)
    _hook_wwise(WWISE, 'WW_playCameraOriented', _hooked_WW_playCameraOriented)

    # ── ⑤ WWISE.playSound —— 碰撞/破坏音效（原 XVM 方案未覆盖）──
    def _hooked_playSound(soundName, position, soundParams=None, soundSwitches=None):
        g_binding_engine.on_event(soundName)
        remapped = g_remapping_engine.replace(soundName)
        return _originals['playSound'](remapped, position, soundParams, soundSwitches)
    _hook_wwise(WWISE, 'playSound', _hooked_playSound)

    # ═════════════════════════════════════════════════════════════
    # 路径 B: PySound 创建函数
    #
    # 事件名替换后调原始 C++ 函数，返回原始 PySound（战斗音效需要
    # 原始 PySound——C++ getSound2D 内部 pybind11 cast 要求）。菜单
    # 预览 .name 不匹配问题由 _patch_settings_preview_sound() 修复。
    #
    # 声音绑定不在此层——Path A 钩子（WW_eventGlobal 等）已覆盖
    # 绝大多数音效的绑定。
    # ═════════════════════════════════════════════════════════════

    # ── ⑥ WW_getSound —— getSound2D / getSound3D 底层 ──
    def _hooked_WW_getSound(eventName, objectName, matrix, local=(0.0, 0.0, 0.0)):
        global _inside_path_b
        _inside_path_b = True
        try:
            g_binding_engine.on_event(eventName)
        except Exception:
            pass
        finally:
            _inside_path_b = False
        remapped = g_remapping_engine.replace(eventName)
        return _originals['WW_getSound'](remapped, objectName, matrix, local)
    _hook_wwise(WWISE, 'WW_getSound', _hooked_WW_getSound)

    # ── ⑦ WW_getSoundPos —— 带位置的 PySound 创建 ──
    def _hooked_WW_getSoundPos(eventName, objectName, position):
        global _inside_path_b
        _inside_path_b = True
        try:
            g_binding_engine.on_event(eventName)
        except Exception:
            pass
        finally:
            _inside_path_b = False
        remapped = g_remapping_engine.replace(eventName)
        return _originals['WW_getSoundPos'](remapped, objectName, position)
    _hook_wwise(WWISE, 'WW_getSoundPos', _hooked_WW_getSoundPos)

    # ── ⑧ WW_getSoundCallback —— 带回调的 PySound 创建 ──
    def _hooked_WW_getSoundCallback(eventName, objectName, matrix, callback):
        global _inside_path_b
        _inside_path_b = True
        try:
            g_binding_engine.on_event(eventName)
        except Exception:
            pass
        finally:
            _inside_path_b = False
        remapped = g_remapping_engine.replace(eventName)
        return _originals['WW_getSoundCallback'](remapped, objectName, matrix, callback)
    _hook_wwise(WWISE, 'WW_getSoundCallback', _hooked_WW_getSoundCallback)

    import SoundGroups as _SG

    # ═════════════════════════════════════════════════════════════
    # ⑨ SoundGroups.g_instance.WWgetSoundObject —— SoundObject 创建
    #
    # 火炮 / 碰撞 / 弹道音效走 SoundObject 路径，独立于 WW_getSound:
    #   WWgetSoundObject(objectName, matrix, ...) → C++ SoundObject
    #     → soundObject.play(eventName) → 直接进 C++ WWISE，Python 不可见
    #
    # objectName 携带音效名（如 psb_main_PC0），用作绑定匹配的输入。
    # 重映射不适用（objectName 不是 Wwise 事件名），直接透传。
    # ═════════════════════════════════════════════════════════════
    _has_wwgetsoundobj = False
    if hasattr(_SG.g_instance, 'WWgetSoundObject'):
        _originals['WWgetSoundObject'] = _SG.g_instance.WWgetSoundObject

        def _hooked_WWgetSoundObject(objectName, matrix,
                                     local=(0.0, 0.0, 0.0), auxSend=False):
            try:
                g_binding_engine.on_event(str(objectName))
            except Exception:
                pass
            # objectName 不经过重映射（非 Wwise 事件名）
            return _originals['WWgetSoundObject'](objectName, matrix,
                                                  local, auxSend)
        _SG.g_instance.WWgetSoundObject = _hooked_WWgetSoundObject
        _has_wwgetsoundobj = True
    else:
        logger.warn('SoundGroups.g_instance.WWgetSoundObject 不存在，跳过此钩子')

    _hooked = True
    logger.info('声音钩子已安装 (Path A: 5 + Path B: 3 + WWgetSoundObject=%s)',
                'OK' if _has_wwgetsoundobj else 'MISSING')

    # ── 注册全局 marker listener（在所有钩子安装之后）──
    # 2D→3D 路由（_hooked_WW_eventGlobal）已就位，
    # 此后所有音效均走 3D 路径，marker 回调可正常携带内嵌名。
    try:
        WWISE.WW_addMarkerListener(_on_wwise_marker)
        logger.info('Wwise marker listener 已注册')
    except Exception:
        logger.exception('WW_addMarkerListener 失败')


def _uninstall_remapping_hooks():
    """卸载所有钩子，恢复原始 WWISE 函数和 SoundGroups 方法。"""
    global _hooked
    if not _hooked:
        return

    # 摘除 marker listener（在恢复函数之前）
    try:
        WWISE.WW_removeMarkerListener(_on_wwise_marker)
        logger.info('Wwise marker listener 已摘除')
    except Exception:
        pass

    # 恢复 SoundGroups.g_instance 上的方法
    _sg_keys = ['WWgetSoundObject']
    for key in _sg_keys:
        if key in _originals:
            try:
                import SoundGroups as _SG
                setattr(_SG.g_instance, key, _originals.pop(key))
            except Exception:
                pass

    for func_name, original in _originals.items():
        try:
            setattr(WWISE, func_name, original)
        except Exception:
            pass

    _originals.clear()
    _hooked = False
    logger.info('声音钩子已卸载')


def _patch_settings_preview_sound():
    """修复设置菜单 playPreviewSound() 因重映射导致的 ValueError。

    重映射后 PySound.name 返回替换后的名字（如 lightbulb_mod），
    但 PreviewSoundSetting._WWISE_EVENTS 仍是原始名（lightbulb），
    .index() 查找失败 → ValueError → 同个音效只能预览一次。

    通过 try/except 包装：捕获 ValueError 后 clearPreviewSound()
    再重试，第二次调用时 __previewSound 为 None 走 else 分支
    直接创建新 sound，不触发 .index() 检查。
    """
    try:
        from account_helpers.settings_core.options import PreviewSoundSetting
    except ImportError:
        logger.warn('account_helpers.settings_core.options 不可用，跳过预览补丁')
        return

    _original = PreviewSoundSetting.playPreviewSound

    def _patched(self, eventIdx):
        try:
            return _original(self, eventIdx)
        except ValueError:
            self.clearPreviewSound()
            return _original(self, eventIdx)

    PreviewSoundSetting.playPreviewSound = _patched
    logger.info('playPreviewSound 已打补丁（重映射兼容）')


# ═══════════════════════════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════════════════════════

def init():
    """初始化声音子系统：安装 WWISE 钩子 + 注册语音切换联动。

    应在 ACV init() 中尽早调用（config 就绪后即可），确保钩子在
    任何游戏声音播放前生效。
    """
    global _voice_changed_registered

    # ── 安装钩子 ──
    _install_remapping_hooks()

    # ── 设置菜单预览补丁 ──
    # 重映射后 PySound.name 返回替换后的名字（如 lightbulb_mod），
    # 而 PreviewSoundSetting._WWISE_EVENTS 仍是原始名（lightbulb），
    # playPreviewSound() 内 .index() 查找失败 → ValueError。
    # 通过 try/except 包装：捕获 ValueError 后 clearPreviewSound()
    # 再重试，第二次 __previewSound 为 None 走 else 分支直接创建。
    _patch_settings_preview_sound()

    # ── 注册语音切换监听器 ──
    # 在 switch_voice 首次调用前注册，确保每次切语音都联动声音子系统
    from autoconfigvoiceover.voices.active_voice import g_active_mgr
    g_active_mgr.onActiveVoiceChanged += _on_active_voice_changed
    _voice_changed_registered = True

    # ── 初始状态：根据配置启用/禁用引擎 ──
    # 全局禁用时强制关闭引擎，无视 per-engine 用户设置
    from .config import load_config, is_enabled
    se = load_config().get('settings', {})
    if is_enabled():
        g_remapping_engine.set_enabled(se.get('soundRemap', False))
        g_binding_engine.set_enabled(se.get('soundBind', False))
    else:
        g_remapping_engine.set_enabled(False)
        g_binding_engine.set_enabled(False)
    logger.debug('引擎初始状态: remap=%s bind=%s (全局%s)',
                 g_remapping_engine.enabled, g_binding_engine.enabled,
                 '启用' if is_enabled() else '禁用')

    # ── 如果已有活跃语音（如 default 已在 init 链中激活），
    #     则立即联动一次；否则等首次 switch_voice 触发 ──
    if g_active_mgr.current is not None:
        _on_active_voice_changed(g_active_mgr.current)


def fini():
    """卸载声音子系统，恢复所有被钩的 WWISE 函数。"""
    global _voice_changed_registered, _marker_listeners, _active_voice_sound
    if _voice_changed_registered:
        from autoconfigvoiceover.voices.active_voice import g_active_mgr
        g_active_mgr.onActiveVoiceChanged -= _on_active_voice_changed
        _voice_changed_registered = False
    _uninstall_remapping_hooks()
    _marker_listeners = []
    _active_voice_sound = None  # 释放语音句柄引用（不再尝试 stop）
