# coding=utf-8
"""ACV (AutoConfigVoiceover) — WoT 语音包 + 字幕管理 mod。

模块级只创建 Logger 和主控制器单例。
init() / fini() 由入口 mod_autoConfigVoiceOver 委托调用。
"""

import game
import Keys
from .logger import Logger, init_log
from gui import InputHandler
from gui.shared.utils.key_mapping import getBigworldNameFromKey

logger = Logger('init')

# ═════════════════════════════════════════════════════════════════
# 热键
# ═════════════════════════════════════════════════════════════════

# 映射表与缓存均在 init_hotkey() 中主动初始化，此后 _on_key_down
# 直接从缓存读取，不做任何文件 I/O。设置页修改热键后通过
# update_hotkey_config() 刷新缓存。
_hotkey_map = {}               # {热键名: BigWorld key 名}
_cached_hotkey_enabled = False # settings.hotkeyEnabled
_cached_hotkey_key = ''        # 对应 BigWorld key 名（空串=未就绪）


def init_hotkey():
    """初始化热键：加载映射表 + 从配置文件缓存当前热键设置。

    在 AutoConfigVoiceover.init() 早期调用（ensure_config_ready 之后），
    确保 hotkey.json 已就位。加载失败不阻断启动——功能降级为无热键。
    """
    global _hotkey_map, _cached_hotkey_enabled, _cached_hotkey_key
    try:
        from .config_init import load_user_json
        hotkey_list = load_user_json('hotkey.json')
        if hotkey_list:
            _hotkey_map = {}
            for entry in hotkey_list:
                if 'hotkey' in entry and 'keycode' in entry:
                    _hotkey_map[entry['hotkey']] = entry['keycode']
            logger.debug('热键映射表已加载: %d 个热键', len(_hotkey_map))
        else:
            logger.warn('hotkey.json 为空，无可配置热键')
    except Exception:
        logger.exception('热键映射表加载失败')

    _refresh_hotkey_cache()


def _refresh_hotkey_cache():
    """从配置文件重新读取热键设置到模块级缓存。"""
    global _cached_hotkey_enabled, _cached_hotkey_key
    try:
        from .config import load_config
        se = load_config(log=False).get('settings', {})
        _cached_hotkey_enabled = bool(se.get('hotkeyEnabled', False))
        hotkey_str = se.get('hotkey', 'F10')
        _cached_hotkey_key = _hotkey_map.get(hotkey_str, '')
        logger.debug('热键缓存已刷新: enabled=%s key=%s→%s',
                     _cached_hotkey_enabled, hotkey_str, _cached_hotkey_key or '(无)')
    except Exception:
        logger.exception('热键配置缓存刷新失败')


def update_hotkey_config():
    """设置页修改热键/启用状态后调用，刷新模块级缓存。

    由 settings_page.handle_hotkey / handle_checkbox('hotkeyEnabled')
    在 save_config 后调用，使修改立即生效无需重启。
    """
    _refresh_hotkey_cache()


def _on_key_down(event):
    """根据缓存的快捷键设置切换菜单显示/隐藏。

    缓存由 init_hotkey() 初始化、update_hotkey_config() 刷新，
    无需每次按键都读配置文件。
    """
    if not event.isKeyDown():
        return False
    if not _cached_hotkey_enabled:
        return False
    if not _cached_hotkey_key:
        return False

    key = getBigworldNameFromKey(event.key)
    if key == _cached_hotkey_key:
        logger.debug('热键触发')
        g_autoConfigVoiceOverMod._toggle_menu()
        return True

    return False


InputHandler.g_instance.onKeyDown += _on_key_down


