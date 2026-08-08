# coding=utf-8
"""SubtitleSettingsPage —— 字幕设置面板。

对应 Flash: com.github._25304_Oxygen.menu.pages.SubtitleSettingsPage
入口: 半折叠面板导航按钮 "字幕"

用途: 调整字幕各元素（头像/标题/背景/正文）在屏幕上的位置。

Flash → Python 消息（经 onLog 路由）:
    subtitleEditStart          — 进入编辑模式
    subtitleEditTarget,<id>    — 选择调整目标 (avatar/title/bg/body)
    subtitleEditSave,<reason>  — 保存 (done/pageHidden/dispose)
    subtitleEditReset          — 重置位置为默认并结束编辑

编辑模式流程:
  1. 用户按"编辑" → 加载模板句子 + 偏移 → SubtitleView 显示静态预览
  2. 用户选目标 → SubtitleView 高亮对应组件边框（白→金黄）
  3. 用户拖拽组件 → Flash 回调 onEditOffset → Python 累积偏移
  4. 完成/重置 → 保存/清零偏移 → 隐藏预览
"""

from autoconfigvoiceover.logger import Logger

logger = Logger('SubtitleSettingsPage')

# ═════════════════════════════════════════════════════════════
# 常量
# ═════════════════════════════════════════════════════════════

TARGET_NAMES = {
    'avatar': '头像',
    'title':  '标题',
    'bg':     '背景',
    'body':   '正文',
}
"""调整目标 id → 中文名（日志用，unicode）。"""

# UI 按钮 id → renderer 组件名
_TARGET_TO_COMPONENT = {
    'avatar': 'poster',
    'title':  'tf_title',
    'bg':     'background',
    'body':   'tf_message',
}

# renderer 组件名 → UI 按钮 id（反向映射）
_COMPONENT_TO_TARGET = {v: k for k, v in _TARGET_TO_COMPONENT.items()}

# ═════════════════════════════════════════════════════════════
# 模块级状态（单例，MenuManager 注入 _meta 后使用）
# ═════════════════════════════════════════════════════════════

_meta = None

# 是否处于编辑模式（Python 侧镜像，用于 View 销毁时的兜底保存）
_editing = False

# 当前编辑会话选中的调整目标（None = 未选择）
_current_target = None

# 当前编辑会话的累积偏移 {component_name: {x, y}}
_edit_offsets = {}

# 当前编辑会话的语音包 VFS 根目录
_pack_root = None


# ═════════════════════════════════════════════════════════════
# 公开接口
# ═════════════════════════════════════════════════════════════

