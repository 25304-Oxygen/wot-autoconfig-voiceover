# coding=utf-8
"""字幕宿主 — 桥接 Python Manager 与 Flash SubtitleView。

═══════════════════════════════════════════════════════════════════════════════
架构
  Wwise marker → sound._on_wwise_marker
               → mgr.on_marker()
               → mgr._emit() → _dispatcher()
               → flashObject.as_create / as_updateContent / ...
               → Flash SubtitleView → SubtitleRenderer
               → onSubtitleCallback (GFx 回退)
               → mgr.on_fade_out_done()

策略切换
  根据 settings 中 subtitleUpdate / multiSub 两个布尔值选择策略:
    S1: update=0 multi=0  →  queue_s1.S1Manager
    S2: update=0 multi=1  →  queue_s2.S2Manager
    S3: update=1 multi=0  →  queue_s3.S3Manager
    S4: update=1 multi=1  →  queue_s4.S4Manager

  运行时切换: update_subtitle_settings() 中检测策略类是否变化，
  变化时 clear() 旧 manager 并创建新 manager。

生命周期
  战斗/车库进入 → loadView → View.__init__ → _populate → _init_manager
  离开          → _dispose → _destroy_manager → unregister marker listener

参照 menu.py 的 ACVMenuMeta 模式:
  - 不依赖 loadView() 返回值（通过 __init__ 保存引用）
  - DAAPI 方法用 as_xxxS 命名，内部调 flashObject.as_xxx
  - Flash → Python 回调通过 GFx 对 null Function 的回退机制
═══════════════════════════════════════════════════════════════════════════════
"""

from gui.Scaleform.framework.entities.View import View

from autoconfigvoiceover.logger import Logger

logger = Logger('SubtitleHost')

# ═════════════════════════════════════════════════════════════
# View 注册标识符
# ═════════════════════════════════════════════════════════════

VIEW_ALIAS = 'autoConfigVoiceOverSubtitle'
VIEW_SWF = 'autoConfigVoiceOverSubtitle.swf'

# ═════════════════════════════════════════════════════════════
# 模块级引用
# ═════════════════════════════════════════════════════════════

_view_instance = None    # BattleSubtitleView 实例（__init__ 设置）
_manager = None          # BaseSubtitleManager 实例
_on_edit_offset_cb = None  # 字幕编辑偏移回调
_preload_pending = []    # 待预加载的图片 URL 列表（DAAPI 就绪前暂存）

# 战斗→车库切换时 lobby app 重建中，loadView 请求不立即创建 View，
# 轮询检查 _view_instance，直到 __init__ 回调设置引用或超时。
_LOAD_RETRY_COUNT = 40     # 最大轮询次数
_LOAD_RETRY_DELAY = 0.5    # 轮询间隔（秒），总窗口约 20 秒
_load_in_progress = False  # loadView + 就绪轮询进行中，防止重复触发


def set_edit_offset_callback(cb):
    """设置字幕编辑偏移回调（subtitle_settings_page 进入编辑模式时调用）。

    传入 None 可清除回调（退出编辑模式时）。
    :param cb: callable(target, x, y) 或 None
    """
    global _on_edit_offset_cb
    _on_edit_offset_cb = cb


def _clear_view():
    """清除 View 引用（_dispose 时调用）。"""
    global _view_instance, _on_edit_offset_cb, _preload_pending
    _view_instance = None
    _on_edit_offset_cb = None
    _preload_pending = []
    logger.debug('View 引用已清除')


def _try_preload_images():
    """尝试将待预加载的图片 URL 发送到 Flash。

    由 _init_manager() 末尾和 _dispatcher() 开头调用。
    DAAPI 未就绪或 View 不存在时静默跳过——
    下一次 dispatcher 调用时会重试，保证迟早触发。
    """
    global _preload_pending
    v = _view_instance
    if v is None or not _preload_pending:
        return
    try:
        if v._isDAAPIInited():
            v.as_preloadImagesS(_preload_pending)
            logger.info('图片预加载已发送: %d 张', len(_preload_pending))
            _preload_pending = []
    except Exception:
        pass  # DAAPI 异常不影响字幕功能


# ═════════════════════════════════════════════════════════════
# Dispatcher: Manager → Flash
# ═════════════════════════════════════════════════════════════

