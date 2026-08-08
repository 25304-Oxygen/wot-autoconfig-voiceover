# coding=utf-8
"""字幕数据加载：样式文件 + 句子文件的双语键名解析。

约定：
  样式文件: {pack_root}subtitles/ 下第一个 .json（不存在→字幕功能不开启）
  句子文件: {pack_root}subtitles/sentences/{marker}.json（marker=音频内嵌名）
  lang 键决定键名语言：缺省/zh_cn→中文键名，en/其他→英文键名
  图片路径: 从 subtitles/images/ 出发的相对路径，加载时解析为 VFS 全路径
"""

import json
import os
from collections import OrderedDict

import ResMgr

from autoconfigvoiceover.constants import MY_SUBTITLES_FOLDER
from autoconfigvoiceover.logger import Logger
from autoconfigvoiceover.utils import load_vfs_json

logger = Logger('SubtitleLoader')

# ═════════════════════════════════════════════════════════════
# 键名映射表
#
# 每个映射表 = {原始键名: 规范键名}。
# 中文映射表直接将中文键名映射到英文章节名，方便后续统一处理。
# ═════════════════════════════════════════════════════════════

# —— 样式文件顶层键名 ——
_CN_STYLE_TOP = {
    '头像样式列表': 'posters',
    '背景样式列表': 'backgrounds',
    '标题样式列表': 'tf_titles',
    '正文样式列表': 'tf_messages',
    '简洁模式':      'simple_mode',
}

_EN_STYLE_TOP = {
    'posters':     'posters',
    'backgrounds': 'backgrounds',
    'tf_titles':   'tf_titles',
    'tf_messages': 'tf_messages',
    'simple_mode': 'simple_mode',
}

# —— 样式文件元素键名 ——
_CN_STYLE_ITEM = {
    '图片路径':  'img',
    '尺寸':      'size',
    '字号':      'font_size',
    '位置':      'position',
    '颜色码':    'color',
    '圆角大小':  'radius',
    '透明度':    'alpha',
    '宽度':      'width',
    '字体':      'font',
    '对齐方式':  'align',
    # 简洁模式子字段
    '正文宽度':     'msg_width',
    '正文位置':     'msg_position',
    '标题正文间隔': 'title_msg_gap',
}

_EN_STYLE_ITEM = {
    'img':       'img',
    'size':      'size',
    'font_size': 'font_size',
    'position':  'position',
    'color':     'color',
    'radius':    'radius',
    'alpha':     'alpha',
    'width':     'width',
    'font':      'font',
    'align':     'align',
    # 简洁模式子字段
    'msg_width':     'msg_width',
    'msg_position':  'msg_position',
    'title_msg_gap': 'title_msg_gap',
}

# —— 句子文件顶层键名 ——
_CN_SENTENCE = {
    '时长': 'duration',
    '顺序': 'timeline',
}

_EN_SENTENCE = {
    'duration': 'duration',
    'timeline': 'timeline',
}

# —— 句子 timeline 条目键名 ——
_CN_TIMELINE_ENTRY = {
    '文本':     'text',
    '角色代号': 'character',
    '头像样式': 'poster',
    '背景样式': 'background',
    '正文样式': 'tf_message',
    '标题样式': 'tf_title',
    '开始时间': 'start_at',
    '入场动画': 'anime',
    '入场动画开始时间': 'anime_start_at',
}

_EN_TIMELINE_ENTRY = {
    'text':           'text',
    'character':      'character',
    'poster':         'poster',
    'background':     'background',
    'tf_message':     'tf_message',
    'tf_title':       'tf_title',
    'start_at':       'start_at',
    'anime':          'anime',
    'anime_start_at': 'anime_start_at',
}

# —— 对齐方式值映射（中文→英文章节名）——
_CN_ALIGN_VALUES = {
    '左对齐': 'left',
    '右对齐': 'right',
    '居中':   'center',
}

# ═════════════════════════════════════════════════════════════
# 硬编码默认值
#
# 样式段为空（{}）或第一个键损坏时使用。
# alpha=0 的背景 → Flash 端不显示背景。
# ═════════════════════════════════════════════════════════════

_DEFAULTS = {
    'poster': {
        'img':      '',
        'size':     [0, 0],
        'position': [0, 0],
    },
    'background': {
        'img':      '',
        'size':     [0, 0],
        'position': [0, 0],
        'color':    '#000000',
        'radius':   0,
        'alpha':    0,
    },
    'tf_title': {
        'img':       '',
        'width':     0,
        'position':  [0, 0],
        'color':     '#F9F74D',
        'font':      '$FieldFont',
        'size':      [0, 0],
        'font_size': 14,
        'align':     'left',
    },
    'tf_message': {
        'width':     0,
        'position':  [0, 0],
        'color':     '#FFFFFF',
        'font':      '$FieldFont',
        'size':      14,
        'align':     'left',
    },
}

