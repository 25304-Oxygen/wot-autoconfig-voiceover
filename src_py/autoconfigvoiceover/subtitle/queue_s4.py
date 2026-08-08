# coding=utf-8
"""S4 并行-合并队列策略。

队列的队列——每个语音自成一列，列间垂直堆叠:
  - 每个语音 = 一个 S4Column，列内 S3 合并 + S1 交叉淡化
  - 列间：新列从底部插入，将旧列整体向上推移
  - 列高度固定（从样式配置推导），不波动
  - 列播放完毕 → 消失 → 上方列下移补位
  - 不跨语音打断、不跨语音合并 renderer
"""

import BigWorld

from autoconfigvoiceover.logger import Logger
from .base import BaseSubtitleManager
from .loader import load_sentence
from .assembler import assemble_entry_data
from .merger import merge_entries

logger = Logger('S4Manager')

DEFAULT_SLOT_HEIGHT = 80


class S4Voice(object):
    """一个语音的完整字幕数据。"""

    __slots__ = ('audio_key', 'entries', 'duration', 'dead')

    def __init__(self, audio_key, data):
        self.audio_key = audio_key
        self.entries = list(data.timeline)
        self.duration = data.duration
        self.dead = False


class S4Column(object):
    """一个语音的视觉列。"""

    __slots__ = ('voice', 'items', 'slot_index', 'base_y',
                 '_active_renderers', '_current_item_index', 'dead')

    def __init__(self, voice, items, slot_index, base_y):
        """
        :param voice:      S4Voice
        :param items:      [CompoundItem, ...]  合并后的队列项
        :param slot_index: int，在 _columns 中的位置（0=最上方）
        :param base_y:     float，列基准 Y 坐标
        """
        self.voice = voice
        self.items = items               # [CompoundItem]
        self.slot_index = slot_index
        self.base_y = base_y
        self._active_renderers = {}      # {rid: {'item_index': int, 'state': str}}
        self._current_item_index = 0
        self.dead = False

    @property
    def active_rids(self):
        """返回当前活跃 renderer 的 ID 列表。"""
        return list(self._active_renderers.keys())


