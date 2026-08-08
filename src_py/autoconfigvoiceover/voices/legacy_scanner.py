# coding=utf-8
"""旧格式语音包扫描——读取 mods/{version}/ 下 voiceover_*.wotmod 的 pack.json。

旧版（1.x）语音包的 pack.json 在 wotmod 内与 res 文件夹同级，不进 VFS，
因此需用 zipfile 从磁盘读取。此模块为向后兼容临时存在，应当在未来移除。

旧格式 JSON 键名约定：
  nickName       —— 显示名称（新版用 name）
  bankPath       —— vo 类型，如 "somefolder/voiceover.bnk"（缺 audioww/ 前缀）
  voiceover_Path —— sbt 类型，如 "audioww/somefolder/voiceover.bnk"（完整路径）

JSON 可以是单个 dict 或 list[dict]，支持 // 注释行。
sbt 类型也当作纯语音包处理——字幕/主题等可选资源不兼容。
"""

import os
import zipfile

from autoconfigvoiceover.constants import MODS_PATH
from autoconfigvoiceover.logger import Logger
from .model import PackInfo

logger = Logger('LegacyScanner')

# wotmod 文件名必须以此前缀开头才会被扫描
_LEGACY_PREFIX = 'voiceover_'
_WOTMOD_SUFFIX = '.wotmod'

# 旧格式 JSON 的前缀约定（仅纯语音包，不再兼容旧版字幕语音包）
_JSON_PREFIXES = ('vo_', 'volist_')


def scan_legacy_packs():
    """扫描 mods/{version}/ 下所有 voiceover_*.wotmod，返回 [PackInfo]。

    无旧格式文件或全部解析失败时返回空列表，不阻断新格式扫描。
    以后会移除。
    """
    version_dir = MODS_PATH
    if not os.path.isdir(version_dir):
        logger.debug('版本目录不存在，跳过旧格式扫描: %s', version_dir)
        return []

    packs = []
    for wotmod_path in _find_legacy_wotmods(version_dir):
        try:
            packs.extend(_read_legacy_wotmod(wotmod_path))
        except Exception:
            logger.exception('读取旧格式语音包失败: %s', wotmod_path)

    if packs:
        logger.info('旧格式语音包扫描完成: %d 个', len(packs))
    return packs


# ═════════════════════════════════════════════════════════════
# 内部
# ═════════════════════════════════════════════════════════════

def _find_legacy_wotmods(version_dir):
    """递归搜索版本目录下所有 voiceover_*.wotmod 文件。"""
    wotmods = []
    try:
        for root, _dirs, files in os.walk(version_dir):
            for name in files:
                if name.startswith(_LEGACY_PREFIX) and name.endswith(_WOTMOD_SUFFIX):
                    wotmods.append(os.path.join(root, name))
    except OSError:
        logger.warn('无法遍历版本目录: %s', version_dir)
        return []

    if wotmods:
        logger.debug('发现 %d 个旧格式 wotmod 文件', len(wotmods))
    return wotmods


def _read_legacy_wotmod(wotmod_path):
    """打开一个旧格式 wotmod，读取其 pack.json 并返回 [PackInfo]。"""
    basename = os.path.basename(wotmod_path)
    # voiceover_MyPack.wotmod → voiceover_MyPack（用作 pack_id 命名空间）
    wotmod_stem = basename[:-len(_WOTMOD_SUFFIX)]

    try:
        with zipfile.ZipFile(wotmod_path, 'r') as zf:
            namelist = zf.namelist()
            # 与 res 同级的 JSON 文件在 zip 根目录
            for name in namelist:
                # 跳过目录条目和 res/ 内的文件
                if name.endswith('/') or name.startswith('res/'):
                    continue
                basename_item = os.path.basename(name)
                prefix = basename_item.split('_')[0] + '_'
                # volist → volist_、vo → vo_
                if prefix not in _JSON_PREFIXES:
                    continue
                if not name.endswith('.json'):
                    continue

                logger.debug('旧格式 wotmod %s → 读取 %s', wotmod_stem, name)
                return _parse_legacy_json(zf, name, wotmod_stem, basename)

            logger.warn('旧格式语音包 %s 中未找到 pack.json，已跳过', basename)
            return []
    except zipfile.BadZipfile:
        logger.warn('旧格式 wotmod 不是有效的 zip 文件: %s', basename)
        return []


def _parse_legacy_json(zf, json_name, wotmod_stem, basename):
    """解析旧格式 JSON 内容，返回 [PackInfo]。

    支持 dict（单语音包）和 list[dict]（多语音包）两种格式。
    """
    raw_bytes = zf.read(json_name)
    data = _parse_jsonc_bytes(raw_bytes)
    if data is None:
        return []

    entries = data if isinstance(data, list) else [data]

    packs = []
    for entry in entries:
        pack = _entry_to_packinfo(entry, wotmod_stem, json_name, basename)
        if pack is not None:
            packs.append(pack)
    return packs


def _parse_jsonc_bytes(raw_bytes):
    """从字节串解析带 // 注释的 JSON；失败返回 None。"""
    from autoconfigvoiceover.utils import parse_jsonc
    text = raw_bytes.decode('utf-8-sig', 'replace')
    return parse_jsonc(text)


def _entry_to_packinfo(entry, wotmod_stem, json_name, basename):
    """将单个旧格式条目转为 PackInfo；关键字段缺失返回 None。"""
    if not isinstance(entry, dict):
        return None

    nick_name = entry.get('nickName')
    if not nick_name:
        logger.warn('旧格式条目缺少 nickName 键，已跳过（%s → %s）',
                    basename, json_name)
        return None

    # bank 路径：vo 用 bankPath
    bank = entry.get('bankPath')
    if not bank:
        logger.warn('旧格式条目 "%s" 缺少 bankPath 键，已跳过',
                    nick_name)
        return None

    # 路径合法性：旧代码要求 bank 不在 audioww 根目录
    bank_stripped = bank
    if bank_stripped.startswith('audioww/'):
        bank_stripped = bank_stripped[len('audioww/'):]

    # bank 目录太浅（直接放在 audioww 下）视为非法
    if '/' not in bank_stripped:
        logger.warn('旧格式条目 "%s" 的 bank 路径不在子目录中，已跳过: %s',
                    nick_name, bank)
        return None

    # 生成 pack_id：bank 所在目录（从 audioww 出发的路径）。
    # 旧版不同 wotmod 的 bank 不会共享同一目录，直接取目录名不会冲突。
    bank_dirname = bank_stripped.rsplit('/', 1)[0]  # voiceover.bnk 的父目录
    pack_id = bank_dirname

    # bank VFS 路径：vo 类型（bankPath）需补齐 audioww/ 前缀
    if not bank.startswith('audioww/'):
        bank = 'audioww/' + bank

    # root 占位——旧格式无包 root，所有可选资源探测自动失败 → 回退
    root = '__legacy__/' + pack_id + '/'

    # DEBUG：逐包明细，启动摘要"旧格式语音包扫描完成"在 INFO 记录
    logger.debug('旧格式语音包: pack_id=%s nick=%s bank=%s',
                 pack_id, nick_name, bank)
    return PackInfo(pack_id=pack_id,
                    nick_name=nick_name,
                    bank=bank,
                    root=root)
