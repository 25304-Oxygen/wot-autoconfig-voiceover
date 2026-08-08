# coding=utf-8
"""消息通知模块——向游戏消息中心发送文本通知，支持 HTML 排版与可点击链接。

API 设计目标："只需传字符串，就能发送除富媒体卡片外任意消息"。
- 传入纯文本 → 信息型通知
- 传入含 HTML 的文本 → Scaleform Flash TextField 渲染
- 传入 title 参数 → 标题+正文模板（InformationHeader）
- <a> 标签中的链接 → 通过 HandleAction 钩子变为可点击（外部浏览器打开）
"""

from .logger import Logger
from .constants import CONFIG_FILE

logger = Logger('Notifier')

# ── 模块级状态 ──
_original_handleAction = None  # 被钩的原始 handleAction 方法


# ═════════════════════════════════════════════════════════════
# 消息发送 API
# ═════════════════════════════════════════════════════════════

def send_message(text, title=None, msg_type=None, priority=None):
    """向游戏消息中心发送一条通知。

    :param text: 消息正文（支持 HTML 标签）
    :param title: 可选标题；传入时使用 InformationHeader 模板（显示标题行）
    :param msg_type: SM_TYPE 枚举值，默认 Information / InformationHeader
    :param priority: 'high' | 'medium' | 'low'，默认 None（用模板默认值）
    """
    try:
        from gui import SystemMessages

        if title is not None:
            sm_type = msg_type or SystemMessages.SM_TYPE.InformationHeader
            message_data = {'header': title}
        else:
            sm_type = msg_type or SystemMessages.SM_TYPE.Information
            message_data = None

        SystemMessages.pushMessage(
            text, type=sm_type, priority=priority, messageData=message_data)
        logger.debug('通知已发送%s: %s',
                     ' [标题=' + title + ']' if title else '',
                     text[:80] + ('...' if len(text) > 80 else ''))

    except Exception:
        logger.exception('发送通知失败')


def notify_voice_switch(voice_name, success=True):
    """语音切换后向消息中心发送通知（受 switchNotify 设置控制）。

    由语音切换页 handle_voice_select / handle_change_type / handle_change_lang
    在切换后调用。仅在用户开启 switchNotify 时发送。

    成功: 标题 "切换语音：xxx" + 正文 "切换成功"（InformationHeader）
    失败: 标题 "切换语音：xxx" + 正文 "切换失败"（Error）
    """
    try:
        from .config import load_config
        if not load_config().get('settings', {}).get('switchNotify', False):
            return

        from gui import SystemMessages

        # 用户可见文本走词典（i18n）
        from . import l10n
        title = l10n.text('notify/switch_title', voice_name)
        if success:
            send_message(l10n.text('notify/switch_success'), title=title,
                         msg_type=SystemMessages.SM_TYPE.InformationHeader)
        else:
            send_message(l10n.text('notify/switch_fail'), title=title,
                         msg_type=SystemMessages.SM_TYPE.Error)
    except Exception:
        logger.exception('发送语音切换通知失败')


# ═════════════════════════════════════════════════════════════
# 可点击链接（钩 NotificationsActionsHandlers.handleAction）
# ═════════════════════════════════════════════════════════════

# customEvent 前缀——消息中按钮的 action 以此前缀开头时，
# 会被本钩子拦截，提取 URL 后用外部浏览器打开。
CUSTOM_EVENT_OPEN_URL = 'CUSTOM_EVENT_OPEN_URL:'


def _get_open_browser():
    """获取浏览器打开函数（兼容不同 WoT 版本）。"""
    import BigWorld
    if hasattr(BigWorld, 'wg_openWebBrowser'):
        return BigWorld.wg_openWebBrowser
    return BigWorld.openWebBrowser


