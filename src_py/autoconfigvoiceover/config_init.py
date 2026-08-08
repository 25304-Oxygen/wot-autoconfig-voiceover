# coding=utf-8
"""配置目录初始化与用户资源管理。

目录结构:
  mods/configs/autoConfigVoiceOver/
    config.json              ← 用户配置文件
    icons/                   ← 图标（用户可替换）
    bgimgs/                  ← 背景图（用户可替换）
    jsons/                   ← 可编辑 JSON + 运行时生成数据
    l10n/                    ← 界面词典 + 帮助页 HTML
    subtitles/               ← 字幕数据
    script.log               ← 日志

所有可编辑资源优先从磁盘读取；磁盘缺失或损坏时从 VFS 恢复。
VFS 中的文件仅用作初始备份，不直接使用。
"""

import os

import ResMgr

from ._metadata import MOD_CONFIG_VERSION
from .constants import CONFIG_FILE, MY_CONFIG_FOLDER, MY_JSONS_FOLDER
from .logger import Logger
from .utils import load_jsonc, load_vfs_json, save_jsonc

logger = Logger('ConfigInit')

# ═════════════════════════════════════════════════════════════
# VFS → 磁盘资源映射
# ═════════════════════════════════════════════════════════════

_VFS_RESOURCE_ROOT = 'mods/autoconfigvoiceover'

# 需要从 VFS 复制到磁盘的用户可编辑文件（相对 _VFS_RESOURCE_ROOT）
# ★ icon.png 不拷贝——ModsList 入口图标仅从 VFS 读取
_USER_RESOURCE_FILES = [
    # jsons —— 用户可编辑的 JSON 配置
    'jsons/hotkey.json',
    'jsons/theme.json',
    'jsons/playEvent.json',
    'jsons/ingameGuiText.json',
    # icons —— 小圆图标（不含 icon.png）
    'icons/settings.png',
    'icons/voice.png',
    'icons/help.png',
    # bgimgs —— 菜单背景图
    'bgimgs/menu.png',
    'bgimgs/panel.png',
    'bgimgs/page.png',
]

# 目录级复制的用户可编辑资源（i18n 第一期，2026-08）：
#   l10n/ —— 界面词典 <lang>.json + 帮助页 HTML <lang>.html
#            （后缀不同天然分隔；磁盘副本加载链优先，见 l10n.py / help_page.py）
# 目录内文件按 copy-if-missing 语义复制（枚举 VFS 目录逐文件判断）。
_DIR_RESOURCES = ['l10n']

# 磁盘上 Flash 加载路径前缀。
# ★ 不能以 "mods/" 开头——ImageCache.load 检测到会自动补 "../../"，
#   结果从 res/gui/flash/ 解析到 res/mods/configs/...（错误）。
#   用 "../../../mods/configs/..." 从 res/gui/flash/ 上溯 3 级到达游戏根目录。
_DISK_FLASH_PREFIX = '../../../mods/configs/autoConfigVoiceOver'

# 已提示过缺失的 VFS 资源路径——同一路径只 WARN 一次。
# 菜单图片解析每次都会探测（get_default_menu_images → ensure_user_resource），
# 缺失资源属设计内回退（Flash 端保持默认外观），反复 WARN 会刷屏。
_warned_vfs_missing = set()


# ═════════════════════════════════════════════════════════════
# 公开接口
# ═════════════════════════════════════════════════════════════