# ═════════════════════════════════════════════════════════════
# 数据类
# ═════════════════════════════════════════════════════════════


class SubtitleStyle(object):
    """字幕样式配置（一个语音包的完整视觉样式）。

    包含四个样式表（posters / backgrounds / tf_titles / tf_messages），
    每个为 {代号: {字段...}} 的 OrderedDict，首键即为默认项。
    外加 simple_mode 简洁模式独立配置（普通 dict，非代号→样式映射）。
    """

    __slots__ = ('lang', 'posters', 'backgrounds', 'tf_titles', 'tf_messages',
                 'simple_mode')

    def __init__(self, lang, posters, backgrounds, tf_titles, tf_messages,
                 simple_mode=None):
        """
        :param lang:        'zh_cn' | 'en' | 其他
        :param posters:     OrderedDict {code: {img, size, position}}
        :param backgrounds: OrderedDict {code: {img, size, position, color, radius, alpha}}
        :param tf_titles:   OrderedDict {code: {width, position, color, font, align}}
        :param tf_messages: OrderedDict {code: {width, position, color, font, align}}
        :param simple_mode: dict {msg_width, msg_position, title_msg_gap} | None
                            简洁模式独立配置，None/空键→get_simple_mode() 回退到 tf_messages
        """
        self.lang = lang
        self.posters = posters
        self.backgrounds = backgrounds
        self.tf_titles = tf_titles
        self.tf_messages = tf_messages
        self.simple_mode = simple_mode or {}

    def get_default_code(self, section_name):
        """返回指定样式段的第一个代号（默认项）；无数据返回空串。"""
        section = getattr(self, section_name, None)
        if section:
            return next(iter(section), '')
        return ''

    def get_poster(self, code=''):
        """获取头像样式；空代号或找不到→默认。"""
        return self._get_section(self.posters, code, _DEFAULTS['poster'])

    def get_background(self, code=''):
        """获取背景样式；空代号或找不到→默认。"""
        return self._get_section(self.backgrounds, code, _DEFAULTS['background'])

    def get_tf_title(self, code=''):
        """获取标题样式；空代号或找不到→默认。"""
        return self._get_section(self.tf_titles, code, _DEFAULTS['tf_title'])

    def get_tf_message(self, code=''):
        """获取正文样式；空代号或找不到→默认。"""
        return self._get_section(self.tf_messages, code, _DEFAULTS['tf_message'])

    def get_simple_mode(self):
        """获取简洁模式的独立配置，缺省字段回退到 tf_messages 默认项。

        回退链:
          msg_width       → simple_mode 优先 → tf_messages.width 回退 → 0
          msg_position    → simple_mode 优先 → tf_messages.position 回退 → [0, 0]
          title_msg_gap   → simple_mode 优先 → 硬编码 20

        :return: dict {msg_width, msg_position, title_msg_gap}
        """
        msg_default = self.get_tf_message('')
        sm = self.simple_mode or {}

        msg_width = sm.get('msg_width')
        if msg_width is None:
            msg_width = msg_default.get('width', 0)

        msg_position = sm.get('msg_position')
        if msg_position is None:
            msg_position = msg_default.get('position', [0, 0])

        title_msg_gap = sm.get('title_msg_gap', 20)

        return {
            'msg_width':     msg_width,
            'msg_position':  msg_position,
            'title_msg_gap': title_msg_gap,
        }

    @staticmethod
    def _get_section(section, code, fallback):
        """获取样式，逐字段回退到 default 命名样式。

        两级回退链（逐字段）：
          1. code 显式给出且值有效 → 使用
          2. 回退到段内键名 "default"（或首键）的对应字段
          3. 回退到硬编码 fallback 参数

        空字典 {} 表示"有意不显示该组件"，原样返回不补齐。

        :param section:  OrderedDict {code: {field...}}，首键为默认项
        :param code:     请求的样式代号，空串=取默认
        :param fallback: 硬编码默认值 dict（_DEFAULTS 的对应段）
        :return:         逐字段补齐后的 dict
        """
        # ── 第一步：解析 default 引用样式（带硬编码兜底）──
        if section:
            if 'default' in section:
                default_raw = section['default']
            else:
                first_key = next(iter(section), None)
                default_raw = section[first_key] if first_key is not None else None
        else:
            default_raw = None

        # 将 default_raw 的缺失/无效字段用硬编码 fallback 补齐
        if default_raw is not None and default_raw:
            # 非空字典：逐字段检查，无效值→硬编码
            default_resolved = {}
            for key, fb_val in fallback.items():
                val = default_raw.get(key)
                if val is not None and not (isinstance(val, basestring) and val == ''):
                    default_resolved[key] = val
                else:
                    default_resolved[key] = fb_val
        elif default_raw is not None and not default_raw:
            # default_raw 是 {}（空字典）→ 非常见情况，当硬编码兜底
            default_resolved = dict(fallback)
        else:
            # 段完全为空 → 纯硬编码
            default_resolved = dict(fallback)

        # ── 第二步：取请求的样式 ──
        if code and code in section:
            raw = section[code]
        else:
            return default_resolved

        # 空字典 {} = 有意不显示，原样返回
        if not raw:
            return {}

        # ── 第三步：逐字段合并（code 的有效值覆盖 default）──
        result = dict(default_resolved)
        for key, value in raw.items():
            # 空字符串视为"用户留空=无效"，保持 default 的值
            if value is not None and not (isinstance(value, basestring) and value == ''):
                result[key] = value

        return result