def _patched_handleAction(self, model, typeID, entityID, actionName):
    """包装后的 handleAction：拦截自定义 URL 打开事件。"""
    if actionName.startswith(CUSTOM_EVENT_OPEN_URL):
        url = actionName[len(CUSTOM_EVENT_OPEN_URL):]
        logger.info('打开外部链接: %s', url)
        try:
            _get_open_browser()(url)
        except Exception:
            logger.exception('打开链接失败: %s', url)
        return
    # 不匹配 → 原始处理流程
    return _original_handleAction(self, model, typeID, entityID, actionName)


def init():
    """安装 HandleAction 钩子（在初始化阶段调用一次）。

    应在 sound subsystem 初始化之后、首次 switch_voice 之前调用。
    幂等：重复调用自动跳过。
    """
    global _original_handleAction
    if _original_handleAction is not None:
        return  # 已安装

    try:
        from notification.actions_handlers import NotificationsActionsHandlers
        _original_handleAction = NotificationsActionsHandlers.handleAction
        NotificationsActionsHandlers.handleAction = _patched_handleAction
        logger.info('通知链接钩子已安装')
    except Exception:
        logger.exception('安装通知链接钩子失败——链接将不可点击')


def fini():
    """卸载 HandleAction 钩子（在 fini 阶段调用）。"""
    global _original_handleAction
    if _original_handleAction is None:
        return

    try:
        from notification.actions_handlers import NotificationsActionsHandlers
        NotificationsActionsHandlers.handleAction = _original_handleAction
        _original_handleAction = None
        logger.info('通知链接钩子已卸载')
    except Exception:
        logger.exception('卸载通知链接钩子失败')


# ═════════════════════════════════════════════════════════════
# 登录欢迎通知 + 语音包增减统计
# ═════════════════════════════════════════════════════════════

_stats_sent = False
"""语音统计消息是否已发送（每会话仅一次）。在 onAccountBecomePlayer 发送，排在欢迎消息之前。"""

_welcome_sent = False
"""登录欢迎消息是否已发送（每会话仅一次）。在 onAccountBecomePlayer 发送，排在语音统计之后。"""


def send_voice_stats():
    """在登录完成后发送语音包增减统计到消息中心。

    在 onAccountBecomePlayer 中、send_welcome 之前调用。
    统计数据对比的是当前扫描结果 vs 上次会话落盘的历史数据，
    repo.run() 后即可 compute_diff()。
    独立于欢迎消息——统计先发送，欢迎消息在 onAccountBecomePlayer 后发送，
    排在统计下方。
    """
    global _stats_sent
    if _stats_sent:
        return
    _stats_sent = True

    try:
        from gui import SystemMessages
        from .config import load_config
        from autoconfigvoiceover.voices.repository import g_voice_repo

        notify_level = load_config().get('settings', {}).get('notifyPushLevel', 'none')
        stats_text = _build_stats_text(notify_level)
        if not stats_text:
            logger.debug('语音统计无可报告内容，跳过')
            return

        body = stats_text

        # 当前语音显示名：优先持久化的 currentVoiceId，
        # 在仓库行中查找 nickName（反映用户改名，兼容内置/第三方）。
        # 不用 g_active_mgr.current.pack.nick_name——内置语音 pack 为
        # None，且该值不反映用户改名；当前时刻 g_active_mgr 也可能
        # 尚未激活（saved_id 为 default 时不走 switch_voice）。
        voice_id = load_config().get('voice', {}).get('currentVoiceId', 'default')
        display_name = None
        for row in g_voice_repo.ingame_rows + g_voice_repo.outside_rows:
            if row.get('voiceID') == voice_id:
                display_name = row.get('nickName', voice_id)
                break
        if display_name is None:
            # 历史选择的语音包已被移除——声音已回退默认语音，
            # 这里也显示默认语音名，而不是暴露原始 voice_id。
            default_row = g_voice_repo.default_voice
            display_name = (default_row.get('nickName', 'default')
                            if default_row else 'default')

        # 标题走词典（i18n）；display_name 是语音包名（内容层，不翻译）
        from . import l10n
        title = l10n.text('notify/current_voice', display_name)

        SystemMessages.pushMessage(
            body,
            type=SystemMessages.SM_TYPE.InformationHeader,
            messageData={'header': title},
        )
        logger.info('语音包统计消息已发送')

    except Exception:
        logger.exception('发送语音统计消息失败')