def _dispatcher(cmd_dict):
    """将 Manager 产出的命令转发到 Flash DAAPI。"""
    v = _view_instance
    if v is None:
        return

    # 首次分发时确保样式图片已预加载（DAAPI 此时一定就绪）
    _try_preload_images()

    cmd = cmd_dict['cmd']
    rid = cmd_dict.get('id', 0)

    try:
        if cmd == 'create':
            v.as_createS(rid, cmd_dict['data'])
        elif cmd == 'update_content':
            v.as_updateContentS(rid, cmd_dict['data'])
        elif cmd == 'shift_up':
            v.as_shiftUpS(rid, cmd_dict.get('distance', 0))
        elif cmd == 'shift_down':
            v.as_shiftDownS(rid, cmd_dict.get('distance', 0))
        elif cmd == 'fade_out':
            v.as_fadeOutS(rid)
        elif cmd == 'clear_all':
            v.as_clearAllS()
    except Exception:
        logger.exception('dispatcher 调用失败: %s id=%d', cmd, rid)


# ═════════════════════════════════════════════════════════════
# 策略选择
# ═════════════════════════════════════════════════════════════

def _resolve_manager_class(settings):
    """根据设置选择策略类。

    :param settings: dict（subtitleUpdate / multiSub）
    :return: BaseSubtitleManager 子类
    """
    from .queue_s1 import S1Manager
    from .queue_s2 import S2Manager
    from .queue_s3 import S3Manager
    from .queue_s4 import S4Manager

    update = bool(settings.get('subtitleUpdate', False))
    multi = bool(settings.get('multiSub', False))

    if not update and not multi:
        return S1Manager
    elif not update and multi:
        return S2Manager
    elif update and not multi:
        return S3Manager
    else:
        return S4Manager


# ═════════════════════════════════════════════════════════════
# Manager 生命周期
# ═════════════════════════════════════════════════════════════

def _init_manager():
    """创建 Manager 并注册 marker listener。

    从当前活跃语音包加载字幕样式，从配置文件读取字幕设置。
    内置语音（pack=None）无字幕数据，跳过初始化。
    实际的 Manager 创建逻辑在 _build_manager（与语音切换补建共用）。
    """
    global _manager

    logger.debug('_init_manager 开始...')

    from autoconfigvoiceover.voices.active_voice import g_active_mgr
    from .loader import load_style

    active = g_active_mgr.current
    if active is None or active.is_builtin:
        logger.debug('当前无活跃语音包或为内置语音，跳过字幕初始化')
        return

    pack_root = active.pack.root

    # 样式加载的真实文件路径由 loader.load_style 记录（INFO），此处不重复
    style = load_style(pack_root)
    if style is None:
        # "未找到字幕样式文件"已由 loader.load_style 记录，此处不重复
        return

    _build_manager(pack_root, style)


def _build_manager(pack_root, style):
    """按当前配置创建字幕 Manager（幂等，已存在则跳过）。

    两个入口复用：
      - View 加载时（_init_manager）：活跃语音恰为带字幕语音包时创建；
      - 语音切换后（update_subtitle_style）：车库启动时活跃语音若是
        非字幕语音包，View 加载阶段不会建 Manager；切到带字幕语音包
        后在此补建，否则车库试听不出字幕（要等进战斗 View 重载才建）。

    :param pack_root: 语音包 VFS 根目录
    :param style:     SubtitleStyle（load_style 返回值，非 None）
    """
    global _manager, _preload_pending

    if _manager is not None:
        logger.debug('字幕 Manager 已存在，跳过创建')
        return

    # —— 从配置读取设置 ——
    from autoconfigvoiceover.config import load_config
    se = load_config(log=False).get('settings', {})

    # 配置的 subtitleDisplay 用 'simple'，manager 用 'concise'，做映射
    display_mode = se.get('subtitleDisplay', 'standard')
    if display_mode == 'simple':
        display_mode = 'concise'

    settings = {
        'display_mode':     display_mode,
        'subtitleUpdate':   bool(se.get('subtitleUpdate', False)),
        'multiSub':         bool(se.get('multiSub', False)),
        'text_speed':       float(se.get('textSpeed', 0.03)),
        'subtitle_anim':    bool(se.get('subtitleAnim', False)),
    }

    # —— 选择策略 ——
    ManagerCls = _resolve_manager_class(settings)

    import autoconfigvoiceover.sound as sound

    _manager = ManagerCls(
        pack_root, style, settings,
        dispatcher=_dispatcher,
    )

    # —— 注册 marker 监听器 ——
    sound.add_marker_listener(_manager.on_marker)

    # —— 收集样式图片并尝试预加载到 Flash ImageCache ——
    from .loader import collect_style_images
    urls = collect_style_images(style)
    if urls:
        _preload_pending = urls
        _try_preload_images()  # DAAPI 未就绪则暂存，首次分发时重试
        logger.debug('待预加载 %d 张样式图片', len(urls))

    logger.info('字幕系统已就绪: strategy=%s mode=%s speed=%.2f',
                ManagerCls.__name__, display_mode, settings['text_speed'])