class SubtitleEntry(object):
    """timeline 中的一条字幕。"""

    __slots__ = ('text', 'character', 'poster', 'background',
                 'tf_message', 'tf_title',
                 'start_at', 'anime', 'anime_start_at')

    def __init__(self, text='', character='', poster='', background='',
                 tf_message='', tf_title='',
                 start_at=0.0, anime=None, anime_start_at=None):
        self.text = text
        self.character = character
        self.poster = poster            # 样式代号，空=默认
        self.background = background    # 样式代号，空=默认
        self.tf_message = tf_message    # 样式代号，空=默认
        self.tf_title = tf_title        # 样式代号，空=默认
        self.start_at = start_at        # 该条目在字幕生命周期中的出现时间（秒）
        # anime / anime_start_at 已归一化为等长列表（见 _normalize_anime）
        self.anime = anime or []        # [str, ...] 额外动画代号序列
        self.anime_start_at = anime_start_at or []  # [float, ...] 每个动画前的等待秒数


class SubtitleData(object):
    """一个字幕文件（对应一个音频内嵌名）的完整内容。"""

    __slots__ = ('duration', 'timeline')

    def __init__(self, duration=1.0, timeline=None):
        """
        :param duration: 字幕总持续秒数（独立于音频长度）
        :param timeline:  [SubtitleEntry, ...] 依次弹出的对话条目
        """
        self.duration = duration
        self.timeline = timeline or []


# ═════════════════════════════════════════════════════════════
# 公开 API
# ═════════════════════════════════════════════════════════════


def collect_style_images(style):
    """收集样式文件中引用的所有图片 URL（已解析为 VFS 全路径）。

    遍历 posters / backgrounds / tf_titles 三个段，
    提取所有非空的 img 字段值，去重后返回。
    用于字幕初始化时批量预加载图片到 ImageCache。

    :param style: SubtitleStyle
    :return: list[str] 去重后的 VFS 全路径列表（可能为空）
    """
    urls = set()
    for section in (style.posters, style.backgrounds, style.tf_titles):
        if not section:
            continue
        for _code, item in section.items():
            if not item:
                continue
            img = item.get('img', '')
            if img:
                urls.add(img)
    return list(urls)


def is_subtitle_available(pack_root):
    """检查语音包是否有可用的字幕样式 JSON。

    条件:
      1. JSON 文件存在且可解析（load_style 返回非 None）
      2. 四个样式段（posters / backgrounds / tf_titles / tf_messages）
         中至少有一个非空

    内置语音的 pack_root 为 None，直接返回 False。

    :param pack_root: 语音包 VFS 根目录，None 表示内置语音
    :return: bool
    """
    if not pack_root:
        return False
    style = load_style(pack_root)
    if style is None:
        return False
    return bool(style.posters or style.backgrounds
                or style.tf_titles or style.tf_messages)


def load_style(pack_root):
    """加载语音包的字幕样式文件。

    扫描 {pack_root}subtitles/ 下第一个 .json 文件。
    不存在或解析失败 → 返回 None（字幕功能不启用）。

    :param pack_root: 语音包 VFS 根目录，如 'mods/voiceover/my_pack/'
    :return: SubtitleStyle | None
    """
    subtitles_dir = pack_root + 'subtitles/'

    style_path = _find_first_json(subtitles_dir)
    if style_path is None:
        logger.info('未找到字幕样式文件（%s 下无 .json），字幕功能不启用',
                    subtitles_dir)
        return None

    logger.info('加载字幕样式: %s', style_path)
    raw = _load_vfs_json_ordered(style_path)
    if raw is None:
        logger.warn('字幕样式文件 %s 解析失败，字幕功能不启用', style_path)
        return None

    return _parse_style(raw, pack_root, style_path)


