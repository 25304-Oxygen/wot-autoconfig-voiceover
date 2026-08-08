# coding=utf-8
"""PersonalSettingsPage —— 个性设置面板。

对应 Flash: com.github._25304_Oxygen.menu.pages.PersonalSettingsPage
入口: 半折叠面板导航按钮 "个性化"

用途: 被点亮喊话的自定义消息、存活队友数条件、快捷消息文本替换。
"""

import re

from helpers import i18n

from autoconfigvoiceover.constants import PERSONAL_SETTINGS_FILE
from autoconfigvoiceover.config_init import load_user_json
from autoconfigvoiceover.utils import load_jsonc, save_jsonc, deep_merge, to_utf8
from autoconfigvoiceover.logger import Logger

logger = Logger('PersonalSettingsPage')

# ═════════════════════════════════════════════════════════════
# 常量
# ═════════════════════════════════════════════════════════════

INGAMEGUI_JSON = 'ingameGuiText.json'
"""下拉列表与预览示例值数据源（磁盘优先，VFS 兜底）。
结构: {"placeholder": {原始占位符: 示例值}, "keyMap": [{text, key}, ...]}"""

PLACEHOLDER_PATTERN = re.compile(r'%\((\w+)\)[sdfg]')
"""匹配 %(target)s, %(reloadTime)d, %(floatArg1)f 等占位符。"""

SIMPLE_PLACEHOLDERS = ['<a>', '<b>', '<c>', '<d>', '<e>', '<f>', '<g>', '<h>']
"""简化占位符序列，按出现顺序分配给原始占位符。"""

SPOTTED_CELL_PLACEHOLDER = '<a>'
"""被点亮喊话中的坐标占位符——战斗时替换为小地图坐标（如 A1）。"""

SPOTTED_CELL_EXAMPLE = 'A1'
"""被点亮喊话预览用的示例坐标。"""

DEFAULTS = {
    'spottedMessage': '',
    'spottedAliveLe': 5,
    'replacements': {}
}

# ═════════════════════════════════════════════════════════════
# 模块级状态（单例，MenuManager 注入 _meta 后使用）
# ═════════════════════════════════════════════════════════════

_meta = None
_dropdown_items = []          # [{text, key}, ...]
_selected_index = 0           # 当前下拉选中索引
_selected_key = None          # 当前选中的 i18n key

# 预览用示例值 {原始占位符: 示例值}，从 ingameGuiText.json 的
# placeholder 字段加载。对于未列出的 %(xxx)s，预览时回退为 <xxx>。
_preview_values = {}

# 占位符映射（每个 key 独立）
# { '#ingame_gui:chat_shortcuts/xxx': {'<a>': '%(target)s', ...} }
_placeholder_maps = {}

# 简化后的格式字符串 { key: simplified_str }
_simplified_strings = {}

# 用户自定义替换字典（写入 personal_settings.json）
# { '#ingame_gui:chat_shortcuts/xxx': '打%(target)s！冷却%(reloadTime)d秒' }
_replacements = {}

# 被点亮喊话
_spotted_message = ''
_spotted_alive_le = 3

# 配置懒加载标志
_config_loaded = False

# 上次 populate 时使用的 selected index，用于检测是否需要保存上一个选中项的编辑
_last_populate_index = 0


# ═════════════════════════════════════════════════════════════
# 公开接口
# ═════════════════════════════════════════════════════════════