def send_welcome(mods_list_available, hotkey='F10', hotkey_enabled=True):
    """登录后发送欢迎通知（onAccountBecomePlayer 时调用）。

    与语音统计分离：统计在 init 阶段先发送，本函数在登录完成后发送，
    排在统计下方。

    :param mods_list_available: bool —— ModsListApi 是否可用
    :param hotkey: 当前配置的热键名（如 'F10'）
    :param hotkey_enabled: bool —— 是否已启用快捷键
    """
    global _welcome_sent
    if _welcome_sent:
        return
    _welcome_sent = True

    try:
        from gui import SystemMessages

        # ── 欢迎正文（4 种组合，用户可见文本走词典）──
        from . import l10n
        lines = []

        if mods_list_available:
            lines.append(l10n.text('notify/welcome_mods_list'))
            if hotkey_enabled:
                lines.append(l10n.text('notify/welcome_hotkey', hotkey))
        else:
            if hotkey_enabled:
                lines.append(l10n.text('notify/welcome_no_mods', hotkey))
            else:
                lines.append(l10n.text('notify/welcome_no_mods_no_hotkey'))
                lines.append(l10n.text('notify/welcome_config_hint', CONFIG_FILE))
        lines.append(l10n.text('notify/welcome_footer', _get_acv_version()))

        body = '<br>'.join(lines)
        title = l10n.text('notify/welcome_title')

        SystemMessages.pushMessage(
            body,
            type=SystemMessages.SM_TYPE.InformationHeader,
            messageData={'header': title},
        )
        logger.info('登录欢迎消息已发送')

    except Exception:
        logger.exception('发送欢迎消息失败')


def _get_acv_version():
    """读取 mod 版本号。"""
    try:
        from ._metadata import MOD_VERSION
        return MOD_VERSION
    except Exception:
        return '1.0.0'