def _destroy_manager():
    """销毁 Manager，注销 marker listener。"""
    global _manager

    if _manager is not None:
        import autoconfigvoiceover.sound as sound
        sound.remove_marker_listener(_manager.on_marker)
        _manager.clear()
        _manager = None
        logger.info('字幕系统已销毁')


# ═════════════════════════════════════════════════════════════
# BattleSubtitleView —— Python ↔ Flash DAAPI 桥接
# ═════════════════════════════════════════════════════════════

class BattleSubtitleView(View):
    """字幕视图。加载 autoConfigVoiceOverSubtitle.swf，
    桥接 Manager 与 Flash SubtitleView 的双向通信。

    __init__() 中将自身保存到模块级 _view_instance，
    供 dispatcher 获取引用（绕过 loadView() 返回 None 的问题）。
    """

    def __init__(self, ctx=None):
        global _view_instance
        super(BattleSubtitleView, self).__init__()
        _view_instance = self
        logger.debug('BattleSubtitleView.__init__() — View 实例已捕获')

    # ── 生命周期 ──

    def _populate(self):
        super(BattleSubtitleView, self)._populate()
        try:
            _init_manager()
        except Exception:
            logger.exception('_init_manager 抛出异常，字幕功能不可用')
        logger.debug('_populate 完成')

    def _dispose(self):
        _destroy_manager()
        _clear_view()
        super(BattleSubtitleView, self)._dispose()
        logger.debug('_dispose 完成')

    # ═════════════════════════════════════════════════════════
    # DAAPI: Python → Flash（6 条命令）
    # ═════════════════════════════════════════════════════════

    def as_createS(self, rid, data):
        """创建字幕 renderer。"""
        if self._isDAAPIInited():
            return self.flashObject.as_create(rid, data)

    def as_updateContentS(self, rid, data):
        """更新已有 renderer 的内容。"""
        if self._isDAAPIInited():
            return self.flashObject.as_updateContent(rid, data)

    def as_shiftUpS(self, rid, distance):
        """renderer 上移指定像素。"""
        if self._isDAAPIInited():
            return self.flashObject.as_shiftUp(rid, distance)

    def as_shiftDownS(self, rid, distance):
        """renderer 下移指定像素。"""
        if self._isDAAPIInited():
            return self.flashObject.as_shiftDown(rid, distance)

    def as_fadeOutS(self, rid):
        """renderer 淡出 → 销毁。"""
        if self._isDAAPIInited():
            return self.flashObject.as_fadeOut(rid)

    def as_clearAllS(self):
        """立即清除全部 renderer。"""
        if self._isDAAPIInited():
            return self.flashObject.as_clearAll()

    def as_preloadImagesS(self, urls):
        """批量预加载样式图片到 ImageCache。"""
        if self._isDAAPIInited():
            return self.flashObject.as_preloadImages(urls)

    # ═════════════════════════════════════════════════════════
    # DAAPI: 字幕位置编辑预览
    # ═════════════════════════════════════════════════════════

    def as_showPreviewS(self, data, offsets):
        """显示字幕位置编辑的静态预览。"""
        if self._isDAAPIInited():
            return self.flashObject.as_showPreview(data, offsets)

    def as_hidePreviewS(self):
        """隐藏字幕位置编辑的静态预览。"""
        if self._isDAAPIInited():
            return self.flashObject.as_hidePreview()

    def as_setEditTargetS(self, target):
        """设置当前编辑目标组件。"""
        if self._isDAAPIInited():
            return self.flashObject.as_setEditTarget(target)

    # ═════════════════════════════════════════════════════════
    # Flash → Python 回调（GFx 回退机制）
    # ═════════════════════════════════════════════════════════

    def onEditOffset(self, target, x, y):
        """接收 Flash 拖拽偏移回调。"""
        if _on_edit_offset_cb is not None:
            try:
                _on_edit_offset_cb(target, float(x), float(y))
            except Exception:
                logger.exception('onEditOffset 处理失败: target=%s', target)

    def onSubtitleCallback(self, cmd, rid, value):
        """接收 Flash SubtitleView 的回调，路由到 Manager。

        :param cmd:   "onReportHeight" | "onFadeOutDone"
        :param rid:   renderer ID（int）
        :param value: height（px）或 0（fade_out_done 时）
        """
        if _manager is None:
            return

        try:
            if cmd == 'onReportHeight':
                # 已废弃——所有策略使用固定高度
                pass
            elif cmd == 'onFadeOutDone':
                _manager.on_fade_out_done(rid)
        except Exception:
            logger.exception('onSubtitleCallback 处理失败: cmd=%s rid=%d', cmd, rid)