def ensure_config_ready():
    """确保配置目录完整且版本正确。

    必须在 mod init() 早期调用（在读取任何配置之前）。
    三种重建场景：
      1. 目录或 config.json 不存在 → 全量重建
      2. config.json 不可读或缺少 __version__ → 重建配置 + 刷新资源
      3. __version__ < MOD_CONFIG_VERSION → 重建配置 + 刷新资源
    """
    # 情况1: 目录或配置文件不存在
    if not os.path.isdir(MY_CONFIG_FOLDER) or not os.path.isfile(CONFIG_FILE):
        _full_rebuild()
        logger.info('\n~~~~~~~~~~~~~~~~~~~~~~~~~'
                    '\n欢迎下载和使用语音包管理插件'
                    '\n~~~~~~~~~~~~~~~~~~~~~~~~~')
        return

    # 尝试读取现有配置
    cfg = load_jsonc(CONFIG_FILE)

    # 情况2: 配置文件不可读或缺少 __version__
    if cfg is None or '__version__' not in cfg:
        logger.info('配置文件不可读或缺少版本号，重建配置并刷新资源')
        _rebuild_config_and_resources()
        return

    # 情况3: 版本过旧
    version = cfg.get('__version__', 0)
    if version < MOD_CONFIG_VERSION:
        logger.info('配置版本 %d < %d，重建配置并刷新资源',
                    version, MOD_CONFIG_VERSION)
        # 版本 < 5 时清理旧版遗留目录（模板 / 旧图片目录）
        if version < 5:
            _cleanup_legacy_folders()
        _rebuild_config_and_resources()
        return

    # 配置就绪，仅补充缺失的个别资源文件（用户可能手动删了某个文件）
    _ensure_resources_exist()
    logger.debug('配置目录校验通过 (version=%d)', version)


def load_user_json(filename):
    """读取用户可编辑的 JSON 文件（磁盘优先，VFS 兜底）。

    1. 从磁盘 jsons/filename 读取
    2. 失败 → 从 VFS 读取 → 写入磁盘副本 → 返回数据
    3. 都失败 → 返回 None

    用于 hotkey.json / theme.json / playEvent.json 等用户可编辑文件。
    """
    disk_path = os.path.join(MY_JSONS_FOLDER, filename)
    vfs_path = '%s/jsons/%s' % (_VFS_RESOURCE_ROOT, filename)

    # 优先磁盘
    data = load_jsonc(disk_path)
    if data is not None:
        return data

    # VFS 兜底
    data = load_vfs_json(vfs_path)
    if data is not None:
        try:
            save_jsonc(disk_path, data)
            logger.debug('已从 VFS 恢复: %s', filename)
        except Exception:
            logger.warn('无法写入磁盘副本: %s', disk_path)
        return data

    logger.warn('用户资源 %s 在磁盘和 VFS 均不可用', filename)
    return None


def ensure_l10n_files():
    """确保磁盘 l10n/ 目录下存在全部 VFS 词典副本（copy-if-missing）。

    用户可编辑磁盘副本是加载链第一优先；VFS 新增的键自动补齐，
    用户旧文件不被覆盖。幂等，可随时调用。
    """
    _copy_dir_if_missing('%s/l10n' % _VFS_RESOURCE_ROOT,
                         os.path.join(MY_CONFIG_FOLDER, 'l10n'))


def ensure_user_resource(subfolder, rel_path):
    """确保用户资源文件在磁盘上存在，返回磁盘绝对路径。

    缺失时从 VFS 复制。用于图片等二进制资源。

    :param subfolder: 'icons' | 'bgimgs' | 'jsons'
    :param rel_path:  文件名，如 'settings.png'
    :return: 磁盘绝对路径；VFS 中也不存在时返回 None
    """
    disk_dir = os.path.join(MY_CONFIG_FOLDER, subfolder)
    disk_path = os.path.join(disk_dir, rel_path)

    if os.path.isfile(disk_path):
        return disk_path

    # 从 VFS 复制
    vfs_path = '%s/%s/%s' % (_VFS_RESOURCE_ROOT, subfolder, rel_path)
    if not ResMgr.isFile(vfs_path):
        if vfs_path not in _warned_vfs_missing:
            _warned_vfs_missing.add(vfs_path)
            logger.warn('VFS 资源不存在: %s', vfs_path)
        return None

    try:
        _copy_vfs_file(vfs_path, disk_path)
        logger.debug('已从 VFS 复制: %s → %s', vfs_path, disk_path)
        return disk_path
    except Exception:
        logger.exception('从 VFS 复制资源失败: %s', vfs_path)
        return None