def load_sentence(pack_root, marker, lang='zh_cn'):
    """根据音频内嵌名加载字幕句子文件。

    :param pack_root: 语音包 VFS 根目录
    :param marker:    音频内嵌名（Wwise marker 字符串），用作文件名
                      可能是 utf-8 bytes 或 unicode；VFS 文件名可能用
                      系统编码（GBK），两者不一致时回退到目录遍历匹配。
    :param lang:      'zh_cn' | 'en'，决定用中文还是英文键名解析
    :return: SubtitleData | None（文件不存在或解析失败返回 None）
    """
    sentences_dir = pack_root + 'subtitles/sentences/'

    # 尝试 1: 直接路径（ASCII marker 或编码恰好匹配）
    path = sentences_dir + marker + '.json'
    raw = load_vfs_json(path)
    if raw is not None:
        result = _parse_sentence(raw, lang, path)
        if result is None:
            logger.warn('字幕句子文件 %s 解析失败', path)
        return result

    # 文件存在但 JSON 解析失败 → 记录警告（区别于文件不存在）
    if _vfs_file_exists(path):
        logger.warn('字幕句子文件 %s JSON 解析失败，请检查 JSON 语法', path)

    # 尝试 2: 遍历目录匹配文件名（处理编码不一致的情况）
    path = _find_sentence_file(sentences_dir, marker)
    if path is not None:
        raw = load_vfs_json(path)
        if raw is not None:
            result = _parse_sentence(raw, lang, path)
            if result is None:
                logger.warn('字幕句子文件 %r 解析失败', path)
            return result
        # 遍历找到文件但 JSON 解析失败
        logger.warn('字幕句子文件 %r JSON 解析失败，请检查 JSON 语法', path)

    return None


# ═════════════════════════════════════════════════════════════
# 内部：VFS 文件探测
# ═════════════════════════════════════════════════════════════


def _vfs_file_exists(vfs_path):
    """安全地检查 VFS 文件是否存在（ResMgr.isFile 可能在编码不匹配时抛异常）。"""
    try:
        return ResMgr.isFile(vfs_path)
    except Exception:
        return False


def _find_first_json(vfs_dir):
    """在 VFS 目录下查找第一个 .json 文件，返回完整 VFS 路径；无则 None。"""
    if not ResMgr.isDir(vfs_dir):
        return None
    folder = ResMgr.openSection(vfs_dir)
    if folder is None:
        return None
    for name in folder.keys():
        if name.endswith('.json'):
            return vfs_dir + name
    return None


def _find_sentence_file(sentences_dir, marker):
    """在 VFS 目录中查找匹配 marker 的句子 JSON 文件。

    marker 可能是 utf-8 bytes（Wwise 内嵌标签）或 unicode，
    而 VFS（.wotmod zip）内的文件名可能是系统编码（如 GBK/cp936）。
    直接拼接路径可能因字节不匹配而找不到文件，因此遍历目录并用多种
    编码解码文件名来比较。

    注意：即使匹配成功，含非 ASCII 字符的路径也无法通过 ResMgr 正确
    读取文件内容（引擎限制）。请使用纯英文文件名。

    :param sentences_dir: 如 'mods/voiceover/sumi/subtitles/sentences/'
    :param marker:        音频内嵌名（str bytes 或 unicode）
    :return: 完整 VFS 路径 或 None
    """
    # sentences_dir 可能是 unicode（上游 pack_root 经 json.loads 未走
    # to_utf8），Python 2 下 unicode + str(name) 会触发隐式 ASCII 解码。
    # 统一转 str 避免此问题。
    if isinstance(sentences_dir, unicode):
        sentences_dir = sentences_dir.encode('utf-8')

    try:
        is_dir = ResMgr.isDir(sentences_dir)
    except Exception:
        return None
    if not is_dir:
        return None

    try:
        folder = ResMgr.openSection(sentences_dir)
    except Exception:
        return None
    if folder is None:
        return None

    # 将 marker 归一化为 unicode
    if isinstance(marker, unicode):
        marker_u = marker
    else:
        marker_u = None
        for enc in ['utf-8', 'gbk']:
            try:
                marker_u = marker.decode(enc)
                break
            except (UnicodeDecodeError, UnicodeEncodeError):
                continue
        if marker_u is None:
            return None

    target_name = marker_u + '.json'

    try:
        names = list(folder.keys())
    except Exception:
        return None

    for name in names:
        for enc in ['gbk', 'utf-8']:
            try:
                if name.decode(enc) == target_name:
                    return sentences_dir + name
            except (UnicodeDecodeError, UnicodeEncodeError):
                continue

    return None


