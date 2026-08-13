# coding=utf-8
"""SettingsPage —— 设置面板。

对应 Flash: com.github._25304_Oxygen.menu.pages.SettingsPage
入口: 左侧小圆导航按钮 #0（齿轮图标）

包含 6 个 GroupBox:
  1. 系别语音设置 —— 男声/女声 单选按钮组
  2. 通知设置     —— 推送级别单选 + 复选框
  3. 显示设置     —— 热键/日志 下拉 + 复选框
  4. 语音通用设置 —— 复选框
  5. 字幕通用设置 —— 字幕显示单选 + 文字速度步进器 + 复选框
  6. UI 主题自定义 —— 颜色方案 + 背景图标下拉 + 大标题颜色单选 + 自定义颜色

Flash 交互 → Python 回调（通过 onLog 前缀匹配）:
  nationVoiceGender,<male|female>     — 系别语音单选
  notifyPush,<none|count|detail>      — 通知推送级别单选
  checkbox,<key>,<0|1>                — 任意复选框变更
  hotkey,<F1..F10>                    — 热键下拉选择
  logLevel,<index>                    — 日志级别下拉选择
  subtitleDisplay,<simple|standard|none> — 字幕显示单选
  textSpeed,<value>                   — 文字速度步进器
  colorScheme,<token>                 — 颜色方案下拉选择（存储 value）
  bgIcon,<token>                      — 背景图标下拉选择（存储 value）
  titleTextMode,<followScheme|custom> — 大标题颜色模式单选
  titleTextColor,<#RRGGBB>            — 自定义大标题颜色
"""

from autoconfigvoiceover.logger import Logger

logger = Logger('SettingsPage')


# ═════════════════════════════════════════════════════════════
# 假数据 / 默认值
# ═════════════════════════════════════════════════════════════

def _get_hotkey_options():
    """读取热键列表供下拉菜单使用（磁盘优先，VFS 兜底）。

    hotkey.json 已由 config_init 在启动时复制到磁盘，
    用户可编辑磁盘副本；读取失败时从 VFS 恢复。
    """
    from autoconfigvoiceover.config_init import load_user_json
    try:
        hotkey_list = load_user_json('hotkey.json')
        if hotkey_list:
            return [entry['hotkey'] for entry in hotkey_list if 'hotkey' in entry]
    except Exception:
        pass
    return []

def _get_log_level_options():
    """日志级别下拉选项（i18n——随生效语言翻译，中文默认见 UI_LABELS）。

    索引协议保持不变（存储值 = 索引，logger.set_log_level 按索引过滤）。
    """
    from autoconfigvoiceover import l10n
    return [l10n.text('settings/log_level/%d' % i) for i in range(4)]


# 颜色方案列表在 push_data() 中动态构建（见 _build_color_scheme_options）
# "使用默认" 和 "跟随语音包" 始终位列前二

# Dark+ 默认色板——硬编码安全备份；所有主题在此之上合并（缺键回退）
# 颜色用 #RRGGBB 字符串便于人眼识别；发送到 Flash 前通过 _colors_to_ints() 转换
DARK_PLUS_DEFAULTS = {
    'surface0':      '#1E1E1E',  # 最深 — 大圆、弹窗背景
    'surface1':      '#2D2D2D',  # 中等 — 全展开面板、输入框、复选框
    'surface2':      '#3C3C3C',  # 较浅 — 滚动条轨道、步进器轨道
    'surface3':      '#252526',  # 特殊 — 半折叠面板、下拉列表行
    'accent':        '#3D6B9B',  # 主色 — 小圆、按钮正常、选中态
    'accentHover':   '#4D8BC5',  # 悬停 — 按钮悬停、步进器拇指
    'accentPress':   '#2D5B7B',  # 按下 — 按钮按下
    'stroke':        '#888888',  # 通用描边
    'textPrimary':   '#D4D4D4',  # 正文/标签
    'textSecondary': "#A0A0A0",  # 次要文字、禁用态
    'titleText':     '#D4D4D4',  # 菜单大标题——默认与 textPrimary 一致
    'sbThumb':       '#666666',  # 滚动条拇指
    'sbBtn':         '#555555',  # 滚动条 ▲▼ 按钮背景
    'sbBtnArrow':    '#CCCCCC',  # 滚动条 ▲▼ 箭头
}

