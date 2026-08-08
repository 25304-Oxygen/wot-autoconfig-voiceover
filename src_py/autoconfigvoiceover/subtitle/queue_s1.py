# coding=utf-8
"""S1 串行-原子队列策略。

最简基线:
  - 每个 entry = 1 个独立 renderer（原子）
  - 队列中永远只有一个语音（串行）
  - entry 按生命周期接替，交接点交叉淡化
  - 新语音打断整队
"""

import BigWorld

from autoconfigvoiceover.logger import Logger
from .base import BaseSubtitleManager
from .loader import load_sentence
from .assembler import assemble_entry_data

logger = Logger('S1Manager')


class S1Queue(object):
    """单个语音的队列。"""

    __slots__ = ('audio_key', 'entries', 'duration',
                 '_active_renderers', '_dead')

    def __init__(self, audio_key, data):
        """
        :param audio_key: 音频标识（marker 名）
        :param data:      SubtitleData 实例
        """
        self.audio_key = audio_key
        self.entries = list(data.timeline)
        self.duration = data.duration
        self._active_renderers = {}   # {entry_index: rid}
        self._dead = False

    def kill(self):
        """标记队列为已终止。"""
        self._dead = True

    @property
    def dead(self):
        return self._dead


class S1Manager(BaseSubtitleManager):
    """S1 字幕队列管理器：串行 + 原子。

    继承 BaseSubtitleManager，复写三个抽象方法。
    """

    def __init__(self, pack_root, style, settings, dispatcher):
        super(S1Manager, self).__init__(
            pack_root, style, settings, dispatcher)
        self._queue = None           # S1Queue | None
        self._all_renderers = {}     # {rid: {'index': int, 'queue': S1Queue, 'state': str}}

    # ═════════════════════════════════════════════════════════
    # 公开 API（实现基类抽象方法）
    # ═════════════════════════════════════════════════════════

    def on_marker(self, marker_str):
        """Wwise marker 回调。加载句子 → 入队调度。"""
        if not self._enabled:
            logger.debug('字幕已禁用，忽略 marker: "%s"', marker_str)
            return
        if not marker_str:
            return

        logger.debug('收到 marker: "%s"', marker_str)
        data = load_sentence(self._pack_root, marker_str, self._style.lang if self._style else 'zh_cn')
        if data is None:
            logger.debug('句子文件未找到: "%s"', marker_str)
            return
        if not data.timeline:
            logger.debug('句子 %s timeline 为空，跳过', marker_str)
            return

        self._enqueue(data, marker_str)

    def on_fade_out_done(self, renderer_id):
        """Flash renderer 淡出完成。从追踪中清理 → 下移补位。

        仅下移曾被 shift_up 过的 renderer（shift_count > 0），
        避免把从未上移的新 renderer 推出正确位置。
        """
        state = self._all_renderers.pop(renderer_id, None)
        if state is None:
            return
        logger.debug('renderer %d 淡出完成', renderer_id)

        for other_rid, other_info in list(self._all_renderers.items()):
            if other_info['state'] == 'dead':
                continue
            if other_info.get('shift_count', 0) > 0:
                self._emit('shift_down', other_rid, distance=self._slot_height)
                other_info['shift_count'] -= 1

    def clear(self):
        """清空所有字幕。"""
        self._emit('clear_all')
        if self._queue is not None:
            self._queue.kill()
            self._queue = None
        self._all_renderers.clear()
        self._next_rid = 1
        logger.debug('字幕已全部清除')

    # ═════════════════════════════════════════════════════════
    # 内部：入队 + 打断
    # ═════════════════════════════════════════════════════════

    def _enqueue(self, data, audio_key):
        """新语音入队：打断旧队列 → 创建新队列 → 调度 callbacks。"""
        self._interrupt()

        queue = S1Queue(audio_key, data)
        self._queue = queue
        logger.info('队列开始: %s (%d 条, %.1fs)',
                    audio_key, len(queue.entries), queue.duration)

        n = len(queue.entries)
        for i, entry in enumerate(queue.entries):
            begin_at = entry.start_at

            # end_at = 下一条的 start_at，最后一条用 duration
            if i + 1 < n:
                end_at = queue.entries[i + 1].start_at
            else:
                end_at = queue.duration

            if begin_at > 0:
                BigWorld.callback(
                    begin_at,
                    lambda e=entry, idx=i, q=queue: self._on_entry_begin(e, idx, q)
                )
            else:
                self._on_entry_begin(entry, i, queue)

            # 淡出回调（end_at == begin_at 时与 _on_entry_begin 同时触发，
            # 但 begin 在 callback 前已执行，所以 renderer 已创建完毕）
            BigWorld.callback(
                end_at,
                lambda idx=i, q=queue: self._on_entry_end(idx, q)
            )

        # 队列结束（duration=0 时立即触发）
        BigWorld.callback(
            max(queue.duration, 0.001),
            lambda q=queue: self._on_queue_done(q)
        )

    def _interrupt(self):
        """打断当前队列：标记 dead → 淡出所有活跃 renderer → 回调。"""
        old = self._queue
        if old is None:
            return

        old.kill()
        logger.debug('打断队列: %s', old.audio_key)

        # 注意：旧音频的停止由 Path A 钩子在新事件入口处处理
        # （_hooked_WW_eventGlobal 等），不在字幕层面重复停止。
        # 此处只负责字幕 renderer 的生命周期。

        # 淡出所有活跃 renderer
        for idx, rid in list(old._active_renderers.items()):
            self._emit('fade_out', rid)
            if rid in self._all_renderers:
                self._all_renderers[rid]['state'] = 'fading'
        old._active_renderers.clear()

        self._queue = None

    # ═════════════════════════════════════════════════════════
    # 内部：生命周期回调
    # ═════════════════════════════════════════════════════════

    def _on_entry_begin(self, entry, index, queue):
        """Entry 开始：避让 → 创建 renderer。"""
        if queue.dead:
            return

        # 碰撞避让: 上移所有活跃 renderer（含淡出中的，它们也需要让位）
        for existing_rid, info in self._all_renderers.items():
            if info['state'] == 'dead':
                continue
            self._emit('shift_up', existing_rid, distance=self._slot_height)
            info['shift_count'] = info.get('shift_count', 0) + 1

        rid = self._gen_rid()
        queue._active_renderers[index] = rid

        data = assemble_entry_data(entry, self._style, self._settings, self._offsets)
        self._emit('create', rid, data=data)
        self._all_renderers[rid] = {'index': index, 'queue': queue,
                                     'state': 'active', 'shift_count': 0}

        logger.debug('entry %d 登场: rid=%d character=%s',
                     index, rid, entry.character)

    def _on_entry_end(self, index, queue):
        """Entry 结束：淡出 renderer。"""
        if queue.dead:
            return  # interrupt 已经处理了

        rid = queue._active_renderers.pop(index, None)
        if rid is not None:
            self._emit('fade_out', rid)
            if rid in self._all_renderers:
                self._all_renderers[rid]['state'] = 'fading'
            logger.debug('entry %d 淡出: rid=%d', index, rid)

    def _on_queue_done(self, queue):
        """队列自然结束：清理。"""
        if queue.dead:
            return  # 已被 interrupt

        logger.debug('队列结束: %s', queue.audio_key)
        # 防御：淡出可能遗留的 renderer
        for idx, rid in list(queue._active_renderers.items()):
            self._emit('fade_out', rid)
            if rid in self._all_renderers:
                self._all_renderers[rid]['state'] = 'fading'
        queue._active_renderers.clear()
        queue.kill()

        if self._queue is queue:
            self._queue = None
