# coding=utf-8
"""ACV 设置菜单 —— Flash View 的 Python 侧管理。

设计要点:
  - 不依赖 app.loadView() 的返回值（经验证它返回 None）
  - 在 ACVMenuMeta.__init__() 中自行保存 View 引用到模块级变量
  - toggle() 经 as_setVisibleS 由 AS3 自行切换 visible，不做额外的状态追踪
    （★ 不能从 Python 直接写 flashObject.visible——会切断 Flash→Python
    的 DAAPI 回调通道，onLog 等全部失联）
"""

import BigWorld
from .logger import Logger

logger = Logger('Menu')
_flash_log = Logger('Flash')

# ═════════════════════════════════════════════════════════════
# View 注册标识符
# ═════════════════════════════════════════════════════════════

VIEW_ALIAS = 'autoConfigVoiceOverMenu'
VIEW_SWF = 'autoConfigVoiceOverMenu.swf'

# ═════════════════════════════════════════════════════════════
# 模块级 View 引用（使用注入器模式，文档类当壳，子元件当内容）
# ═════════════════════════════════════════════════════════════

_view_instance = None           # 由 ACVMenuMeta.__init__() 设置
_menu_manager = None            # 由 MenuManager.__init__() 设置，供 onLog 回调使用
_voice_switch_page = None       # VoiceSwitchPage 实例，MenuManager 懒初始化
_settings_page = None           # SettingsPage 实例，MenuManager 懒初始化
_help_page = None               # HelpPage 实例，MenuManager 懒初始化
_voice_pack_detail_page = None  # VoicePackDetailPage 实例，MenuManager 懒初始化
_personal_settings_page = None  # PersonalSettingsPage 实例，MenuManager 懒初始化
_subtitle_settings_page = None  # SubtitleSettingsPage 实例，MenuManager 懒初始化


def _clear_view():
    """清除 View 引用及所有页面单例（_dispose 时调用）。

    WoT 在车库↔战斗切换时会销毁并重建 View。页面单例持有
    对旧 View 的 _meta 引用，必须一并清除，否则 push_data()
    会推送到已销毁的 Flash 对象上，导致组件接收不到数据。
    """
    global _view_instance
    global _voice_switch_page, _settings_page, _help_page
    global _voice_pack_detail_page, _personal_settings_page
    global _subtitle_settings_page
    _view_instance = None
    _voice_switch_page = None
    _settings_page = None
    _help_page = None
    _voice_pack_detail_page = None
    _personal_settings_page = None
    _subtitle_settings_page = None
    logger.debug('View 引用及页面单例已清除')


# 语音包自定义图片 → images dict 键名映射
# 图标方案（bgIcon 下拉控制）仅含 5 张：panel/page/settings/voice/help。
# menu.png（bigCircle 大圆）不属图标方案，见 _MENU_BIG_CIRCLE_MAP。
_VOICE_PACK_IMAGE_MAP = [
    # (vfs_rel_path,              image_key,       sub_index)
    ('bgimgs/panel.png',          'semiPanel',     None),  # 半折叠面板背景
    ('bgimgs/page.png',           'fullPanel',     None),  # 全展开面板背景
    ('icons/settings.png',        'smallCircles',  0),     # 设置图标
    ('icons/voice.png',           'smallCircles',  1),     # 语音图标
    ('icons/help.png',            'smallCircles',  2),     # 帮助图标
]

# 大圆 menu.png：独立于图标方案，始终跟随当前活跃语音包
_MENU_BIG_CIRCLE_MAP = [
    ('bgimgs/menu.png', 'bigCircle', None),  # 大圆
]


def _override_with_voice_pack_images(images):
    """若当前活跃语音包 VFS 中有自定义图片，覆盖图标方案 5 个槽位。

    仅覆盖图标方案：半折叠背景、全展开背景、设置/语音/帮助图标。
    大圆 menu.png 不在图标方案内，由 _apply_active_pack_menu_image 单独处理。
    用于菜单初次加载和语音切换后刷新全部图片。
    """
    from autoconfigvoiceover.voices import g_active_mgr
    active = g_active_mgr.current
    if active is None or active.is_builtin:
        return
    _override_with_pack_images(active.pack, images, _VOICE_PACK_IMAGE_MAP)


def _apply_active_pack_menu_image(images):
    """覆盖 bigCircle（menu.png）：始终跟随当前活跃语音包。

    与图标方案（bgIcon）无关：无论用户选择哪种图标方案，大圆图片都取
    活跃语音包的 bgimgs/menu.png；若活跃包不含 menu.png 或为内置语音，
    则保持磁盘默认图片。
    """
    from autoconfigvoiceover.voices import g_active_mgr
    active = g_active_mgr.current
    if active is None or active.is_builtin:
        return
    _override_with_pack_images(active.pack, images, _MENU_BIG_CIRCLE_MAP)