class PersonalSettingsPage(object):
    """个性设置页的业务逻辑。"""

    def __init__(self, meta):
        global _meta
        _meta = meta

    # ── 数据推送 ──

    def push_data(self):
        """向 Flash 推送个性设置页的全部初始数据。"""
        global _selected_index, _selected_key, _last_populate_index

        self._ensure_items_loaded()
        _load_config()

        if not _dropdown_items:
            logger.warn('下拉列表数据为空，跳过推送')
            return

        # 确定初始选中的 key
        if _selected_key is None and _dropdown_items:
            _selected_key = _dropdown_items[0]['key']
            _selected_index = 0

        _last_populate_index = _selected_index

        # 获取当前选中项的占位符映射和简化串
        mapping = _placeholder_maps.get(_selected_key, {})
        simplified = _simplified_strings.get(_selected_key, '')

        # 输入框内容：用户已保存的替换文本（还原占位符为简化形式），否则预填充简化格式串
        saved_replacement = _replacements.get(_selected_key, '')
        if saved_replacement:
            replace_text = _simplify_user_text(saved_replacement, mapping)
        else:
            replace_text = simplified  # 预填充，与 placeholder 相同内容

        # placeholder：简化后的格式字符串（占位提示走词典）
        from autoconfigvoiceover import l10n
        replace_placeholder = simplified if simplified else l10n.text('personal/replace_placeholder')

        # 被点亮喊话 placeholder
        spotted_placeholder = l10n.text('personal/spotted_placeholder')

        # 预览文本
        preview = self._build_preview(_selected_key, replace_text, mapping)

        data = {
            'spottedMessage': _spotted_message,
            'spottedMsgPlaceholder': spotted_placeholder,
            'spottedPreview': _build_spotted_preview(_spotted_message),
            'spottedAliveLe': _spotted_alive_le,
            'replaceDropdownItems': [item['text'] for item in _dropdown_items],
            'replaceSelectedIndex': _selected_index,
            'replaceText': replace_text,
            'replacePlaceholder': replace_placeholder,
            'previewText': preview,
            'tooltips': _get_tooltips(),
        }

        if _meta is not None:
            _meta.as_populatePersonalSettingsS(data)
            logger.info('个性设置页数据已推送 (selected=%s)', _selected_key)
        else:
            logger.warn('push_data: _meta 为 None')

    def _push_update(self, replace_text=None, preview_text=None):
        """推送增量更新到 Flash（用户交互后）。"""
        global _selected_index

        if _meta is None:
            return

        data = {
            'replaceSelectedIndex': _selected_index,
        }

        mapping = _placeholder_maps.get(_selected_key, {})
        simplified = _simplified_strings.get(_selected_key, '')

        from autoconfigvoiceover import l10n
        if replace_text is not None:
            data['replaceText'] = replace_text
            data['replacePlaceholder'] = simplified if simplified else l10n.text('personal/replace_placeholder')
        else:
            # 无用户输入时，预填充简化格式串
            saved = _replacements.get(_selected_key, '')
            if saved:
                data['replaceText'] = _simplify_user_text(saved, mapping)
            else:
                data['replaceText'] = simplified
            data['replacePlaceholder'] = simplified if simplified else l10n.text('personal/replace_placeholder')

        if preview_text is not None:
            data['previewText'] = preview_text
        else:
            data['previewText'] = self._build_preview(
                _selected_key,
                data.get('replaceText', ''),
                mapping,
            )

        _meta.as_populatePersonalSettingsS(data)

    # ── 回调处理 ──

    def handle_spotted_msg(self, text):
        """用户编辑被点亮喊话内容。"""
        global _spotted_message
        _spotted_message = text
        _save_config()

        # 更新右侧预览（<a> 替换为示例坐标）
        if _meta is not None:
            _meta.as_populatePersonalSettingsS({
                'spottedPreview': _build_spotted_preview(text),
            })
        logger.info('被点亮喊话已更新: %s', text)

    def handle_spotted_alive_le(self, value):
        """用户调节存活队友阈值。"""
        global _spotted_alive_le
        _spotted_alive_le = int(value)
        _save_config()
        logger.info('喊话触发阈值已更新: %d', _spotted_alive_le)

    def handle_replace_select(self, index_str):
        """用户切换下拉列表选中项。"""
        global _selected_index, _selected_key

        try:
            new_index = int(index_str)
        except (ValueError, TypeError):
            logger.warn('无效的下拉索引: %s', index_str)
            return

        if new_index < 0 or new_index >= len(_dropdown_items):
            logger.warn('下拉索引越界: %d (items=%d)', new_index, len(_dropdown_items))
            return

        _selected_index = new_index
        _selected_key = _dropdown_items[new_index]['key']

        mapping = _placeholder_maps.get(_selected_key, {})
        simplified = _simplified_strings.get(_selected_key, '')

        # 输入框内容：用户已保存的替换文本（还原占位符为简化形式），否则预填充简化格式串
        saved = _replacements.get(_selected_key, '')
        if saved:
            replace_text = _simplify_user_text(saved, mapping)
        else:
            replace_text = simplified

        preview = self._build_preview(_selected_key, replace_text, mapping)

        self._push_update(replace_text=replace_text, preview_text=preview)
        logger.info('下拉选中切换 → %s (index=%d)', _selected_key, _selected_index)

    def handle_replace_text(self, text):
        """用户编辑替换文本。"""
        global _selected_key

        if _selected_key is None:
            logger.warn('handle_replace_text: _selected_key 为 None')
            return

        mapping = _placeholder_maps.get(_selected_key, {})

        if not text or text.strip() == '':
            # 清空输入框 → 从替换字典中移除
            _replacements.pop(_selected_key, None)
            logger.info('替换文本已清空，移除 key: %s', _selected_key)
        else:
            # 还原占位符 → 存入替换字典
            restored = _restore_placeholders(text, mapping)
            _replacements[_selected_key] = restored
            logger.info('替换文本已更新: %s → %s', text, restored)

        _save_config()

        # 更新预览
        preview = self._build_preview(_selected_key, text, mapping)
        self._push_update(replace_text=text, preview_text=preview)

    # ── 内部方法 ──

    def _ensure_items_loaded(self):
        """确保 _dropdown_items、_preview_values 和 _simplified_strings 已加载。"""
        global _dropdown_items, _simplified_strings, _placeholder_maps
        global _preview_values

        if _dropdown_items:
            return  # 已加载

        # 1. 读取 ingameGuiText.json（磁盘优先 → VFS 兜底 → 写回磁盘）
        data = load_user_json(INGAMEGUI_JSON)
        if data is None:
            logger.error('无法读取 %s（磁盘和 VFS 均不可用）', INGAMEGUI_JSON)
            return

        _preview_values = data.get('placeholder', {}) or {}
        items = data.get('keyMap', []) or []
        if not items:
            logger.error('%s 缺少 keyMap 数据', INGAMEGUI_JSON)
            return

        _dropdown_items = items
        logger.info('已加载 %d 条预览示例值', len(_preview_values))

        # 2. 为每个 item 获取格式字符串并简化
        for item in items:
            key = item.get('key', '')
            if not key:
                continue

            try:
                format_str = i18n.makeString(key)
            except Exception:
                logger.warn('makeString 失败: %s', key)
                format_str = key  # 回退为 key 本身

            result = _simplify_placeholders(format_str)
            _simplified_strings[key] = result['simplified']
            _placeholder_maps[key] = result['mapping']

        logger.info('已加载 %d 条快捷消息', len(_dropdown_items))

    def _build_preview(self, key, user_text, mapping):
        """构造预览文本。

        1. 如果有用户输入 → 还原为原始占位符 → 用示例值替换 → 返回
        2. 否则 → 用原始格式字符串 → 用示例值替换 → 返回
        """
        if not key:
            return u''

        # 确定要预览的文本（含原始占位符）
        saved = _replacements.get(key, '')
        if saved:
            raw_text = saved  # 用户保存的文本，已含原始占位符
        elif user_text and user_text.strip():
            # 用户正在输入但尚未保存 → 还原占位符
            raw_text = _restore_placeholders(user_text, mapping)
        else:
            # 使用原始格式字符串
            try:
                raw_text = i18n.makeString(key)
            except Exception:
                raw_text = key

        return _substitute_preview(raw_text)


