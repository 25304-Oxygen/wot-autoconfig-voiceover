# coding=utf-8
"""S3 串行-合并队列策略。

单语音串行 + 同角色 entry 合并:
  - 同一语音内连续同角色 entry → 合并为一个 CompoundItem，共享 renderer
  - 内容切换通过 update_content 实现（瞬间替换，无入场动画）
  - 新语音打断整队，但同角色 renderer 可被跨语音复用
  - 无堆叠（串行），屏幕上同时最多一个 renderer（交接瞬间两个）
"""

import BigWorld

from autoconfigvoiceover.logger import Logger
from .base import BaseSubtitleManager
from .loader import load_sentence
from .assembler import assemble_entry_data
from .merger import merge_entries

logger = Logger('S3Manager')

# Flash SubtitleRenderer.ENTRY_DURATION 常量（秒）。
# S3 跨语音复用时无入场动画，额外动画的 anime_start_at 计时基准
# 整体左移了一个入场动画时长，需补偿首个 anime_start_at。
_ENTRY_DURATION = 0.3


class S3Voice(object):
    """一个语音的字幕数据。"""

    __slots__ = ('audio_key', 'duration', 'items', 'dead')

    def __init__(self, audio_key, data):
        """
        :param audio_key: 音频标识（marker 名）
        :param data:      SubtitleData 实例
        """
        self.audio_key = audio_key
        self.duration = data.duration
        self.items = merge_entries(data.timeline, data.duration)  # [CompoundItem]
        self.dead = False

    def kill(self):
        self.dead = True