def _override_with_pack_images(pack, images, image_map):
    """用指定语音包的 VFS 自定义图片覆盖 images dict 中对应槽位。

    与 _override_with_voice_pack_images 相同的覆盖逻辑，
    但接受显式 pack 参数，不依赖 g_active_mgr.current。
    供 SettingsPage.resolve_bg_icon 等需要针对非活跃语音包操作时调用。

    :param pack:       PackInfo 实例
    :param images:     get_default_menu_images() 返回的 dict
    :param image_map:  _VOICE_PACK_IMAGE_MAP 格式的映射列表
    """
    try:
        import ResMgr

        root = pack.root
        for vfs_rel, key, idx in image_map:
            vfs_path = root + vfs_rel
            if not ResMgr.isFile(vfs_path):
                continue

            # Flash ImageCache 从 res/gui/flash/ 加载，
            # ../../ + VFS 路径 = res/mods/voiceover/.../bgimgs/xxx.png
            path = '../../' + vfs_path
            # ★ GFx 需要 unicode 字符串
            if isinstance(path, str):
                path = path.decode('utf-8')

            if idx is not None:
                images[key][idx] = path
            else:
                images[key] = path
            logger.debug('语音包自定义图片: %s → %s', vfs_rel, key)
    except Exception:
        logger.exception('覆盖语音包自定义图片失败')


def _resolve_menu_images(bg_icon_token=None):
    """根据背景图标设置解析菜单图片 dict。

    bg_icon_token 为 None 时从配置文件读取 'bgIcon'。
    供菜单初次加载和语音切换后刷新全部图片使用，保证图片显示
    与用户选择的背景图标方案一致（而不是总是跟随当前语音包）。

    图标方案（bgIcon）仅决定 5 张图：半折叠背景、全展开背景、
    设置/语音/帮助图标。大圆 menu.png 独立于图标方案，
    始终跟随当前活跃语音包（见 _apply_active_pack_menu_image）。

    :param bg_icon_token: BGICON_DEFAULT_TOKEN / FOLLOW_PACK_TOKEN /
                          语音包 pack_id（稳定身份）；None → 读配置
    :return: get_default_menu_images() 结构
    """
    from .config import load_config
    from autoconfigvoiceover.voices import g_voice_repo
    from autoconfigvoiceover.pages.settings_page import (
        BGICON_DEFAULT_TOKEN, FOLLOW_PACK_TOKEN)

    if bg_icon_token is None:
        bg_icon_token = load_config().get('settings', {}).get(
            'bgIcon', BGICON_DEFAULT_TOKEN)

    from .config_init import get_default_menu_images
    images = get_default_menu_images()

    if bg_icon_token == BGICON_DEFAULT_TOKEN:
        # 5 张图标方案图保持磁盘默认
        pass
    elif bg_icon_token == FOLLOW_PACK_TOKEN:
        _override_with_voice_pack_images(images)
    else:
        # 按 pack_id 查找（稳定身份，不依赖可改名的显示名）
        pack = g_voice_repo.get_pack(bg_icon_token)
        if pack is not None:
            _override_with_pack_images(pack, images, _VOICE_PACK_IMAGE_MAP)
        else:
            logger.warn('未知背景图标方案: %s，保持默认', bg_icon_token)

    # 大圆 menu.png 独立于图标方案：始终跟随当前活跃语音包
    _apply_active_pack_menu_image(images)
    return images


def refresh_voice_pack_ui():
    """语音切换后刷新语音包相关的 UI：图片 + 详情页。

    由 VoiceSwitchPage.handle_voice_select 和 onLog(toggle) 调用。
    将当前活跃语音包的自定义图片推送到 Flash，并刷新详情页 HTML。
    """
    global _view_instance, _menu_manager

    if _view_instance is None:
        return

    # ── 刷新全部菜单图片（按用户选择的背景图标方案）──
    try:
        if _settings_page is not None:
            images = _resolve_menu_images(_settings_page._bg_icon)
        else:
            images = _resolve_menu_images()
        _view_instance.as_setImagesS(images)
        logger.debug('语音切换后已刷新菜单图片')
    except Exception:
        logger.exception('刷新菜单图片失败')

    # ── 刷新详情页 ──
    if _menu_manager is not None:
        try:
            vpd = _menu_manager._get_voice_pack_detail_page()
            if vpd is not None:
                vpd.push_data()
                logger.debug('语音切换后已刷新详情页')
        except Exception:
            logger.exception('刷新详情页失败')


# ═════════════════════════════════════════════════════════════
# DAAPI Meta 桥接层
# ═════════════════════════════════════════════════════════════

from gui.Scaleform.framework.entities.View import View