# ═════════════════════════════════════════════════════════════
# ViewSettings 注册
# ═════════════════════════════════════════════════════════════

def _getViewSettings():
    """返回 ViewSettings 元组。"""
    from gui.Scaleform.framework import ViewSettings, ScopeTemplates
    from frameworks.wulf import WindowLayer

    return (
        ViewSettings(
            VIEW_ALIAS,
            BattleSubtitleView,
            VIEW_SWF,
            WindowLayer.WINDOW,
            None,                         # 不自动触发——手动加载
            ScopeTemplates.GLOBAL_SCOPE,
        ),
    )


# ═════════════════════════════════════════════════════════════
# 公开 API（模块级函数）
# ═════════════════════════════════════════════════════════════

def init_subtitle():
    """注册字幕 View 设置（在 ACV init() 中调用一次）。"""
    from gui.Scaleform.framework import g_entitiesFactories

    for settings in _getViewSettings():
        g_entitiesFactories.addSettings(settings)
    logger.info('字幕 View 设置已注册')


def load_subtitle_view():
    """在当前 app 上下文中加载字幕 View（手动触发）。

    战斗→车库切换期间 lobby app 重建中，loadView 请求会被框架排队，
    不立即创建 View；loadView 返回时 _view_instance 可能仍为 None。
    """
    from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
    from gui.shared.personality import ServicesLocator

    global _view_instance, _load_in_progress

    if _load_in_progress:
        logger.info('字幕 View 加载已在进行，跳过本次请求')
        return
    _load_in_progress = True

    try:
        app = ServicesLocator.appLoader.getApp()
        if app is None:
            logger.warn('无法获取当前 app，字幕 View 加载失败')
            _load_in_progress = False
            return

        _view_instance = None  # 清除旧引用，等待 __init__ 回调
        app.loadView(SFViewLoadParams(VIEW_ALIAS))

        if _view_instance is not None:
            logger.info('字幕 View 已加载（通过 __init__ 回调）')
            _load_in_progress = False
            return

        logger.info('loadView 返回后 _view_instance 仍为 None，启动就绪轮询...')
        _poll_view_ready(0)  # 结束或超时时由 _poll_view_ready 复位 _load_in_progress
    except Exception:
        logger.exception('字幕 View 加载失败（SWF 是否已编译？）')
        _load_in_progress = False


def _poll_view_ready(attempt):
    """检查 _view_instance 是否已由 __init__ 回调设置。"""
    global _load_in_progress

    import BigWorld

    v = _view_instance
    if v is not None:
        logger.info('字幕 View 已就绪（loadView 后第 %d 次轮询）', attempt + 1)
        _load_in_progress = False
        return
    if attempt + 1 >= _LOAD_RETRY_COUNT:
        logger.warn('字幕 View 就绪轮询 %d 次仍无结果，放弃本次加载（下次 ensure 会重试）',
                    _LOAD_RETRY_COUNT)
        _load_in_progress = False
        return
    BigWorld.callback(_LOAD_RETRY_DELAY, lambda: _poll_view_ready(attempt + 1))


def ensure_subtitle_view():
    """确保字幕 View 在当前上下文中已加载（未加载或失效则重新创建）。

    从战斗返回车库后，旧 app 的 View 已随 app 销毁，但 _view_instance
    可能残留指向失效 SWF 的引用。通过 _isDAAPIInited() 检测 SWF 是否
    仍然可用：不可用时清空引用并重新加载。
    """
    global _view_instance
    logger.info('ensure_subtitle_view() 调用: _view_instance=%s', _view_instance)
    if _view_instance is not None:
        try:
            if _view_instance._isDAAPIInited():
                logger.info('字幕 View 已存在且 DAAPI 就绪，跳过加载')
                return
            else:
                logger.info('字幕 View 存在但 DAAPI 未就绪（SWF 可能已失效），重新加载')
                _view_instance = None
        except Exception:
            logger.exception('检测 View 状态失败，强制重新加载')
            _view_instance = None
    load_subtitle_view()