class SubtitleSettingsPage(object):
    """字幕设置页的业务逻辑。"""

    def __init__(self, meta):
        global _meta
        _meta = meta

    # ── 数据推送 ──

    def push_data(self):
        """向 Flash 推送字幕设置页的初始数据。"""
        data = {
            'tooltips': _get_tooltips(),
            'displayMode': _get_display_mode(),
        }

        if _meta is not None:
            _meta.as_populateSubtitleSettingsS(data)
            logger.info('字幕设置页数据已推送')
        else:
            logger.warn('push_data: _meta 为 None')

    # ── 回调处理 ──

    def handle_edit_start(self):
        """用户按下"编辑"，进入字幕位置编辑模式。"""
        global _editing, _current_target, _edit_offsets, _pack_root

        _editing = True
        _current_target = None

        # —— 获取当前活跃语音包 ——
        try:
            from autoconfigvoiceover.voices.active_voice import g_active_mgr
            active = g_active_mgr.current
        except Exception:
            logger.exception('获取活跃语音包失败')
            active = None

        if active is None or active.is_builtin:
            logger.info('当前无第三方语音包，无法进入编辑模式')
            _editing = False
            return

        pack_root = active.pack.root
        _pack_root = pack_root

        # —— 检查字幕可用性 ——
        from autoconfigvoiceover.subtitle.loader import (
            is_subtitle_available, load_style, load_template_sentence,
            load_offsets,
        )

        if not is_subtitle_available(pack_root):
            logger.info('语音包 %s 无合法字幕样式，无法进入编辑模式', pack_root)
            _editing = False
            return

        # —— 加载样式（在加载模板句子之前，需要用 style.lang 匹配语句文件的键名语言）——
        style = load_style(pack_root)

        # —— 加载模板句子 ——
        template_data = load_template_sentence(pack_root, style.lang)
        if template_data is None or not template_data.timeline:
            logger.info('语音包 %s 无可用模板句子，无法进入编辑模式', pack_root)
            _editing = False
            return

        # —— 加载偏移 ——
        offsets = load_offsets(pack_root)
        _edit_offsets = dict(offsets)

        # —— 组装预览数据 ——
        entry = template_data.timeline[0]
        preview_data = _assemble_preview_data(style, entry)

        # —— 确保 SubtitleView 在当前上下文中已加载 ——
        # 从战斗返回车库后，旧 View 已被销毁，_view_instance 可能为 None
        # 或指向失效的 SWF 对象。ensure_subtitle_view 会按需重新加载。
        try:
            from autoconfigvoiceover.subtitle.host import (
                _view_instance, ensure_subtitle_view,
                set_edit_offset_callback,
            )
            ensure_subtitle_view()
            if _view_instance is not None:
                _view_instance.as_showPreviewS(preview_data, offsets)
                set_edit_offset_callback(_on_offset_updated)
                logger.info('预览已显示 (content=%s...)', entry.text[:30])
            else:
                logger.warn('字幕 View 未加载，无法显示预览')
                _editing = False
                return
        except Exception:
            logger.exception('显示预览失败')
            _editing = False
            return

        logger.info('进入字幕位置编辑模式')

    def handle_edit_target(self, target):
        """用户选择调整目标。

        :param target: avatar / title / bg / body
                       简洁模式下仅 body（正文）有效，其余忽略。
        """
        global _current_target

        # 简洁模式下仅正文位置可编辑
        if _get_display_mode() == 'concise' and target != 'body':
            logger.debug('简洁模式下目标 %s 不可编辑，已忽略', target)
            return

        _current_target = target

        component = _TARGET_TO_COMPONENT.get(target, target)

        try:
            from autoconfigvoiceover.subtitle.host import _view_instance
            if _view_instance is not None:
                _view_instance.as_setEditTargetS(component)
                logger.info('选择调整目标: %s → %s', target, component)
        except Exception:
            logger.exception('设置编辑目标失败: %s', target)

    def handle_save(self, reason):
        """结束编辑并保存。

        :param reason: done（按"完成"）/ pageHidden（切页/关菜单/F10 隐藏）/
                       dispose（View 销毁，如车库↔战斗切换）
        """
        global _editing, _current_target, _edit_offsets, _pack_root
        if not _editing:
            logger.debug('handle_save: 未在编辑中，跳过 (reason=%s)', reason)
            return

        # —— 保存偏移到磁盘 ——
        if _pack_root and _edit_offsets:
            from autoconfigvoiceover.subtitle.loader import save_offsets
            save_offsets(_pack_root, _edit_offsets)

            # 通知字幕管理器重载偏移（战斗中编辑保存后立刻生效）
            from autoconfigvoiceover.subtitle.host import reload_subtitle_offsets
            reload_subtitle_offsets()

        # —— 隐藏预览 ——
        _hide_preview()

        _editing = False
        _current_target = None
        _edit_offsets = {}
        _pack_root = None

        logger.info('字幕位置已保存 (reason=%s)', reason)

    def handle_reset(self):
        """重置字幕位置为默认并结束编辑。"""
        global _editing, _current_target, _edit_offsets, _pack_root
        if not _editing:
            logger.debug('handle_reset: 未在编辑中，跳过')
            return

        # —— 写全零偏移 ——
        zero = {
            'poster':      {'x': 0, 'y': 0},
            'tf_title':    {'x': 0, 'y': 0},
            'background':  {'x': 0, 'y': 0},
            'tf_message':  {'x': 0, 'y': 0},
            'simple_mode': {'x': 0, 'y': 0},
        }
        if _pack_root:
            from autoconfigvoiceover.subtitle.loader import save_offsets
            save_offsets(_pack_root, zero)

            # 通知字幕管理器重载偏移
            from autoconfigvoiceover.subtitle.host import reload_subtitle_offsets
            reload_subtitle_offsets()

        # —— 隐藏预览 ——
        _hide_preview()

        _editing = False
        _current_target = None
        _edit_offsets = {}
        _pack_root = None

        logger.info('字幕位置已重置为默认')

    def ensure_saved(self, reason):
        """View 销毁前的兜底保存。

        车库↔战斗切换时 Flash 侧 dispose 链路（onAction→DAAPI）
        可能已断开送达不了，由 ACVMenuMeta._dispose() 主动调用此方法，
        基于 Python 侧镜像的编辑状态直接保存。
        """
        if _editing:
            logger.info('检测到编辑中未保存，执行兜底保存')
            self.handle_save(reason)


