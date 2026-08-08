# coding=utf-8
"""语音包数据持久层——jsons/ 目录读写与合并。

落盘文件沿用 1.x 命名（与旧版共用目录，继承旧版用户数据，零迁移）：
  gameSoundModes.json —— 内置语音行（用户可改名，回读继承）
  voiceover.json      —— 第三方语音行 + 音量方案

试听事件列表 playEvent.json 随 mod 打包（VFS 只读资源），
作为语音包 events.json 缺失时的回退列表，不在 configs/ 下生成、不落盘。
"""

from autoconfigvoiceover.constants import (DEFAULT_VOLUME,
                                           GAME_SOUND_MODES_JSON,
                                           VOICEOVER_JSON)
from autoconfigvoiceover.logger import Logger
from autoconfigvoiceover.utils import load_jsonc, save_jsonc

logger = Logger('VoiceStorage')


# ═════════════════════════════════════════════════════════════
# 读取
# ═════════════════════════════════════════════════════════════

def load_saved_ingame():
    """读取已保存的内置语音行；无文件/损坏返回 []。"""
    return _load_rows(GAME_SOUND_MODES_JSON)


def load_saved_outside():
    """读取已保存的第三方语音行；无文件/损坏返回 []。"""
    return _load_rows(VOICEOVER_JSON)


def _load_rows(path):
    try:
        rows = load_jsonc(path)
    except (ValueError, TypeError):
        logger.warn('读取 %s 出错，该份数据将重置为默认', path)
        return []
    return rows if isinstance(rows, list) else []


def load_play_events():
    """读取全局试听事件列表 [{'text','event'}]（磁盘优先，VFS 兜底）。

    用作语音包 events.json 缺失时的回退列表。
    playEvent.json 已由 config_init 在启动时复制到磁盘，
    用户可编辑磁盘副本来自定义回退试听列表。
    若磁盘文件格式异常（如旧版 id/name 键），自动删除并从 VFS 恢复。
    """
    from autoconfigvoiceover.config_init import load_user_json
    events = load_user_json('playEvent.json')
    if not isinstance(events, list) or not events:
        logger.warn('试听事件列表读取失败（检查打包是否完整）')
        return []

    # 验证格式：每个项必须有 text 和 event 键
    # 旧版 playEvent.json 使用 id/name 键，应视为损坏
    if _is_valid_event_list(events):
        return events

    logger.warn('playEvent.json 格式异常（缺 text/event 键），'
                '可能是旧版 id/name 格式，将强制从 VFS 恢复')
    # 删除磁盘损坏文件 → 重新加载（磁盘不在了 → VFS 兜底 → 写入正确副本）
    import os as _os
    from autoconfigvoiceover.constants import MY_JSONS_FOLDER
    disk_path = _os.path.join(MY_JSONS_FOLDER, 'playEvent.json')
    if _os.path.isfile(disk_path):
        try:
            _os.remove(disk_path)
            logger.info('已删除损坏的 playEvent.json')
        except Exception:
            logger.exception('删除损坏的 playEvent.json 失败')

    events = load_user_json('playEvent.json')
    if not isinstance(events, list) or not events:
        logger.warn('从 VFS 恢复 playEvent.json 后仍失败')
        return []
    return events


def _is_valid_event_list(events):
    """验证事件列表中每项是否都有 text 和 event 键。

    旧版数据使用 id/name 键，不满足此约束。空列表视为有效（用户可能
    有意清空），但被 load_play_events 上层的 `not events` 守卫拦截，
    不会到这里。
    """
    for e in events:
        if not isinstance(e, dict):
            return False
        if not e.get('text') or not e.get('event'):
            return False
    return True


# ═════════════════════════════════════════════════════════════
# 合并（移植旧版 _set_volume + add_new_dict_only 语义）
# ═════════════════════════════════════════════════════════════

def merge_ingame(fresh_rows, saved_rows):
    """内置语音合并：已保存行优先（保留用户对名称的二次编辑），
    追加本次新读到的语音；缺音量的行补占位值 100。

    游戏内语音是只增不减的（除非换用了别的 main_sound_modes.xml），
    所以不做移除处理。
    """
    merged = [dict(row) for row in saved_rows if row.get('voiceID')]
    seen = set(row['voiceID'] for row in merged)
    for row in fresh_rows:
        if row.get('voiceID') and row['voiceID'] not in seen:
            merged.append(dict(row))
            seen.add(row['voiceID'])
    for row in merged:
        if 'volume' not in row:
            row['volume'] = 100
    return merged


def merge_outside(fresh_rows, saved_rows, current_volume):
    """第三方语音合并：以本次扫描为基准（卸载的包自然消失），
    音量沿用已保存方案，新包用当前 voice 通道音量。
    """
    if current_volume is None:
        current_volume = DEFAULT_VOLUME
    volume_map = dict((row['voiceID'], row['volume']) for row in saved_rows
                      if 'voiceID' in row and 'volume' in row)
    return [dict(row, volume=volume_map.get(row.get('voiceID'), current_volume))
            for row in fresh_rows]


# ═════════════════════════════════════════════════════════════
# 落盘
# ═════════════════════════════════════════════════════════════

# 落盘文件的头部注释（save_all / save_volume 共用）
_INGAME_HEADER = '游戏内语音包信息——nickName 可自行编辑，' \
                 '下次启动继承；删除此文件可恢复默认'
_OUTSIDE_HEADER = '第三方语音包信息与音量方案（以每次扫描结果为基准）'


def _save_rows(path, rows, comment):
    """写单个语音行列表到 JSON 文件。"""
    save_jsonc(path, rows, header_comment=comment)


def save_all(ingame_rows, outside_rows):
    """写回内置/第三方语音行（playEvent.json 是只读回退资源，不落盘）。"""
    _save_rows(GAME_SOUND_MODES_JSON, ingame_rows, _INGAME_HEADER)
    _save_rows(VOICEOVER_JSON, outside_rows, _OUTSIDE_HEADER)
    logger.info('语音包信息已保存: 内置 %d 条、第三方 %d 条',
                len(ingame_rows), len(outside_rows))


def save_volume(ingame_rows, outside_rows, voice_id):
    """把单个语音行的音量立即写回所属 JSON 文件（拖动音量滑块时调用）。

    与 save_all 不同，不受"一次会话只写一次"限制——音量是随时可调的
    高频改动，需要即时持久化。voiceID 命中内置列表 → gameSoundModes.json；
    命中第三方列表 → voiceover.json；两处都未命中则跳过（语音可能已被
    移除，保守起见不写）。
    """
    for rows, path, comment in ((ingame_rows, GAME_SOUND_MODES_JSON, _INGAME_HEADER),
                                (outside_rows, VOICEOVER_JSON, _OUTSIDE_HEADER)):
        for row in rows:
            if row.get('voiceID') == voice_id:
                _save_rows(path, rows, comment)
                logger.info('语音音量已保存: %s = %d', voice_id, row['volume'])
                return
    logger.debug('音量保存跳过——语音 %s 不在列表中', voice_id)