# ═════════════════════════════════════════════════════════════
# 占位符处理（模块级函数，无副作用）
# ═════════════════════════════════════════════════════════════

def _build_spotted_preview(text):
    """构造被点亮喊话的预览文本——<a> 替换为示例坐标。

    例如: "我在<a>被点亮了！" → "我在A1被点亮了！"
    空输入返回空串（预览区留白）。
    """
    if not text or not text.strip():
        return ''
    return text.replace(SPOTTED_CELL_PLACEHOLDER, SPOTTED_CELL_EXAMPLE)


def _get_tooltips():
    """返回个性设置页各组件 Tooltip 的富文本 HTML 字典（随生效语言）。"""
    from autoconfigvoiceover import l10n
    return {
        'spottedMessage': l10n.text('personal/tooltip/spotted_message'),
    }


def _simplify_placeholders(format_str):
    """将格式字符串中的 %(xxx)s / %(xxx)d 替换为 <a>, <b>, ...。

    :returns: {'simplified': str, 'mapping': {'<a>': '%(target)s', ...}}
    """
    if not format_str:
        return {'simplified': '', 'mapping': {}}

    matches = PLACEHOLDER_PATTERN.findall(format_str)
    # 去重但保持顺序
    seen = set()
    unique = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique.append(m)

    mapping = {}
    simplified = format_str

    for i, var_name in enumerate(unique):
        if i >= len(SIMPLE_PLACEHOLDERS):
            break
        original = '%({})'.format(var_name)
        # 找到完整占位符（带类型后缀）
        full_pattern = re.compile(r'%\(' + re.escape(var_name) + r'\)[sdfg]')
        full_match = full_pattern.search(format_str)
        if full_match:
            original_full = full_match.group(0)
            simple = SIMPLE_PLACEHOLDERS[i]
            mapping[simple] = original_full
            simplified = simplified.replace(original_full, simple)

    return {'simplified': simplified, 'mapping': mapping}