class AutoConfigVoiceover(object):
    """Mod 主控制器。

    init() 中延迟 import 子模块，避免模块级代码触碰游戏 API。
    """

    def __init__(self):
        self._menu_manager = None
        self._is_mods_list_present = False
        self._original_game_handleKeyEvent = None

    # ── 公开接口（入口委托） ──

    def init(self):
        init_log()

        # ── 配置目录初始化：确保目录结构、config.json、资源副本就绪 ──
        #    必须在任何配置读取之前执行（纯净模式清除后自动重建）
        try:
            from .config_init import ensure_config_ready
            ensure_config_ready()
        except Exception:
            pass  # 初始化失败不阻断启动，后续读取配置时兜底

        # 尽早加载日志级别 + 全局启用标志，确保后续钩子安装前 _is_enabled 已就位
        try:
            from .config import load_config as _early_cfg, set_enabled as _set_enabled
            from .logger import set_log_level as _set_lv
            _ecfg = _early_cfg()
            _set_lv(_ecfg.get('settings', {}).get('logLevel', 2))
            _set_enabled(_ecfg.get('settings', {}).get('enabled', True))
        except Exception:
            pass  # 配置读取失败不影响启动

        # ── 热键：主动加载映射表并缓存设置，确保首次按键即生效 ──
        try:
            init_hotkey()
        except Exception:
            logger.exception('热键初始化失败')

        # ── 声音子系统：绑定 + 重映射钩子（尽早安装，确保在任何声音播放前生效）──
        try:
            from .sound import init as _sound_init
            _sound_init()
        except Exception:
            logger.exception('声音子系统初始化失败')

        # ── 消息通知：安装可点击链接钩子（在声音子系统之后、首次消息发送之前）──
        try:
            from .notifier import init as _notifier_init
            _notifier_init()
        except Exception:
            logger.exception('消息通知模块初始化失败')

        # ── 字幕系统：注册 View 设置（View 在进入战斗时由 battle 钩子加载）──
        try:
            from autoconfigvoiceover.subtitle.host import init_subtitle as _sub_init
            _sub_init()
        except Exception:
            logger.exception('字幕系统初始化失败')

        self._resolve_dependencies()

        if self._is_mods_list_present:
            self._register_mods_list()
        else:
            logger.warn('ModsListApi 不可用，跳过入口注册')

        # 语音包信息读取：第三方扫描 + 游戏内语音 + 本地化译名 + 历史合并
        # （防御在 repo.run() 内部，失败不阻断后续初始化）
        from .voices import g_voice_repo
        g_voice_repo.run()

        # 捕获游戏原始 default 模式的 voiceLanguage（override_default 用；
        # 必须在 sound_manager.register 缓存原始 modes 之前）
        from .voices import voice_switcher
        voice_switcher.capture_default_lang()

        # 第三方语音包注册进游戏声音模式表（内部防御，fini 时还原）
        from .voices import sound_manager
        sound_manager.register()

        # 内置语音的本地化名称写入游戏声音模式表 description，
        # 让游戏自带的声音设置菜单显示正确名称
        sound_manager.set_builtin_display_names(g_voice_repo.ingame_rows)

        # 根据用户设置控制语音在游戏声音菜单中的可见性
        # 禁用状态下强制隐藏已知语音包（default 不受影响）
        from .config import load_config as _cfg2, is_enabled as _ie2
        from .voices import voice_switcher as _vs
        _se2 = _cfg2().get('settings', {})
        if _ie2():
            _vs.apply_voice_visibility(
                show_ingame=_se2.get('showIngameVoices', False),
                show_outside=_se2.get('showInstalledVoices', False))
        else:
            _vs.apply_voice_visibility(
                show_ingame=False, show_outside=False)

        # 安装外部语音变化监测（在首次 switch_voice 之前，
        # 在 sound_manager.register 之后，确保所有模式已就位）
        _vs.init_monitoring()

        # 从持久化配置解析并记录用户选择的语音模式名，
        # 供 setMode 钩子守护（不调 switch_voice——避免 loading
        # 界面播放确认音和消息推送）。
        # 禁用状态下跳过——_current_resolved_mode 保持 'default'，
        # setMode 钩子不会拦截游戏对 default 的重置。
        from .config import load_config, is_enabled
        if is_enabled():
            voice_cfg = load_config().get('voice', {})
            saved_id = voice_cfg.get('currentVoiceId', 'default')
            type_idx = voice_cfg.get('typeIndex', 0)
            lang_idx = voice_cfg.get('langIndex', 0)
            if not voice_switcher.prepare_resolved_mode(saved_id, type_idx, lang_idx):
                logger.warn('上次选择的语音 %s 解析失败，守护 default', saved_id)
        else:
            logger.info('插件已禁用——跳过语音模式守护，setMode 钩子将直通')

        # 钩入 game.handleKeyEvent 拦截 ESC（比 InputHandler 更底层，
        # 游戏设置菜单由此派发，必须在此拦截才能阻止穿透）
        self._original_game_handleKeyEvent = game.handleKeyEvent
        game.handleKeyEvent = self._on_game_key_event

        from . import hooks  # noqa: F401 — import 即注册游戏生命周期回调
        logger.info('ACV 初始化完成')

    def fini(self):
        # 卸载声音钩子，恢复原始 WWISE 函数
        try:
            from .sound import fini as _sound_fini
            _sound_fini()
        except Exception:
            pass
        # 卸载消息通知钩子
        try:
            from .notifier import fini as _notifier_fini
            _notifier_fini()
        except Exception:
            pass
        # 销毁字幕视图（战斗中退出时清理）
        try:
            from autoconfigvoiceover.subtitle.host import destroy_subtitle_view
            destroy_subtitle_view()
        except Exception:
            pass
        # 卸载外部语音变化监测钩子
        try:
            from .voices import voice_switcher
            voice_switcher.fini_monitoring()
        except Exception:
            pass
        # 摘除注册的第三方语音模式，还原游戏声音模式表
        from .voices import sound_manager
        sound_manager.recover()
        # 恢复 game.handleKeyEvent 原始处理器
        if self._original_game_handleKeyEvent is not None:
            game.handleKeyEvent = self._original_game_handleKeyEvent
            self._original_game_handleKeyEvent = None
        if self._menu_manager is not None:
            self._menu_manager.destroy()
            self._menu_manager = None
        logger.info('ACV 已退出')

    def on_account_become_player(self):
        """进入账号后回调（入口 onAccountBecomePlayer 转发）。

        1. 若插件禁用 → 跳过语音恢复和通知，仅落盘 repo 数据
        2. 静默恢复语音设置（silent=True）——init() 中 prepare_resolved_mode
           已记录目标模式名，setMode 钩子自动拦截游戏登录/进战斗对 default
           的重置；此处仅补齐 ActiveVoice 激活 + gender + volume
        3. 发送语音包增减统计（SystemMessages）——排在欢迎消息上方
        4. 发送欢迎通知（SystemMessages）——_welcome_sent 守卫保证一次会话只发一次
        5. 语音包信息落盘——沿旧版惯例把文件写入推迟到登录后，
           避免拖慢客户端启动；repo 内部保证一次会话只写一次
        """
        from .voices import g_voice_repo
        from .config import load_config, is_enabled
        from .voices import voice_switcher

        if not is_enabled():
            logger.info('插件已禁用——跳过语音恢复和欢迎通知')
            g_voice_repo.save_all()
            return

        # ── 登录后静默恢复语音设置：setMode 钩子已自动拦截游戏对
        #     default 的重置，此处只做 ActiveVoice 激活 + gender +
        #     volume（silent=True 跳过确认音和消息推送）──
        voice_cfg = load_config().get('voice', {})
        saved_id = voice_cfg.get('currentVoiceId', 'default')
        type_idx = voice_cfg.get('typeIndex', 0)
        lang_idx = voice_cfg.get('langIndex', 0)

        if saved_id and saved_id != 'default':
            if not voice_switcher.switch_voice(saved_id, type_idx, lang_idx, silent=True):
                logger.warn('登录后恢复语音 %s 失败', saved_id)

        # ── 语音统计先发送（排在欢迎消息上方）──
        try:
            from .notifier import send_voice_stats
            send_voice_stats()
        except Exception:
            pass

        # 欢迎通知（在 save_all 之前：此时 repo 的 _saved_* 仍为
        # 上次会话的历史数据，compute_diff 可正确对比增减；但统计
        # 已在 init 阶段独立发送，此处仅发送欢迎消息）
        from .notifier import send_welcome
        se = load_config().get('settings', {})
        hotkey = se.get('hotkey', 'F10')
        hotkey_enabled = se.get('hotkeyEnabled', False)
        send_welcome(self._is_mods_list_present, hotkey, hotkey_enabled)

        g_voice_repo.save_all()

        # ── 字幕视图：在车库中加载（设置页拖拽 + 声音预览字幕）──
        try:
            import BigWorld
            from autoconfigvoiceover.subtitle.host import ensure_subtitle_view
            # 延迟到下一帧确保 lobby app 的 View 系统就绪
            logger.info('调度字幕 View 加载（0.5s 延迟）...')
            BigWorld.callback(0.5, ensure_subtitle_view)
            logger.info('字幕 View 加载已调度')
        except Exception:
            logger.exception('字幕视图车库加载失败')

    # ── 依赖检查 ──

    def _resolve_dependencies(self):
        """检查软依赖 ModsListApi 是否可用。"""
        try:
            from gui.modsListApi import g_modsListApi

            self._is_mods_list_present = g_modsListApi is not None
            if self._is_mods_list_present:
                logger.info('ModsListApi 可用')
        except ImportError:
            self._is_mods_list_present = False
            logger.warn('ModsListApi 未安装，车库入口按钮不可用')
        except Exception:
            self._is_mods_list_present = False
            logger.exception('ModsListApi 加载异常')

    # ── ModsList 注册 ──

    def _register_mods_list(self):
        """向 ModsListApi 注册车库底部入口按钮（幂等——同 id 重复注册走 updateModification）。

        名字/描述从词典读取（modslist/name、modslist/description），随生效语言变化；
        切语言后重调 refresh_mods_list_entry 即可更新弹窗里的显示
        （ModsListApi 对已存在 id 自动转 updateModification → setData → onListUpdated）。
        """
        from gui.modsListApi import g_modsListApi
        from ._metadata import MOD_ID
        from .constants import MODSLIST_RES_ICONS
        from . import l10n

        g_modsListApi.addModification(
            id=MOD_ID,
            name=l10n.text('modslist/name'),
            description=l10n.text('modslist/description'),
            icon=MODSLIST_RES_ICONS,
            enabled=True,
            login=False,
            lobby=True,
            callback=self._on_mods_list_click,
        )
        logger.info('已注册到 ModsList')

    def refresh_mods_list_entry(self):
        """语言变更后刷新 ModsList 入口名称/描述（幂等；ModsList 不可用时静默跳过）。

        供 settings_page.handle_ui_lang 在 l10n.reload() 后调用。
        """
        if not self._is_mods_list_present:
            return
        try:
            self._register_mods_list()
        except Exception:
            logger.exception('刷新 ModsList 入口失败')

    def _on_mods_list_click(self):
        """ModsList 按钮被点击 → 直接切换菜单。

        ModsList 内部已通过 BigWorld.callback(0, ...) 延迟到下一帧执行回调
        （见 download_mod_src/.../data.py:216），此时 popover 已关闭、
        View 状态已稳定。无需我们再做二次延迟。
        """
        logger.debug('ModsList 点击回调触发 → 直接 toggle')
        self._toggle_menu()

    def _toggle_menu(self):
        """实际执行菜单显示/隐藏切换（供 ModsList 回调和 F10 热键共用）。"""
        if self._menu_manager is None:
            from .menu import MenuManager
            self._menu_manager = MenuManager()
        self._menu_manager.toggle()

    def _on_game_key_event(self, event):
        """钩入 game.handleKeyEvent，拦截 ESC 防止穿透到游戏设置菜单。

        game.handleKeyEvent 是游戏设置菜单 ESC 的派发入口。
        InputHandler.onKeyDown 返回 True 无法阻止这条独立的派发链，
        必须在 game 层面拦截。（ModsSettingsAPI 同款做法）

        返回 True → 事件被消费，游戏设置菜单不弹出。
        返回 _original_game_handleKeyEvent(event) → 正常派发。
        """
        if (event.key == Keys.KEY_ESCAPE
                and self._menu_manager is not None
                and self._menu_manager.is_visible()):
            self._menu_manager.collapse_and_hide()
            return True
        return self._original_game_handleKeyEvent(event)


# 模块级单例 —— 入口 mod_*.py 通过它访问主控制器
g_autoConfigVoiceOverMod = AutoConfigVoiceover()
