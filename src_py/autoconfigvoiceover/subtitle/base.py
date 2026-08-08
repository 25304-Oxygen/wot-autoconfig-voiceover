# coding=utf-8
"""字幕队列管理器基类。

抽取四个排队策略的公共字段和方法，子类只需实现:
  - on_marker(marker_str)        — Wwise marker 回调
  - on_fade_out_done(renderer_id) — Flash renderer 淡出完成
  - clear()                      — 清空所有字幕
"""

import struct

import ResMgr

from autoconfigvoiceover.logger import Logger
from .loader import load_offsets, load_template_sentence
from .assembler import assemble_entry_data

logger = Logger('BaseSubtitleManager')


# ═════════════════════════════════════════════════════════════
# 模块级：文本高度估算辅助
# ═════════════════════════════════════════════════════════════


def _safe_float(value, default=0.0):
    """安全转换为 float，不可转换（None/列表/字典/乱码）时返回默认值。"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_position_y(component):
    """从组件 dict 中安全提取 position[1]（Y坐标），不可用时返回 None。"""
    if not component:
        return None
    pos = component.get('position')
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        return None
    try:
        return float(pos[1])
    except (ValueError, TypeError):
        return None


def _get_png_native_height(vfs_path):
    """读取 PNG 文件 IHDR chunk 获取原始高度。

    PNG 不缩放——图片以原始尺寸渲染，style 中的 size 字段对图片无效。
    仅读取文件头 24 字节，不加载整张图片。

    PNG 文件结构:
      0-7:   签名 \\x89PNG\\r\\n\\x1a\\n
      8-11:  IHDR 长度 (大端 uint32, 固定 13)
      12-15: "IHDR"
      16-19: 宽度 (大端 uint32)
      20-23: 高度 (大端 uint32)

    返回 int 高度；文件不存在/非 PNG/读取失败 → None。
    """
    if not vfs_path:
        return None
    try:
        if not ResMgr.isFile(vfs_path):
            return None
        section = ResMgr.openSection(vfs_path)
        if section is None:
            return None
        data = section.asString
        if not data or len(data) < 24:
            return None
        # 验证 PNG 签名
        if data[:8] != '\x89PNG\r\n\x1a\n':
            return None
        # 验证 IHDR chunk 标识
        if data[12:16] != 'IHDR':
            return None
        height = struct.unpack('>I', data[20:24])[0]
        return int(height)
    except Exception:
        return None


def _get_png_native_size(vfs_path):
    """读取 PNG 文件 IHDR chunk 获取原始宽高。

    返回 (width, height) 整数元组；文件不存在/非 PNG/读取失败 → None。
    """
    if not vfs_path:
        return None
    try:
        if not ResMgr.isFile(vfs_path):
            return None
        section = ResMgr.openSection(vfs_path)
        if section is None:
            return None
        data = section.asString
        if not data or len(data) < 24:
            return None
        if data[:8] != '\x89PNG\r\n\x1a\n':
            return None
        if data[12:16] != 'IHDR':
            return None
        width = struct.unpack('>I', data[16:20])[0]
        height = struct.unpack('>I', data[20:24])[0]
        return (int(width), int(height))
    except Exception:
        return None


def _get_component_height(component, default_h=80.0):
    """获取组件的实际渲染高度。

    规则（与 Flash 端一致）:
      - 所有组件由 size 字段决定显示尺寸
      - 图片类型(size=[w,h]) → size[1] 为显示高度，PNG 超出部分被裁剪
      - 文本类型(size=字号) → 返回字号，由调用方 × 行数 × 1.4 计算实际高度

    安全兜底返回 default_h。
    """
    if not component:
        return default_h

    sz = component.get('size')
    if isinstance(sz, (list, tuple)):
        # 矩形 / 图片: size = [w, h]
        if len(sz) > 1:
            val = _safe_float(sz[1], None)
            if val is not None:
                return val
        return default_h
    # 文本: size = font_size（数值，由调用方用于行数计算）
    val = _safe_float(sz, None)
    if val is not None:
        return val
    return default_h


def _estimate_standard_height(entry_data):
    """估算标准模式渲染数据的外接矩形高度。

    只计算固定尺寸组件（头像、背景、图片标题）。
    文本框（正文、文本标题）高度可变，不参与估算。

    规则（与 Flash 端一致）:
      - 所有组件由 size 字段决定显示尺寸，图片超出部分被裁剪
      - 头像 poster:      始终参与
      - 背景 background:   始终参与
      - 标题 tf_title:    仅图片类型参与
      - 正文 tf_message:  不参与（文本高度可变）
    """
    # 用 None 哨兵：从第一个组件初始化 min_y/max_y，
    # 杜绝原点 (0,0) 污染外接矩形（字幕在屏幕上半部时 max(0, 负数)=0 导致计算错误）。
    min_y = None
    max_y = None

    # —— 头像 poster ——
    p_y = _safe_position_y(entry_data.get('poster'))
    if p_y is not None:
        p_h = _get_component_height(entry_data.get('poster'), 64.0)
        if min_y is None:
            min_y = p_y
            max_y = p_y + p_h
        else:
            min_y = min(min_y, p_y)
            max_y = max(max_y, p_y + p_h)

    # —— 背景 background ——
    bg_y = _safe_position_y(entry_data.get('background'))
    if bg_y is not None:
        bg_h = _get_component_height(entry_data.get('background'), 80.0)
        if min_y is None:
            min_y = bg_y
            max_y = bg_y + bg_h
        else:
            min_y = min(min_y, bg_y)
            max_y = max(max_y, bg_y + bg_h)

    # —— 标题 tf_title（仅图片类型）——
    t_y = _safe_position_y(entry_data.get('tf_title'))
    if t_y is not None:
        title = entry_data.get('tf_title') or {}
        if title.get('img', ''):
            t_h = _get_component_height(title, 40.0)
            if min_y is None:
                min_y = t_y
                max_y = t_y + t_h
            else:
                min_y = min(min_y, t_y)
                max_y = max(max_y, t_y + t_h)

    # 没有任何固定组件 → 回退
    if min_y is None:
        return 80.0

    return max_y - min_y + 4.0  # 4px padding 对齐 _measureHeight()


def _estimate_concise_height(entry_data):
    """估算简洁模式渲染数据的外接矩形高度。

    简洁模式无固定尺寸组件（仅 nameTF + messageTF 两个文本框），
    不能基于模板句子文本估算（文本高度因字幕而异）。
    改用 font_size 基准公式，假设典型 2 行正文。
    """
    c = entry_data.get('concise', {}) or {}
    font_size = _safe_float(c.get('size', 14), 14.0)
    return max(font_size * 1.4 * 2 + 10, 40)


class BaseSubtitleManager(object):
    """字幕队列管理器基类。

    子类继承后复写三个抽象方法即可接入 host.py。
    """

    def __init__(self, pack_root, style, settings, dispatcher):
        """
        :param pack_root:  语音包 VFS 根目录，如 'mods/voiceover/my_pack/'
        :param style:      SubtitleStyle 实例（可为 None → 字幕功能不启用）
        :param settings:   dict，键:
            display_mode  — 'concise' | 'standard' | 'none'
            text_speed    — float，逐字出字速度（秒/字），0=瞬间
            subtitle_anim — bool，是否允许播放额外动画
        :param dispatcher: callable(cmd_dict)，将命令发往 Flash
        """
        self._pack_root = pack_root
        self._style = style
        self._settings = settings
        self._dispatch = dispatcher

        self._next_rid = 1
        self._offsets = load_offsets(pack_root) if pack_root else {}
        self._enabled = (style is not None
                         and settings.get('display_mode', 'standard') != 'none')
        self._slot_height = self._compute_slot_height()

    # ═════════════════════════════════════════════════════════
    # 子类必须实现
    # ═════════════════════════════════════════════════════════

    def on_marker(self, marker_str):
        """Wwise marker 回调。加载句子 → 入队调度。

        :param marker_str: 音频内嵌名（utf-8 字节串），用作句子文件名
        """
        raise NotImplementedError

    def on_fade_out_done(self, renderer_id):
        """Flash renderer 淡出完成。

        :param renderer_id: 已完成淡出的 renderer ID
        """
        raise NotImplementedError

    def clear(self):
        """清空所有字幕（切换语音包 / 离开战斗时调用）。"""
        raise NotImplementedError

    # ═════════════════════════════════════════════════════════
    # 共享实现
    # ═════════════════════════════════════════════════════════

    def update_settings(self, settings):
        """运行时更新设置（设置页改动后调用）。

        合并而非替换——设置页可能只传部分键。
        """
        old_enabled = self._enabled
        self._settings.update(settings)
        self._enabled = (self._style is not None
                         and self._settings.get('display_mode', 'standard') != 'none')

        if old_enabled and not self._enabled:
            self.clear()

    def update_style(self, pack_root, style):
        """切换语音包时更新样式和数据源。"""
        self.clear()
        self._pack_root = pack_root
        self._style = style
        self._enabled = (style is not None
                         and self._settings.get('display_mode', 'standard') != 'none')
        self._offsets = load_offsets(pack_root) if pack_root else {}
        self._slot_height = self._compute_slot_height()

    def reload_offsets(self):
        """重新加载偏移文件（字幕位置编辑保存后调用）。"""
        if self._pack_root:
            self._offsets = load_offsets(self._pack_root)
            self._slot_height = self._compute_slot_height()
            logger.debug('偏移已重载: %d 组件', len(self._offsets))

    # ═════════════════════════════════════════════════════════
    # 内部工具
    # ═════════════════════════════════════════════════════════

    def _gen_rid(self):
        """生成唯一递增 renderer ID。"""
        rid = self._next_rid
        self._next_rid += 1
        return rid

    def _compute_slot_height(self):
        """从模板句子 + 样式 + 偏移计算槽位高度。

        加载语音包的 template 句子, 组装为渲染数据,
        在 Python 侧估算字幕外接矩形高度, 乘以 1.25 作为槽位高度。

        模板句子缺失 / timeline 为空 → 回退 80px。
        """
        if not self._pack_root or not self._style:
            return 80

        lang = self._style.lang if self._style else 'zh_cn'
        data = load_template_sentence(self._pack_root, lang)
        if data is None or not data.timeline:
            logger.debug('_compute_slot_height: 无模板句子, 回退 80')
            return 80

        first_entry = data.timeline[0]
        entry_data = assemble_entry_data(
            first_entry, self._style, self._settings, self._offsets
        )

        mode = self._settings.get('display_mode', 'standard')

        # —— 调试：打印各组件数据 ——
        for key in ('poster', 'background', 'tf_title', 'tf_message'):
            comp = entry_data.get(key)
            if comp and comp.get('position'):
                logger.debug('  %s: pos=%s size=%s img=%s',
                             key, comp.get('position'), comp.get('size'),
                             comp.get('img', ''))

        if mode == 'concise':
            height = _estimate_concise_height(entry_data)
        else:
            height = _estimate_standard_height(entry_data)

        slot = max(int(height * 1.25), 80)
        logger.debug('_compute_slot_height: height=%.0f × 1.25 → slot=%d (mode=%s)',
                     height, slot, mode)
        return slot

    def _emit(self, cmd, renderer_id=0, data=None, distance=0):
        """产出命令到 dispatcher。

        :param cmd:         命令名: 'create'|'update_content'|'shift_up'|
                                    'shift_down'|'fade_out'|'clear_all'
        :param renderer_id: 目标 renderer ID（clear_all 时忽略）
        :param data:        create/update_content 的渲染数据 dict
        :param distance:    shift_up/shift_down 的像素距离
        """
        cmd_dict = {'cmd': cmd, 'id': renderer_id}
        if data is not None:
            cmd_dict['data'] = data
        if cmd in ('shift_up', 'shift_down'):
            cmd_dict['distance'] = float(distance)

        try:
            self._dispatch(cmd_dict)
        except Exception:
            logger.exception('dispatcher 调用失败: %s id=%d', cmd, renderer_id)