def _load_vfs_json_ordered(vfs_path):
    """同 load_vfs_json，但通过 OrderedDict 保留键插入顺序。

    首键=默认项的约定依赖键顺序，标准 json.loads 在 Py2 下不保证顺序。
    内部经 parse_jsonc 过滤 // 注释行。

    注意：游戏引擎的 ResMgr/VFS 不支持含非 ASCII 字符（如中文）的路径，
    此类文件读取会失败。请使用纯英文文件名。
    """
    try:
        if not ResMgr.isFile(vfs_path):
            return None
    except Exception:
        return None
    try:
        section = ResMgr.openSection(vfs_path)
    except Exception:
        return None
    if section is None:
        return None

    from autoconfigvoiceover.utils import parse_jsonc
    return parse_jsonc(section.asString, object_pairs_hook=OrderedDict)


# ═════════════════════════════════════════════════════════════
# 内部：键名翻译
# ═════════════════════════════════════════════════════════════


def _get_mappings(lang):
    """根据 lang 返回 (style_top, style_item, sentence, entry) 四组映射。"""
    if lang == 'zh_cn':
        return _CN_STYLE_TOP, _CN_STYLE_ITEM, _CN_SENTENCE, _CN_TIMELINE_ENTRY
    else:
        return _EN_STYLE_TOP, _EN_STYLE_ITEM, _EN_SENTENCE, _EN_TIMELINE_ENTRY


def _translate(raw, mapping):
    """将 raw dict 的键按 mapping 翻译为规范键名。

    mapping: {原始键: 规范键}
    返回新 dict，仅包含在 raw 中实际存在的键。
    """
    return {dst: raw[src] for src, dst in mapping.items() if src in raw}


def _normalize_align(value):
    """将对齐方式值统一为英文（'left'/'right'/'center'）。"""
    if not value:
        return 'left'
    if value in _CN_ALIGN_VALUES:
        return _CN_ALIGN_VALUES[value]
    if value in ('left', 'right', 'center'):
        return value
    logger.warn('未知对齐方式: %s，使用默认 left', value)
    return 'left'


def _resolve_image(pack_root, img_path):
    """将 JSON 中的相对图片路径解析为 VFS 全路径。

    JSON 中路径从 subtitles/images/ 出发，如 'avatar.png'
    → 'mods/voiceover/my_pack/subtitles/images/avatar.png'
    空路径直接返回空串。
    """
    if not img_path:
        return ''
    return pack_root + 'subtitles/images/' + img_path


# ═════════════════════════════════════════════════════════════
# 内部：样式文件解析
# ═════════════════════════════════════════════════════════════


def _detect_lang(raw):
    """检测 JSON 文件自身的 "lang" 键，返回 'zh_cn' | 'en' | None。

    None 表示文件中无 lang 键，由调用方自行决定默认值。
    "lang" 键缺省或值为 'zh_cn' → 'zh_cn'；其他 → 'en'。
    """
    lang = raw.get('lang', None)
    if lang is None:
        return None
    if lang == 'zh_cn':
        return 'zh_cn'
    return 'en'


def _parse_style(raw, pack_root, style_path):
    """解析样式 JSON → SubtitleStyle。"""
    # 检测语言（"lang" 键始终用英文名）
    lang = _detect_lang(raw)
    if lang is None:
        lang = 'zh_cn'

    style_top, style_item, _, _ = _get_mappings(lang)

    posters = _parse_style_section(raw, style_top, 'posters', style_item,
                                   _DEFAULTS['poster'], pack_root)
    backgrounds = _parse_style_section(raw, style_top, 'backgrounds', style_item,
                                       _DEFAULTS['background'], pack_root)
    tf_titles = _parse_style_section(raw, style_top, 'tf_titles', style_item,
                                     _DEFAULTS['tf_title'], pack_root)
    tf_messages = _parse_style_section(raw, style_top, 'tf_messages', style_item,
                                       _DEFAULTS['tf_message'], pack_root)

    # —— 简洁模式独立配置（可选，不存在则为 None）——
    simple_mode = _parse_simple_mode(raw, style_top, style_item)

    return SubtitleStyle(lang, posters, backgrounds, tf_titles, tf_messages,
                         simple_mode)


