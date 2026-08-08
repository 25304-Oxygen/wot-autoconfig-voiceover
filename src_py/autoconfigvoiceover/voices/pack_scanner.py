# coding=utf-8
"""第三方语音包扫描——枚举 VFS mods/voiceover/ 下的包目录。

只负责"读取"：子目录存在 + pack.json 合法（仅 path/name 两键）即收录，
bank 存在性校验属于"加载"阶段（repository/注册处），无效包在那里被移除。
目录内可选资源也不在此探测入模型（懒加载策略，见 model.py 头注释），
仅以 debug 日志输出一份结构摘要，供语音包作者自查打包是否正确。

旧版（1.x zip 扫描 voiceover_*.wotmod + vo_/sbt_ json）由
legacy_scanner 模块单独处理，本扫描器仅负责新格式。
"""

import ResMgr

from autoconfigvoiceover.constants import VOICEOVER_PACKS_DIR
from autoconfigvoiceover.logger import Logger
from autoconfigvoiceover.utils import load_vfs_json
from . import model
from .model import PackInfo

logger = Logger('PackScanner')


def scan_packs():
    """扫描并返回全部语音包。

    :return: [PackInfo]——pack.json 缺失/非法的目录被跳过（warn）；
             bank 是否存在此处不校验
    """
    packs = []
    for pack_id in _list_subdirs(VOICEOVER_PACKS_DIR):
        pack = _read_pack(pack_id)
        if pack is not None:
            packs.append(pack)
            _log_structure(pack)

    logger.info('第三方语音包扫描完成: 共读取 %d 个', len(packs))
    return packs


# ═════════════════════════════════════════════════════════════
# 内部
# ═════════════════════════════════════════════════════════════

def _list_subdirs(vfs_dir):
    """列出 VFS 目录下的子目录名（ResMgr 枚举；keys() 可能重复，需去重）。"""
    result = []
    folder = ResMgr.openSection(vfs_dir)
    if folder is not None and ResMgr.isDir(vfs_dir):
        for name in folder.keys():
            if name not in result and ResMgr.isDir(vfs_dir + name):
                result.append(name)
    return sorted(result)


def _read_pack(pack_id):
    """读取单个包目录的 pack.json，返回 PackInfo；非法返回 None。"""
    root = VOICEOVER_PACKS_DIR + pack_id + '/'

    data = load_vfs_json(root + model.PACK_JSON)
    if data is None:
        logger.warn('语音包 %s 缺少 pack.json 或解析失败，已跳过', pack_id)
        return None
    if not isinstance(data, dict) or not data.get('path') or not data.get('name'):
        logger.warn('语音包 %s 的 pack.json 缺少 path/name 键，已跳过', pack_id)
        return None

    return PackInfo(pack_id=pack_id,
                    nick_name=data['name'],
                    bank=data['path'],
                    root=root)


def _log_structure(pack):
    """debug 输出包结构摘要（探测后即弃，不入模型）。"""
    found = []
    probes = [
        ('字幕样式', model.SUB_STYLES_DIR, True),
        ('字幕文本', model.SUB_SENTENCES_DIR, True),
        ('字幕图片', model.SUB_IMAGES_DIR, True),
        ('菜单背景图', model.BGIMGS_DIR, True),
        ('小圆图标', model.ICONS_DIR, True),
        ('事件表', model.EVENTS_JSON, False),
        ('颜色主题', model.THEME_JSON, False),
        ('绑定方案', model.ATTACH_JSON, False),
    ]
    for label, rel, is_dir in probes:
        exists = (ResMgr.isDir if is_dir else ResMgr.isFile)(pack.root + rel)
        if exists:
            found.append(label)
    for label, candidates in (('重映射', model.REMAP_CANDIDATES),
                              ('详情', model.INFO_CANDIDATES)):
        path = model.find_first(pack, candidates)
        if path:
            found.append(label + '(' + path.rsplit('/', 1)[-1] + ')')

    logger.debug('语音包 %s (%s): bank=%s%s', pack.pack_id, pack.nick_name,
                 pack.bank, (' | ' + '、'.join(found)) if found else '')