# ═════════════════════════════════════════════════════════════
# 模块级函数
# ═════════════════════════════════════════════════════════════


def _on_offset_updated(target, x, y):
    """Flash 拖拽松手后的偏移回调。

    :param target: 组件名（标准模式: poster/tf_title/background/tf_message；
                   简洁模式: tf_message → 映射为 simple_mode 偏移键）
    :param x:      累积偏移 X（px）
    :param y:      累积偏移 Y（px）
    """
    global _edit_offsets
    # 简洁模式下正文偏移存入独立的 simple_mode 键
    if _get_display_mode() == 'concise' and target == 'tf_message':
        target = 'simple_mode'
    _edit_offsets[target] = {'x': int(x), 'y': int(y)}
    logger.debug('偏移更新: %s → (%d, %d)', target, int(x), int(y))


def _hide_preview():
    """隐藏字幕预览并清除偏移回调。"""
    try:
        from autoconfigvoiceover.subtitle.host import (
            _view_instance, set_edit_offset_callback,
        )
        set_edit_offset_callback(None)
        if _view_instance is not None:
            _view_instance.as_hidePreviewS()
            logger.debug('预览已隐藏')
    except Exception:
        logger.exception('隐藏预览失败')


def _assemble_preview_data(style, entry):
    """组装预览用的 Flash 渲染数据。

    根据当前字幕显示模式（standard/concise）组装对应格式的结构。
    取 timeline 第一条的样式代号，用 style 解析为实际样式值。

    :param style: SubtitleStyle 实例
    :param entry: SubtitleEntry（template timeline[0]）
    :return: dict（与 manager._assemble_data 同格式，加 preview 标记）
    """
    mode = _get_display_mode()
    if mode == 'concise':
        return _assemble_preview_concise(style, entry)
    else:
        return _assemble_preview_standard(style, entry)


def _get_display_mode():
    """读取当前字幕显示模式（standard/concise/none）。"""
    try:
        from autoconfigvoiceover.config import load_config
        se = load_config(log=False).get('settings', {})
        mode = se.get('subtitleDisplay', 'standard')
        if mode == 'simple':
            mode = 'concise'
        return mode
    except Exception:
        return 'standard'