def _parse_style_section(raw, top_map, canonical_name, item_map, defaults,
                         pack_root):
    """解析样式文件的单个段（posters/backgrounds/tf_titles/tf_messages）。

    1. 在 raw 中查找本段的实际键名（通过 top_map 反向查找）
    2. 遍历段内每个代号：
       - 空字典 {} → 保留为空，表示"不显示该组件"
       - 非空字典 → 翻译子键、补齐默认值、解析图片路径
    3. 返回 OrderedDict {代号: {规范字段...}}，首项即为默认
    """
    # 查找 raw 中本段的实际键名
    actual_key = None
    for src, dst in top_map.items():
        if dst == canonical_name:
            actual_key = src
            break

    section = raw.get(actual_key, None)
    if not isinstance(section, dict):
        if section is not None:
            logger.warn('样式段 %s 格式错误（应为对象），使用空默认', actual_key)
        return OrderedDict()

    result = OrderedDict()
    for code, raw_item in section.items():
        try:
            code = str(code)
        except Exception:
            pass
        if not isinstance(raw_item, dict):
            logger.warn('样式段 %s 代号 %s 格式错误（应为对象），已跳过',
                        canonical_name, code)
            continue
        try:
            if not raw_item:
                # 空字典 {} → "不显示该组件"，保留为空（不补默认值）
                item = {}
            else:
                item = _translate(raw_item, item_map)
                # 注意：不在此处补齐默认值。
                # 补齐延迟到 SubtitleStyle._get_section() 消费时，
                # 确保非 default 样式缺失/无效的字段能正确回退到 default
                # 命名样式而非硬编码默认值。
                # 解析图片路径
                if 'img' in item and item['img']:
                    item['img'] = _resolve_image(pack_root, item['img'])
                # 翻译对齐方式
                if 'align' in item:
                    item['align'] = _normalize_align(item['align'])
            result[code] = item
        except Exception:
            logger.warn('样式段 %s 代号 %s 解析异常，已跳过',
                        canonical_name, code)

    return result


def _parse_simple_mode(raw, top_map, item_map):
    """解析样式文件中可选的简洁模式独立配置段。

    simple_mode 不是代号→样式映射，而是单层配置对象：
        {"msg_width": N, "msg_position": [x,y], "title_msg_gap": N}

    不存在或为空对象 → 返回空 dict，由 SubtitleStyle.get_simple_mode()
    负责回退到 tf_messages 的对应值。

    :param raw:      样式 JSON 的完整 dict
    :param top_map:  顶层键名映射表
    :param item_map: 子字段键名映射表
    :return: dict（可能为空）
    """
    # 查找 raw 中 simple_mode 的实际键名
    actual_key = None
    for src, dst in top_map.items():
        if dst == 'simple_mode':
            actual_key = src
            break

    section = raw.get(actual_key, None)
    if not isinstance(section, dict) or not section:
        return {}

    result = _translate(section, item_map)

    # 类型规范化
    for key in ('msg_width', 'title_msg_gap'):
        if key in result:
            try:
                result[key] = int(result[key])
            except (ValueError, TypeError):
                result[key] = 0

    if 'msg_position' in result:
        pos = result['msg_position']
        if isinstance(pos, list) and len(pos) >= 2:
            try:
                result['msg_position'] = [int(pos[0]), int(pos[1])]
            except (ValueError, TypeError):
                result['msg_position'] = [0, 0]
        else:
            result['msg_position'] = [0, 0]

    return result


# ═════════════════════════════════════════════════════════════
# 内部：句子文件解析
# ═════════════════════════════════════════════════════════════


def _parse_sentence(raw, lang, path):
    """解析句子 JSON → SubtitleData。

    lang 参数仅作为 fallback：句子文件自身的 "lang" 键优先。
    """
    if not isinstance(raw, dict):
        logger.warn('字幕文件 %r 格式错误（应为对象）', path)
        return None

    # 检测语言——句子文件自身的 "lang" 键优先于调用者传入的 lang
    detected = _detect_lang(raw)
    if detected is not None:
        final_lang = detected
    else:
        final_lang = lang

    _, _, sentence_map, entry_map = _get_mappings(final_lang)

    # 翻译顶层键名
    data = _translate(raw, sentence_map)

    # duration
    duration = _parse_float(data.get('duration', 1.0), 1.0, 'duration', path)

    # timeline
    timeline_raw = data.get('timeline', None)
    if timeline_raw is None:
        # 用中文/英文键名再试一次
        timeline_raw = raw.get('顺序', raw.get('timeline', []))
    if not isinstance(timeline_raw, list):
        logger.warn('字幕文件 %r timeline 格式错误（应为数组）', path)
        return SubtitleData(duration=duration)

    timeline = []
    for entry_raw in timeline_raw:
        if not isinstance(entry_raw, dict):
            continue
        entry = _parse_timeline_entry(entry_raw, entry_map)
        timeline.append(entry)

    return SubtitleData(duration=duration, timeline=timeline)


# 中文别名 → 英文规范名（loader 归一化，Flash 只认英文）
_ANIME_ALIASES = {
    '冒泡':      'bubble',
    'maopao':    'bubble',
    '惊讶':      'surprise',
    'jingya':    'surprise',
    '晃动':      'shake',
    'huangdong': 'shake',
    '摇头':      'sway',
    'yaotou':    'sway',
    '点头':      'drop',
    'diantou':   'drop',
    '抱歉':      'sorry',
    'baoqian':   'sorry'
}