def destroy_subtitle_view():
    """销毁字幕 View（离开车库或战斗时调用）。"""
    global _view_instance

    if _view_instance is not None:
        try:
            _view_instance.destroy()
        except Exception:
            logger.exception('字幕 View 销毁异常')
        _view_instance = None


def update_subtitle_settings(settings):
    """运行时更新字幕设置（设置页改动后调用）。

    若策略类型发生变化 → clear() 旧 manager 并重建。

    重要：settings 可能是部分键（如只含 display_mode 或只含 subtitleUpdate）。
    重建 manager 时必须以配置文件为基底，再用传入 settings 覆盖，
    否则未传入的 key 会回退硬编码默认值，导致其他设置项"丢失"。
    """
    global _manager

    # ── 以配置文件为基底，传入 settings 覆盖 ──
    from autoconfigvoiceover.config import load_config
    se = load_config(log=False).get('settings', {})

    # 键名映射：config 用 subtitleDisplay，manager 用 display_mode
    display_mode = settings.get('display_mode')
    if display_mode is None:
        display_mode = se.get('subtitleDisplay', 'standard')
        if display_mode == 'simple':
            display_mode = 'concise'

    full_settings = {
        'display_mode':   display_mode,
        'subtitleUpdate': bool(settings.get('subtitleUpdate',
                                            se.get('subtitleUpdate', False))),
        'multiSub':       bool(settings.get('multiSub',
                                            se.get('multiSub', False))),
        'text_speed':     float(settings.get('text_speed',
                                             se.get('textSpeed', 0.03))),
        'subtitle_anim':  bool(settings.get('subtitle_anim',
                                            se.get('subtitleAnim', False))),
    }

    if _manager is not None:
        new_cls = _resolve_manager_class(full_settings)
        if not isinstance(_manager, new_cls):
            # 策略切换 —— 清空旧 manager，创建新 manager
            logger.info('策略切换: %s → %s',
                        type(_manager).__name__, new_cls.__name__)
            import autoconfigvoiceover.sound as sound
            sound.remove_marker_listener(_manager.on_marker)
            _manager.clear()
            _manager = None

    if _manager is None:
        # 重建 manager（首次初始化或策略切换后）
        from autoconfigvoiceover.voices.active_voice import g_active_mgr
        from .loader import load_style

        active = g_active_mgr.current
        if active is not None and not active.is_builtin:
            pack_root = active.pack.root
            style = load_style(pack_root)
            if style is not None:
                ManagerCls = _resolve_manager_class(full_settings)
                import autoconfigvoiceover.sound as sound

                _manager = ManagerCls(
                    pack_root, style, full_settings,
                    dispatcher=_dispatcher,
                )
                sound.add_marker_listener(_manager.on_marker)
                logger.info('字幕 Manager 已重建: %s', ManagerCls.__name__)
    else:
        _manager.update_settings(settings)


def update_subtitle_style(pack_root, style):
    """切换语音包时更新字幕样式并预加载新语音包的图片。

    Manager 尚未创建时（车库启动时活跃语音为非字幕语音包，
    View 加载阶段未建 Manager）→ 切到带字幕语音包后在此补建，
    否则车库试听不出字幕；已存在则仅更新样式。

    :param pack_root: 语音包 VFS 根目录
    :param style:     SubtitleStyle | None（无字幕语音包为 None）
    """
    global _preload_pending

    if _manager is not None:
        _manager.update_style(pack_root, style)
    elif style is not None:
        # 补建 Manager——内部已含样式图片预加载，直接返回避免重复
        _build_manager(pack_root, style)
        return

    # 新语音包 → 新图片 → 重新预加载
    if style is not None:
        from .loader import collect_style_images
        urls = collect_style_images(style)
        if urls:
            _preload_pending = urls
            _try_preload_images()
            logger.debug('语音包切换: 待预加载 %d 张样式图片', len(urls))


def reload_subtitle_offsets():
    """重新加载偏移文件（字幕位置编辑保存后调用）。"""
    if _manager is not None:
        _manager.reload_offsets()


def debug_fire_marker(marker_str):
    """调试：手动注入 marker 触发字幕管道。

    用法（车库/战斗中 Python 控制台）:
        from .host import debug_fire_marker
        debug_fire_marker("vo_some_sentence")

    marker 经 sound._on_wwise_marker 分发到所有监听器（含字幕 manager），
    与真实音频内嵌 marker 走完全相同的路径。
    """
    import autoconfigvoiceover.sound as sound
    sound._on_wwise_marker(str(marker_str))
