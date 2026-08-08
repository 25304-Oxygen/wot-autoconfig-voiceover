# coding=utf-8
"""Entry 合并逻辑——S3/S4 共用。

将连续同角色 entry 合并为一个 CompoundItem（多个 ContentStage）。
"""


class CompoundItem(object):
    """合并后的队列项——多个同角色连续 entry 共享一个 renderer。

    __slots__ 按需延迟分配（Python 2 旧式类兼容）。
    """

    __slots__ = ('character', 'span', 'stages', 'rid')

    def __init__(self, character, span, stages):
        """
        :param character: str，角色代号
        :param span:      [begin_at, end_at]，在时间轴上的跨度
        :param stages:    [ContentStage, ...]，按 at 排序的内容切换点
        """
        self.character = character
        self.span = span        # [float, float]
        self.stages = stages    # [ContentStage]
        self.rid = None         # int | None，关联的 renderer ID（登场后分配）


class ContentStage(object):
    """CompoundItem 内的一次内容切换。"""

    __slots__ = ('at', 'entry')

    def __init__(self, at, entry):
        """
        :param at:    float，切换时间（相对语音开始）
        :param entry: SubtitleEntry，切换到的内容
        """
        self.at = at            # float
        self.entry = entry      # SubtitleEntry


def merge_entries(timeline, duration):
    """将 timeline 中连续同角色 entry 合并为 CompoundItem 列表。

    :param timeline: [SubtitleEntry, ...]
    :param duration: float，语音总时长
    :return: [CompoundItem, ...]
    """
    if not timeline:
        return []

    items = []
    current_ci = None

    for entry in timeline:
        if current_ci is not None and current_ci.character == entry.character:
            # 同角色 → 追加 stage
            current_ci.stages.append(ContentStage(entry.start_at, entry))
        else:
            # 新角色 → 结束上一个 CI，开始新 CI
            if current_ci is not None:
                _finalize_compound_item(items, current_ci, duration)
            current_ci = CompoundItem(
                character=entry.character,
                span=[entry.start_at, 0.0],  # end_at 稍后计算
                stages=[ContentStage(entry.start_at, entry)],
            )

    # 收尾最后一个 CI
    if current_ci is not None:
        _finalize_compound_item(items, current_ci, duration)

    return items


def _finalize_compound_item(items, ci, duration):
    """计算 CompoundItem 的 end_at 并添加到列表。

    end_at = 下一个 CI 的第一个 stage.at。
    若这是列表中的第一个 CI，其 end_at 暂时未知——先放入列表，
    待下一个 CI 出现时回填。最后一个 CI 的 end_at = duration。
    """
    if items:
        # 回填上一个 CI 的 end_at = 当前 CI 的 begin_at
        items[-1].span[1] = ci.span[0]

    items.append(ci)

    # 最后一个 CI 的 end_at 在调用方知道 duration 后再填
    # 这里先设为 duration（merge_entries 结束时统一处理）
    ci.span[1] = duration