def _build_stats_text(notify_level):
    """构建语音包增减统计文本。

    :param notify_level: 'count' → 已安装仅显示数字；
                         'detail' → 已安装逐条罗列名称
    :return: HTML 格式的统计文本；无可报告内容返回 None

    规则:
    - "仅计数"只影响"已安装的语音包"段落；新增和移除始终显示名称。
    - 新增内置语音仅在 gameSoundModes.json 已存在（有历史基线）时才报告，
      否则首次运行会列出上百条内置语音。
    - 新增第三方语音始终报告（数量可控）。
    - 内置语音不考虑减少。
    """
    if notify_level not in ('count', 'detail'):
        return None

    try:
        from autoconfigvoiceover.voices.repository import g_voice_repo

        if not g_voice_repo.is_ready:
            logger.debug('语音仓库未就绪，跳过统计')
            return None

        diff = g_voice_repo.compute_diff()
        is_count = (notify_level == 'count')
        has_iv_history = bool(g_voice_repo._saved_ingame)
        has_ov_history = bool(g_voice_repo._saved_outside)

        logger.debug('语音统计: iv_hist=%s ov_hist=%s add_iv=%d add_ov=%d rm_ov=%d',
                     has_iv_history, has_ov_history,
                     len(diff['added_ingame']), len(diff['added_outside']),
                     len(diff['removed_outside']))

        # 颜色定义（对齐旧 mod collectData.py）
        C_ADD_IV = '#f5ffff'    # 新增内置语音包
        C_ADD_OV = '#ffe4e1'    # 新增第三方语音包
        C_EXIST = '#fff0f5'     # 已安装的第三方语音包
        C_REMOVED = '#dcdcdc'   # 已移除的第三方语音包

        outside_rows = g_voice_repo.outside_rows
        added_ov_set = set(diff['added_outside'])
        has_outside = bool(outside_rows)
        has_removals = has_ov_history and bool(diff['removed_outside'])

        result = ''

        # ═══════════════════════════════════════════════════════
        # 1. 已安装的语音包
        #    = 当前存在 ∩ 历史上已存在（即非新增）。
        #    无历史基线时全部视为新增，此段不输出。
        #    仅此段受 count/detail 模式影响。
        # ═══════════════════════════════════════════════════════
        if has_ov_history:
            installed = [row for row in outside_rows
                         if row.get('voiceID') not in added_ov_set]
        else:
            installed = []

        from . import l10n

        if installed:
            if is_count:
                result += '<br>' + l10n.text('notify/stats_installed') + _wrap_color(
                    '<br>' + l10n.text('notify/stats_installed_count') + str(len(installed)), C_EXIST)
            else:
                names_html = _build_name_lines(installed)
                result += '<br>' + l10n.text('notify/stats_installed') + _wrap_color(names_html, C_EXIST)
            result += '<br>'

        # ═══════════════════════════════════════════════════════
        # 2. 新增语音包（始终逐条显示名称）
        #    内置新增需要历史基线；第三方新增无此限制。
        # ═══════════════════════════════════════════════════════
        add_iv_html = ''
        add_ov_html = ''

        if has_iv_history and diff['added_ingame']:
            names = _resolve_names(diff['added_ingame'],
                                   g_voice_repo.ingame_rows)
            add_iv_html = _wrap_color(_build_name_lines(names), C_ADD_IV)

        if diff['added_outside']:
            names = _resolve_names(diff['added_outside'], outside_rows)
            add_ov_html = _wrap_color(_build_name_lines(names), C_ADD_OV)

        if add_iv_html or add_ov_html:
            result += '<br>' + l10n.text('notify/stats_added') + add_iv_html + add_ov_html + '<br>'
        elif has_ov_history or has_iv_history:
            result += '<br>' + l10n.text('notify/stats_added') + '<br>' + l10n.text('notify/stats_no_new') + '<br>'

        # ═══════════════════════════════════════════════════════
        # 3. 已移除的语音包（始终逐条显示名称）
        # ═══════════════════════════════════════════════════════
        if has_removals:
            names = _resolve_names(diff['removed_outside'],
                                   g_voice_repo._saved_outside)
            del_html = _wrap_color(_build_name_lines(names), C_REMOVED)
            result += '<br>' + l10n.text('notify/stats_removed') + del_html + '<br>'

        # ═══════════════════════════════════════════════════════
        # 4. 兜底——无任何可报告内容
        # ═══════════════════════════════════════════════════════
        if not result:
            if not has_outside and not has_removals:
                return '<br>' + l10n.text('notify/stats_empty') + '<br>'
            return None

        return result

    except Exception:
        logger.exception('构建语音包统计失败')
        return None


def _wrap_color(text, color):
    """用 font 标签包裹带颜色的文本。"""
    return '<font color="{}">{}</font>'.format(color, text)


def _resolve_names(voice_ids, rows):
    """从 rows 中查找 voiceID 对应的 nickName（找不到用 voiceID 兜底）。

    结果按名称排序保证输出稳定。
    """
    id_to_name = {row['voiceID']: row.get('nickName', row['voiceID'])
                  for row in rows if row.get('voiceID')}
    return sorted(id_to_name.get(vid, vid) for vid in voice_ids)


def _build_name_lines(names_or_rows):
    """构建逐行名称 HTML（每行以 <br> 开头）。

    可接受 dict 行列表（含 nickName/voiceID 键）或纯字符串列表。
    """
    if not names_or_rows:
        return ''
    lines = []
    for item in names_or_rows:
        if isinstance(item, dict):
            name = item.get('nickName', item.get('voiceID', ''))
        else:
            name = item
        lines.append('<br>' + name)
    return ''.join(lines)