class ACVMenuMeta(View):
    """Python ↔ Flash 通信的 DAAPI 桥接。

    __init__() 中将自身保存到模块级 _view_instance，
    供 MenuManager 获取引用（绕过 loadView() 返回 None 的问题）。

    公开方法命名规则:
      as_xxxS   — Python → Flash（通过 flashObject.as_xxx 调用）
      onXxx     — Flash → Python 回调桩
    """

    def __init__(self, ctx=None):
        global _view_instance
        super(ACVMenuMeta, self).__init__()
        _view_instance = self
        logger.debug('ACVMenuMeta.__init__() — View 实例已捕获')

    # — Python → Flash —

    def as_setConfigS(self, config_json):
        """向 Flash 推送配置数据。"""
        if self._isDAAPIInited():
            return self.flashObject.as_setConfig(config_json)

    def as_setLabelsS(self, labels):
        """向 Flash 推送 UI 标签 dict（i18n 词典，切语言后重推）。

        Flash 端 L10n.setLabels 存入词典并刷新所有已注册页面/组件。
        """
        if self._isDAAPIInited():
            return self.flashObject.as_setLabels(labels)

    def as_populateSettingsS(self, data):
        """向 Flash 推送设置页组件数据（下拉列表项、图标、Tooltip 等）。"""
        if self._isDAAPIInited():
            return self.flashObject.as_populateSettings(data)

    def as_populateVoiceSwitchesS(self, data):
        """向 Flash 推送语音切换页数据（语音包列表、音量、试听事件等）。"""
        if self._isDAAPIInited():
            return self.flashObject.as_populateVoiceSwitches(data)

    def as_populatePageS(self, pageId, data):
        """向 Flash 推送 HTML 内容页数据（帮助页、语音包详情页等）。"""
        if self._isDAAPIInited():
            return self.flashObject.as_populatePage(pageId, data)

    def as_applyThemeS(self, theme_data):
        """运行时切换主题色板。所有已注册组件立即重绘。

        theme_data 为 dict，只更新传入的键，未传的保留当前值。
        例: _view_instance.as_applyThemeS({'accent': 0xFF6B6B, 'surface0': 0x1A1A2E})
        """
        if self._isDAAPIInited():
            return self.flashObject.as_applyTheme(theme_data)

    def as_setImagesS(self, data):
        """运行时挂载/替换菜单组件图片（与主题换肤同理，只处理传入的键）。

        data 为 dict，可选键:
          bigCircle:    大圆图片路径（str）
          semiPanel:    半折叠圆角面板背景图（str）
          fullPanel:    全展开直角面板背景图（str）
          smallCircles: 三个小圆的图片路径 list [设置, 语音, 帮助]
        路径相对 res/gui/flash/（见 constants.MOD_RES_FLASH_ICON_DIR）。
        值为空字符串 = 清除图片恢复默认；加载失败 = 保持默认外观。
        """
        if self._isDAAPIInited():
            return self.flashObject.as_setImages(data)

    def as_flipBigCircleS(self, newImagePath=None):
        """触发大圆 2D 翻转（绕圆心竖直轴压扁再展开）。

        启用/禁用插件、切换语音包时调用。
        :param newImagePath: 可选——翻转中点替换的新图片 Flash 路径
        """
        if self._isDAAPIInited():
            if newImagePath:
                return self.flashObject.as_flipBigCircle(newImagePath)
            else:
                return self.flashObject.as_flipBigCircle()

    def as_populatePersonalSettingsS(self, data):
        """向 Flash 推送个性设置页数据（被点亮喊话、快捷消息替换等）。"""
        if self._isDAAPIInited():
            return self.flashObject.as_populatePersonalSettings(data)

    def as_populateSubtitleSettingsS(self, data):
        """向 Flash 推送字幕设置页数据（标题 Tooltip 等）。"""
        if self._isDAAPIInited():
            return self.flashObject.as_populateSubtitleSettings(data)

    def as_notifyHiddenS(self):
        """通知 Flash 菜单即将被隐藏（F10/ModsList 切换，as_setVisibleS(False) 前）。

        这种隐藏不走 Flash 侧折叠动画，页面感知不到——需主动通知
        让当前页执行 hide() 生命周期（如字幕设置页编辑中自动保存）。
        """
        if self._isDAAPIInited():
            return self.flashObject.as_notifyHidden()

    def as_setVisibleS(self, visible):
        """显隐整个菜单视图（F10 热键 / ModsList 入口切换）。

        ★ 不要从 Python 直接写 flashObject.visible——经实测该操作会
        切断 Flash → Python 的 DAAPI 回调通道（onLog 等全部失联），
        WG 官方代码也从不这样做。必须经 DAAPI 让 AS3 自己设置 visible。
        GFx 无法序列化 Python bool，传 1/0。
        """
        if self._isDAAPIInited():
            return self.flashObject.as_setVisible(1 if visible else 0)

    def as_collapseAndHideS(self):
        """ESC 触发：折叠菜单并隐藏视图。

        Flash 端折叠动画完成后会通过 onLog("menuHidden") 回调
        通知 Python 更新状态。
        """
        if self._isDAAPIInited():
            return self.flashObject.as_collapseAndHide()

    def as_setInitialStateS(self, data):
        """推送上次保存的位置和页面状态（跨会话恢复）。

        Flash 端直接设置可见性和位置，不走动画。
        """
        if self._isDAAPIInited():
            return self.flashObject.as_setInitialState(data)

    def as_setTitleTextS(self, text):
        """更新半折叠面板标题文本为当前语音包显示名称。"""
        if self._isDAAPIInited():
            return self.flashObject.as_setTitleText(text)

    def as_setSubtitleAvailableS(self, available):
        """通知 Flash 当前语音包是否有字幕样式 JSON。

        Flash 端会据此显示/隐藏半折叠面板的"字幕"按钮；
        若当前正在字幕设置页且 available=False，会自动切到帮助页。

        ★ GFx 无法序列化 Python bool，传 1/0。
        """
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_setSubtitleAvailable(1 if available else 0)
            except AttributeError:
                logger.warn('as_setSubtitleAvailable: DAAPI 方法未就绪')

    # — Flash → Python 回调桩 —

    # ═════════════════════════════════════════════════════════════
    # ★ 主界面走的与 Python 绑定的独立回调方案，而功能页面的信号却走
    #   "字符串信号量"单通道，这是因为：
    #
    #   1. byd 的 DAAPI 对我们的文档类 swf 限制很大（继承 AbstractView 类）
    #      当时跟 DeepSeek 讨论后最终也没改用 Adobe Animate，算我很能赤石了
    #      6 个功能页面（如SettingsPage 等）是 Flash 端 new 出来的子组件。
    #      GFx 不支持在 new 对象上设置 script 属性——DAAPI 的
    #      movieClip.script = self 在它们身上静默失败，而 Python 回调
    #      绑定正是靠 script 查找实现的。因此页面信号只能经 onAction
    #      上报给有 script 的文档类 MenuView（onPopulate 中
    #      _pages[x].onAction = this.onLog），再经 MenuView.onLog 到 Python。
    #
    #   2. 使用 "前缀,参数" 的字符串协议省事
    #   3. 可以复用日志回传通道
    #
    #   代价：无类型安全（前缀拼错静默失效）、分发集中在一个入口。
    #   因此这里用"前缀 → handler"注册表集中管理信号清单：
    #     - 新增信号 = 加一个 handler 方法 + 注册表一行，不改分发主流程
    #     - 每个 handler 独立异常边界，一个信号失败不影响其它信号
    # ═════════════════════════════════════════════════════════════

    _SIGNAL_HANDLERS = {
        # ── 特殊信号（无参数，精确前缀）──
        '__menuReady__':      '_on_menu_ready',       # Flash 就绪 → 推送全部页面数据
        'menuHidden':         '_on_menu_hidden',      # ESC 折叠完成 → 同步隐藏状态
        'toggle':             '_on_toggle',           # 半折叠面板总开关
        # ── 语音切换页 ──
        'voiceSelect':        '_handle_voice_select',
        'volumeChange':       '_handle_volume_change',
        'preview':            '_handle_preview',
        'changeType':         '_handle_change_type',
        'changeLang':         '_handle_change_lang',
        # ── 设置页 ──
        'nationVoiceGender':  '_handle_nation_voice_gender',
        'notifyPush':         '_handle_notify_push',
        'checkbox':           '_handle_checkbox',
        'hotkey':             '_handle_hotkey',
        'logLevel':           '_handle_log_level',
        'subtitleDisplay':    '_handle_subtitle_display',
        'textSpeed':          '_handle_text_speed',
        'colorScheme':        '_handle_color_scheme',
        'bgIcon':             '_handle_bg_icon',
        'titleTextMode':      '_handle_title_text_mode',
        'titleTextColor':     '_handle_title_text_color',
        'uiLang':             '_handle_ui_lang',
        # ── HTML 内容页 ──
        'htmlLink':           '_handle_html_link',
        # ── 个性设置页 ──
        'spottedMsg':         '_handle_spotted_msg',
        'spottedAliveLe':     '_handle_spotted_alive_le',
        'replaceSelect':      '_handle_replace_select',
        'replaceText':        '_handle_replace_text',
        # ── 字幕设置页 ──
        'subtitleEditStart':  '_handle_subtitle_edit_start',
        'subtitleEditTarget': '_handle_subtitle_edit_target',
        'subtitleEditSave':   '_handle_subtitle_edit_save',
        'subtitleEditReset':  '_handle_subtitle_edit_reset',
    }

    def onLog(self, msg):
        """接收 Flash 端信号量（日志 + 功能面板信号），写入 script.log 并分发。

        信号清单见 _SIGNAL_HANDLERS 的 keys——两者必须保持同步。
        Flash 端经 Log.setPythonLogger / 页面 onAction 都汇到本通道
        （为什么用单通道见上方注释）。
        """
        _flash_log.raw(msg)

        if _menu_manager is None:
            return

        prefix = msg.split(',', 1)[0]
        handler = self._SIGNAL_HANDLERS.get(prefix)
        if handler is None:
            return  # 未知信号——保持静默

        try:
            getattr(self, handler)(msg)
        except Exception:
            logger.exception('信号 %r 处理异常 (msg=%r)', prefix, msg)

    # ── 信号处理辅助 ──

    @staticmethod
    def _arg(msg):
        """'prefix,value' → 'value'；无逗号时返回原串。"""
        return msg.split(',', 1)[1] if ',' in msg else msg

    # ── 特殊信号 ──

    def _on_menu_ready(self, msg):
        """Flash MenuView 完成 onPopulate，可以安全推送页面数据。"""
        _ = msg  # 无参信号——msg 仅供统一分发接口的参数位
        logger.info('收到 Flash 就绪信号，开始推送设置数据')
        _menu_manager._push_settings_data()

    def _on_menu_hidden(self, msg):
        """ESC 折叠完成，Flash 已自设 visible=False，同步 Python 状态。"""
        _ = msg  # 无参信号——msg 仅供统一分发接口的参数位
        _menu_manager._visible = False
        logger.debug('Flash 确认视图已隐藏，状态同步')

    def _on_toggle(self, msg):
        """半折叠面板总开关：启用/禁用插件（触发大圆翻转）。"""
        enabled = (self._arg(msg) == 'enabled')
        logger.info('插件%s', '启用' if enabled else '禁用')

        from .config import save_config, load_config, set_enabled
        from autoconfigvoiceover.voices import voice_switcher as _vs2
        from .sound import (
            g_remapping_engine, g_binding_engine,
            _install_remapping_hooks, _uninstall_remapping_hooks,
        )

        set_enabled(enabled)
        _cfg = load_config()
        _se = _cfg.get('settings', {})

        if enabled:
            # ── 启用：先装回声音钩子 → 恢复语音可见性 → 切回上次语音 → 开启引擎 ──
            try:
                _install_remapping_hooks()
            except Exception:
                logger.exception('启用时重装声音钩子失败')

            _vs2.apply_voice_visibility(
                show_ingame=_se.get('showIngameVoices', False),
                show_outside=_se.get('showInstalledVoices', False))

            vo = _cfg.get('voice', {})
            saved_id = vo.get('currentVoiceId', 'default')
            type_idx = vo.get('typeIndex', 0)
            lang_idx = vo.get('langIndex', 0)
            if saved_id and saved_id != 'default':
                _vs2.switch_voice(saved_id, type_idx, lang_idx, silent=True)
                logger.info('启用：已恢复语音 %s', saved_id)
            else:
                _vs2.switch_voice('default', silent=True)
                logger.info('启用：无历史语音，保持 default')

            # 按用户开关恢复声音引擎
            g_remapping_engine.set_enabled(_se.get('soundRemap', True))
            g_binding_engine.set_enabled(_se.get('soundBind', True))
        else:
            # ── 禁用：切回 default → 隐藏已知语音包 → 关闭引擎 → 卸载钩子 ──
            _vs2.switch_voice('default', silent=True)
            _vs2.apply_voice_visibility(
                show_ingame=False, show_outside=False)

            # 关闭声音引擎
            g_remapping_engine.set_enabled(False)
            g_binding_engine.set_enabled(False)

            # 卸载 WWISE 钩子，恢复原始 C++ 函数
            try:
                _uninstall_remapping_hooks()
            except Exception:
                logger.exception('禁用时卸载声音钩子失败')

            logger.info('禁用：已切回 default，声音引擎已关闭，钩子已卸载')

        save_config({'settings': {'enabled': enabled}})
        # 大圆翻转动画
        self.as_flipBigCircleS()
        # 刷新语音包相关的全部 UI（图片 + 详情页）
        if enabled:
            refresh_voice_pack_ui()

        # 启用/禁用通知（用户可见文本走词典）
        try:
            from .notifier import send_message
            from . import l10n
            if enabled:
                send_message(l10n.text('notify/enabled'))
            else:
                send_message(l10n.text('notify/disabled'))
        except Exception:
            logger.exception('发送启用/禁用通知失败')

    # ── 语音切换页信号 ──

    def _handle_voice_select(self, msg):
        page = _menu_manager._get_voice_switch_page()
        if page is not None:
            page.handle_voice_select(self._arg(msg))

    def _handle_volume_change(self, msg):
        page = _menu_manager._get_voice_switch_page()
        if page is not None:
            page.handle_volume_change(int(self._arg(msg)))

    def _handle_preview(self, msg):
        page = _menu_manager._get_voice_switch_page()
        if page is not None:
            page.handle_preview(self._arg(msg))

    def _handle_change_type(self, msg):
        page = _menu_manager._get_voice_switch_page()
        if page is not None:
            page.handle_change_type(self._arg(msg))

    def _handle_change_lang(self, msg):
        page = _menu_manager._get_voice_switch_page()
        if page is not None:
            page.handle_change_lang(self._arg(msg))

    # ── 设置页信号 ──

    def _handle_nation_voice_gender(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_nation_voice_gender(self._arg(msg))

    def _handle_notify_push(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_notify_push(self._arg(msg))

    def _handle_checkbox(self, msg):
        """格式: checkbox,<key>,<0|1> —— 多段参数，单独解析。"""
        page = _menu_manager._get_settings_page()
        if page is not None:
            parts = msg.split(',')
            if len(parts) >= 3:
                page.handle_checkbox(parts[1], parts[2])

    def _handle_hotkey(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_hotkey(self._arg(msg))

    def _handle_log_level(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_log_level(self._arg(msg))

    def _handle_subtitle_display(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_subtitle_display(self._arg(msg))

    def _handle_text_speed(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_text_speed(self._arg(msg))

    def _handle_color_scheme(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_color_scheme(self._arg(msg))

    def _handle_bg_icon(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_bg_icon(self._arg(msg))

    def _handle_title_text_mode(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_title_text_mode(self._arg(msg))

    def _handle_title_text_color(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_title_text_color(self._arg(msg))

    def _handle_ui_lang(self, msg):
        page = _menu_manager._get_settings_page()
        if page is not None:
            page.handle_ui_lang(self._arg(msg))

    # ── HTML 内容页信号 ──

    def _handle_html_link(self, msg):
        """格式: htmlLink,<pageId>,<payload> —— 按 pageId 二次分发。"""
        parts = msg.split(',', 2)
        if len(parts) < 3:
            return
        page_id, payload = parts[1], parts[2]
        if page_id == 'help':
            page = _menu_manager._get_help_page()
            if page is not None:
                page.handle_link(payload)
        elif page_id == 'voicePackDetail':
            page = _menu_manager._get_voice_pack_detail_page()
            if page is not None:
                page.handle_link(payload)

    # ── 个性设置页信号 ──

    def _handle_spotted_msg(self, msg):
        page = _menu_manager._get_personal_settings_page()
        if page is not None:
            page.handle_spotted_msg(self._arg(msg))

    def _handle_spotted_alive_le(self, msg):
        page = _menu_manager._get_personal_settings_page()
        if page is not None:
            page.handle_spotted_alive_le(self._arg(msg))

    def _handle_replace_select(self, msg):
        page = _menu_manager._get_personal_settings_page()
        if page is not None:
            page.handle_replace_select(self._arg(msg))

    def _handle_replace_text(self, msg):
        page = _menu_manager._get_personal_settings_page()
        if page is not None:
            page.handle_replace_text(self._arg(msg))

    # ── 字幕设置页信号 ──

    def _handle_subtitle_edit_start(self, msg):
        _ = msg  # 无参信号——msg 仅供统一分发接口的参数位
        page = _menu_manager._get_subtitle_settings_page()
        if page is not None:
            page.handle_edit_start()

    def _handle_subtitle_edit_target(self, msg):
        page = _menu_manager._get_subtitle_settings_page()
        if page is not None:
            page.handle_edit_target(self._arg(msg))

    def _handle_subtitle_edit_save(self, msg):
        page = _menu_manager._get_subtitle_settings_page()
        if page is not None:
            page.handle_save(self._arg(msg))

    def _handle_subtitle_edit_reset(self, msg):
        _ = msg  # 无参信号——msg 仅供统一分发接口的参数位
        page = _menu_manager._get_subtitle_settings_page()
        if page is not None:
            page.handle_reset()

    def onCloseMenu(self):
        self._printOverrideError('onCloseMenu')

    def onRequestConfig(self):
        self._printOverrideError('onRequestConfig')

    def onSavePosition(self, normX, normY):
        """Flash 端拖拽松手后回调，保存菜单位置到配置文件。"""
        from .config import save_config
        try:
            save_config({
                'position': {
                    'normX': float(normX),
                    'normY': float(normY),
                },
            })
            logger.debug('位置已保存: normX=%.3f, normY=%.3f', normX, normY)
        except Exception:
            logger.exception('保存位置到配置文件失败')

    def onSaveState(self, stateJson):
        """Flash 端展开/收起/页面切换后回调，保存状态到配置文件。"""
        import json as _json
        from .config import save_config
        try:
            state = _json.loads(str(stateJson))
            save_config({'lastState': state})
            logger.debug('状态已保存: %s', state.get('state', '?'))
        except Exception:
            logger.exception('保存状态到配置文件失败')

    # — 生命周期追踪 —

    def _dispose(self):
        """WoT 框架销毁此 View 时调用。"""
        logger.debug('ACVMenuMeta._dispose() — View 被框架销毁')

        # 兜底：编辑中被销毁（车库↔战斗切换）时，Flash 侧 dispose 链路
        # （onAction→DAAPI）可能已断开——由 Python 侧基于镜像状态直接保存。
        if _subtitle_settings_page is not None:
            try:
                _subtitle_settings_page.ensure_saved('dispose')
            except Exception:
                logger.exception('字幕设置兜底保存失败')

        _clear_view()
        super(ACVMenuMeta, self)._dispose()


# ═════════════════════════════════════════════════════════════
# ViewSettings 注册（模块 import 即执行）
# ═════════════════════════════════════════════════════════════

from gui.Scaleform.framework import ViewSettings, g_entitiesFactories, ScopeTemplates
from frameworks.wulf import WindowLayer


def _getViewSettings():
    return (
        ViewSettings(
            VIEW_ALIAS,
            ACVMenuMeta,
            VIEW_SWF,
            WindowLayer.WINDOW,
            None,                          # event — 无自动触发
            ScopeTemplates.GLOBAL_SCOPE,
        ),
    )


for _vs in _getViewSettings():
    try:
        g_entitiesFactories.addSettings(_vs)
    except Exception:
        logger.debug('View 已注册（跳过重复）: %s', VIEW_ALIAS)
    else:
        logger.debug('View 已注册: %s → %s', VIEW_ALIAS, VIEW_SWF)


# ═════════════════════════════════════════════════════════════
# 辅助函数
# ═════════════════════════════════════════════════════════════

from helpers import dependency
from skeletons.gui.impl import IGuiLoader


@dependency.replace_none_kwargs(guiLoader=IGuiLoader)
def _getParentWindow(guiLoader=None):
    """获取当前主窗口，用作 View 的 parent。"""
    if guiLoader and guiLoader.windowsManager:
        return guiLoader.windowsManager.getMainWindow()
    return None


# ═════════════════════════════════════════════════════════════
# MenuManager —— testWindow 模式
# ═════════════════════════════════════════════════════════════

from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.shared.personality import ServicesLocator


class MenuManager(object):
    """菜单窗口管理 —— 参照 testWindow 的极简模式。

    不区分 show/hide，只提供 toggle():
      - View 不存在 → loadView 创建（通过 __init__ 回调获取引用）
      - View 存在   → as_setVisibleS 让 AS3 自行切换 visible
        （不能直接写 flashObject.visible，会切断 Flash→Python 回调）
    """

    def __init__(self):
        global _menu_manager
        _menu_manager = self
        self._visible = False  # 当前 flashObject.visible 状态
        self._push_retries = 0

    # ── 公开方法 ──

    def toggle(self):
        """切换显示/隐藏。"""
        global _view_instance

        if _view_instance is None:
            # View 不存在 → 创建前纠正外部语音变化
            try:
                from autoconfigvoiceover.voices.voice_switcher import ensure_voice_consistency
                ensure_voice_consistency()
            except Exception:
                pass
            self._create()
            if _view_instance is not None:
                self._visible = True  # 新 View 默认可见
                logger.debug('toggle(): View 已创建，默认可见')
            else:
                logger.warn('toggle(): View 创建失败')
            return

        # View 存在 → 切换可见性（经 DAAPI 让 AS3 自己设 visible，
        # 直接写 flashObject.visible 会切断 Flash→Python 回调通道）
        self._visible = not self._visible
        if self._visible:
            # 即将显示 → 纠正外部语音变化（车库试听/游戏菜单修改）
            try:
                from autoconfigvoiceover.voices.voice_switcher import ensure_voice_consistency
                ensure_voice_consistency()
            except Exception:
                pass
        try:
            if not self._visible:
                # 即将隐藏——先通知当前页执行 hide() 生命周期
                # （如字幕设置页编辑中自动保存）
                _view_instance.as_notifyHiddenS()
            if not _view_instance._isDAAPIInited():
                raise Exception('DAAPI 未就绪')
            _view_instance.as_setVisibleS(self._visible)
            logger.debug('toggle(): visible=%s', self._visible)
        except Exception:
            logger.debug('toggle(): flashObject 不可用，View 已死')
            _clear_view()
            self._visible = False

    def destroy(self):
        """销毁 View。"""
        global _view_instance
        if _view_instance is not None:
            try:
                _view_instance.destroy()
            except Exception:
                logger.exception('销毁菜单 View 时出错')
        _clear_view()
        self._visible = False

    def collapse_and_hide(self):
        """ESC 关闭：折叠菜单动画 + 隐藏视图。

        与 toggle() 不同：toggle 保持展开状态，collapse_and_hide
        强制回到全折叠态再隐藏，视觉上等同于"窗口被销毁"。
        """
        global _view_instance
        if _view_instance is None:
            logger.debug('collapse_and_hide: View 不存在，跳过')
            return
        if not self._visible:
            logger.debug('collapse_and_hide: 菜单已隐藏，跳过')
            return

        self._visible = False
        try:
            _view_instance.as_collapseAndHideS()
            logger.debug('collapse_and_hide: 已通知 Flash')
        except Exception:
            logger.exception('collapse_and_hide: Flash 通信失败')

    def is_visible(self):
        """菜单当前是否可见。

        View 被框架销毁（车库↔战斗切换）时 _visible 可能残留 True，
        导致 ESC 拦截器误判并吞掉按键——以 View 实际存在为准。
        """
        if _view_instance is None:
            self._visible = False
        return self._visible

    # ── 设置数据推送 ──

    def _get_voice_switch_page(self):
        """懒初始化 VoiceSwitchPage 实例（模块级单例）。

        View 不存在时返回 None 且不创建——View 销毁期间 Flash 的
        dispose 日志仍会经 onLog 进来触发本 getter，若此时创建，
        单例会永久持有 meta=None，导致下次 push_data 全部失败。
        （以下各 getter 同理）
        """
        global _voice_switch_page
        if _voice_switch_page is None:
            if _view_instance is None:
                return None
            from autoconfigvoiceover.pages.voice_switch_page import VoiceSwitchPage
            _voice_switch_page = VoiceSwitchPage(_view_instance)
            logger.debug('VoiceSwitchPage 实例已创建')
        return _voice_switch_page

    def _get_settings_page(self):
        """懒初始化 SettingsPage 实例（模块级单例）。"""
        global _settings_page
        if _settings_page is None:
            if _view_instance is None:
                return None
            from autoconfigvoiceover.pages.settings_page import SettingsPage
            _settings_page = SettingsPage(_view_instance)
            logger.debug('SettingsPage 实例已创建')
        return _settings_page

    def _get_help_page(self):
        """懒初始化 HelpPage 实例（模块级单例）。"""
        global _help_page
        if _help_page is None:
            if _view_instance is None:
                return None
            from autoconfigvoiceover.pages.help_page import HelpPage
            _help_page = HelpPage(_view_instance)
            logger.debug('HelpPage 实例已创建')
        return _help_page

    def _get_voice_pack_detail_page(self):
        """懒初始化 VoicePackDetailPage 实例（模块级单例）。"""
        global _voice_pack_detail_page
        if _voice_pack_detail_page is None:
            if _view_instance is None:
                return None
            from autoconfigvoiceover.pages.voice_pack_detail_page import VoicePackDetailPage
            _voice_pack_detail_page = VoicePackDetailPage(_view_instance)
            logger.debug('VoicePackDetailPage 实例已创建')
        return _voice_pack_detail_page

    def _get_personal_settings_page(self):
        """懒初始化 PersonalSettingsPage 实例（模块级单例）。"""
        global _personal_settings_page
        if _personal_settings_page is None:
            if _view_instance is None:
                return None
            from autoconfigvoiceover.pages.personal_settings_page import PersonalSettingsPage
            _personal_settings_page = PersonalSettingsPage(_view_instance)
            logger.debug('PersonalSettingsPage 实例已创建')
        return _personal_settings_page

    def _get_subtitle_settings_page(self):
        """懒初始化 SubtitleSettingsPage 实例（模块级单例）。"""
        global _subtitle_settings_page
        if _subtitle_settings_page is None:
            if _view_instance is None:
                return None
            from autoconfigvoiceover.pages.subtitle_settings_page import SubtitleSettingsPage
            _subtitle_settings_page = SubtitleSettingsPage(_view_instance)
            logger.debug('SubtitleSettingsPage 实例已创建')
        return _subtitle_settings_page

    def _push_settings_data(self):
        """向 Flash 推送设置页组件数据。

        由 Flash 端 MenuView.onPopulate 完成后发出的 '__menuReady__'
        信号触发（通过 ACVMenuMeta.onLog 检测），确保 Flash 方法已注册。
        """
        global _view_instance
        if _view_instance is None:
            logger.warn('_push_settings_data: View 不存在，跳过')
            return
        if not _view_instance._isDAAPIInited():
            logger.warn('_push_settings_data: DAAPI 未就绪，跳过')
            return

        # ── i18n 标签（必须先于页面数据——页面 _applyLabels 依赖词典就绪）──
        try:
            from . import l10n
            _view_instance.as_setLabelsS(l10n.build_ui_labels())
        except Exception:
            logger.exception('推送界面标签失败')

        try:
            settings_page = self._get_settings_page()
            settings_page.push_data()
            self._push_retries = 0
        except Exception:
            self._push_retries += 1
            logger.exception('推送设置页数据失败 (第%d次)', self._push_retries)
            if self._push_retries <= 1:
                # 重试一次（DAAPI 方法注册可能滞后于 isDAAPIInited）
                BigWorld.callback(1.5, self._retry_push_settings_data)
            return  # 推送失败则不继续推初始状态

        # ── 语音切换页数据 ──
        try:
            voice_page = self._get_voice_switch_page()
            voice_page.push_data()
        except Exception:
            logger.exception('推送语音切换页数据失败')

        # ── 帮助页数据 ──
        try:
            help_page = self._get_help_page()
            help_page.push_data()
        except Exception:
            logger.exception('推送帮助页数据失败')

        # ── 语音包详情页数据 ──
        try:
            vpd_page = self._get_voice_pack_detail_page()
            vpd_page.push_data()
        except Exception:
            logger.exception('推送语音包详情页数据失败')

        # ── 个性设置页数据 ──
        try:
            ps_page = self._get_personal_settings_page()
            ps_page.push_data()
        except Exception:
            logger.exception('推送个性设置页数据失败')

        # ── 字幕设置页数据 ──
        try:
            ss_page = self._get_subtitle_settings_page()
            ss_page.push_data()
        except Exception:
            logger.exception('推送字幕设置页数据失败')

        # ── 菜单组件图片（按用户选择的背景图标方案）──
        try:
            images = _resolve_menu_images(settings_page._bg_icon)
            _view_instance.as_setImagesS(images)
        except Exception:
            logger.exception('推送菜单组件图片失败')

        # 推送上次保存的位置和页面状态（跨会话恢复）
        self._push_initial_state()

    def _push_initial_state(self):
        """推送上次保存的位置和页面状态，用于跨会话恢复。"""
        global _view_instance
        if _view_instance is None:
            return

        from .config import load_config
        try:
            cfg = load_config()
            _view_instance.as_setInitialStateS({
                'position': cfg.get('position', {}),
                'lastState': cfg.get('lastState', {}),
            })
            logger.info('初始状态已推送')
        except Exception:
            logger.exception('推送初始状态失败')

    def _retry_push_settings_data(self):
        """重试推送设置数据。"""
        self._push_settings_data()

    # ── 内部方法 ──

    def _create(self):
        """通过当前 app 加载 SWF。

        不依赖 loadView() 返回值——View 的 __init__() 会自行保存引用到
        模块级 _view_instance。
        """
        global _view_instance

        app = ServicesLocator.appLoader.getApp()
        if app is None:
            logger.error('无法获取当前 app，菜单创建失败')
            return

        _view_instance = None  # 清除旧引用，等待 __init__ 回调
        try:
            app.loadView(
                SFViewLoadParams(VIEW_ALIAS, parent=_getParentWindow())
            )
            # loadView 返回后，__init__ 应该已设置 _view_instance
            if _view_instance is not None:
                logger.debug('菜单 View 已创建（通过 __init__ 回调）')
                # 不在此处推送数据——等待 Flash 端 MenuView.onPopulate
                # 完成后发出 '__menuReady__' 信号，由 onLog 触发推送。
            else:
                logger.warn('_create(): loadView 返回后 _view_instance 仍为 None')
        except Exception:
            logger.exception('菜单 View 创建失败')