def _restore_placeholders(user_text, mapping):
    """将用户文本中的简化占位符 <a>, <b> 还原为原始占位符。

    例如: "打<a>！冷却<b>秒" → "打%(target)s！冷却%(reloadTime)d秒"
    """
    if not user_text or not mapping:
        return user_text

    result = user_text
    for simple, original in mapping.items():
        result = result.replace(simple, original)
    return result


def _simplify_user_text(user_text, mapping):
    """将用户保存的文本（含原始占位符）转换回简化形式，用于在输入框中显示。

    例如: "打%(target)s！冷却%(reloadTime)d秒" → "打<a>！冷却<b>秒"
    """
    if not user_text or not mapping:
        return user_text

    result = user_text
    for simple, original in mapping.items():
        result = result.replace(original, simple)
    return result


def _substitute_preview(text):
    """将文本中的占位符替换为示例值，用于预览。

    示例值来自 ingameGuiText.json 的 placeholder 字段。
    例如: "攻击%(target)s，装填还需%(reloadTime)d秒"
       → "攻击目标，装填还需114514秒"
    """
    if not text:
        return ''

    result = text
    for placeholder, example in _preview_values.items():
        result = result.replace(placeholder, example)

    # 对未列出的 %(xxx)s 占位符，替换为变量名本身
    remaining = PLACEHOLDER_PATTERN.findall(result)
    for var_name in remaining:
        full = PLACEHOLDER_PATTERN.search(result)
        if full:
            result = result.replace(full.group(0), '<' + var_name + '>')

    return result


# ═════════════════════════════════════════════════════════════
# 公共 getter（供 hooks.py 等战斗模块使用，无需实例化页面）
# ═════════════════════════════════════════════════════════════

def get_replacement(key):
    """返回指定 i18n key 的用户自定义替换文本（已还原占位符），无替换时返回 None。

    供 i18n.makeString 钩子调用。key 格式: #ingame_gui:chat_shortcuts/xxx
    首次调用时懒加载配置（hooks 可能早于设置页初始化）。
    """
    if not _config_loaded:
        _load_config()
    return _replacements.get(key)


def get_spotted_config():
    """返回 (spotted_message, spotted_alive_le) 元组。

    spotted_message 为空字符串表示用户未设置被点亮喊话。
    供第六感钩子调用。
    首次调用时懒加载配置（hooks 可能早于设置页初始化）。
    """
    if not _config_loaded:
        _load_config()
    return (_spotted_message, _spotted_alive_le)


# ═════════════════════════════════════════════════════════════
# 配置读写
# ═════════════════════════════════════════════════════════════

def _load_config():
    """从 personal_settings.json 加载已保存的配置。"""
    global _spotted_message, _spotted_alive_le, _replacements, _selected_index, _selected_key
    global _config_loaded

    data = load_jsonc(PERSONAL_SETTINGS_FILE)
    if data is None:
        data = dict(DEFAULTS)
    else:
        data = deep_merge(DEFAULTS, data)

    _spotted_message = to_utf8(data.get('spottedMessage', ''))
    _spotted_alive_le = data.get('spottedAliveLe', 3)
    _replacements = data.get('replacements', {})

    logger.info('配置已加载: spottedMessage=%s, spottedAliveLe=%d, replacements=%d keys',
                _spotted_message, _spotted_alive_le, len(_replacements))
    _config_loaded = True


def _save_config():
    """将当前状态保存到 personal_settings.json。"""
    save_jsonc(PERSONAL_SETTINGS_FILE, {
        'spottedMessage': _spotted_message,
        'spottedAliveLe': _spotted_alive_le,
        'replacements': _replacements
    }, header_comment='个性设置：被点亮喊话与快捷消息替换')
