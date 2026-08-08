# coding=utf-8
"""S2 并行-原子队列策略。

单队列、动态重排、多语音共存堆叠:
  - 每个 entry = 1 个独立 renderer（原子）
  - 多个语音的 entry 共存于同一队列（并行）
  - 双列表模型: Active（已登场，含 fading）+ Pending（未登场，可重排）
  - 新语音→重排 Pending，不打断 Active
  - 垂直堆叠：下方新 entry 登场 → 上方 renderer 上移
  - renderer 死亡 → 上方 renderer 下移补位
"""

import BigWorld

from autoconfigvoiceover.logger import Logger
from .base import BaseSubtitleManager
from .loader import load_sentence
from .assembler import assemble_entry_data

logger = Logger('S2Manager')

# 固定槽位高度（从样式配置推导，不用动态测量）
DEFAULT_SLOT_HEIGHT = 80


class S2Voice(object):
    """一个语音的完整字幕数据。"""

    __slots__ = ('audio_key', 'entries', 'duration', 'priority', 'dead')

    def __init__(self, audio_key, data, priority):
        """
        :param audio_key: 音频标识（marker 名）
        :param data:      SubtitleData 实例
        :param priority:  int，到达顺序（越小越优先）
        """
        self.audio_key = audio_key
        self.entries = list(data.timeline)
        self.duration = data.duration
        self.priority = priority
        self.dead = False