# ── 内置选项 token（第零期 token 化，2026-08）──
# colorScheme/bgIcon 的存储值改为稳定 ASCII token，与显示文本（label）分离：
#   颜色方案: token 'default' / 'follow_pack' / 主题 name（内容身份，不翻译）
#   背景图标: token 'default' / 'follow_pack' / 语音包 pack_id（稳定身份，
#             label=nick_name 显示名可随用户改名变化，身份不受影响）
# 匹配 / 持久化全链路无中文参与（历史版本直接存中文标签，改英文后失配）。
# 配置值不正确（不在选项列表）→ __init__ 校验并回退默认，不做兼容迁移。
THEME_DEFAULT_TOKEN = 'default'        # 颜色方案：使用默认
BGICON_DEFAULT_TOKEN = 'default'       # 背景图标：默认
FOLLOW_PACK_TOKEN = 'follow_pack'      # 颜色方案/背景图标：跟随语音包

# 内置选项显示文本（i18n 第一期起经 l10n.text 查表，中文默认在 UI_LABELS）
# 键: settings/theme_default_label / settings/bgicon_default_label /
#     settings/follow_pack_label


def _to_unicode(s):
    """utf-8 字节串 → unicode；已是 unicode 则原样返回。"""
    if isinstance(s, str):
        return s.decode('utf-8')
    return s


def _options_to_unicode(options):
    """下拉选项 [{value, label}] 中所有字符串转 unicode（GFx 序列化需要）。

    value 可能是 ASCII token 或主题名/语音包显示名（中文），
    统一转 unicode 后跨 Python↔Flash 边界不再有 bytes/unicode 失配。
    """
    return [
        {'value': _to_unicode(o['value']), 'label': _to_unicode(o['label'])}
        for o in options
    ]


# ═════════════════════════════════════════════════════════════
# 模块级主题工具（供 voice_switch_page 等外部调用）
# ═════════════════════════════════════════════════════════════

def _colors_to_ints(theme_dict):
    """将颜色 dict 中的 #RRGGBB 字符串转为 Flash 可接受的整数。

    Flash Theme.apply() 对每个值执行 uint(v)，而 AS3 的 uint("#1E1E1E")
    会返回 0（无法解析 # 前缀）。因此必须在 Python 端先转换为整数。

    已为整数的值原样保留（兼容旧版 theme.json 的十进制整数格式）。
    """
    result = {}
    for k, v in theme_dict.items():
        if isinstance(v, str) and v.startswith('#'):
            result[k] = int(v[1:], 16)
        else:
            result[k] = v
    return result


def resolve_theme(token):
    """把颜色方案 token 解析为完整颜色 dict（已合并 Dark+ 默认，已转为 Flash 整数）。

    token: THEME_DEFAULT_TOKEN / FOLLOW_PACK_TOKEN /
           预设主题 name / 语音包内嵌主题 pack_id（内容身份）。
    合并策略：以 Dark+ 默认色板为底，主题只覆盖其声明的键；
    缺失的键保持默认值。未知 token 返回默认色板。
    返回前通过 _colors_to_ints() 将 #RRGGBB 字符串转为整数。

    供 SettingsPage 和 voice_switch_page 共用。
    """
    from autoconfigvoiceover.voices import g_voice_repo

    result = None  # 最终颜色 dict（未经 _colors_to_ints 转换）

    if token == THEME_DEFAULT_TOKEN:
        result = dict(DARK_PLUS_DEFAULTS)

    elif token == FOLLOW_PACK_TOKEN:
        theme = _get_current_pack_theme()
        if theme is not None:
            result = dict(DARK_PLUS_DEFAULTS)
            result.update(theme)
        else:
            result = dict(DARK_PLUS_DEFAULTS)

    else:
        # 搜索 VFS 预设主题（value = 主题 name）
        found = False
        for t in g_voice_repo.vfs_themes:
            if t.get('name') == token:
                result = dict(DARK_PLUS_DEFAULTS)
                result.update({k: v for k, v in t.items() if k != 'name'})
                found = True
                break

        # 搜索语音包内嵌主题（value = pack_id，每个包至多一个主题）
        if not found:
            theme = g_voice_repo.get_pack_theme(token)
            if theme is not None:
                result = dict(DARK_PLUS_DEFAULTS)
                result.update(
                    {k: v for k, v in theme.items()
                     if k not in ('name', 'pack_id')})
                found = True

        # 未知 → 默认
        if not found:
            from autoconfigvoiceover.logger import Logger
            Logger('SettingsPage').warn(
                '未知颜色方案: %s，回退 Dark+ 默认', token)
            result = dict(DARK_PLUS_DEFAULTS)

    return _colors_to_ints(result)