class S4Manager(BaseSubtitleManager):
    """S4 字幕队列管理器：并行 + 合并。

    列列表模型:
      _columns: [S4Column]  按 slot_index 排序（0=最上方）
    """

    def __init__(self, pack_root, style, settings, dispatcher):
        super(S4Manager, self).__init__(
            pack_root, style, settings, dispatcher)
        self._columns = []           # [S4Column]
        self._slot_height = self._compute_slot_height()

    # ═════════════════════════════════════════════════════════
    # 公开 API
    # ═════════════════════════════════════════════════════════

    def on_marker(self, marker_str):
        """Wwise marker 回调。加载句子 → 合并 → 插入新列。"""
        if not self._enabled:
            return
        if not marker_str:
            return

        logger.debug('收到 marker: "%s"', marker_str)
        data = load_sentence(self._pack_root, marker_str, self._style.lang if self._style else 'zh_cn')
        if data is None:
            return
        if not data.timeline:
            return

        self._add_column(marker_str, data)

    def on_fade_out_done(self, renderer_id):
        """renderer 淡出完成 → 从所属列清理。

        不执行列内 shift_down:
          旧 renderer 在 _on_item_begin 中被 shift_up 推出槽位后淡出消失，
          新 renderer 创建于列槽位且从未被 shift_up。
          若对新 renderer 做 shift_down 会把它推离正确位置，导致列漂移。
        """
        for col in self._columns:
            if renderer_id in col._active_renderers:
                del col._active_renderers[renderer_id]
                logger.debug('renderer %d 淡出完成 (列 %d: %s)',
                             renderer_id, col.slot_index, col.voice.audio_key)
                return
        logger.debug('renderer %d 淡出完成（已不在追踪中）', renderer_id)

    def clear(self):
        """清空所有字幕。"""
        self._emit('clear_all')
        for col in self._columns:
            col.dead = True
            col.voice.dead = True
        self._columns = []
        self._next_rid = 1
        logger.debug('字幕已全部清除')

    # ═════════════════════════════════════════════════════════
    # 内部：列管理
    # ═════════════════════════════════════════════════════════

    def _add_column(self, audio_key, data):
        """新语音到达：合并 entries → 创建列 → 推旧列上移 → 插入底部。"""
        voice = S4Voice(audio_key, data)
        items = merge_entries(data.timeline, data.duration)

        if not items:
            logger.debug('合并后无队列项，跳过: %s', audio_key)
            return

        # 新列插入底部 → 所有现有列上移
        slot_index = len(self._columns)
        base_y = 0.0  # 底部位置 = 0，旧列往上（负 Y）

        for col in self._columns:
            self._shift_column(col, 'up', self._slot_height)

        column = S4Column(voice, items, slot_index, base_y)
        self._columns.append(column)

        logger.info('新列插入: %s (slot=%d, %d 条 → %d 复合项, %.1fs)',
                    audio_key, slot_index, len(data.timeline), len(items), voice.duration)

        # 调度列内回调
        self._schedule_column(column)

        # 列结束回调
        BigWorld.callback(
            max(voice.duration, 0.001),
            lambda c=column: self._on_column_done(c)
        )

    def _remove_column(self, column):
        """移除列并让上方列下移补位。

        地面模型：下方列不主动上移。
          屏幕底部 = 地面，列从底部插入向上推旧列。
          上方列消失时下方列原地不动——字幕不会主动离开地面，
          只会被动被下面的新列顶上去。
        """
        if column.dead:
            return

        column.dead = True
        column.voice.dead = True

        removed_slot = column.slot_index

        # 防御：淡出列内所有 renderer
        for rid in column.active_rids:
            self._emit('fade_out', rid)
        column._active_renderers.clear()

        try:
            self._columns.remove(column)
        except ValueError:
            return

        # 更新 slot_index 并对上方列（原 slot < removed_slot）下移补位
        for col in self._columns:
            if col.slot_index < removed_slot:
                self._shift_column(col, 'down', self._slot_height)
            # 更新 slot_index
            if col.slot_index > removed_slot:
                col.slot_index -= 1

        logger.debug('列移除: slot=%d, 剩余 %d 列', removed_slot, len(self._columns))

    # ═════════════════════════════════════════════════════════
    # 内部：列内调度
    # ═════════════════════════════════════════════════════════

    def _schedule_column(self, column):
        """调度一个列内所有 CompoundItem 的 callbacks。"""
        for item_index, item in enumerate(column.items):
            begin_at = item.span[0]
            end_at = item.span[1]

            # 首个 stage（入场）
            if begin_at > 0:
                BigWorld.callback(
                    begin_at,
                    lambda c=column, idx=item_index: self._on_item_begin(c, idx)
                )
            else:
                self._on_item_begin(column, item_index)

            # 后续 stage（内容更新）
            for stage_index, stage in enumerate(item.stages[1:], start=1):
                BigWorld.callback(
                    stage.at,
                    lambda c=column, idx=item_index, si=stage_index:
                        self._on_stage_update(c, idx, si)
                )

            # 结束（淡出）
            if end_at > begin_at:
                BigWorld.callback(
                    end_at,
                    lambda c=column, idx=item_index: self._on_item_end(c, idx)
                )

    # ═════════════════════════════════════════════════════════
    # 内部：列内生命周期回调
    # ═════════════════════════════════════════════════════════

    def _on_item_begin(self, column, item_index):
        """CompoundItem 首个 stage：列内避让 → 创建 renderer。

        位置计算:
          1. 默认位置（assemble_entry_data 产出）
          2. + 列偏移 base_y（列间堆叠）
          3. 新 renderer 不参与列内避让上移——旧 renderer 上移浮空淡出，
             新 renderer 留在列槽位，避免"自己避让自己"导致重叠。
        """
        if column.dead:
            return

        # 碰撞避让 (列内): 上移同列内所有非 dead 的旧 renderer
        # 新 renderer 不在此列——它留在槽位，旧 renderer 上移后自然分离
        for rid, info in column._active_renderers.items():
            if info['state'] != 'dead':
                self._emit('shift_up', rid, distance=self._slot_height)

        item = column.items[item_index]
        rid = self._gen_rid()
        item.rid = rid

        stage = item.stages[0]
        data = assemble_entry_data(stage.entry, self._style, self._settings, self._offsets)
        self._emit('create', rid, data=data)

        # 应用列的 base_y 偏移，使 renderer 加入正确的列位置（列间堆叠）
        if column.base_y != 0.0:
            direction = 'up' if column.base_y < 0 else 'down'
            self._emit('shift_' + direction, rid, distance=abs(column.base_y))

        column._active_renderers[rid] = {'item_index': item_index, 'state': 'entering'}
        column._current_item_index = item_index

        logger.debug('列 %d 复合项 %d 登场: rid=%d character=%s base_y=%.0f',
                     column.slot_index, item_index, rid, item.character,
                     column.base_y)

    def _on_stage_update(self, column, item_index, stage_index):
        """CompoundItem 后续 stage：update_content 瞬间替换。"""
        if column.dead:
            return

        item = column.items[item_index]
        rid = item.rid
        if rid is None or rid not in column._active_renderers:
            return

        stage = item.stages[stage_index]
        data = assemble_entry_data(stage.entry, self._style, self._settings, self._offsets)
        self._emit('update_content', rid, data=data)
        column._active_renderers[rid]['state'] = 'active'

        logger.debug('列 %d 复合项 %d stage %d 更新: rid=%d',
                     column.slot_index, item_index, stage_index, rid)

    def _on_item_end(self, column, item_index):
        """CompoundItem 结束：淡出 renderer。"""
        if column.dead:
            return

        item = column.items[item_index]
        rid = item.rid
        if rid is None:
            return

        if rid in column._active_renderers:
            self._emit('fade_out', rid)
            column._active_renderers[rid]['state'] = 'fading'
            logger.debug('列 %d 复合项 %d 淡出: rid=%d',
                         column.slot_index, item_index, rid)

    def _on_column_done(self, column):
        """列播放完毕：从列列表中移除，上方列下移。"""
        if column.dead:
            return

        logger.debug('列播放完毕: slot=%d audio=%s',
                     column.slot_index, column.voice.audio_key)
        self._remove_column(column)

    # ═════════════════════════════════════════════════════════
    # 内部：列级 shift
    # ═════════════════════════════════════════════════════════

    def _shift_column(self, column, direction, distance):
        """将列内的所有活跃 renderer 统一 shift。

        交叉淡化期间列内有两个 renderer（旧 fading + 新 entering），
        两者作为列的整体一起移动。

        :param direction: 'up'（负 Y）| 'down'（正 Y）
        :param distance:  float，移动像素距离
        """
        cmd = 'shift_up' if direction == 'up' else 'shift_down'
        for rid in column.active_rids:
            self._emit(cmd, rid, distance=distance)

        if direction == 'up':
            column.base_y -= distance
        else:
            column.base_y += distance