class S2Manager(BaseSubtitleManager):
    """S2 字幕队列管理器：并行 + 原子。

    双列表模型:
      _active:  {rid: info}  已登场 renderer（含 'fading' 状态），参与 shift
      _pending: [dict]       未登场 entry，按 (start_at, priority) 排序
    """

    def __init__(self, pack_root, style, settings, dispatcher):
        super(S2Manager, self).__init__(
            pack_root, style, settings, dispatcher)
        self._active = {}            # {rid: {'voice': S2Voice, 'index': int, 'state': str}}
        self._pending = []           # [{'entry': SubtitleEntry, 'voice': S2Voice, 'start_at': float, 'end_at': float, 'rid': int}]
        self._voices = []            # [S2Voice]
        self._next_priority = 1
        self._slot_height = self._compute_slot_height()

    # ═════════════════════════════════════════════════════════
    # 公开 API
    # ═════════════════════════════════════════════════════════

    def on_marker(self, marker_str):
        """Wwise marker 回调。加载句子 → 创建语音 → 重排 Pending。"""
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

        self._add_voice(marker_str, data)

    def on_fade_out_done(self, renderer_id):
        """renderer 淡出完成 → 移除 → 上方 renderer 下移补位。

        仅下移那些曾被 shift_up 过的 renderer（shift_count > 0），
        避免把从未上移的底层新 renderer 推出正确位置。
        """
        info = self._active.pop(renderer_id, None)
        if info is None:
            return
        logger.debug('renderer %d 淡出完成，下移补位', renderer_id)

        for other_rid in list(self._active.keys()):
            other_info = self._active[other_rid]
            if other_info['state'] == 'dead':
                continue
            # 仅当 renderer 曾被上移时才下移还原
            if other_info.get('shift_count', 0) > 0:
                self._emit('shift_down', other_rid, distance=self._slot_height)
                other_info['shift_count'] -= 1
                other_info['state'] = 'shifting'

    def clear(self):
        """清空所有字幕。"""
        self._emit('clear_all')
        for voice in self._voices:
            voice.dead = True
        self._voices = []
        self._pending = []
        self._active.clear()
        self._next_rid = 1
        self._next_priority = 1
        logger.debug('字幕已全部清除')

    # ═════════════════════════════════════════════════════════
    # 内部：语音管理
    # ═════════════════════════════════════════════════════════

    def _add_voice(self, audio_key, data):
        """新语音到达：创建 S2Voice → 构建 PendingEntry → 重排 → 调度。"""
        voice = S2Voice(audio_key, data, self._next_priority)
        self._next_priority += 1
        self._voices.append(voice)

        logger.info('语音加入: %s (priority=%d, %d 条, %.1fs)',
                    audio_key, voice.priority, len(voice.entries), voice.duration)

        n = len(voice.entries)
        new_pending = []
        for i, entry in enumerate(voice.entries):
            begin_at = entry.start_at
            end_at = (voice.entries[i + 1].start_at if i + 1 < n
                      else voice.duration)

            new_pending.append({
                'entry': entry,
                'voice': voice,
                'start_at': begin_at,
                'end_at': end_at,
            })

        # 合并到全局 pending 并重排
        self._pending.extend(new_pending)
        self._reorder_pending()

        # 为每个新 pending 分配 RID 并调度 callbacks
        for pe in new_pending:
            self._schedule_pending_entry(pe)

        # 语音结束
        BigWorld.callback(
            max(voice.duration, 0.001),
            lambda v=voice: self._on_voice_done(v)
        )

    def _reorder_pending(self):
        """重排 Pending 列表：按 (start_at ASC, voice_priority ASC) 排序。

        重排后重新分配 RID（从 _next_rid 递增）。
        """
        self._pending.sort(key=lambda pe: (pe['start_at'], pe['voice'].priority))

        # 重分配 RID（同步更新 self._next_rid，防止连续重排时 RID 回退）
        next_rid = self._next_rid
        for pe in self._pending:
            pe['rid'] = next_rid
            next_rid += 1
        self._next_rid = next_rid

    # ═════════════════════════════════════════════════════════
    # 内部：调度
    # ═════════════════════════════════════════════════════════

    def _schedule_pending_entry(self, pe):
        """为单个 PendingEntry 调度 begin / end callbacks。

        注意：RID 可能在后续重排中变化，callback 触发时从 pe 实时读取。
        """
        begin_at = pe['start_at']
        end_at = pe['end_at']
        voice = pe['voice']

        if begin_at > 0:
            BigWorld.callback(
                begin_at,
                lambda p=pe: self._on_entry_begin(p)
            )
        else:
            self._on_entry_begin(pe)

        BigWorld.callback(
            end_at,
            lambda p=pe: self._on_entry_end(p)
        )

    # ═════════════════════════════════════════════════════════
    # 内部：生命周期回调
    # ═════════════════════════════════════════════════════════

    def _on_entry_begin(self, pe):
        """Entry 登场：shift 上方 → create 新 renderer。"""
        voice = pe['voice']
        if voice.dead:
            return

        rid = pe['rid']

        # 对所有 Active renderer（含 fading）上移让位
        for other_rid, info in list(self._active.items()):
            if info['state'] not in ('dead',):
                self._emit('shift_up', other_rid, distance=self._slot_height)
                info['state'] = 'shifting'
                info['shift_count'] = info.get('shift_count', 0) + 1

        # 创建 renderer（shift_count=0，表示未被上移过）
        data = assemble_entry_data(pe['entry'], self._style, self._settings, self._offsets)
        self._emit('create', rid, data=data)
        self._active[rid] = {'voice': voice, 'state': 'entering', 'shift_count': 0}
        self._next_rid = max(self._next_rid, rid + 1)

        # 从 pending 中移除
        try:
            self._pending.remove(pe)
        except ValueError:
            pass

        logger.debug('entry 登场: rid=%d character=%s (voice=%s priority=%d)',
                     rid, pe['entry'].character, voice.audio_key, voice.priority)

    def _on_entry_end(self, pe):
        """Entry 结束：淡出 renderer（保持 active 参与后续 shift）。"""
        voice = pe['voice']
        if voice.dead:
            return

        rid = pe['rid']
        if rid in self._active:
            self._emit('fade_out', rid)
            self._active[rid]['state'] = 'fading'
            logger.debug('entry 淡出: rid=%d', rid)

    def _on_voice_done(self, voice):
        """语音生命周期结束：标记 dead，清理残留。"""
        voice.dead = True
        logger.debug('语音结束: %s', voice.audio_key)

        # 清理该语音的残留 pending
        self._pending = [pe for pe in self._pending if pe['voice'] is not voice]

        # 清理该语音的残留 active（防御）
        for rid, info in list(self._active.items()):
            if info['voice'] is voice and info['state'] not in ('dead', 'fading'):
                self._emit('fade_out', rid)
                info['state'] = 'fading'