def _get_current_pack_theme():
    """返回当前活跃语音包的内嵌主题（纯颜色 dict，不含 name/pack_id）。

    仅对第三方语音包有效；内置语音返回 None。
    """
    from autoconfigvoiceover.voices import g_active_mgr, g_voice_repo
    if g_active_mgr.current is None:
        return None
    voice_id = g_active_mgr.current.voice_id
    theme = g_voice_repo.get_pack_theme(voice_id)
    if theme is None:
        return None
    return {k: v for k, v in theme.items()
            if k not in ('name', 'pack_id')}


def resolve_bg_icon(token):
    """把背景图标方案 token 解析为图像路径 dict。

    与 resolve_theme 同级，供 SettingsPage 和外部调用。
    内部复用 menu._resolve_menu_images：图标方案 5 张图按方案解析，
    bigCircle(menu.png) 始终跟随当前活跃语音包，与方案无关。

    :param token: BGICON_DEFAULT_TOKEN / FOLLOW_PACK_TOKEN / 语音包 pack_id
    :return: {'bigCircle': path, 'semiPanel': path, 'fullPanel': path,
              'smallCircles': [path, path, path]}
    """
    from autoconfigvoiceover.menu import _resolve_menu_images
    return _resolve_menu_images(token)


class SettingsPage(object):
    """设置页的业务逻辑。

    持有全部设置项的当前值，提供 push_data() 推送初始数据，
    以及各 handle_*() 方法处理 Flash 端用户操作。
    """

    def __init__(self, meta):
        """
        :param meta: ACVMenuMeta 实例，用于 DAAPI 通信
        """
        self._meta = meta

        # ── 从配置文件恢复（无文件时回退到 config.DEFAULTS）──
        from autoconfigvoiceover.config import load_config
        se = load_config().get('settings', {})

        # ── GB1: 系别语音设置 ──
        self._nation_voice_gender = se.get('nationVoiceGender', 'male')

        # ── GB2: 通知设置 ──
        self._notify_push_level = se.get('notifyPushLevel', 'count')
        self._ui_sound_enabled = se.get('uiSoundEnabled', True)
        self._switch_notify = se.get('switchNotify', False)

        # ── GB3: 显示设置 ──
        self._hotkey_enabled = se.get('hotkeyEnabled', False)
        self._hotkey = se.get('hotkey', 'F10')
        self._log_level = se.get('logLevel', 2)
        self._show_ingame_voices = se.get('showIngameVoices', False)
        self._show_installed_voices = se.get('showInstalledVoices', False)

        # ── GB4: 语音通用设置 ──
        self._auto_volume = se.get('autoVolume', True)
        self._play_on_switch = se.get('playOnSwitch', True)
        self._sound_remap = se.get('soundRemap', True)
        self._sound_bind = se.get('soundBind', True)
        self._voice_override = se.get('voiceOverride', True)

        # ── GB5: 字幕通用设置 ──
        self._subtitle_display = se.get('subtitleDisplay', 'standard')
        self._text_speed = se.get('textSpeed', 0.03)
        self._subtitle_update = se.get('subtitleUpdate', True)
        self._subtitle_anim = se.get('subtitleAnim', True)
        self._multi_sub = se.get('multiSub', False)

        # ── GB6: UI 主题自定义 ──
        # 存储值 = ASCII token。值不在当前选项列表中（旧中文值、已删除的
        # 主题/语音包等）→ 直接回退默认——插件未发布，不做兼容迁移
        self._color_scheme = se.get('colorScheme', FOLLOW_PACK_TOKEN)
        self._bg_icon = se.get('bgIcon', FOLLOW_PACK_TOKEN)
        if not any(o['value'] == self._color_scheme
                   for o in self._build_color_scheme_options()):
            logger.warn('颜色方案 %r 不在选项列表中，回退默认', self._color_scheme)
            self._color_scheme = FOLLOW_PACK_TOKEN
        if not any(o['value'] == self._bg_icon
                   for o in self._build_bg_icon_options()):
            logger.warn('背景图标 %r 不在选项列表中，回退默认', self._bg_icon)
            self._bg_icon = FOLLOW_PACK_TOKEN
        self._title_text_mode = se.get('titleTextMode', 'followScheme')
        self._title_text_color = se.get('titleTextColor', '#D4D4D4')

        # ── 界面语言（i18n 第一期）──
        # 存储值 = 'auto'（跟随客户端）或语言代码；值不在选项列表
        # （用户手改）→ 回退跟随客户端，不做兼容迁移
        self._ui_lang = se.get('uiLang', 'auto')
        if not any(o['value'] == self._ui_lang
                   for o in self._build_ui_lang_options()):
            logger.warn('界面语言 %r 不在选项列表中，回退跟随客户端', self._ui_lang)
            self._ui_lang = 'auto'

    # ═════════════════════════════════════════════════════════
    # 数据推送 → Flash
    # ═════════════════════════════════════════════════════════

    def push_data(self):
        """向 Flash 推送设置页全部初始数据。

        在 __menuReady__ 信号触发后由 MenuManager 调用。
        一次性打包: 6 个 GroupBox 的初始值、下拉列表选项、Tooltip HTML、主题。
        """
        # ★ 下拉列表：hotkey/logLevel 保持索引协议（现状不动）；
        #    colorScheme/bgIcon 改传存储 value（token），选项为 [{value,label}]，
        #    Flash 端按 value 恢复选中（setSelectedValue），全链路无中文匹配。
        from autoconfigvoiceover import l10n
        hotkey = self._hotkey
        if isinstance(hotkey, str):
            hotkey = hotkey.decode('utf-8')
        hotkey_options = [o.decode('utf-8') if isinstance(o, str) else o
                          for o in _get_hotkey_options()]
        log_level_options = [o.decode('utf-8') if isinstance(o, str) else o
                             for o in _get_log_level_options()]
        color_scheme_options = _options_to_unicode(
            self._build_color_scheme_options())
        bg_icon_options = _options_to_unicode(
            self._build_bg_icon_options())
        color_scheme = _to_unicode(self._color_scheme)
        bg_icon = _to_unicode(self._bg_icon)
        ui_lang_options = _options_to_unicode(self._build_ui_lang_options())
        ui_lang = _to_unicode(self._ui_lang)

        title_text_mode = self._title_text_mode
        if isinstance(title_text_mode, str):
            title_text_mode = title_text_mode.decode('utf-8')
        title_text_color = self._title_text_color
        if isinstance(title_text_color, str):
            title_text_color = title_text_color.decode('utf-8')

        # 存储值已在 __init__ 校验回退，此处必在选项列表中；
        # Flash 端 setSelectedValue 找不到时仍会回退第一项（防御）
        # 在选项列表中查找已保存项的索引（找不到回退为 0）
        hotkey_idx = 0
        try:
            hotkey_idx = hotkey_options.index(hotkey)
        except ValueError:
            logger.warn('已保存的热键 %s 不在选项列表中，回退为索引 0', hotkey)

        data = {
            # ── GB1: 系别语音设置 ──
            'nationVoiceGender': self._nation_voice_gender,

            # ── GB2: 通知设置 ──
            'notifyPushLevel':   self._notify_push_level,
            'uiSoundEnabled':    1 if self._ui_sound_enabled else 0,
            'switchNotify':      1 if self._switch_notify else 0,

            # ── GB3: 显示设置 ──
            'hotkeyEnabled':      1 if self._hotkey_enabled else 0,
            'hotkey':             hotkey_idx,
            'hotkeyOptions':      hotkey_options,
            'logLevel':           self._log_level,
            'logLevelOptions':    log_level_options,
            'showIngameVoices':   1 if self._show_ingame_voices else 0,
            'showInstalledVoices': 1 if self._show_installed_voices else 0,

            # ── GB4: 语音通用设置 ──
            'autoVolume':    1 if self._auto_volume else 0,
            'playOnSwitch':  1 if self._play_on_switch else 0,
            'soundRemap':    1 if self._sound_remap else 0,
            'soundBind':     1 if self._sound_bind else 0,
            'voiceOverride': 1 if self._voice_override else 0,

            # ── GB5: 字幕通用设置 ──
            'subtitleDisplay': self._subtitle_display,
            'textSpeed':       self._text_speed,
            'subtitleUpdate':  1 if self._subtitle_update else 0,
            'subtitleAnim':    1 if self._subtitle_anim else 0,
            'multiSub':        1 if self._multi_sub else 0,
            # 打字预览文本（i18n——随语言翻译；AS3 端做上限截断 §5.5）
            'previewText':     l10n.text('settings/preview_text'),

            # ── GB6: UI 主题自定义 ──
            # 存储 value（token）+ [{value,label}] 选项；Flash 按 value 恢复
            'colorScheme':        color_scheme,
            'colorSchemeOptions': color_scheme_options,
            'bgIcon':             bg_icon,
            'bgIconOptions':      bg_icon_options,
            'titleTextMode':      title_text_mode,
            'titleTextColor':     title_text_color,

            # ── 界面语言（i18n）──
            'uiLang':             ui_lang,
            'uiLangOptions':      ui_lang_options,

            # ── Tooltip ──
            'tooltips':          self._get_tooltips(),
            'titleTooltipHtml':  self._get_title_tooltip_html(),
        }
        self._meta.as_populateSettingsS(data)
        logger.info('设置页数据已推送 (%d 热键, %d 日志级别, %d 颜色方案, '
                    '%d 背景图标方案)',
                    len(hotkey_options), len(log_level_options),
                    len(color_scheme_options), len(bg_icon_options))

        # 应用已保存的主题色板——Flash 只通过下拉选中方案名，
        # 实际色板需 Python 端 resolve_theme 后显式推送。
        theme = resolve_theme(self._color_scheme)
        # 若标题颜色为自定义模式，覆盖 titleText
        if self._title_text_mode == 'custom':
            try:
                theme['titleText'] = int(self._title_text_color.lstrip('#'), 16)
            except (ValueError, AttributeError):
                theme['titleText'] = int('D4D4D4', 16)
        self._meta.as_applyThemeS(theme)

    # ═════════════════════════════════════════════════════════
    # 回调处理（Flash → Python）
    # ═════════════════════════════════════════════════════════

    def handle_nation_voice_gender(self, gender):
        """系别语音单选按钮切换。

        持久化性别偏好；若当前活跃语音是系别语音则即时应用。
        """
        self._nation_voice_gender = gender
        self._save_to_config()

        # 如果当前活跃语音是系别语音，即时应用性别切换
        from autoconfigvoiceover.voices import g_active_mgr, voice_switcher
        if g_active_mgr.current is not None:
            voice_switcher._apply_gender(g_active_mgr.current.voice_id)

        logger.info('系别语音性别: %s（已持久化%s）', gender,
                    ' + 已应用' if g_active_mgr.current is not None
                    and g_active_mgr.current.voice_id != 'default' else '')

    def handle_notify_push(self, level):
        """通知推送级别单选按钮切换。"""
        self._notify_push_level = level
        self._save_to_config()
        logger.info('推送级别: %s（已持久化）', level)

    def handle_checkbox(self, key, checked):
        """复选框变更（统一入口）。"""
        checked_bool = bool(int(checked))
        # 更新内部状态
        key_map = {
            'uiSound':            '_ui_sound_enabled',
            'switchNotify':       '_switch_notify',
            'hotkeyEnabled':      '_hotkey_enabled',
            'showIngameVoices':   '_show_ingame_voices',
            'showInstalledVoices': '_show_installed_voices',
            'autoVolume':         '_auto_volume',
            'playOnSwitch':       '_play_on_switch',
            'soundRemap':         '_sound_remap',
            'soundBind':          '_sound_bind',
            'voiceOverride':      '_voice_override',
            'subtitleUpdate':     '_subtitle_update',
            'subtitleAnim':       '_subtitle_anim',
            'multiSub':           '_multi_sub',
        }
        attr = key_map.get(key)
        if attr:
            setattr(self, attr, checked_bool)

        self._save_to_config()
        logger.info('复选框 %s = %s（已持久化）', key, checked_bool)

        # 语音包显示/隐藏：即时应用到游戏声音设置菜单
        if key in ('showIngameVoices', 'showInstalledVoices'):
            from autoconfigvoiceover.voices import voice_switcher
            voice_switcher.apply_voice_visibility(
                show_ingame=self._show_ingame_voices,
                show_outside=self._show_installed_voices)

        # 声音重映射/绑定：即时启用/禁用引擎 + 同步当前语音包数据
        if key in ('soundRemap', 'soundBind'):
            self._apply_sound_engine_state(key, checked_bool)

        # 热键启用/禁用：即时刷新模块级缓存
        if key == 'hotkeyEnabled':
            from autoconfigvoiceover import update_hotkey_config
            update_hotkey_config()

        # 字幕设置即时应用到 SubtitleManager
        if key in ('subtitleUpdate', 'multiSub'):
            from autoconfigvoiceover.subtitle.host import update_subtitle_settings
            update_subtitle_settings({key: checked_bool})
        # 字幕额外动画开关 → 即时应用到 SubtitleManager
        if key == 'subtitleAnim':
            from autoconfigvoiceover.subtitle.host import update_subtitle_settings
            update_subtitle_settings({'subtitle_anim': checked_bool})

    def _apply_sound_engine_state(self, key, enabled):
        """即时启用/禁用声音引擎，并在开启时同步当前语音包数据。

        由 handle_checkbox 在 soundRemap / soundBind 复选框变更时调用。

        声音绑定/重映射无方案时置空。
        """
        from autoconfigvoiceover.sound import g_remapping_engine, g_binding_engine
        from autoconfigvoiceover.voices import g_active_mgr

        if key == 'soundRemap':
            g_remapping_engine.set_enabled(enabled)
            if enabled and g_active_mgr.current is not None:
                av = g_active_mgr.current
                if av.remap:
                    g_remapping_engine.load_dict(av.remap)
                else:
                    g_remapping_engine.load_dict({})
            logger.info('声音重映射已%s', '启用' if enabled else '禁用')

        elif key == 'soundBind':
            g_binding_engine.set_enabled(enabled)
            if enabled and g_active_mgr.current is not None:
                av = g_active_mgr.current
                if av.attach_data:
                    g_binding_engine.load_data(av.attach_data)
                else:
                    # 语音包无有效绑定方案 → 置空，而非回退到用户规则
                    g_binding_engine.load_data(None)
            logger.info('声音绑定已%s', '启用' if enabled else '禁用')

    def _save_to_config(self):
        """将当前全部设置项写入配置文件。"""
        from autoconfigvoiceover.config import save_config
        save_config({'settings': {
            'uiSoundEnabled':      self._ui_sound_enabled,
            'switchNotify':        self._switch_notify,
            'hotkeyEnabled':       self._hotkey_enabled,
            'hotkey':              self._hotkey,
            'logLevel':            self._log_level,
            'showIngameVoices':    self._show_ingame_voices,
            'showInstalledVoices': self._show_installed_voices,
            'autoVolume':          self._auto_volume,
            'playOnSwitch':        self._play_on_switch,
            'soundRemap':          self._sound_remap,
            'soundBind':           self._sound_bind,
            'voiceOverride':       self._voice_override,
            'subtitleUpdate':      self._subtitle_update,
            'subtitleAnim':        self._subtitle_anim,
            'multiSub':            self._multi_sub,
            'nationVoiceGender':   self._nation_voice_gender,
            'notifyPushLevel':     self._notify_push_level,
            'subtitleDisplay':     self._subtitle_display,
            'textSpeed':           self._text_speed,
            'colorScheme':         self._color_scheme,
            'bgIcon':              self._bg_icon,
            'titleTextMode':       self._title_text_mode,
            'titleTextColor':      self._title_text_color,
            'uiLang':              self._ui_lang,
        }})

    def handle_hotkey(self, hotkey):
        """热键下拉列表选择。

        验证 hotkey 在 HOTKEY_OPTIONS 中，更新内部状态并持久化。
        （实际的输入监听在 __init__._on_key_down 中通过读配置文件生效）
        """
        if hotkey not in _get_hotkey_options():
            logger.warn('无效热键: %s（跳过）', hotkey)
            return

        self._hotkey = hotkey
        self._save_to_config()
        # 刷新模块级热键缓存，使修改即时生效
        from autoconfigvoiceover import update_hotkey_config
        update_hotkey_config()
        logger.info('热键: %s（已持久化 + 已生效）', hotkey)

    def handle_log_level(self, index):
        """日志级别下拉列表选择。"""
        index = int(index)
        options = _get_log_level_options()
        if index < 0 or index >= len(options):
            logger.warn('无效日志级别索引: %d', index)
            return

        self._log_level = index
        from autoconfigvoiceover.logger import set_log_level
        set_log_level(index)
        self._save_to_config()

        level_name = options[index]
        logger.info('日志级别: %s（已应用 + 已持久化）', level_name)

    def handle_subtitle_display(self, mode):
        """字幕显示模式单选按钮切换。

        持久化到配置 + 运行时热应用到 SubtitleManager。
        config 用 'simple'，manager 用 'concise'，做映射。
        """
        self._subtitle_display = mode
        self._save_to_config()

        from autoconfigvoiceover.subtitle.host import update_subtitle_settings
        mgr_mode = 'concise' if mode == 'simple' else mode
        update_subtitle_settings({'display_mode': mgr_mode})

        # 同步通知 Flash 字幕设置页更新 displayMode，
        # 否则编辑模式下按钮启用/禁用逻辑使用过期值
        from .subtitle_settings_page import repush_display_mode
        repush_display_mode()

        logger.info('字幕显示模式: %s（已持久化 + 已应用）', mode)

    def handle_text_speed(self, value):
        """文字速度步进器变更。

        持久化到配置 + 运行时热应用到 SubtitleManager（打字机效果速度）。
        """
        self._text_speed = float(value)
        self._save_to_config()

        from autoconfigvoiceover.subtitle.host import update_subtitle_settings
        update_subtitle_settings({'text_speed': self._text_speed})

        logger.info('文字速度: %.2f（已持久化 + 已应用）', self._text_speed)

    def handle_color_scheme(self, token):
        """UI 颜色方案下拉列表选择。

        "default" → Dark+ 硬编码；"follow_pack" → 查找语音包内
        theme.json；其他 → VFS 预设 / 语音包主题表。均以默认色板打底
        再覆盖（缺键回退默认）。
        若标题颜色为自定义模式，覆盖 titleText。

        token 为 Flash 回传的存储 value（ASCII token 或主题 name）。
        """
        self._color_scheme = token
        theme = resolve_theme(token)
        if self._title_text_mode == 'custom':
            try:
                theme['titleText'] = int(self._title_text_color.lstrip('#'), 16)
            except (ValueError, AttributeError):
                theme['titleText'] = int('D4D4D4', 16)
        self._meta.as_applyThemeS(theme)
        self._save_to_config()
        logger.info('颜色方案: %s（已应用 + 已持久化）', token)

    def handle_bg_icon(self, token):
        """背景图标下拉列表选择 → resolve → as_setImagesS。

        token 为 Flash 回传的存储 value（ASCII token 或语音包 pack_id）。
        """
        self._bg_icon = token
        self._meta.as_setImagesS(resolve_bg_icon(token))
        self._save_to_config()
        logger.info('背景图标: %s（已应用 + 已持久化）', token)

    def handle_title_text_mode(self, mode):
        """大标题颜色模式切换。

        "跟随颜色方案" → 用 resolve_theme 恢复当前颜色方案中的 titleText；
        "自定义" → 应用保存的自定义颜色。

        幂等保护：启动时 Flash populate 会把已保存的模式原样回显，
        若与当前一致则跳过——主题已由 push_data() 末尾应用过一次，
        避免同一次启动重复 apply 主题。
        """
        if mode == self._title_text_mode:
            return
        self._title_text_mode = mode
        if mode == 'followScheme':
            self._meta.as_applyThemeS(resolve_theme(self._color_scheme))
        else:
            self._apply_custom_title_text()
        self._save_to_config()
        logger.info('大标题颜色模式: %s（已应用 + 已持久化）', mode)

    def handle_title_text_color(self, color_hex):
        """自定义大标题颜色（Flash 端已校验 #RRGGBB 格式）。"""
        self._title_text_color = color_hex
        self._apply_custom_title_text()
        self._save_to_config()
        logger.info('自定义标题颜色: %s（已应用 + 已持久化）', color_hex)

    def handle_ui_lang(self, lang):
        """界面语言切换：持久化 → 重解析词典 → 重推全部页面。

        lang 为 Flash 回传的存储 value（'auto' 或语言代码）。
        populate 幂等（设计前提 §5.3）——重推 = 全部页面按新语言刷新。
        """
        if lang == self._ui_lang:
            return
        if not any(o['value'] == lang for o in self._build_ui_lang_options()):
            logger.warn('未知界面语言: %s（跳过）', lang)
            return

        self._ui_lang = lang
        self._save_to_config()

        # 重解析词典（生效语言变化）→ 重推全部页面
        from autoconfigvoiceover import l10n
        l10n.reload()
        from autoconfigvoiceover.menu import _menu_manager
        if _menu_manager is not None:
            _menu_manager._push_settings_data()
        # ModsList 入口名称/描述随语言刷新（同 id 重复注册 = 幂等更新，不可用时静默跳过）
        from autoconfigvoiceover import g_autoConfigVoiceOverMod
        g_autoConfigVoiceOverMod.refresh_mods_list_entry()
        logger.info('界面语言: %s（已应用 + 已持久化）', lang)

    def _apply_custom_title_text(self):
        """将自定义 titleText 颜色推送到 Flash。"""
        try:
            color_int = int(self._title_text_color.lstrip('#'), 16)
        except (ValueError, AttributeError):
            color_int = int('D4D4D4', 16)
        self._meta.as_applyThemeS({'titleText': color_int})

    def reapply_theme_if_following_pack(self):
        """切语音后调用：若当前颜色方案为"跟随语音包"则重切主题。
        若标题颜色为自定义模式，覆盖 titleText。
        """
        if self._color_scheme == FOLLOW_PACK_TOKEN:
            theme = resolve_theme(FOLLOW_PACK_TOKEN)
            if self._title_text_mode == 'custom':
                try:
                    theme['titleText'] = int(
                        self._title_text_color.lstrip('#'), 16)
                except (ValueError, AttributeError):
                    theme['titleText'] = int('D4D4D4', 16)
            self._meta.as_applyThemeS(theme)
            logger.debug('跟随语音包：已重切主题')

    def _build_color_scheme_options(self):
        """动态构建颜色方案下拉选项 [{value, label}]。

        顺序: 使用默认 → 跟随语音包 → VFS 预设 → 语音包内嵌主题。
        value 即存储 token：内置选项为固定 ASCII token；
        预设主题取 name（内容身份）；语音包内嵌主题取 pack_id
        （作者改主题 name 不影响已保存配置，身份跟着包走，与 bgIcon 一致）；
        label 均为显示文本。
        """
        from autoconfigvoiceover.voices import g_voice_repo
        from autoconfigvoiceover import l10n
        options = [
            {'value': THEME_DEFAULT_TOKEN,
             'label': l10n.text('settings/theme/default_label')},
            {'value': FOLLOW_PACK_TOKEN,
             'label': l10n.text('settings/theme/follow_pack_label')},
        ]
        options.extend(
            {'value': t.get('name'), 'label': t.get('name')}
            for t in g_voice_repo.vfs_themes if t.get('name'))
        options.extend(
            {'value': t.get('pack_id'), 'label': t.get('name')}
            for t in g_voice_repo.pack_themes if t.get('name'))
        return options

    def _build_ui_lang_options(self):
        """界面语言下拉选项 [{value, label}]。

        'auto'（跟随客户端）恒在首位；其余 = 可选语言（VFS l10n/ 枚举
        + 内置 zh_cn）。label = 语言母语名（不随界面语言变化，任何语言
        下自解释）——优先读语言文件 __meta__.displayName（新增语言只需
        写文件，无需改代码），zh_cn 回退内置表；'auto' 的 label 走词典。
        """
        from autoconfigvoiceover import l10n
        options = [{'value': 'auto', 'label': l10n.text('ui_lang/auto')}]
        for code in l10n.get_available_langs():
            options.append({
                'value': code,
                'label': l10n.get_lang_display_name(code),
            })
        return options

    def _build_bg_icon_options(self):
        """动态构建背景图标下拉选项 [{value, label}]。

        顺序: 默认 → 跟随语音包 → 有自定义图片的语音包。
        value = pack_id（稳定 ASCII 身份，显示名可随用户改名变化，
        身份不受影响）；label = nick_name（显示名）。
        """
        import ResMgr
        from autoconfigvoiceover.voices import g_voice_repo
        from autoconfigvoiceover.menu import _VOICE_PACK_IMAGE_MAP
        from autoconfigvoiceover import l10n
        options = [
            {'value': BGICON_DEFAULT_TOKEN,
             'label': l10n.text('settings/theme/bgicon_default_label')},
            {'value': FOLLOW_PACK_TOKEN,
             'label': l10n.text('settings/theme/follow_pack_label')},
        ]
        for pack in g_voice_repo.packs:
            has_images = any(
                ResMgr.isFile(pack.root + rel)
                for rel, _, _ in _VOICE_PACK_IMAGE_MAP
            )
            if has_images:
                options.append({'value': pack.pack_id, 'label': pack.nick_name})
        return options

    # ═════════════════════════════════════════════════════════
    # Tooltip HTML（后续可从配置文件生成）
    # ═════════════════════════════════════════════════════════

    def _get_tooltips(self):
        """返回各组件 Tooltip 的富文本 HTML 字典（随生效语言）。"""
        from autoconfigvoiceover import l10n
        return {
            'nationVoice': l10n.text('settings/tooltip/nation_voice'),
            'soundRemap': l10n.text('settings/tooltip/sound_remap'),
            'soundBind': l10n.text('settings/tooltip/sound_bind'),
            'subtitle': l10n.text('settings/tooltip/subtitle'),
            'subtitleSimple': l10n.text('settings/tooltip/subtitle_simple'),
            'subtitleStandard': l10n.text('settings/tooltip/subtitle_standard'),
            'subtitleUpdate': l10n.text('settings/tooltip/subtitle_update'),
            'subtitleAnim': l10n.text('settings/tooltip/subtitle_anim'),
            'multiSub': l10n.text('settings/tooltip/multi_sub'),
            'textSpeed': l10n.text('settings/tooltip/text_speed'),
            'colorScheme': l10n.text('settings/tooltip/color_scheme'),
            'bgIcon': l10n.text('settings/tooltip/bg_icon'),
            'titleTextColor': l10n.text('settings/tooltip/title_text_color'),
        }

    def _get_title_tooltip_html(self):
        """标题 Tooltip HTML。"""
        from autoconfigvoiceover import l10n
        return l10n.text('settings/tooltip/title')