class S3Manager(BaseSubtitleManager):
    """S3 字幕队列管理器：串行 + 合并。

    单语音模型：_voice 始终是当前唯一的活跃语音。
    打断时同角色 renderer 可被复用（update_content）。
    """

    def __init__(self, pack_root, style, settings, dispatcher):
        super(S3Manager, self).__init__(
            pack_root, style, settings, dispatcher)
        self._voice = None           # S3Voice | None
        self._active = {}            # {rid: {'item': CompoundItem, 'voice': S3Voice, 'state': str}}

    # ═════════════════════════════════════════════════════════
    # 公开 API
    # ═════════════════════════════════════════════════════════

    def on_marker(self, marker_str):
        """Wwise marker 回调。加载句子 → 合并 → 打断旧语音 → 入队。"""
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

        self._enqueue(marker_str, data)

    def on_fade_out_done(self, renderer_id):
        """renderer 淡出完成。从追踪中清理 → 下移补位。

        仅下移曾被 shift_up 过的 renderer（shift_count > 0），
        避免把从未上移的新 renderer 推出正确位置。
        """
        info = self._active.pop(renderer_id, None)
        if info is None:
            return
        logger.debug('renderer %d 淡出完成', renderer_id)

        for other_rid, other_info in list(self._active.items()):
            if other_info['state'] == 'dead':
                continue
            if other_info.get('shift_count', 0) > 0:
                self._emit('shift_down', other_rid, distance=self._slot_height)
                other_info['shift_count'] -= 1

    def clear(self):
        """清空所有字幕。"""
        self._emit('clear_all')
        if self._voice is not None:
            self._voice.kill()
            self._voice = None
        self._active.clear()
        self._next_rid = 1
        logger.debug('字幕已全部清除')

    # ═════════════════════════════════════════════════════════
    # 内部：入队 + 打断
    # ═════════════════════════════════════════════════════════

    def _enqueue(self, audio_key, data):
        """新语音入队：打断旧语音 → 尝试复用 → 调度。"""
        new_voice = S3Voice(audio_key, data)

        if not new_voice.items:
            logger.debug('合并后无队列项，跳过: %s', audio_key)
            return

        # DEBUG：逐战斗语音事件入队，属高频诊断级；INFO 留给系统级状态
        logger.debug('语音入队: %s (%d 条目 → %d 复合项, %.1fs)',
                     audio_key, len(data.timeline), len(new_voice.items), new_voice.duration)

        # 打断旧语音
        old = self._voice
        if old is not None:
            old.kill()
            logger.debug('打断旧语音: %s', old.audio_key)

            # 注意：旧音频的停止由 Path A 钩子在新事件入口处处理
            # （_hooked_WW_eventGlobal 等），不在字幕层面重复停止。
            # 此处只负责字幕 renderer 的生命周期。

            # 遍历所有旧 renderer：匹配角色 → 复用，不匹配 → 淡出
            # 每个 renderer 独立判决，消除"复用→跳过全部淡出"的僵尸 bug
            # 规则：淡出中的字幕只做避让，不参与复用
            new_first_char = new_voice.items[0].character
            reused = False
            for rid, info in list(self._active.items()):
                if info['voice'] is old:
                    if info['state'] == 'fading':
                        continue  # 已在淡出，不碰——只参与后续 shift 避让
                    item = info['item']
                    if not reused and item.character == new_first_char:
                        # 同角色 → 复用 renderer（仅第一个匹配的活跃 renderer）
                        stage = new_voice.items[0].stages[0]
                        data = assemble_entry_data(stage.entry, self._style,
                                                   self._settings, self._offsets)

                        # 跨语音复用无入场动画，额外动画的计时基准
                        # 整体左移了 ENTRY_DURATION。补偿首个 anime_start_at。
                        anime = data.get('anime', [])
                        if anime:
                            start_at = data.get('anime_start_at', [])
                            if start_at:
                                start_at[0] = start_at[0] + _ENTRY_DURATION
                            else:
                                start_at = [_ENTRY_DURATION]
                            data['anime_start_at'] = start_at

                        self._emit('update_content', rid, data=data)
                        info['voice'] = new_voice
                        info['item'] = new_voice.items[0]
                        info['state'] = 'active'
                        new_voice.items[0].rid = rid
                        reused = True
                        logger.debug('跨语音复用 renderer: rid=%d character=%s',
                                     rid, new_first_char)
                    else:
                        # 不匹配或已复用 → 淡出
                        self._emit('fade_out', rid)
                        info['state'] = 'fading'

        self._voice = new_voice

        # 调度所有 CompoundItem
        for item_index, item in enumerate(new_voice.items):
            self._schedule_item(new_voice, item, item_index)

        # 语音结束
        BigWorld.callback(
            max(new_voice.duration, 0.001),
            lambda v=new_voice: self._on_voice_done(v)
        )

    # ═════════════════════════════════════════════════════════
    # 内部：调度
    # ═════════════════════════════════════════════════════════

    def _schedule_item(self, voice, item, item_index):
        """调度一个 CompoundItem 的全部 stages 和结束回调。

        首个 stage (at=begin_at):
          - 若已被复用（item.rid 已设置）→ 跳过 create
          - 否则 → create renderer
        后续 stage (at): update_content
        结束 (end_at): fade_out
        """
        begin_at = item.span[0]
        end_at = item.span[1]

        # 首个 stage
        first_stage = item.stages[0]
        if item.rid is not None:
            # 已被跨语音复用，跳过 create
            pass
        elif begin_at > 0:
            BigWorld.callback(
                begin_at,
                lambda v=voice, it=item: self._on_item_begin(v, it)
            )
        else:
            self._on_item_begin(voice, item)

        # 后续 stage
        for stage in item.stages[1:]:
            BigWorld.callback(
                stage.at,
                lambda v=voice, it=item, s=stage: self._on_stage_update(v, it, s)
            )

        # 结束
        if end_at > begin_at:
            BigWorld.callback(
                end_at,
                lambda v=voice, it=item: self._on_item_end(v, it)
            )

    # ═════════════════════════════════════════════════════════
    # 内部：生命周期回调
    # ═════════════════════════════════════════════════════════

    def _on_item_begin(self, voice, item):
        """CompoundItem 首个 stage：避让 → 创建 renderer。"""
        if voice.dead:
            return

        # 碰撞避让: 上移所有非 dead 的 renderer（含 fading）
        # 跨语音复用时 item.rid 已设置，不会走到此分支
        for existing_rid, info in self._active.items():
            if info['state'] != 'dead':
                self._emit('shift_up', existing_rid, distance=self._slot_height)
                info['shift_count'] = info.get('shift_count', 0) + 1

        rid = self._gen_rid()
        item.rid = rid

        stage = item.stages[0]
        data = assemble_entry_data(stage.entry, self._style, self._settings, self._offsets)
        self._emit('create', rid, data=data)
        self._active[rid] = {'item': item, 'voice': voice,
                             'state': 'entering', 'shift_count': 0}

        logger.debug('复合项 %s 登场: rid=%d character=%s',
                     item.character, rid, item.character)

    def _on_stage_update(self, voice, item, stage):
        """CompoundItem 后续 stage：update_content 瞬间替换。"""
        if voice.dead:
            return

        rid = item.rid
        if rid is None or rid not in self._active:
            return

        data = assemble_entry_data(stage.entry, self._style, self._settings, self._offsets)
        self._emit('update_content', rid, data=data)
        self._active[rid]['state'] = 'active'

        logger.debug('复合项 %s 更新内容: rid=%d at=%.1f',
                     item.character, rid, stage.at)

    def _on_item_end(self, voice, item):
        """CompoundItem 结束：淡出 renderer。"""
        if voice.dead:
            return

        rid = item.rid
        if rid is None:
            return

        if rid in self._active:
            self._emit('fade_out', rid)
            self._active[rid]['state'] = 'fading'
            logger.debug('复合项 %s 淡出: rid=%d', item.character, rid)

    def _on_voice_done(self, voice):
        """语音结束：标记 dead，防御清理。"""
        if voice.dead:
            return

        voice.kill()
        logger.debug('语音结束: %s', voice.audio_key)

        # 防御：淡出残留 renderer
        for rid, info in list(self._active.items()):
            if info['voice'] is voice and info['state'] not in ('dead', 'fading'):
                self._emit('fade_out', rid)
                info['state'] = 'fading'

        if self._voice is voice:
            self._voice = None