def get_user_resource_flash_path(subfolder, rel_path):
    """返回 Flash 可用的磁盘资源路径。

    先 ensure 文件在磁盘存在，再返回 mods/configs/... 格式的路径。
    VFS 也不存在时回退到 VFS 路径（让 Flash 端自然降级）。

    :param subfolder: 'icons' | 'bgimgs'
    :param rel_path:  文件名，如 'settings.png'
    :return: 'mods/configs/autoConfigVoiceOver/icons/settings.png'
    """
    disk_abs = ensure_user_resource(subfolder, rel_path)
    if disk_abs is not None:
        return '%s/%s/%s' % (_DISK_FLASH_PREFIX, subfolder, rel_path)
    # 回退：VFS 路径（Flash 加载失败时组件保持默认外观）
    return '%s/%s/%s' % (_VFS_RESOURCE_ROOT, subfolder, rel_path)


def get_default_menu_images():
    """返回菜单组件默认图片路径 dict（全部来自磁盘副本）。

    每个路径都经过 ensure，缺失时已从 VFS 复制到磁盘。
    """
    return {
        'bigCircle':    get_user_resource_flash_path('bgimgs', 'menu.png'),
        'semiPanel':    get_user_resource_flash_path('bgimgs', 'panel.png'),
        'fullPanel':    get_user_resource_flash_path('bgimgs', 'page.png'),
        'smallCircles': [
            get_user_resource_flash_path('icons', 'settings.png'),
            get_user_resource_flash_path('icons', 'voice.png'),
            get_user_resource_flash_path('icons', 'help.png'),
        ],
    }


# ═════════════════════════════════════════════════════════════
# 内部实现
# ═════════════════════════════════════════════════════════════


def _cleanup_legacy_folders():
    """删除旧版遗留的 templates / images 目录（如果存在）。

    早期版本在配置目录下创建了 templates（模板）和 images（旧图片目录），
    现已不再使用。版本升至 5 时一次性清理。
    """
    import shutil
    settings_json = os.path.join(MY_CONFIG_FOLDER, 'jsons', 'settings.json')
    if os.path.isfile(settings_json):
        try:
            shutil.rmtree(settings_json)
            logger.info('已删除旧文件：settings.json')
        except Exception:
            logger.warn('删除旧文件失败：settings.json')
    for folder_name in ('templates', 'Images'):
        folder_path = os.path.join(MY_CONFIG_FOLDER, folder_name)
        if os.path.isdir(folder_path):
            try:
                shutil.rmtree(folder_path)
                logger.info('已删除旧版遗留目录: %s', folder_path)
            except Exception:
                logger.warn('删除旧版遗留目录失败: %s', folder_path)


def _full_rebuild():
    """创建目录结构 → 写入默认 config.json → 复制全部 VFS 资源。"""
    _ensure_dirs()
    _write_default_config()
    _copy_all_resources()


def _rebuild_config_and_resources():
    """覆盖 config.json → 覆盖全部 VFS 资源到磁盘。"""
    _write_default_config()
    _copy_all_resources()


def _ensure_dirs():
    """创建配置目录及子目录。"""
    for sub in ('icons', 'bgimgs', 'jsons', 'subtitles', 'l10n'):
        d = os.path.join(MY_CONFIG_FOLDER, sub)
        if not os.path.isdir(d):
            os.makedirs(d)


def _ensure_resources_exist():
    """逐文件检查：磁盘缺失的从 VFS 补充（不覆盖已有文件）。"""
    for rel in _USER_RESOURCE_FILES:
        subfolder, filename = rel.split('/', 1)
        disk_path = os.path.join(MY_CONFIG_FOLDER, subfolder, filename)
        if os.path.isfile(disk_path):
            continue
        vfs_path = '%s/%s' % (_VFS_RESOURCE_ROOT, rel)
        if ResMgr.isFile(vfs_path):
            try:
                _copy_vfs_file(vfs_path, disk_path)
            except Exception:
                logger.warn('补充资源失败: %s', vfs_path)
    # 目录级资源（l10n/）
    for sub in _DIR_RESOURCES:
        _copy_dir_if_missing('%s/%s' % (_VFS_RESOURCE_ROOT, sub),
                             os.path.join(MY_CONFIG_FOLDER, sub))