def _assemble_preview_standard(style, entry):
    """标准模式预览数据。"""
    poster = style.get_poster(entry.poster)
    background = style.get_background(entry.background)
    tf_title = style.get_tf_title(entry.tf_title)
    tf_message = style.get_tf_message(entry.tf_message)

    # 规范化 tf_title：图片类型 → size 为 [w,h] 数组；文本类型 → 去 img，
    # 并将 size 由 [0,0]（图片尺寸占位）转为 font_size 字号——样式约定
    # size=图片尺寸、font_size=文字字号，Flash 端 _makeTextField 只认 size。
    # 与渲染路径 assembler._assemble_standard 保持一致。
    tf_title = dict(tf_title)
    if tf_title.get('img', ''):
        if not isinstance(tf_title.get('size'), list):
            tf_title['size'] = [200, 40]
    else:
        tf_title.pop('img', None)
        sz = tf_title.get('size', [0, 0])
        if isinstance(sz, list):
            tf_title['size'] = tf_title.get('font_size', 14)

    # 标题文本: 样式代号即文本内容。
    # 跳过条件: ①无代号 ②图片标题 ③空字典 {}（不显示）
    title_text = ''
    if entry.tf_title and not tf_title.get('img', '') and len(tf_title) > 0:
        title_text = entry.tf_title

    data = {
        'mode':       'standard',
        'preview':    True,
        'text_speed': 0,
        'poster':     dict(poster),
        'background': dict(background),
        'tf_title':   tf_title,
        'tf_message': dict(tf_message),
        'anime':      [],
        'anime_start_at': [],
    }
    data['tf_title']['text'] = title_text
    data['tf_message']['text'] = entry.text

    return data


def _assemble_preview_concise(style, entry):
    """简洁模式预览数据。"""
    name_code = entry.tf_title
    msg_style = style.get_tf_message(entry.tf_message)
    title_style = style.get_tf_title(name_code if name_code else '')
    sm = style.get_simple_mode()

    # 角色名后加全角冒号（展示层，与 manager._assemble_concise 一致）
    # 若标题样式为空字典 {}（用户标记"不显示该组件"）→ 角色名也隐藏
    if len(title_style) == 0:
        display_name = ''
    else:
        display_name = (name_code + '：') if name_code else ''

    data = {
        'mode':       'concise',
        'preview':    True,
        'text_speed': 0,
        'anime':      [],
        'anime_start_at': [],
        'concise': {
            'name':       display_name,
            'name_color': title_style.get('color', '#FFFFFF'),
            'text':       entry.text,
            'text_color': msg_style.get('color', '#FFFFFF'),
            'position':   sm['msg_position'],
            'width':      sm['msg_width'],
            'font':       msg_style.get('font', '$FieldFont'),
            'size':       msg_style.get('size', 14),
            'gap':        sm['title_msg_gap'],
        },
    }

    return data


def ensure_saved_on_voice_switch():
    """语音切换时的兜底保存——若当前正在编辑中，先保存再切换。

    由 sound._on_active_voice_changed 调用。
    """
    global _editing, _edit_offsets, _pack_root
    if not _editing:
        return

    logger.info('语音切换时检测到字幕编辑中，执行兜底保存')
    if _pack_root and _edit_offsets:
        from autoconfigvoiceover.subtitle.loader import save_offsets
        save_offsets(_pack_root, _edit_offsets)

        # 通知字幕管理器重载偏移
        from autoconfigvoiceover.subtitle.host import reload_subtitle_offsets
        reload_subtitle_offsets()

    _hide_preview()
    _editing = False
    _edit_offsets = {}
    _pack_root = None


def repush_display_mode():
    """当用户在设置页切换字幕显示模式后，通知 Flash SubtitleSettingsPage 更新。

    仅推送 displayMode 字段，不重推 tooltips（避免不必要的 Tooltip 重建）。
    """
    global _meta
    if _meta is None:
        return
    try:
        data = {'displayMode': _get_display_mode()}
        _meta.as_populateSubtitleSettingsS(data)
        logger.debug('displayMode 已推送到 Flash: %s', data['displayMode'])
    except Exception:
        logger.exception('推送 displayMode 失败')


def _get_tooltips():
    """返回字幕设置页各组件 Tooltip 的富文本 HTML 字典（随生效语言）。"""
    from autoconfigvoiceover import l10n
    return {
        'pageTitle': l10n.text('subtitle_settings/tooltip/page_title'),
    }