def _normalize_anime(anime_raw, start_at_raw):
    """将 anime / anime_start_at 归一化为等长列表。

    向后兼容旧格式（单值），同时支持多动画序列（数组）：
      - anime='' 或 [] → ([], [])
      - anime='bubble' → (['bubble'], [start_at_raw 或 0.0])
      - anime=['bubble','shake'], start_at_raw=0.5 → (['bubble','shake'], [0.5, 0.5])
      - anime=['bubble','shake'], start_at_raw=[0.0, 0.3] → 原样返回

    中文别名自动转换为英文规范名:
      maopao→bubble, jingya→surprise, yaotou→shake, ditou→drop,
      yaobai→sway, 抱歉→sorry

    校验：两列表长度必须一致，不一致时截断至较短长度并 warn。
    非字符串/列表的 anime 值视为无效 → 返回空列表。
    """
    # —— 归一化 anime ——
    if not anime_raw:
        return [], []
    if isinstance(anime_raw, list):
        anime_list = [str(a) for a in anime_raw]
    elif isinstance(anime_raw, basestring):
        anime_list = [str(anime_raw)]
    else:
        logger.warn('anime 值类型无效（%s），已忽略', type(anime_raw).__name__)
        return [], []

    # 中文别名 → 英文规范名（Flash 只认英文代号）
    anime_list = [_ANIME_ALIASES.get(a, a) for a in anime_list]

    # —— 归一化 anime_start_at ——
    n = len(anime_list)
    if isinstance(start_at_raw, list):
        start_list = []
        for v in start_at_raw:
            try:
                start_list.append(float(v))
            except (ValueError, TypeError):
                start_list.append(0.0)
    elif isinstance(start_at_raw, (int, float)):
        start_list = [float(start_at_raw)] * n
    else:
        start_list = [0.0] * n

    # —— 对齐长度 ——
    if len(start_list) < n:
        logger.warn('anime_start_at 条目少于 anime（%d < %d），尾部补 0.0',
                    len(start_list), n)
        start_list.extend([0.0] * (n - len(start_list)))
    elif len(start_list) > n:
        logger.warn('anime_start_at 条目多于 anime（%d > %d），已截断',
                    len(start_list), n)
        start_list = start_list[:n]

    return anime_list, start_list


def _parse_timeline_entry(raw_entry, entry_map):
    """解析 timeline 中的一条 → SubtitleEntry。

    样式代号字段缺省→空串，由 SubtitleStyle.get_*() 负责取默认项。
    anime / anime_start_at 经 _normalize_anime 归一化为等长列表。
    """
    entry = _translate(raw_entry, entry_map)
    anime_seq, anime_start_seq = _normalize_anime(
        entry.get('anime', ''), entry.get('anime_start_at', 0.0))
    return SubtitleEntry(
        text=entry.get('text', ''),
        character=entry.get('character', ''),
        poster=entry.get('poster', ''),
        background=entry.get('background', ''),
        tf_message=entry.get('tf_message', ''),
        tf_title=entry.get('tf_title', ''),
        start_at=_parse_float(entry.get('start_at', 0.0), 0.0,
                              'start_at', None),
        anime=anime_seq,
        anime_start_at=anime_start_seq,
    )


def _parse_float(value, default, field_name, path):
    """安全解析浮点数，失败时 warn 并返回默认值。"""
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warn('字幕文件 %r %s 无效（%s），使用默认 %s',
                    path, field_name, value, default)
        return default


# ═════════════════════════════════════════════════════════════
# 偏移文件读写
# ═════════════════════════════════════════════════════════════

_ZERO_OFFSETS = {
    'poster':      {'x': 0, 'y': 0},
    'tf_title':    {'x': 0, 'y': 0},
    'background':  {'x': 0, 'y': 0},
    'tf_message':  {'x': 0, 'y': 0},
    'simple_mode': {'x': 0, 'y': 0},
}
"""全零偏移，兜底用。"""


def get_pack_id(pack_root):
    """从 VFS 路径提取语音包目录名作为 pack_id。

    :param pack_root: 如 'mods/voiceover/my_pack/'
    :return:          如 'my_pack'
    """
    if not pack_root:
        return None
    # 去掉尾部斜杠，取最后一段
    normalized = pack_root.rstrip('/')
    return normalized.split('/')[-1] if '/' in normalized else normalized


