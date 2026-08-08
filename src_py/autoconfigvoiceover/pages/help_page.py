# coding=utf-8
"""HelpPage —— 帮助面板。

对应 Flash: com.github._25304_Oxygen.menu.pages.HelpPage
入口: 左侧小圆导航按钮 #2

用途: 显示 mod 使用说明、版本信息、快捷链接等。
Flash 端渲染 HTML，超链接通过 TextEvent.LINK → onLog("htmlLink,...") 回调。
"""

from autoconfigvoiceover.logger import Logger
from autoconfigvoiceover.constants import MY_CONFIG_FOLDER
from autoconfigvoiceover._metadata import MOD_VERSION

logger = Logger('HelpPage')

# help 文件与界面词典统一放在 l10n/ 文件夹（后缀不同天然分隔）：
#   VFS:      mods/autoconfigvoiceover/l10n/<lang>.html
#   磁盘副本: mods/configs/autoConfigVoiceOver/l10n/<lang>.html
_HELP_VFS_ROOT = 'mods/autoconfigvoiceover/l10n'


def _strip_guard(raw):
    """剥离首字符保护位（含行尾换行）与 UTF-8 BOM，并移除正文换行符。

    help 文件（l10n/<lang>.html）首行统一为保护位（约定 '#'，非空格、非 '<'）
    ——ResMgr 会把以 '<' 开头的文件当作 XML 解析（HTML 非严格 XML，解析失败
    返回 None），保护位让首字节非 '<'。保护位具体字符不限，读取时无条件
    丢弃第一个字符（连同其行尾换行），再剥离可能由编辑器添加的 UTF-8 BOM。

    正文换行符统一移除：Flash/Scaleform 的 htmlText 与浏览器不同，源码中的
    \n 会作为真实换行渲染，不会按 HTML 空白折叠规则忽略。help 文件里的换行
    只是源码排版（长句折行、标签换行），段落与行换行由 <p> / <br> 负责——
    若不删掉，</p> 与 <p> 之间的 \n 会多渲染出一个空白行（两个 <p> 变三行）。
    文本按 utf-8 解码后再处理（磁盘 'rb' 读到的是字节串）。
    """
    if not raw:
        return raw
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'replace')
    if raw[:1] == '\ufeff':
        raw = raw[1:]
    raw = raw[1:].lstrip('\r\n')
    return raw.replace('\r\n', '').replace('\n', '').replace('\r', '')


def _read_disk_or_restore(disk_path, vfs_path):
    """读取磁盘 help 文件；缺失/损坏时自动用 VFS 对应文件覆盖恢复。

    磁盘副本是用户可编辑的（加载链第一优先）。文件缺失或读取失败时，
    将 VFS 对应文件原样覆盖到磁盘（自愈，尽力而为——写失败仅记日志），
    并返回 VFS 内容。VFS 亦不可用时返回 None（由调用方继续下一候选）。
    """
    import os
    import ResMgr

    if os.path.isfile(disk_path):
        try:
            with open(disk_path, 'rb') as fh:
                return _strip_guard(fh.read())
        except Exception:
            logger.warn('磁盘 help 文件读取失败，尝试从 VFS 恢复: %s', disk_path)

    # 磁盘缺失或读取失败 → 从 VFS 覆盖恢复
    try:
        section = ResMgr.openSection(vfs_path)
        if section is None:
            return None
        raw = section.asBinary
        disk_dir = os.path.dirname(disk_path)
        if not os.path.isdir(disk_dir):
            os.makedirs(disk_dir)
        with open(disk_path, 'wb') as fh:
            fh.write(raw)
        logger.info('已从 VFS 恢复磁盘 help 文件: %s', disk_path)
        return _strip_guard(raw)
    except Exception:
        logger.warn('VFS help 文件不可用: %s', vfs_path)
        return None


def _load_help_html():
    """按生效语言加载帮助页 HTML（未格式化，含 {0}/{1} 占位符）。

    加载链: 磁盘 l10n/<lang>.html（缺失/损坏自动从 VFS 覆盖恢复）→
    磁盘 l10n/zh_cn.html（同上）→ 词典兜底文本。
    磁盘副本由 config_init 的目录级复制保证存在（用户可编辑）。

    文件首字符为保护位（约定 '#'，见 _strip_guard）。磁盘分支用 open
    读原始字节；VFS 分支用 openSection.asBinary（保护位让首字节非 '<'，
    不会触发 XML 解析）。统一经 _strip_guard 剥离保护位。
    """
    import os
    from autoconfigvoiceover import l10n

    lang = l10n.get_effective_lang()

    for code in (lang, l10n.LANG_ZH_CN):
        content = _read_disk_or_restore(
            os.path.join(MY_CONFIG_FOLDER, 'l10n', code + '.html'),
            '%s/%s.html' % (_HELP_VFS_ROOT, code))
        if content is not None:
            return content

    # 全部缺失（资源损坏）——词典兜底
    logger.warn('帮助页 HTML 全部缺失，使用词典兜底文本')
    return '<p align="left">' + l10n.text('help/load_failed') + '</p>'


class HelpPage(object):
    """帮助页的业务逻辑。

    Flash 端 HtmlContentPage 负责全部渲染，Python 端仅推送 HTML 内容。
    """

    def __init__(self, meta):
        """
        :param meta: ACVMenuMeta 实例，用于 DAAPI 通信
        """
        self._meta = meta

    # ── 数据推送 ──

    def push_data(self):
        """向 Flash 推送帮助页 HTML 内容（l10n/<lang>.html 资源化，i18n）。

        帮助页长文不入词典（§5.4）——整页 HTML 按生效语言从资源文件加载。
        加载链: 磁盘 l10n/<lang>.html（缺失/损坏自动从 VFS 覆盖恢复）→
        磁盘 l10n/zh_cn.html（同上）→ 词典兜底文本。文件内含 {0}/{1}
        占位符（配置目录 / 版本号）。
        """
        from autoconfigvoiceover import l10n
        html = _load_help_html()
        data = {
            'title': l10n.text('help/title'),
            'titleTooltipHtml': l10n.text('help/tooltip/title'),
            'html': html.format(MY_CONFIG_FOLDER, MOD_VERSION),
        }
        self._meta.as_populatePageS('help', data)
        logger.info('帮助页数据已推送')

    # ── 回调处理 ──

    def handle_link(self, payload):
        """用户点击了帮助页中的超链接。

        :param payload: href 中 "event:" 后的内容（如 "github"、"bilibili"）
        """
        import BigWorld

        if payload == 'github':
            url = 'https://github.com/25304-Oxygen/wot-autoconfig-voiceover'
        elif payload == 'bilibili':
            url = 'https://space.bilibili.com/4691837'
        elif payload == 'bilibili_2':
            url = 'https://space.bilibili.com/375281099'
        else:
            logger.info('帮助页未知链接: %s', payload)
            return

        logger.info('打开外部链接: %s', url)
        try:
            if hasattr(BigWorld, 'wg_openWebBrowser'):
                BigWorld.wg_openWebBrowser(url)
            else:
                BigWorld.openWebBrowser(url)
        except Exception:
            logger.exception('打开链接失败: %s', url)