def _write_default_config():
    """写入带当前版本号的默认配置文件。"""
    from .config import DEFAULTS
    data = dict(DEFAULTS)
    data['__version__'] = MOD_CONFIG_VERSION
    save_jsonc(CONFIG_FILE, data, header_comment='ACV 用户配置文件')
    logger.info('默认配置文件已写入 (version=%d)', MOD_CONFIG_VERSION)


def _copy_all_resources():
    """从 VFS 复制全部用户资源到磁盘（覆盖已有）。"""
    for rel in _USER_RESOURCE_FILES:
        subfolder, filename = rel.split('/', 1)
        vfs_path = '%s/%s' % (_VFS_RESOURCE_ROOT, rel)
        disk_path = os.path.join(MY_CONFIG_FOLDER, subfolder, filename)
        if ResMgr.isFile(vfs_path):
            try:
                _copy_vfs_file(vfs_path, disk_path)
            except Exception:
                logger.warn('复制资源失败: %s → %s', vfs_path, disk_path)
    # 目录级资源（l10n/）——覆盖复制（重建场景）
    for sub in _DIR_RESOURCES:
        _copy_dir_all('%s/%s' % (_VFS_RESOURCE_ROOT, sub),
                      os.path.join(MY_CONFIG_FOLDER, sub))
    logger.info('已从 VFS 复制 %d 个资源文件到配置目录',
                len(_USER_RESOURCE_FILES))


def _copy_dir_if_missing(vfs_dir, disk_dir):
    """枚举 VFS 目录下全部文件，磁盘缺失的复制（不覆盖已有文件）。

    用于 l10n/ 等目录级用户可编辑资源（界面词典 json + 帮助页 html）。
    """
    try:
        sec = ResMgr.openSection(vfs_dir)
        if sec is None:
            return
        if not os.path.isdir(disk_dir):
            os.makedirs(disk_dir)
        for name in sec.keys():
            disk_path = os.path.join(disk_dir, name)
            if os.path.isfile(disk_path):
                continue
            vfs_path = '%s/%s' % (vfs_dir, name)
            try:
                _copy_vfs_file(vfs_path, disk_path)
                logger.debug('已从 VFS 复制: %s → %s', vfs_path, disk_path)
            except Exception:
                logger.warn('补充目录资源失败: %s', vfs_path)
    except Exception:
        pass


def _copy_dir_all(vfs_dir, disk_dir):
    """枚举 VFS 目录下全部文件并覆盖复制到磁盘（重建场景）。"""
    try:
        sec = ResMgr.openSection(vfs_dir)
        if sec is None:
            return
        if not os.path.isdir(disk_dir):
            os.makedirs(disk_dir)
        for name in sec.keys():
            vfs_path = '%s/%s' % (vfs_dir, name)
            disk_path = os.path.join(disk_dir, name)
            try:
                _copy_vfs_file(vfs_path, disk_path)
            except Exception:
                logger.warn('复制目录资源失败: %s', vfs_path)
    except Exception:
        pass


def _copy_vfs_file(vfs_path, disk_path):
    """从 VFS 复制单个文件到磁盘（自动创建目标目录）。"""
    disk_dir = os.path.dirname(disk_path)
    if not os.path.isdir(disk_dir):
        os.makedirs(disk_dir)
    section = ResMgr.openSection(vfs_path)
    if section is None:
        raise IOError('VFS 文件不存在: %s' % vfs_path)
    with open(disk_path, 'wb') as f:
        f.write(section.asBinary)