def load_offsets(pack_root):
    """加载语音包的字幕组件偏移量。

    从 {MY_SUBTITLES_FOLDER}/{pack_id}.json 读取。
    文件不存在或解析失败 → 返回全零偏移。

    :param pack_root: 语音包 VFS 根目录
    :return: dict {poster/tf_title/background/tf_message: {x, y}}
    """
    pack_id = get_pack_id(pack_root)
    if not pack_id:
        return dict(_ZERO_OFFSETS)

    path = os.path.join(MY_SUBTITLES_FOLDER, pack_id + '.json')
    if not os.path.isfile(path):
        logger.debug('偏移文件不存在: %s，使用全零', path)
        return dict(_ZERO_OFFSETS)

    try:
        from autoconfigvoiceover.utils import load_jsonc
        raw = load_jsonc(path)
        if raw is None:
            raise ValueError('偏移文件为空或格式错误')
        offsets = raw.get('offsets', None)
        if not isinstance(offsets, dict):
            logger.warn('偏移文件 %s 缺少 offsets 键，使用全零', path)
            return dict(_ZERO_OFFSETS)

        # 补全缺失的组件
        result = dict(_ZERO_OFFSETS)
        for key in _ZERO_OFFSETS:
            if key in offsets and isinstance(offsets[key], dict):
                result[key] = {
                    'x': float(offsets[key].get('x', 0)),
                    'y': float(offsets[key].get('y', 0)),
                }
        logger.debug('已加载偏移: %s (%d 组件)', path, len(result))
        return result
    except (ValueError, TypeError, IOError):
        logger.exception('偏移文件 %s 读取失败，使用全零', path)
        return dict(_ZERO_OFFSETS)


def save_offsets(pack_root, offsets):
    """保存语音包的字幕组件偏移量到磁盘。

    :param pack_root: 语音包 VFS 根目录
    :param offsets:   dict {poster/tf_title/background/tf_message: {x, y}}
    """
    pack_id = get_pack_id(pack_root)
    if not pack_id:
        logger.warn('save_offsets: 无法提取 pack_id（pack_root=%s）', pack_root)
        return

    # 确保目录存在
    if not os.path.isdir(MY_SUBTITLES_FOLDER):
        try:
            os.makedirs(MY_SUBTITLES_FOLDER)
        except OSError:
            logger.exception('创建字幕偏移目录失败: %s', MY_SUBTITLES_FOLDER)
            return

    path = os.path.join(MY_SUBTITLES_FOLDER, pack_id + '.json')
    # OrderedDict 保证 x 在 y 前（Py2 dict 无序，JSON 里键序由哈希决定）
    data = {'offsets': OrderedDict(
        (k, OrderedDict((('x', int(v.get('x', 0))), ('y', int(v.get('y', 0))))))
        for k, v in offsets.items()
    )}

    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if isinstance(text, unicode):
            text = text.encode('utf-8')
        with open(path, 'w') as fh:
            fh.write(text)
        logger.info('偏移已保存: %s', path)
    except (IOError, OSError):
        logger.exception('保存偏移文件失败: %s', path)


# ═════════════════════════════════════════════════════════════
# 模板句子加载
# ═════════════════════════════════════════════════════════════


def load_template_sentence(pack_root, lang='zh_cn'):
    """加载用于字幕位置编辑预览的模板句子。

    按优先级尝试:
      1. {pack_root}subtitles/sentences/template.json
      2. sentences/ 下第一个合法 JSON 的第一句
      3. 都不成功 → 返回 None，同时通知用户

    :param pack_root: 语音包 VFS 根目录
    :param lang:      'zh_cn' | 'en'
    :return: SubtitleData | None
    """
    sentences_dir = pack_root + 'subtitles/sentences/'

    # —— 优先: template.json ——
    template_path = sentences_dir + 'template.json'
    if ResMgr.isFile(template_path):
        result = load_sentence(pack_root, 'template', lang)
        if result is not None and result.timeline:
            logger.info('使用模板句子: %s (%d 条)', template_path, len(result.timeline))
            return result
        logger.warn('template.json 存在但无合法 timeline: %s', template_path)

    # —— 回退: 扫描 sentences/ 下第一个 JSON ——
    json_path = _find_first_json(sentences_dir)
    if json_path is not None:
        # 从路径提取 marker 名（去掉目录和 .json 后缀）
        marker = os.path.basename(json_path)
        if marker.endswith('.json'):
            marker = marker[:-5]
        result = load_sentence(pack_root, marker, lang)
        if result is not None and result.timeline:
            logger.info('使用回退句子: %s (%d 条)', json_path, len(result.timeline))
            return result

    # —— 失败: 日志 + 通知 ——
    msg = ('字幕位置编辑不可用：语音包 {} 的 '
           'subtitles/sentences/ 目录下未找到合法句子文件。'
           '请添加 template.json 或至少一个句子文件。').format(
        get_pack_id(pack_root) or pack_root)
    logger.warn(msg)

    try:
        from autoconfigvoiceover.notifier import send_message
        send_message(msg)
    except Exception:
        logger.exception('发送模板句子加载失败通知异常')

    return None
